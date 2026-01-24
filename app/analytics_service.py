from datetime import datetime
from typing import Optional

from sqlalchemy import func, extract, asc, desc
from sqlalchemy.orm import Session

from app.db_models import Receipt, ReceiptItem, ReceiptDiscount
from app.analytics_models import (
    SummaryResponse,
    SpendingOverTimeResponse,
    SpendingPeriod,
    StoreAnalyticsResponse,
    StoreStats,
    ProductAnalyticsResponse,
    ProductStats,
    SavingsAnalyticsResponse,
    DiscountTypeStats,
    ReceiptListResponse,
    ReceiptListItem,
    ReceiptDetailDB,
    ReceiptItemDB,
    ReceiptDiscountDB,
)


def get_summary(db: Session) -> SummaryResponse:
    """Get overall spending summary statistics."""
    result = db.query(
        func.count(Receipt.id).label("total_receipts"),
        func.coalesce(func.sum(Receipt.total_amount), 0).label("total_spending"),
        func.coalesce(func.sum(Receipt.discount_total), 0).label("total_savings"),
        func.min(Receipt.transaction_moment).label("first_receipt"),
        func.max(Receipt.transaction_moment).label("last_receipt"),
    ).first()

    total_receipts = result.total_receipts or 0
    total_spending = result.total_spending or 0
    total_savings = abs(result.total_savings or 0)  # Discounts are typically negative
    average = total_spending / total_receipts if total_receipts > 0 else 0

    return SummaryResponse(
        total_receipts=total_receipts,
        total_spending=round(total_spending, 2),
        total_savings=round(total_savings, 2),
        average_per_receipt=round(average, 2),
        first_receipt_date=result.first_receipt,
        last_receipt_date=result.last_receipt,
    )


def get_spending_over_time(
    db: Session,
    granularity: str = "month",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> SpendingOverTimeResponse:
    """Get spending aggregated by time period."""
    query = db.query(Receipt)

    if start_date:
        query = query.filter(Receipt.transaction_moment >= start_date)
    if end_date:
        query = query.filter(Receipt.transaction_moment <= end_date)

    # Build the period expression based on granularity
    if granularity == "day":
        period_expr = func.strftime("%Y-%m-%d", Receipt.transaction_moment)
    elif granularity == "week":
        period_expr = func.strftime("%Y-W%W", Receipt.transaction_moment)
    else:  # month (default)
        period_expr = func.strftime("%Y-%m", Receipt.transaction_moment)

    results = (
        db.query(
            period_expr.label("period"),
            func.sum(Receipt.total_amount).label("total_spending"),
            func.count(Receipt.id).label("receipt_count"),
            func.coalesce(func.sum(Receipt.discount_total), 0).label("total_savings"),
        )
        .filter(Receipt.transaction_moment.isnot(None))
        .group_by(period_expr)
        .order_by(period_expr)
    )

    if start_date:
        results = results.filter(Receipt.transaction_moment >= start_date)
    if end_date:
        results = results.filter(Receipt.transaction_moment <= end_date)

    periods = [
        SpendingPeriod(
            period=r.period,
            total_spending=round(r.total_spending, 2),
            receipt_count=r.receipt_count,
            total_savings=round(abs(r.total_savings or 0), 2),
        )
        for r in results.all()
    ]

    return SpendingOverTimeResponse(granularity=granularity, periods=periods)


def get_store_analytics(db: Session, limit: int = 20) -> StoreAnalyticsResponse:
    """Get spending statistics by store."""
    results = (
        db.query(
            Receipt.store_id,
            Receipt.store_name,
            Receipt.store_city,
            func.sum(Receipt.total_amount).label("total_spending"),
            func.count(Receipt.id).label("receipt_count"),
            func.coalesce(func.sum(Receipt.discount_total), 0).label("total_savings"),
        )
        .group_by(Receipt.store_id, Receipt.store_name, Receipt.store_city)
        .order_by(func.sum(Receipt.total_amount).desc())
        .limit(limit)
        .all()
    )

    stores = [
        StoreStats(
            store_id=r.store_id,
            store_name=r.store_name,
            store_city=r.store_city,
            total_spending=round(r.total_spending, 2),
            receipt_count=r.receipt_count,
            average_per_receipt=round(r.total_spending / r.receipt_count, 2)
            if r.receipt_count > 0
            else 0,
            total_savings=round(abs(r.total_savings or 0), 2),
        )
        for r in results
    ]

    return StoreAnalyticsResponse(stores=stores)


def get_product_analytics(
    db: Session,
    limit: int = 50,
    search: Optional[str] = None,
    sort_by: str = "total_spending",
    sort_order: str = "desc",
) -> ProductAnalyticsResponse:
    """Get top products by total spending."""
    total_quantity_col = func.sum(ReceiptItem.quantity).label("total_quantity")
    total_spending_col = func.sum(ReceiptItem.line_total).label("total_spending")
    purchase_count_col = func.count(func.distinct(ReceiptItem.receipt_id)).label("purchase_count")

    query = db.query(
        ReceiptItem.product_id,
        ReceiptItem.product_name,
        total_quantity_col,
        total_spending_col,
        purchase_count_col,
    )

    if search:
        query = query.filter(ReceiptItem.product_name.ilike(f"%{search}%"))

    query = query.group_by(ReceiptItem.product_name)

    # Build sort expression
    sort_columns = {
        "product_name": ReceiptItem.product_name,
        "total_quantity": total_quantity_col,
        "total_spending": total_spending_col,
        "purchase_count": purchase_count_col,
        "average_price": total_spending_col / total_quantity_col,
    }
    sort_col = sort_columns.get(sort_by, total_spending_col)
    order_func = desc if sort_order == "desc" else asc
    query = query.order_by(order_func(sort_col))

    results = query.limit(limit).all()

    total_count = db.query(func.count(func.distinct(ReceiptItem.product_name))).scalar()

    products = [
        ProductStats(
            product_id=r.product_id,
            product_name=r.product_name,
            total_quantity=round(r.total_quantity or 0, 2),
            total_spending=round(r.total_spending or 0, 2),
            purchase_count=r.purchase_count,
            average_price=round(
                (r.total_spending or 0) / (r.total_quantity or 1), 2
            ),
        )
        for r in results
    ]

    return ProductAnalyticsResponse(products=products, total_products=total_count or 0)


def get_savings_analytics(db: Session) -> SavingsAnalyticsResponse:
    """Get savings/discount analytics."""
    # Total savings from receipts
    receipt_stats = db.query(
        func.coalesce(func.sum(Receipt.discount_total), 0).label("total_savings"),
        func.count(Receipt.id).label("receipt_count"),
    ).first()

    total_savings = abs(receipt_stats.total_savings or 0)
    receipt_count = receipt_stats.receipt_count or 0
    avg_savings = total_savings / receipt_count if receipt_count > 0 else 0

    # Breakdown by discount type
    discount_results = (
        db.query(
            ReceiptDiscount.discount_type,
            ReceiptDiscount.discount_name,
            func.sum(ReceiptDiscount.discount_amount).label("total_savings"),
            func.count(ReceiptDiscount.id).label("occurrence_count"),
        )
        .group_by(ReceiptDiscount.discount_type, ReceiptDiscount.discount_name)
        .order_by(func.sum(ReceiptDiscount.discount_amount).desc())
        .all()
    )

    discount_types = [
        DiscountTypeStats(
            discount_type=r.discount_type,
            discount_name=r.discount_name,
            total_savings=round(abs(r.total_savings or 0), 2),
            occurrence_count=r.occurrence_count,
        )
        for r in discount_results
    ]

    total_discounts = db.query(func.count(ReceiptDiscount.id)).scalar() or 0

    return SavingsAnalyticsResponse(
        total_savings=round(total_savings, 2),
        total_discounts_applied=total_discounts,
        average_savings_per_receipt=round(avg_savings, 2),
        discount_types=discount_types,
    )


def get_receipts_list(
    db: Session,
    offset: int = 0,
    limit: int = 20,
    sort_by: str = "transaction_moment",
    sort_order: str = "desc",
) -> ReceiptListResponse:
    """Get paginated list of receipts."""
    total = db.query(func.count(Receipt.id)).scalar() or 0

    item_count_col = func.count(ReceiptItem.id).label("item_count")

    query = (
        db.query(
            Receipt.id,
            Receipt.transaction_moment,
            Receipt.total_amount,
            Receipt.store_name,
            Receipt.store_city,
            Receipt.discount_total,
            item_count_col,
        )
        .outerjoin(ReceiptItem, Receipt.id == ReceiptItem.receipt_id)
        .group_by(Receipt.id)
    )

    # Build sort expression
    sort_columns = {
        "transaction_moment": Receipt.transaction_moment,
        "store_name": Receipt.store_name,
        "item_count": item_count_col,
        "discount_total": Receipt.discount_total,
        "total_amount": Receipt.total_amount,
    }
    sort_col = sort_columns.get(sort_by, Receipt.transaction_moment)
    order_func = desc if sort_order == "desc" else asc
    query = query.order_by(order_func(sort_col))

    results = query.offset(offset).limit(limit).all()

    receipts = [
        ReceiptListItem(
            id=r.id,
            transaction_moment=r.transaction_moment,
            total_amount=r.total_amount,
            store_name=r.store_name,
            store_city=r.store_city,
            discount_total=r.discount_total,
            item_count=r.item_count,
        )
        for r in results
    ]

    return ReceiptListResponse(
        receipts=receipts, total=total, offset=offset, limit=limit
    )


def get_receipt_detail(db: Session, receipt_id: str) -> Optional[ReceiptDetailDB]:
    """Get detailed receipt information."""
    receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()

    if not receipt:
        return None

    items = [
        ReceiptItemDB(
            id=item.id,
            product_id=item.product_id,
            product_name=item.product_name,
            quantity=item.quantity or 1,
            unit_price=item.unit_price,
            line_total=item.line_total,
        )
        for item in receipt.items
    ]

    discounts = [
        ReceiptDiscountDB(
            id=d.id,
            discount_type=d.discount_type,
            discount_name=d.discount_name,
            discount_amount=d.discount_amount,
        )
        for d in receipt.discounts
    ]

    return ReceiptDetailDB(
        id=receipt.id,
        transaction_moment=receipt.transaction_moment,
        total_amount=receipt.total_amount,
        subtotal=receipt.subtotal,
        discount_total=receipt.discount_total,
        member_id=receipt.member_id,
        store_id=receipt.store_id,
        store_name=receipt.store_name,
        store_street=receipt.store_street,
        store_city=receipt.store_city,
        store_postal_code=receipt.store_postal_code,
        checkout_lane=receipt.checkout_lane,
        payment_method=receipt.payment_method,
        items=items,
        discounts=discounts,
    )
