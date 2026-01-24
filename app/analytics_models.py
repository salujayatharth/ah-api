from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# Summary Response
class SummaryResponse(BaseModel):
    total_receipts: int
    total_spending: float
    total_savings: float
    average_per_receipt: float
    first_receipt_date: Optional[datetime] = None
    last_receipt_date: Optional[datetime] = None


# Spending Over Time
class SpendingPeriod(BaseModel):
    period: str  # e.g., "2024-01", "2024-W01", "2024-01-15"
    total_spending: float
    receipt_count: int
    total_savings: float


class SpendingOverTimeResponse(BaseModel):
    granularity: str  # "day", "week", "month"
    periods: list[SpendingPeriod]


# Store Analytics
class StoreStats(BaseModel):
    store_id: Optional[int]
    store_name: Optional[str]
    store_city: Optional[str]
    total_spending: float
    receipt_count: int
    average_per_receipt: float
    total_savings: float


class StoreAnalyticsResponse(BaseModel):
    stores: list[StoreStats]


# Product Analytics
class ProductStats(BaseModel):
    product_id: Optional[str]
    product_name: str
    total_quantity: float
    total_spending: float
    purchase_count: int  # Number of receipts containing this product
    average_price: float


class ProductAnalyticsResponse(BaseModel):
    products: list[ProductStats]
    total_products: int


# Savings Analytics
class DiscountTypeStats(BaseModel):
    discount_type: Optional[str]
    discount_name: Optional[str]
    total_savings: float
    occurrence_count: int


class SavingsAnalyticsResponse(BaseModel):
    total_savings: float
    total_discounts_applied: int
    average_savings_per_receipt: float
    discount_types: list[DiscountTypeStats]


# Receipt List (from DB)
class ReceiptItemDB(BaseModel):
    id: int
    product_id: Optional[str]
    product_name: str
    quantity: float
    unit_price: Optional[float]
    line_total: Optional[float]

    class Config:
        from_attributes = True


class ReceiptDiscountDB(BaseModel):
    id: int
    discount_type: Optional[str]
    discount_name: Optional[str]
    discount_amount: float

    class Config:
        from_attributes = True


class ReceiptListItem(BaseModel):
    id: str
    transaction_moment: datetime
    total_amount: float
    store_name: Optional[str]
    store_city: Optional[str]
    discount_total: Optional[float]
    item_count: int

    class Config:
        from_attributes = True


class ReceiptListResponse(BaseModel):
    receipts: list[ReceiptListItem]
    total: int
    offset: int
    limit: int


class ReceiptDetailDB(BaseModel):
    id: str
    transaction_moment: datetime
    total_amount: float
    subtotal: Optional[float]
    discount_total: Optional[float]
    member_id: Optional[str]
    store_id: Optional[int]
    store_name: Optional[str]
    store_street: Optional[str]
    store_city: Optional[str]
    store_postal_code: Optional[str]
    checkout_lane: Optional[int]
    payment_method: Optional[str]
    items: list[ReceiptItemDB]
    discounts: list[ReceiptDiscountDB]

    class Config:
        from_attributes = True
