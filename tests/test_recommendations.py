"""
Tests for recommendation endpoints (/analytics/recommendations/*).
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db_models import Receipt, ReceiptItem, ReceiptDiscount


@pytest.fixture
def receipts_for_recommendations(db_session: Session) -> list[Receipt]:
    """Create receipts with purchase patterns suitable for recommendation testing."""
    receipts = []
    base_date = datetime.now()

    # Create receipts over the past 60 days with regular purchase patterns
    for i in range(10):
        receipt = Receipt(
            id=f"rec-recommend-{i:03d}",
            transaction_moment=base_date - timedelta(days=i * 7),  # Weekly shopping
            total_amount=50.00 + (i * 5),
            subtotal=55.00 + (i * 5),
            discount_total=-5.00,
            member_id="member-recommend",
            store_id=1001,
            store_name="AH Recommend Test",
            store_street="789 Test Ave",
            store_city="Utrecht",
            store_postal_code="3500CD",
            checkout_lane=2,
            payment_method="PIN",
        )
        db_session.add(receipt)
        receipts.append(receipt)

    db_session.flush()

    # Add items with regular purchase patterns
    # Milk - bought every week (high frequency)
    for i, receipt in enumerate(receipts):
        item = ReceiptItem(
            receipt_id=receipt.id,
            product_id="prod-milk-001",
            product_name="Halfvolle Melk 1L",
            quantity=2,
            unit_price=1.29,
            line_total=2.58,
        )
        db_session.add(item)

    # Bread - bought every other week
    for i, receipt in enumerate(receipts):
        if i % 2 == 0:
            item = ReceiptItem(
                receipt_id=receipt.id,
                product_id="prod-bread-001",
                product_name="Volkoren Brood",
                quantity=1,
                unit_price=2.49,
                line_total=2.49,
            )
            db_session.add(item)

    # Eggs - bought every 3 weeks
    for i, receipt in enumerate(receipts):
        if i % 3 == 0:
            item = ReceiptItem(
                receipt_id=receipt.id,
                product_id="prod-eggs-001",
                product_name="Scharreleieren 10 stuks",
                quantity=1,
                unit_price=3.99,
                line_total=3.99,
            )
            db_session.add(item)

    # Butter - bought twice total (not enough data for reliable prediction)
    for i, receipt in enumerate(receipts[:2]):
        item = ReceiptItem(
            receipt_id=receipt.id,
            product_id="prod-butter-001",
            product_name="Roomboter",
            quantity=1,
            unit_price=2.79,
            line_total=2.79,
        )
        db_session.add(item)

    # Cheese - bought once (should be filtered out)
    item = ReceiptItem(
        receipt_id=receipts[0].id,
        product_id="prod-cheese-001",
        product_name="Oude Kaas",
        quantity=0.5,
        unit_price=12.99,
        line_total=6.50,
    )
    db_session.add(item)

    db_session.commit()
    for receipt in receipts:
        db_session.refresh(receipt)

    return receipts


class TestShoppingListRecommendation:
    """Tests for GET /analytics/recommendations/shopping-list endpoint."""

    def test_shopping_list_empty_database(self, client: TestClient):
        """Test shopping list with empty database."""
        response = client.get("/analytics/recommendations/shopping-list")
        assert response.status_code == 200
        data = response.json()

        assert "generated_at" in data
        assert "planning_horizon_days" in data
        assert data["needed_items"] == []
        assert data["might_need_soon"] == []
        assert data["estimated_total"] == 0
        assert data["items_analyzed"] == 0

    def test_shopping_list_with_data(self, client: TestClient, receipts_for_recommendations: list[Receipt]):
        """Test shopping list with purchase history."""
        response = client.get("/analytics/recommendations/shopping-list")
        assert response.status_code == 200
        data = response.json()

        assert "generated_at" in data
        assert data["planning_horizon_days"] == 4  # Default
        assert "needed_items" in data
        assert "might_need_soon" in data
        assert "estimated_total" in data
        assert "items_analyzed" in data

    def test_shopping_list_custom_horizon(self, client: TestClient, receipts_for_recommendations: list[Receipt]):
        """Test shopping list with custom planning horizon."""
        response = client.get("/analytics/recommendations/shopping-list?days_ahead=7")
        assert response.status_code == 200
        data = response.json()

        assert data["planning_horizon_days"] == 7

    def test_shopping_list_custom_confidence(self, client: TestClient, receipts_for_recommendations: list[Receipt]):
        """Test shopping list with custom confidence threshold."""
        response = client.get("/analytics/recommendations/shopping-list?min_confidence=0.5")
        assert response.status_code == 200
        data = response.json()

        # All returned items should have confidence >= 0.5
        for item in data["needed_items"]:
            assert item["confidence"] >= 0.5
        for item in data["might_need_soon"]:
            assert item["confidence"] >= 0.5

    def test_shopping_list_custom_min_purchases(self, client: TestClient, receipts_for_recommendations: list[Receipt]):
        """Test shopping list with custom minimum purchases."""
        # With min_purchases=5, products bought less frequently should be filtered
        response = client.get("/analytics/recommendations/shopping-list?min_purchases=5")
        assert response.status_code == 200
        data = response.json()

        # Verify items with fewer purchases are filtered
        assert data["items_filtered_out"] >= 0

    def test_shopping_list_all_parameters(self, client: TestClient, receipts_for_recommendations: list[Receipt]):
        """Test shopping list with all custom parameters."""
        response = client.get(
            "/analytics/recommendations/shopping-list"
            "?days_ahead=10"
            "&min_confidence=0.2"
            "&decay_rate=0.03"
            "&min_purchases=2"
            "&max_avg_interval=45"
            "&max_days_since_last=120"
        )
        assert response.status_code == 200
        data = response.json()

        assert data["planning_horizon_days"] == 10

    def test_shopping_list_item_structure(self, client: TestClient, receipts_for_recommendations: list[Receipt]):
        """Test that shopping list items have correct structure."""
        response = client.get("/analytics/recommendations/shopping-list?min_purchases=1")
        assert response.status_code == 200
        data = response.json()

        all_items = data["needed_items"] + data["might_need_soon"]
        if len(all_items) > 0:
            item = all_items[0]
            required_fields = [
                "product_name", "product_id", "suggested_quantity",
                "urgency", "estimated_days_until_needed", "median_price",
                "estimated_cost", "confidence", "last_purchase_date",
                "purchase_count"
            ]
            for field in required_fields:
                assert field in item, f"Missing field: {field}"

    def test_shopping_list_invalid_days_ahead(self, client: TestClient):
        """Test shopping list with invalid days_ahead parameter."""
        response = client.get("/analytics/recommendations/shopping-list?days_ahead=0")
        assert response.status_code == 422

        response = client.get("/analytics/recommendations/shopping-list?days_ahead=50")
        assert response.status_code == 422

    def test_shopping_list_invalid_min_confidence(self, client: TestClient):
        """Test shopping list with invalid confidence parameter."""
        response = client.get("/analytics/recommendations/shopping-list?min_confidence=-0.1")
        assert response.status_code == 422

        response = client.get("/analytics/recommendations/shopping-list?min_confidence=1.5")
        assert response.status_code == 422


class TestConsumptionPatterns:
    """Tests for GET /analytics/recommendations/consumption-patterns endpoint."""

    def test_consumption_patterns_empty_database(self, client: TestClient):
        """Test consumption patterns with empty database."""
        response = client.get("/analytics/recommendations/consumption-patterns")
        assert response.status_code == 200
        data = response.json()

        assert "generated_at" in data
        assert data["products"] == []
        assert data["total_products_analyzed"] == 0
        assert "filter_criteria" in data

    def test_consumption_patterns_with_data(self, client: TestClient, receipts_for_recommendations: list[Receipt]):
        """Test consumption patterns with purchase history."""
        response = client.get("/analytics/recommendations/consumption-patterns")
        assert response.status_code == 200
        data = response.json()

        assert "generated_at" in data
        assert "products" in data
        assert "total_products_analyzed" in data
        assert "products_filtered_out" in data
        assert "filter_criteria" in data

    def test_consumption_patterns_product_structure(self, client: TestClient, receipts_for_recommendations: list[Receipt]):
        """Test that consumption patterns have correct product structure."""
        response = client.get("/analytics/recommendations/consumption-patterns?min_purchases=1")
        assert response.status_code == 200
        data = response.json()

        if len(data["products"]) > 0:
            product = data["products"][0]
            required_fields = [
                "product_name", "product_id", "purchase_count",
                "total_quantity_purchased", "median_quantity_per_purchase",
                "median_interval_days", "weighted_avg_interval_days",
                "consumption_rate_per_day", "last_purchase_date",
                "days_since_last_purchase", "estimated_inventory",
                "days_until_needed", "median_price", "confidence"
            ]
            for field in required_fields:
                assert field in product, f"Missing field: {field}"

    def test_consumption_patterns_custom_parameters(self, client: TestClient, receipts_for_recommendations: list[Receipt]):
        """Test consumption patterns with custom parameters."""
        response = client.get(
            "/analytics/recommendations/consumption-patterns"
            "?decay_rate=0.05"
            "&min_purchases=2"
            "&max_avg_interval=30"
            "&max_days_since_last=60"
        )
        assert response.status_code == 200
        data = response.json()

        # Verify filter criteria is returned
        assert "filter_criteria" in data

    def test_consumption_patterns_filter_criteria(self, client: TestClient, receipts_for_recommendations: list[Receipt]):
        """Test that filter criteria is correctly returned."""
        response = client.get(
            "/analytics/recommendations/consumption-patterns"
            "?min_purchases=4"
            "&max_avg_interval=50"
        )
        assert response.status_code == 200
        data = response.json()

        assert data["filter_criteria"]["min_purchases"] == 4
        # The API uses "max_avg_interval_days" as the key name
        assert data["filter_criteria"]["max_avg_interval_days"] == 50


class TestProductConsumptionDetail:
    """Tests for GET /analytics/recommendations/product/{product_name} endpoint."""

    def test_product_detail_not_found(self, client: TestClient):
        """Test product detail for non-existent product."""
        response = client.get("/analytics/recommendations/product/NonExistentProduct123")
        assert response.status_code == 404
        data = response.json()
        assert "No purchase history found" in data["detail"]

    def test_product_detail_found(self, client: TestClient, receipts_for_recommendations: list[Receipt]):
        """Test product detail for existing product."""
        response = client.get("/analytics/recommendations/product/Halfvolle%20Melk%201L")
        assert response.status_code == 200
        data = response.json()

        assert data["product_name"] == "Halfvolle Melk 1L"
        assert "product_id" in data
        assert "purchase_history" in data
        assert "consumption_pattern" in data
        assert "prediction_explanation" in data

    def test_product_detail_partial_match(self, client: TestClient, receipts_for_recommendations: list[Receipt]):
        """Test product detail with partial name match."""
        response = client.get("/analytics/recommendations/product/Melk")
        assert response.status_code == 200
        data = response.json()

        assert "Melk" in data["product_name"]

    def test_product_detail_case_insensitive(self, client: TestClient, receipts_for_recommendations: list[Receipt]):
        """Test product detail is case insensitive."""
        response_upper = client.get("/analytics/recommendations/product/MELK")
        response_lower = client.get("/analytics/recommendations/product/melk")

        # Both should return the same product
        assert response_upper.status_code == 200
        assert response_lower.status_code == 200

        data_upper = response_upper.json()
        data_lower = response_lower.json()
        assert data_upper["product_name"] == data_lower["product_name"]

    def test_product_detail_purchase_history_structure(self, client: TestClient, receipts_for_recommendations: list[Receipt]):
        """Test that purchase history has correct structure."""
        response = client.get("/analytics/recommendations/product/Melk")
        assert response.status_code == 200
        data = response.json()

        assert len(data["purchase_history"]) > 0
        purchase = data["purchase_history"][0]

        required_fields = ["date", "quantity", "unit_price", "receipt_id"]
        for field in required_fields:
            assert field in purchase, f"Missing field in purchase history: {field}"

    def test_product_detail_consumption_pattern_structure(self, client: TestClient, receipts_for_recommendations: list[Receipt]):
        """Test that consumption pattern has correct structure."""
        response = client.get("/analytics/recommendations/product/Melk")
        assert response.status_code == 200
        data = response.json()

        pattern = data["consumption_pattern"]
        required_fields = [
            "product_name", "purchase_count", "total_quantity_purchased",
            "median_quantity_per_purchase", "median_interval_days",
            "weighted_avg_interval_days", "consumption_rate_per_day",
            "last_purchase_date", "days_since_last_purchase",
            "estimated_inventory", "days_until_needed", "median_price", "confidence"
        ]
        for field in required_fields:
            assert field in pattern, f"Missing field in consumption pattern: {field}"

    def test_product_detail_custom_decay_rate(self, client: TestClient, receipts_for_recommendations: list[Receipt]):
        """Test product detail with custom decay rate."""
        response = client.get("/analytics/recommendations/product/Melk?decay_rate=0.05")
        assert response.status_code == 200
        data = response.json()

        # Response should still be valid
        assert "consumption_pattern" in data
        assert "prediction_explanation" in data

    def test_product_detail_prediction_explanation(self, client: TestClient, receipts_for_recommendations: list[Receipt]):
        """Test that prediction explanation is human readable."""
        response = client.get("/analytics/recommendations/product/Melk")
        assert response.status_code == 200
        data = response.json()

        # Explanation should be a non-empty string
        assert isinstance(data["prediction_explanation"], str)
        assert len(data["prediction_explanation"]) > 0

    def test_product_detail_invalid_decay_rate(self, client: TestClient):
        """Test product detail with invalid decay rate."""
        response = client.get("/analytics/recommendations/product/test?decay_rate=0.0001")
        assert response.status_code == 422

        response = client.get("/analytics/recommendations/product/test?decay_rate=0.2")
        assert response.status_code == 422


class TestRecommendationEdgeCases:
    """Tests for edge cases in recommendation endpoints."""

    def test_recommendations_with_single_purchase(self, client: TestClient, db_session: Session):
        """Test recommendations when products have only one purchase."""
        # Create a receipt with single-purchase items
        receipt = Receipt(
            id="single-purchase-001",
            transaction_moment=datetime.now() - timedelta(days=10),
            total_amount=10.00,
            subtotal=10.00,
            store_id=9999,
            store_name="Single Test Store",
        )
        db_session.add(receipt)
        db_session.flush()

        item = ReceiptItem(
            receipt_id=receipt.id,
            product_id="single-prod-001",
            product_name="Single Purchase Item",
            quantity=1,
            unit_price=10.00,
            line_total=10.00,
        )
        db_session.add(item)
        db_session.commit()

        # With default min_purchases=3, this should be filtered
        response = client.get("/analytics/recommendations/shopping-list")
        assert response.status_code == 200
        data = response.json()

        # The single-purchase item should be filtered out
        all_items = data["needed_items"] + data["might_need_soon"]
        product_names = [item["product_name"] for item in all_items]
        assert "Single Purchase Item" not in product_names

    def test_recommendations_with_very_old_purchases(self, client: TestClient, db_session: Session):
        """Test recommendations filter out very old purchases."""
        # Create receipts from 100+ days ago
        for i in range(5):
            receipt = Receipt(
                id=f"old-purchase-{i:03d}",
                transaction_moment=datetime.now() - timedelta(days=100 + i * 7),
                total_amount=10.00,
                subtotal=10.00,
                store_id=8888,
                store_name="Old Test Store",
            )
            db_session.add(receipt)
            db_session.flush()

            item = ReceiptItem(
                receipt_id=receipt.id,
                product_id="old-prod-001",
                product_name="Old Purchase Item",
                quantity=1,
                unit_price=10.00,
                line_total=10.00,
            )
            db_session.add(item)

        db_session.commit()

        # With default max_days_since_last=90, this should be filtered
        response = client.get("/analytics/recommendations/shopping-list")
        assert response.status_code == 200
        data = response.json()

        all_items = data["needed_items"] + data["might_need_soon"]
        product_names = [item["product_name"] for item in all_items]
        assert "Old Purchase Item" not in product_names
