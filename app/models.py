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
