from datetime import datetime
from typing import Optional
from enum import Enum

from pydantic import BaseModel


class UrgencyLevel(str, Enum):
    NEEDED = "needed"
    SOON = "soon"
    LATER = "later"


class PurchaseEvent(BaseModel):
    """A single purchase event for a product."""
    date: datetime
    quantity: float
    unit_price: Optional[float]
    receipt_id: str
    product_id: Optional[str] = None


class ProductConsumptionPattern(BaseModel):
    """Consumption pattern analysis for a product."""
    product_name: str
    product_id: Optional[str]
    purchase_count: int
    total_quantity_purchased: float
    median_quantity_per_purchase: float
    median_interval_days: float
    weighted_avg_interval_days: float
    consumption_rate_per_day: float
    last_purchase_date: datetime
    days_since_last_purchase: float
    estimated_inventory: float
    days_until_needed: float
    median_price: float
    confidence: float


class ShoppingListItem(BaseModel):
    """A single item in the shopping list recommendation."""
    product_name: str
    product_id: Optional[str]
    suggested_quantity: int
    urgency: UrgencyLevel
    estimated_days_until_needed: float
    estimated_inventory: float
    median_price: float
    estimated_cost: float
    confidence: float
    last_purchase_date: datetime
    purchase_count: int
    # Additional fields for decay rate sensitivity visualization
    median_interval_days: Optional[float] = None
    weighted_avg_interval_days: Optional[float] = None


class ShoppingListRecommendation(BaseModel):
    """Complete shopping list recommendation response."""
    generated_at: datetime
    planning_horizon_days: int
    needed_items: list[ShoppingListItem]
    might_need_soon: list[ShoppingListItem]
    estimated_total: float
    items_analyzed: int
    items_filtered_out: int


class ConsumptionPatternsResponse(BaseModel):
    """Response containing all analyzed consumption patterns."""
    generated_at: datetime
    products: list[ProductConsumptionPattern]
    total_products_analyzed: int
    products_filtered_out: int
    filter_criteria: dict


class ProductConsumptionDetail(BaseModel):
    """Detailed consumption analysis for a single product."""
    product_name: str
    product_id: Optional[str]
    purchase_history: list[PurchaseEvent]
    consumption_pattern: ProductConsumptionPattern
    prediction_explanation: str
