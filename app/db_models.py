from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(Text, primary_key=True)  # AH transaction ID
    transaction_moment = Column(DateTime, nullable=False)
    total_amount = Column(Float, nullable=False)
    subtotal = Column(Float)
    discount_total = Column(Float)
    member_id = Column(Text)
    store_id = Column(Integer)
    store_name = Column(Text)
    store_street = Column(Text)
    store_city = Column(Text)
    store_postal_code = Column(Text)
    checkout_lane = Column(Integer)
    payment_method = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    items = relationship("ReceiptItem", back_populates="receipt", cascade="all, delete-orphan")
    discounts = relationship("ReceiptDiscount", back_populates="receipt", cascade="all, delete-orphan")
    vat_entries = relationship("ReceiptVAT", back_populates="receipt", cascade="all, delete-orphan")


class ReceiptItem(Base):
    __tablename__ = "receipt_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_id = Column(Text, ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Text)
    product_name = Column(Text, nullable=False)
    quantity = Column(Float, default=1)
    unit_price = Column(Float)
    line_total = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    receipt = relationship("Receipt", back_populates="items")


class ReceiptDiscount(Base):
    __tablename__ = "receipt_discounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_id = Column(Text, ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False)
    discount_type = Column(Text)
    discount_name = Column(Text)
    discount_amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    receipt = relationship("Receipt", back_populates="discounts")


class ReceiptVAT(Base):
    __tablename__ = "receipt_vat"

    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_id = Column(Text, ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False)
    vat_percentage = Column(Float, nullable=False)
    vat_amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    receipt = relationship("Receipt", back_populates="vat_entries")


class ProductCache(Base):
    """Cache for product details fetched from AH API."""
    __tablename__ = "product_cache"

    product_id = Column(Text, primary_key=True)  # AH product ID from receipts
    webshop_id = Column(Text, index=True)  # AH webshop ID
    title = Column(Text, nullable=False)
    brand = Column(Text)
    category = Column(Text)
    subcategory = Column(Text)
    price = Column(Float)
    unit_size = Column(Text)
    image_url = Column(Text)
    description = Column(Text)
    raw_json = Column(Text)  # Store full API response as JSON string
    fetched_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # Cache expiry time
