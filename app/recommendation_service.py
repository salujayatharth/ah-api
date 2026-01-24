import math
import statistics
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db_models import Receipt, ReceiptItem
from app.recommendation_models import (
    PurchaseEvent,
    ProductConsumptionPattern,
    ShoppingListItem,
    ShoppingListRecommendation,
    ConsumptionPatternsResponse,
    ProductConsumptionDetail,
    UrgencyLevel,
)


def get_product_purchase_history(
    db: Session,
    product_name: Optional[str] = None,
    min_purchases: int = 1,
) -> dict[str, list[PurchaseEvent]]:
    """
    Get purchase history for products, grouped by product name.

    Returns a dict mapping product_name -> list of PurchaseEvent sorted by date.
    """
    query = (
        db.query(
            ReceiptItem.product_name,
            ReceiptItem.product_id,
            ReceiptItem.quantity,
            ReceiptItem.unit_price,
            ReceiptItem.receipt_id,
            Receipt.transaction_moment,
        )
        .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
        .order_by(ReceiptItem.product_name, Receipt.transaction_moment)
    )

    if product_name:
        query = query.filter(ReceiptItem.product_name.ilike(f"%{product_name}%"))

    results = query.all()

    # Group by product name
    products: dict[str, list[PurchaseEvent]] = {}
    for row in results:
        name = row.product_name
        if name not in products:
            products[name] = []
        products[name].append(
            PurchaseEvent(
                date=row.transaction_moment,
                quantity=row.quantity or 1.0,
                unit_price=row.unit_price,
                receipt_id=row.receipt_id,
                product_id=row.product_id,
            )
        )

    # Filter by minimum purchases
    if min_purchases > 1:
        products = {k: v for k, v in products.items() if len(v) >= min_purchases}

    return products


def calculate_exponential_weight(days_ago: float, decay_rate: float = 0.02) -> float:
    """
    Calculate exponential decay weight for a purchase.

    With decay_rate=0.02, a purchase from 35 days ago has ~50% weight of today.
    """
    return math.exp(-decay_rate * days_ago)


def calculate_consumption_pattern(
    product_name: str,
    purchases: list[PurchaseEvent],
    decay_rate: float = 0.02,
    now: Optional[datetime] = None,
) -> ProductConsumptionPattern:
    """
    Calculate consumption pattern for a single product.

    Uses exponential decay weighting to give more importance to recent purchases.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Make now timezone-aware if not already
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # Sort purchases by date
    sorted_purchases = sorted(purchases, key=lambda p: p.date)

    # Get product_id from most recent purchase
    product_id = sorted_purchases[-1].product_id if sorted_purchases else None

    # Calculate basic stats
    purchase_count = len(sorted_purchases)
    quantities = [p.quantity for p in sorted_purchases]
    total_quantity = sum(quantities)
    median_quantity = statistics.median(quantities) if quantities else 0.0

    # Calculate median price (excluding None values)
    prices = [p.unit_price for p in sorted_purchases if p.unit_price is not None]
    median_price = statistics.median(prices) if prices else 0.0

    # Calculate intervals between consecutive purchases
    intervals: list[tuple[float, float]] = []  # (interval_days, weight)
    for i in range(1, len(sorted_purchases)):
        prev_date = sorted_purchases[i - 1].date
        curr_date = sorted_purchases[i].date

        # Make dates timezone-aware for comparison
        if prev_date.tzinfo is None:
            prev_date = prev_date.replace(tzinfo=timezone.utc)
        if curr_date.tzinfo is None:
            curr_date = curr_date.replace(tzinfo=timezone.utc)

        interval_days = (curr_date - prev_date).total_seconds() / 86400

        # Weight based on how recent this interval is
        days_ago = (now - curr_date).total_seconds() / 86400
        weight = calculate_exponential_weight(days_ago, decay_rate)

        intervals.append((interval_days, weight))

    # Calculate weighted median interval and simple median interval
    if intervals:
        weighted_sum = sum(interval * weight for interval, weight in intervals)
        weight_sum = sum(weight for _, weight in intervals)
        weighted_avg_interval = weighted_sum / weight_sum if weight_sum > 0 else 0

        # Median interval (more robust to outliers)
        interval_values = [i for i, _ in intervals]
        median_interval = statistics.median(interval_values)
    else:
        # Only one purchase - estimate based on time since purchase
        last_date = sorted_purchases[-1].date
        if last_date.tzinfo is None:
            last_date = last_date.replace(tzinfo=timezone.utc)
        days_since = (now - last_date).total_seconds() / 86400
        weighted_avg_interval = max(days_since, 7)  # Assume at least weekly
        median_interval = weighted_avg_interval

    # Calculate consumption rate using median values (more robust to outliers)
    consumption_rate = median_quantity / weighted_avg_interval if weighted_avg_interval > 0 else 0

    # Calculate days since last purchase
    last_purchase = sorted_purchases[-1]
    last_date = last_purchase.date
    if last_date.tzinfo is None:
        last_date = last_date.replace(tzinfo=timezone.utc)
    days_since_last = (now - last_date).total_seconds() / 86400

    # Estimate current inventory
    # Assume they had median_quantity after last purchase, consumed at consumption_rate
    estimated_inventory = max(0, median_quantity - (days_since_last * consumption_rate))

    # Calculate days until needed (when inventory hits zero)
    # Cap at 9999 instead of inf since JSON doesn't support infinity
    if consumption_rate > 0:
        days_until_needed = min(9999.0, estimated_inventory / consumption_rate)
    else:
        days_until_needed = 9999.0

    # Calculate confidence score
    confidence = calculate_confidence(
        purchase_count=purchase_count,
        median_interval=median_interval,
        days_since_last=days_since_last,
    )

    return ProductConsumptionPattern(
        product_name=product_name,
        product_id=product_id,
        purchase_count=purchase_count,
        total_quantity_purchased=total_quantity,
        median_quantity_per_purchase=median_quantity,
        median_interval_days=median_interval,
        weighted_avg_interval_days=weighted_avg_interval,
        consumption_rate_per_day=consumption_rate,
        last_purchase_date=last_purchase.date,
        days_since_last_purchase=days_since_last,
        estimated_inventory=estimated_inventory,
        days_until_needed=days_until_needed,
        median_price=median_price,
        confidence=confidence,
    )


def calculate_confidence(
    purchase_count: int,
    median_interval: float,
    days_since_last: float,
) -> float:
    """
    Calculate confidence score based on data quality.

    Higher confidence when:
    - More purchases (more data)
    - Regular intervals (predictable pattern)
    - Recent activity (still relevant)
    """
    # Purchase count factor (saturates around 10 purchases)
    count_factor = min(1.0, purchase_count / 10.0)

    # Recency factor (decay if not purchased in a while relative to interval)
    if median_interval > 0:
        recency_ratio = days_since_last / median_interval
        # If ratio > 2, confidence drops significantly
        recency_factor = max(0, 1 - (recency_ratio - 1) * 0.3) if recency_ratio > 1 else 1.0
    else:
        recency_factor = 0.5

    # Combine factors
    confidence = count_factor * recency_factor * 0.9  # Cap at 0.9
    return round(max(0, min(1, confidence)), 2)


def should_include_product(
    pattern: ProductConsumptionPattern,
    min_purchases: int = 3,
    max_avg_interval: float = 60,
    max_days_since_last: float = 90,
) -> bool:
    """
    Filter out one-off purchases and products no longer being bought.
    """
    if pattern.purchase_count < min_purchases:
        return False
    if pattern.median_interval_days > max_avg_interval:
        return False
    if pattern.days_since_last_purchase > max_days_since_last:
        return False
    return True


def get_consumption_patterns(
    db: Session,
    decay_rate: float = 0.02,
    min_purchases: int = 3,
    max_avg_interval: float = 60,
    max_days_since_last: float = 90,
) -> ConsumptionPatternsResponse:
    """
    Get consumption patterns for all products.
    """
    now = datetime.now(timezone.utc)

    # Get all purchase history
    all_products = get_product_purchase_history(db, min_purchases=1)

    patterns: list[ProductConsumptionPattern] = []
    filtered_count = 0

    for product_name, purchases in all_products.items():
        pattern = calculate_consumption_pattern(
            product_name=product_name,
            purchases=purchases,
            decay_rate=decay_rate,
            now=now,
        )

        if should_include_product(
            pattern,
            min_purchases=min_purchases,
            max_avg_interval=max_avg_interval,
            max_days_since_last=max_days_since_last,
        ):
            patterns.append(pattern)
        else:
            filtered_count += 1

    # Sort by days until needed
    patterns.sort(key=lambda p: p.days_until_needed)

    return ConsumptionPatternsResponse(
        generated_at=now,
        products=patterns,
        total_products_analyzed=len(patterns),
        products_filtered_out=filtered_count,
        filter_criteria={
            "min_purchases": min_purchases,
            "max_avg_interval_days": max_avg_interval,
            "max_days_since_last": max_days_since_last,
        },
    )


def generate_shopping_list(
    db: Session,
    days_ahead: int = 4,
    min_confidence: Optional[float] = None,
    decay_rate: float = 0.02,
    min_purchases: int = 3,
    max_avg_interval: float = 60,
    max_days_since_last: float = 90,
) -> ShoppingListRecommendation:
    """
    Generate shopping list recommendation for items needed within planning horizon.

    If min_confidence is None, returns all items regardless of confidence level.
    """
    now = datetime.now(timezone.utc)

    # Get consumption patterns
    patterns_response = get_consumption_patterns(
        db,
        decay_rate=decay_rate,
        min_purchases=min_purchases,
        max_avg_interval=max_avg_interval,
        max_days_since_last=max_days_since_last,
    )

    needed_items: list[ShoppingListItem] = []
    might_need_soon: list[ShoppingListItem] = []

    for pattern in patterns_response.products:
        # Skip low confidence predictions only if min_confidence is specified
        if min_confidence is not None and pattern.confidence < min_confidence:
            continue

        # Calculate suggested quantity (round up to nearest integer, using median)
        suggested_qty = max(1, math.ceil(pattern.median_quantity_per_purchase))

        # Determine urgency
        if pattern.days_until_needed <= days_ahead:
            urgency = UrgencyLevel.NEEDED
        elif pattern.days_until_needed <= days_ahead * 2:
            urgency = UrgencyLevel.SOON
        else:
            urgency = UrgencyLevel.LATER

        item = ShoppingListItem(
            product_name=pattern.product_name,
            product_id=pattern.product_id,
            suggested_quantity=suggested_qty,
            urgency=urgency,
            estimated_days_until_needed=round(pattern.days_until_needed, 1),
            estimated_inventory=round(pattern.estimated_inventory, 1),
            median_price=round(pattern.median_price, 2),
            estimated_cost=round(pattern.median_price * suggested_qty, 2),
            confidence=pattern.confidence,
            last_purchase_date=pattern.last_purchase_date,
            purchase_count=pattern.purchase_count,
        )

        if urgency == UrgencyLevel.NEEDED:
            needed_items.append(item)
        elif urgency == UrgencyLevel.SOON:
            might_need_soon.append(item)

    # Sort by days until needed
    needed_items.sort(key=lambda x: x.estimated_days_until_needed)
    might_need_soon.sort(key=lambda x: x.estimated_days_until_needed)

    # Calculate estimated total
    estimated_total = sum(item.estimated_cost for item in needed_items)

    return ShoppingListRecommendation(
        generated_at=now,
        planning_horizon_days=days_ahead,
        needed_items=needed_items,
        might_need_soon=might_need_soon,
        estimated_total=round(estimated_total, 2),
        items_analyzed=patterns_response.total_products_analyzed,
        items_filtered_out=patterns_response.products_filtered_out,
    )


def get_product_consumption_detail(
    db: Session,
    product_name: str,
    decay_rate: float = 0.02,
) -> Optional[ProductConsumptionDetail]:
    """
    Get detailed consumption analysis for a specific product.
    """
    now = datetime.now(timezone.utc)

    # Get purchase history for this product
    products = get_product_purchase_history(db, product_name=product_name, min_purchases=1)

    if not products:
        return None

    # Find exact or best match
    exact_match = None
    best_match = None

    for name, purchases in products.items():
        if name.lower() == product_name.lower():
            exact_match = (name, purchases)
            break
        elif product_name.lower() in name.lower():
            if best_match is None or len(purchases) > len(best_match[1]):
                best_match = (name, purchases)

    matched = exact_match or best_match
    if not matched:
        # Just use first result
        matched = next(iter(products.items()))

    name, purchases = matched

    # Calculate pattern
    pattern = calculate_consumption_pattern(
        product_name=name,
        purchases=purchases,
        decay_rate=decay_rate,
        now=now,
    )

    # Generate explanation
    explanation = _generate_prediction_explanation(pattern, now)

    return ProductConsumptionDetail(
        product_name=name,
        product_id=pattern.product_id,
        purchase_history=sorted(purchases, key=lambda p: p.date, reverse=True),
        consumption_pattern=pattern,
        prediction_explanation=explanation,
    )


def _generate_prediction_explanation(
    pattern: ProductConsumptionPattern,
    now: datetime,
) -> str:
    """Generate human-readable explanation of the prediction."""
    lines = []

    lines.append(f"Based on {pattern.purchase_count} purchases:")
    lines.append(f"- You typically buy this every {pattern.median_interval_days:.1f} days")
    lines.append(f"- Typical quantity per purchase: {pattern.median_quantity_per_purchase:.1f}")
    lines.append(f"- Estimated consumption rate: {pattern.consumption_rate_per_day:.3f} units/day")
    lines.append(f"")
    lines.append(f"Last purchased {pattern.days_since_last_purchase:.1f} days ago.")
    lines.append(f"Estimated remaining inventory: {pattern.estimated_inventory:.2f} units")

    if pattern.days_until_needed >= 9999:
        lines.append(f"Unable to predict when you'll need more (insufficient data).")
    elif pattern.days_until_needed <= 0:
        lines.append(f"You likely need to restock NOW.")
    elif pattern.days_until_needed <= 4:
        lines.append(f"Estimated to need restocking in {pattern.days_until_needed:.1f} days.")
    else:
        lines.append(f"Estimated to need restocking in about {pattern.days_until_needed:.0f} days.")

    lines.append(f"")
    lines.append(f"Confidence: {pattern.confidence * 100:.0f}%")

    return "\n".join(lines)
