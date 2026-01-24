from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.analytics_models import (
    SummaryResponse,
    SpendingOverTimeResponse,
    StoreAnalyticsResponse,
    ProductAnalyticsResponse,
    SavingsAnalyticsResponse,
    ReceiptListResponse,
    ReceiptDetailDB,
)
from app.recommendation_models import (
    ShoppingListRecommendation,
    ProductConsumptionDetail,
)
from app import analytics_service
from app import recommendation_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary", response_model=SummaryResponse)
def get_summary(db: Session = Depends(get_db)):
    """Get overall spending summary statistics."""
    return analytics_service.get_summary(db)


@router.get("/spending/over-time", response_model=SpendingOverTimeResponse)
def get_spending_over_time(
    granularity: str = Query("month", enum=["day", "week", "month"]),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    """Get spending aggregated by time period.

    - **granularity**: How to group the data (day, week, month)
    - **start_date**: Filter receipts from this date
    - **end_date**: Filter receipts until this date
    """
    return analytics_service.get_spending_over_time(
        db, granularity, start_date, end_date
    )


@router.get("/stores", response_model=StoreAnalyticsResponse)
def get_store_analytics(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get spending statistics by store."""
    return analytics_service.get_store_analytics(db, limit)


@router.get("/products", response_model=ProductAnalyticsResponse)
def get_product_analytics(
    limit: int = Query(50, ge=1, le=200),
    sort_by: str = Query("total_spending", enum=["product_name", "total_quantity", "purchase_count", "total_spending", "average_price"]),
    sort_order: str = Query("desc", enum=["asc", "desc"]),
    db: Session = Depends(get_db),
):
    """Get top products by total spending."""
    return analytics_service.get_product_analytics(db, limit, sort_by=sort_by, sort_order=sort_order)


@router.get("/products/search", response_model=ProductAnalyticsResponse)
def search_products(
    q: str = Query(..., min_length=1, description="Search term"),
    limit: int = Query(50, ge=1, le=200),
    sort_by: str = Query("total_spending", enum=["product_name", "total_quantity", "purchase_count", "total_spending", "average_price"]),
    sort_order: str = Query("desc", enum=["asc", "desc"]),
    db: Session = Depends(get_db),
):
    """Search products by name."""
    return analytics_service.get_product_analytics(db, limit, search=q, sort_by=sort_by, sort_order=sort_order)


@router.get("/savings", response_model=SavingsAnalyticsResponse)
def get_savings_analytics(db: Session = Depends(get_db)):
    """Get savings/discount analytics."""
    return analytics_service.get_savings_analytics(db)


@router.get("/receipts", response_model=ReceiptListResponse)
def get_receipts_list(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("transaction_moment", enum=["transaction_moment", "store_name", "item_count", "discount_total", "total_amount"]),
    sort_order: str = Query("desc", enum=["asc", "desc"]),
    db: Session = Depends(get_db),
):
    """Get paginated list of receipts from the database."""
    return analytics_service.get_receipts_list(db, offset, limit, sort_by=sort_by, sort_order=sort_order)


@router.get("/receipts/{receipt_id}", response_model=ReceiptDetailDB)
def get_receipt_detail(receipt_id: str, db: Session = Depends(get_db)):
    """Get detailed receipt information."""
    receipt = analytics_service.get_receipt_detail(db, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt


# =============================================================================
# Recommendation Endpoints
# =============================================================================


@router.get("/recommendations/shopping-list", response_model=ShoppingListRecommendation)
def get_shopping_list(
    days_ahead: int = Query(4, ge=1, le=30, description="Planning horizon in days (default 4 for 2x/week shopping)"),
    min_confidence: float = Query(0.3, ge=0, le=1, description="Minimum confidence threshold"),
    decay_rate: float = Query(0.02, ge=0.001, le=0.1, description="Exponential decay rate for weighting recent purchases"),
    min_purchases: int = Query(3, ge=1, le=10, description="Minimum purchases required to include product"),
    max_avg_interval: float = Query(60, ge=7, le=180, description="Max average interval to consider product regular"),
    max_days_since_last: float = Query(90, ge=14, le=365, description="Max days since last purchase to include product"),
    db: Session = Depends(get_db),
):
    """
    Generate shopping list recommendations based on consumption patterns.

    This endpoint analyzes purchase history to predict which items you'll need
    within the specified planning horizon. Uses exponential decay weighting
    to prioritize recent purchase patterns.

    **Algorithm:**
    - Calculates weighted average purchase intervals (recent = higher weight)
    - Estimates current inventory based on consumption rate
    - Predicts when each product will need restocking

    **Parameters:**
    - **days_ahead**: Planning horizon (4 days = shop 2x/week)
    - **min_confidence**: Filter out low-confidence predictions
    - **decay_rate**: λ in e^(-λ×days), 0.02 gives ~35-day half-life
    - **min_purchases**: Minimum purchase count to include product (filters one-offs)
    - **max_avg_interval**: Max average days between purchases (filters rare items)
    - **max_days_since_last**: Exclude items not bought recently
    """
    return recommendation_service.generate_shopping_list(
        db,
        days_ahead=days_ahead,
        min_confidence=min_confidence,
        decay_rate=decay_rate,
        min_purchases=min_purchases,
        max_avg_interval=max_avg_interval,
        max_days_since_last=max_days_since_last,
    )


@router.get("/recommendations/product/{product_name}", response_model=ProductConsumptionDetail)
def get_product_consumption_detail(
    product_name: str,
    decay_rate: float = Query(0.02, ge=0.001, le=0.1, description="Exponential decay rate"),
    db: Session = Depends(get_db),
):
    """
    Get detailed consumption analysis for a specific product.

    Includes:
    - Full purchase history
    - Consumption pattern metrics
    - Human-readable prediction explanation

    The product_name can be a partial match (case-insensitive).
    """
    result = recommendation_service.get_product_consumption_detail(
        db,
        product_name=product_name,
        decay_rate=decay_rate,
    )
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No purchase history found for product matching '{product_name}'"
        )
    return result
