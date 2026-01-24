"""
Pytest configuration and fixtures for integration tests.
"""
import os
import sys
from datetime import datetime, timedelta
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, get_db
from app.db_models import Receipt, ReceiptItem, ReceiptDiscount
from app.main import app
from app.client import AHClient


# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Create a fresh database session for each test."""
    # Create all tables
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop all tables after test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Create a test client with database override."""
    # Override the database dependency
    app.dependency_overrides[get_db] = override_get_db

    # Create tables for this test
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as test_client:
        yield test_client

    # Clean up
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_receipt(db_session: Session) -> Receipt:
    """Create a sample receipt in the database."""
    receipt = Receipt(
        id="test-receipt-001",
        transaction_moment=datetime(2024, 1, 15, 10, 30, 0),
        total_amount=45.67,
        subtotal=50.00,
        discount_total=-4.33,
        member_id="member-123",
        store_id=1234,
        store_name="AH Test Store",
        store_street="123 Test Street",
        store_city="Amsterdam",
        store_postal_code="1000AB",
        checkout_lane=5,
        payment_method="PIN",
    )
    db_session.add(receipt)
    db_session.commit()
    db_session.refresh(receipt)
    return receipt


@pytest.fixture
def sample_receipt_with_items(db_session: Session) -> Receipt:
    """Create a sample receipt with items and discounts."""
    receipt = Receipt(
        id="test-receipt-002",
        transaction_moment=datetime(2024, 1, 20, 14, 45, 0),
        total_amount=32.50,
        subtotal=35.00,
        discount_total=-2.50,
        member_id="member-456",
        store_id=5678,
        store_name="AH Market",
        store_street="456 Market Lane",
        store_city="Rotterdam",
        store_postal_code="3000XY",
        checkout_lane=3,
        payment_method="Cash",
    )
    db_session.add(receipt)
    db_session.flush()

    # Add items
    items = [
        ReceiptItem(
            receipt_id=receipt.id,
            product_id="prod-001",
            product_name="Milk 1L",
            quantity=2,
            unit_price=1.50,
            line_total=3.00,
        ),
        ReceiptItem(
            receipt_id=receipt.id,
            product_id="prod-002",
            product_name="Bread Whole Wheat",
            quantity=1,
            unit_price=2.50,
            line_total=2.50,
        ),
        ReceiptItem(
            receipt_id=receipt.id,
            product_id="prod-003",
            product_name="Cheese Gouda",
            quantity=0.5,
            unit_price=10.00,
            line_total=5.00,
        ),
    ]
    for item in items:
        db_session.add(item)

    # Add discounts
    discount = ReceiptDiscount(
        receipt_id=receipt.id,
        discount_type="BONUS",
        discount_name="2 for 1 Milk",
        discount_amount=-1.50,
    )
    db_session.add(discount)

    db_session.commit()
    db_session.refresh(receipt)
    return receipt


@pytest.fixture
def multiple_receipts(db_session: Session) -> list[Receipt]:
    """Create multiple receipts for testing analytics."""
    receipts = []
    base_date = datetime(2024, 1, 1)

    for i in range(5):
        receipt = Receipt(
            id=f"test-receipt-{i:03d}",
            transaction_moment=base_date + timedelta(days=i * 7),
            total_amount=20.00 + (i * 10),
            subtotal=22.00 + (i * 10),
            discount_total=-2.00,
            member_id="member-multi",
            store_id=1000 + i,
            store_name=f"AH Store {i}",
            store_street=f"{i}00 Main Street",
            store_city=["Amsterdam", "Rotterdam", "The Hague", "Utrecht", "Eindhoven"][i],
            store_postal_code=f"{1000 + i}AA",
            checkout_lane=i + 1,
            payment_method="PIN",
        )
        db_session.add(receipt)
        receipts.append(receipt)

    db_session.commit()
    for receipt in receipts:
        db_session.refresh(receipt)

    return receipts


@pytest.fixture
def multiple_receipts_with_items(db_session: Session, multiple_receipts: list[Receipt]) -> list[Receipt]:
    """Add items to multiple receipts for product analytics testing."""
    product_names = ["Milk 1L", "Bread Whole Wheat", "Cheese Gouda", "Eggs 12-pack", "Butter"]

    for i, receipt in enumerate(multiple_receipts):
        for j, product_name in enumerate(product_names[:3]):
            item = ReceiptItem(
                receipt_id=receipt.id,
                product_id=f"prod-{j:03d}",
                product_name=product_name,
                quantity=1 + (i % 3),
                unit_price=2.00 + j,
                line_total=(2.00 + j) * (1 + (i % 3)),
            )
            db_session.add(item)

        # Add a discount to some receipts
        if i % 2 == 0:
            discount = ReceiptDiscount(
                receipt_id=receipt.id,
                discount_type="BONUS",
                discount_name="Weekly Offer",
                discount_amount=-1.00,
            )
            db_session.add(discount)

    db_session.commit()
    for receipt in multiple_receipts:
        db_session.refresh(receipt)

    return multiple_receipts


@pytest.fixture
def mock_ah_client():
    """Create a mock AH client for testing authenticated endpoints."""
    with patch.object(AHClient, '__new__', return_value=MagicMock(spec=AHClient)) as mock_class:
        mock_instance = mock_class.return_value
        mock_instance._initialized = True
        mock_instance.is_authenticated.return_value = True

        # Mock GraphQL methods
        mock_instance.get_receipts = AsyncMock(return_value={
            "pagination": {"offset": 0, "limit": 20, "totalElements": 2},
            "posReceipts": [
                {
                    "id": "mock-receipt-001",
                    "dateTime": "2024-01-15T10:30:00",
                    "totalAmount": {"amount": 45.67, "formatted": "45,67"},
                    "storeAddress": {"city": "Amsterdam", "street": "123 Test St"},
                },
                {
                    "id": "mock-receipt-002",
                    "dateTime": "2024-01-20T14:45:00",
                    "totalAmount": {"amount": 32.50, "formatted": "32,50"},
                    "storeAddress": {"city": "Rotterdam", "street": "456 Main St"},
                },
            ],
        })

        mock_instance.get_receipt = AsyncMock(return_value={
            "id": "mock-receipt-001",
            "memberId": "member-123",
            "storeInfo": "AH Test Store",
            "products": [
                {
                    "id": "prod-001",
                    "name": "Test Product",
                    "quantity": 2,
                    "price": {"amount": 1.50, "formatted": "1,50"},
                    "amount": {"amount": 3.00, "formatted": "3,00"},
                }
            ],
            "subtotalProducts": {"amount": {"amount": 3.00, "formatted": "3,00"}},
            "discounts": [],
            "discountTotal": {"amount": 0, "formatted": "0,00"},
            "total": {"amount": 3.00, "formatted": "3,00"},
            "payments": [{"method": "PIN", "amount": {"amount": 3.00, "formatted": "3,00"}}],
            "transaction": {"dateTime": "2024-01-15T10:30:00", "store": "1234", "lane": 5, "id": "tx-001"},
            "address": {"street": "123 Test St", "city": "Amsterdam", "postalCode": "1000AB"},
            "vat": {"levels": [], "total": {"amount": {"amount": 0, "formatted": "0,00"}}},
        })

        mock_instance.get_receipt_pdf = AsyncMock(return_value={
            "url": "https://example.com/receipt.pdf"
        })

        mock_instance.exchange_code = AsyncMock(return_value={
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "expires_in": 7200,
        })

        yield mock_instance


@pytest.fixture
def mock_unauthenticated_client():
    """Create a mock AH client that is not authenticated."""
    with patch.object(AHClient, '__new__', return_value=MagicMock(spec=AHClient)) as mock_class:
        mock_instance = mock_class.return_value
        mock_instance._initialized = True
        mock_instance.is_authenticated.return_value = False
        yield mock_instance
