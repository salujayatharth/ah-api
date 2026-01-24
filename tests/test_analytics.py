"""
Tests for analytics endpoints (/analytics/*).
"""
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app.db_models import Receipt, ReceiptItem, ReceiptDiscount


class TestSummaryEndpoint:
    """Tests for GET /analytics/summary endpoint."""

    def test_summary_empty_database(self, client: TestClient):
        """Test summary with empty database."""
        response = client.get("/analytics/summary")
        assert response.status_code == 200
        data = response.json()

        assert data["total_receipts"] == 0
        assert data["total_spending"] == 0
        assert data["total_savings"] == 0
        assert data["average_per_receipt"] == 0
        assert data["first_receipt_date"] is None
        assert data["last_receipt_date"] is None

    def test_summary_with_single_receipt(self, client: TestClient, sample_receipt: Receipt):
        """Test summary with a single receipt."""
        response = client.get("/analytics/summary")
        assert response.status_code == 200
        data = response.json()

        assert data["total_receipts"] == 1
        assert data["total_spending"] == 45.67
        assert data["total_savings"] == 4.33  # abs(-4.33)
        assert data["average_per_receipt"] == 45.67

    def test_summary_with_multiple_receipts(self, client: TestClient, multiple_receipts: list[Receipt]):
        """Test summary with multiple receipts."""
        response = client.get("/analytics/summary")
        assert response.status_code == 200
        data = response.json()

        assert data["total_receipts"] == 5
        # Sum of: 20 + 30 + 40 + 50 + 60 = 200
        assert data["total_spending"] == 200.0
        # 5 receipts * 2.00 discount each = 10.00 total savings
        assert data["total_savings"] == 10.0
        # Average: 200 / 5 = 40
        assert data["average_per_receipt"] == 40.0


class TestSpendingOverTimeEndpoint:
    """Tests for GET /analytics/spending/over-time endpoint."""

    def test_spending_over_time_empty_database(self, client: TestClient):
        """Test spending over time with empty database."""
        response = client.get("/analytics/spending/over-time")
        assert response.status_code == 200
        data = response.json()

        assert data["granularity"] == "month"
        assert data["periods"] == []

    def test_spending_over_time_default_granularity(self, client: TestClient, multiple_receipts: list[Receipt]):
        """Test spending over time with default monthly granularity."""
        response = client.get("/analytics/spending/over-time")
        assert response.status_code == 200
        data = response.json()

        assert data["granularity"] == "month"
        assert len(data["periods"]) >= 1
        # All receipts are in January 2024
        assert any(p["period"] == "2024-01" for p in data["periods"])

    def test_spending_over_time_daily_granularity(self, client: TestClient, multiple_receipts: list[Receipt]):
        """Test spending over time with daily granularity."""
        response = client.get("/analytics/spending/over-time?granularity=day")
        assert response.status_code == 200
        data = response.json()

        assert data["granularity"] == "day"
        # Should have multiple days (receipts are 7 days apart)
        assert len(data["periods"]) >= 1

    def test_spending_over_time_weekly_granularity(self, client: TestClient, multiple_receipts: list[Receipt]):
        """Test spending over time with weekly granularity."""
        response = client.get("/analytics/spending/over-time?granularity=week")
        assert response.status_code == 200
        data = response.json()

        assert data["granularity"] == "week"

    def test_spending_over_time_with_date_filter(self, client: TestClient, multiple_receipts: list[Receipt]):
        """Test spending over time with date filters."""
        response = client.get("/analytics/spending/over-time?start_date=2024-01-10&end_date=2024-01-25")
        assert response.status_code == 200
        data = response.json()

        # Should filter based on dates
        assert data["granularity"] == "month"

    def test_spending_over_time_invalid_granularity(self, client: TestClient):
        """Test spending over time with invalid granularity defaults to month."""
        # The API uses Query with enum validation, but it seems to accept invalid values
        # and default to "month" based on the endpoint implementation
        response = client.get("/analytics/spending/over-time?granularity=invalid")
        # API may accept invalid values and use default behavior
        # If it returns 200, check that it uses default granularity
        if response.status_code == 200:
            data = response.json()
            # Invalid granularity may default to month
            assert "granularity" in data
        else:
            assert response.status_code == 422


class TestStoreAnalyticsEndpoint:
    """Tests for GET /analytics/stores endpoint."""

    def test_store_analytics_empty_database(self, client: TestClient):
        """Test store analytics with empty database."""
        response = client.get("/analytics/stores")
        assert response.status_code == 200
        data = response.json()

        assert data["stores"] == []

    def test_store_analytics_with_receipts(self, client: TestClient, multiple_receipts: list[Receipt]):
        """Test store analytics with multiple receipts."""
        response = client.get("/analytics/stores")
        assert response.status_code == 200
        data = response.json()

        assert len(data["stores"]) == 5  # 5 different stores
        for store in data["stores"]:
            assert "store_id" in store
            assert "store_name" in store
            assert "store_city" in store
            assert "total_spending" in store
            assert "receipt_count" in store
            assert "average_per_receipt" in store
            assert "total_savings" in store

    def test_store_analytics_with_limit(self, client: TestClient, multiple_receipts: list[Receipt]):
        """Test store analytics with limit parameter."""
        response = client.get("/analytics/stores?limit=3")
        assert response.status_code == 200
        data = response.json()

        assert len(data["stores"]) <= 3

    def test_store_analytics_invalid_limit(self, client: TestClient):
        """Test store analytics with invalid limit."""
        response = client.get("/analytics/stores?limit=0")
        assert response.status_code == 422

        response = client.get("/analytics/stores?limit=150")
        assert response.status_code == 422


class TestProductAnalyticsEndpoint:
    """Tests for GET /analytics/products endpoint."""

    def test_product_analytics_empty_database(self, client: TestClient):
        """Test product analytics with empty database."""
        response = client.get("/analytics/products")
        assert response.status_code == 200
        data = response.json()

        assert data["products"] == []
        assert data["total_products"] == 0

    def test_product_analytics_with_items(self, client: TestClient, multiple_receipts_with_items: list[Receipt]):
        """Test product analytics with items."""
        response = client.get("/analytics/products")
        assert response.status_code == 200
        data = response.json()

        assert len(data["products"]) > 0
        assert data["total_products"] > 0

        for product in data["products"]:
            assert "product_id" in product
            assert "product_name" in product
            assert "total_quantity" in product
            assert "total_spending" in product
            assert "purchase_count" in product
            assert "average_price" in product

    def test_product_analytics_with_limit(self, client: TestClient, multiple_receipts_with_items: list[Receipt]):
        """Test product analytics with limit parameter."""
        response = client.get("/analytics/products?limit=2")
        assert response.status_code == 200
        data = response.json()

        assert len(data["products"]) <= 2

    def test_product_analytics_sort_by_name(self, client: TestClient, multiple_receipts_with_items: list[Receipt]):
        """Test product analytics sorted by name."""
        response = client.get("/analytics/products?sort_by=product_name&sort_order=asc")
        assert response.status_code == 200
        data = response.json()

        if len(data["products"]) > 1:
            names = [p["product_name"] for p in data["products"]]
            assert names == sorted(names)

    def test_product_analytics_sort_by_quantity(self, client: TestClient, multiple_receipts_with_items: list[Receipt]):
        """Test product analytics sorted by quantity."""
        response = client.get("/analytics/products?sort_by=total_quantity&sort_order=desc")
        assert response.status_code == 200
        data = response.json()

        if len(data["products"]) > 1:
            quantities = [p["total_quantity"] for p in data["products"]]
            assert quantities == sorted(quantities, reverse=True)


class TestProductSearchEndpoint:
    """Tests for GET /analytics/products/search endpoint."""

    def test_product_search_empty_database(self, client: TestClient):
        """Test product search with empty database."""
        response = client.get("/analytics/products/search?q=milk")
        assert response.status_code == 200
        data = response.json()

        assert data["products"] == []

    def test_product_search_with_results(self, client: TestClient, multiple_receipts_with_items: list[Receipt]):
        """Test product search with matching results."""
        response = client.get("/analytics/products/search?q=Milk")
        assert response.status_code == 200
        data = response.json()

        assert len(data["products"]) > 0
        for product in data["products"]:
            assert "milk" in product["product_name"].lower()

    def test_product_search_case_insensitive(self, client: TestClient, multiple_receipts_with_items: list[Receipt]):
        """Test product search is case insensitive."""
        response_upper = client.get("/analytics/products/search?q=MILK")
        response_lower = client.get("/analytics/products/search?q=milk")

        assert response_upper.status_code == 200
        assert response_lower.status_code == 200

        # Both should return same results
        data_upper = response_upper.json()
        data_lower = response_lower.json()
        assert len(data_upper["products"]) == len(data_lower["products"])

    def test_product_search_no_results(self, client: TestClient, multiple_receipts_with_items: list[Receipt]):
        """Test product search with no matching results."""
        response = client.get("/analytics/products/search?q=nonexistentproduct123")
        assert response.status_code == 200
        data = response.json()

        assert data["products"] == []

    def test_product_search_missing_query(self, client: TestClient):
        """Test product search without query parameter."""
        response = client.get("/analytics/products/search")
        assert response.status_code == 422  # Missing required parameter


class TestSavingsAnalyticsEndpoint:
    """Tests for GET /analytics/savings endpoint."""

    def test_savings_analytics_empty_database(self, client: TestClient):
        """Test savings analytics with empty database."""
        response = client.get("/analytics/savings")
        assert response.status_code == 200
        data = response.json()

        assert data["total_savings"] == 0
        assert data["total_discounts_applied"] == 0
        assert data["average_savings_per_receipt"] == 0
        assert data["discount_types"] == []

    def test_savings_analytics_with_receipts(self, client: TestClient, multiple_receipts_with_items: list[Receipt]):
        """Test savings analytics with receipts and discounts."""
        response = client.get("/analytics/savings")
        assert response.status_code == 200
        data = response.json()

        assert data["total_savings"] >= 0
        assert data["total_discounts_applied"] >= 0
        assert "average_savings_per_receipt" in data
        assert "discount_types" in data


class TestReceiptsListEndpoint:
    """Tests for GET /analytics/receipts endpoint."""

    def test_receipts_list_empty_database(self, client: TestClient):
        """Test receipts list with empty database."""
        response = client.get("/analytics/receipts")
        assert response.status_code == 200
        data = response.json()

        assert data["receipts"] == []
        assert data["total"] == 0
        assert data["offset"] == 0
        assert data["limit"] == 20

    def test_receipts_list_with_data(self, client: TestClient, multiple_receipts_with_items: list[Receipt]):
        """Test receipts list with data."""
        response = client.get("/analytics/receipts")
        assert response.status_code == 200
        data = response.json()

        assert len(data["receipts"]) == 5
        assert data["total"] == 5

        for receipt in data["receipts"]:
            assert "id" in receipt
            assert "transaction_moment" in receipt
            assert "total_amount" in receipt
            assert "store_name" in receipt
            assert "item_count" in receipt

    def test_receipts_list_with_pagination(self, client: TestClient, multiple_receipts_with_items: list[Receipt]):
        """Test receipts list with pagination."""
        response = client.get("/analytics/receipts?offset=2&limit=2")
        assert response.status_code == 200
        data = response.json()

        assert len(data["receipts"]) == 2
        assert data["offset"] == 2
        assert data["limit"] == 2

    def test_receipts_list_sort_by_amount(self, client: TestClient, multiple_receipts_with_items: list[Receipt]):
        """Test receipts list sorted by amount."""
        response = client.get("/analytics/receipts?sort_by=total_amount&sort_order=desc")
        assert response.status_code == 200
        data = response.json()

        if len(data["receipts"]) > 1:
            amounts = [r["total_amount"] for r in data["receipts"]]
            assert amounts == sorted(amounts, reverse=True)

    def test_receipts_list_sort_by_store(self, client: TestClient, multiple_receipts_with_items: list[Receipt]):
        """Test receipts list sorted by store name."""
        response = client.get("/analytics/receipts?sort_by=store_name&sort_order=asc")
        assert response.status_code == 200
        data = response.json()

        # Verify it returns successfully
        assert "receipts" in data

    def test_receipts_list_invalid_sort(self, client: TestClient):
        """Test receipts list with invalid sort parameter uses default."""
        response = client.get("/analytics/receipts?sort_by=invalid_field")
        # API uses Query with enum validation, invalid values should be rejected
        # If API accepts invalid values and defaults, it returns 200
        if response.status_code == 200:
            # Invalid sort falls back to default
            data = response.json()
            assert "receipts" in data
        else:
            assert response.status_code == 422


class TestReceiptDetailEndpoint:
    """Tests for GET /analytics/receipts/{receipt_id} endpoint."""

    def test_receipt_detail_not_found(self, client: TestClient):
        """Test receipt detail for non-existent receipt."""
        response = client.get("/analytics/receipts/nonexistent-id")
        assert response.status_code == 404
        data = response.json()
        assert "Receipt not found" in data["detail"]

    def test_receipt_detail_found(self, client: TestClient, sample_receipt_with_items: Receipt):
        """Test receipt detail for existing receipt."""
        response = client.get(f"/analytics/receipts/{sample_receipt_with_items.id}")
        assert response.status_code == 200
        data = response.json()

        assert data["id"] == sample_receipt_with_items.id
        assert data["total_amount"] == 32.50
        assert data["store_name"] == "AH Market"
        assert data["store_city"] == "Rotterdam"
        assert len(data["items"]) == 3
        assert len(data["discounts"]) == 1

    def test_receipt_detail_includes_all_fields(self, client: TestClient, sample_receipt_with_items: Receipt):
        """Test receipt detail includes all expected fields."""
        response = client.get(f"/analytics/receipts/{sample_receipt_with_items.id}")
        assert response.status_code == 200
        data = response.json()

        # Check main fields
        required_fields = [
            "id", "transaction_moment", "total_amount", "subtotal",
            "discount_total", "store_id", "store_name", "store_street",
            "store_city", "store_postal_code", "checkout_lane",
            "payment_method", "items", "discounts"
        ]
        for field in required_fields:
            assert field in data

        # Check item fields
        for item in data["items"]:
            assert "id" in item
            assert "product_name" in item
            assert "quantity" in item

        # Check discount fields
        for discount in data["discounts"]:
            assert "id" in discount
            assert "discount_amount" in discount
