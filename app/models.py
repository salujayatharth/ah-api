from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ReceiptSummary(BaseModel):
    transactionId: str
    transactionMoment: datetime
    total: float
    storeId: Optional[int] = None
    storeName: Optional[str] = None


class ReceiptItem(BaseModel):
    description: str
    quantity: Optional[float] = None
    amount: Optional[float] = None
    unitPrice: Optional[float] = None
    productId: Optional[str] = None


class ReceiptDetail(BaseModel):
    transactionId: str
    transactionMoment: datetime
    total: float
    storeId: Optional[int] = None
    storeName: Optional[str] = None
    items: list[ReceiptItem] = []
    subtotal: Optional[float] = None
    discountTotal: Optional[float] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"


class ReceiptsListResponse(BaseModel):
    receipts: list[ReceiptSummary]


class ErrorResponse(BaseModel):
    detail: str


# Sync endpoint models
class SyncedReceiptSummary(BaseModel):
    id: str
    transaction_moment: datetime
    total_amount: float
    store_name: Optional[str] = None


class SyncError(BaseModel):
    receipt_id: str
    error: str


class SyncResultResponse(BaseModel):
    status: str  # "success", "partial", "error"
    synced_count: int
    skipped_count: int
    error_count: int
    total_in_db: int
    synced_receipts: list[SyncedReceiptSummary]
    errors: list[SyncError]
