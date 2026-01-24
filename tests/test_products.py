"""
Integration tests for the Products API endpoints.
"""
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db_models import ProductCache
from app.product_models import ProductDetail, ProductPrice, ProductImage


class TestProductGet:
    """Tests for GET /products/{product_id} endpoint."""

    def test_get_product_not_found(self, client: TestClient):
        """Test getting a non-existent product."""
        with patch("app.product_routes.get_product_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_product = AsyncMock(return_value=None)
            mock_get_client.return_value = mock_client

            response = client.get("/products/999999")
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_get_product_from_api(self, client: TestClient, db_session):
        """Test getting a product from AH API."""
        mock_product = ProductDetail(
            product_id="123456",
            webshop_id="wi123456",
            title="Test Product",
            brand="Test Brand",
            category="Test Category",
            price=ProductPrice(amount=2.99, unit_size="500g"),
            unit_size="500g",
            images=[ProductImage(url="https://example.com/image.jpg")],
            is_available=True,
            is_bonus=False,
        )

        with patch("app.product_routes.get_product_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_product = AsyncMock(return_value=mock_product)
            mock_get_client.return_value = mock_client

            response = client.get("/products/123456")
            assert response.status_code == 200
            data = response.json()
            assert data["product_id"] == "123456"
            assert data["title"] == "Test Product"
            assert data["brand"] == "Test Brand"
            assert data["price"]["amount"] == 2.99

    def test_get_product_from_cache(self, client: TestClient):
        """Test getting a product from cache."""
        from tests.conftest import TestingSessionLocal

        # Use same session factory as client to add cache entry
        with TestingSessionLocal() as session:
            cache_entry = ProductCache(
                product_id="cached-123",
                webshop_id="wi-cached-123",
                title="Cached Product",
                brand="Cached Brand",
                category="Cached Category",
                price=1.99,
                unit_size="250g",
                image_url="https://example.com/cached.jpg",
                fetched_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )
            session.add(cache_entry)
            session.commit()

        response = client.get("/products/cached-123")
        assert response.status_code == 200
        data = response.json()
        assert data["product_id"] == "cached-123"
        assert data["title"] == "Cached Product"

    def test_get_product_refresh_bypasses_cache(self, client: TestClient, db_session):
        """Test that refresh=true bypasses cache."""
        # Add to cache
        cache_entry = ProductCache(
            product_id="refresh-123",
            webshop_id="wi-refresh-123",
            title="Old Cached Product",
            brand="Old Brand",
            price=1.00,
            fetched_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db_session.add(cache_entry)
        db_session.commit()

        # Mock API to return different data
        mock_product = ProductDetail(
            product_id="refresh-123",
            webshop_id="wi-refresh-123",
            title="Fresh API Product",
            brand="New Brand",
            price=ProductPrice(amount=2.00),
        )

        with patch("app.product_routes.get_product_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_product = AsyncMock(return_value=mock_product)
            mock_get_client.return_value = mock_client

            response = client.get("/products/refresh-123?refresh=true")
            assert response.status_code == 200
            data = response.json()
            assert data["title"] == "Fresh API Product"
            assert data["brand"] == "New Brand"

    def test_get_product_api_error(self, client: TestClient):
        """Test handling API errors gracefully."""
        with patch("app.product_routes.get_product_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_product = AsyncMock(side_effect=Exception("API Error"))
            mock_get_client.return_value = mock_client

            response = client.get("/products/error-123")
            assert response.status_code == 502
            assert "Failed to fetch" in response.json()["detail"]


class TestProductSearch:
    """Tests for GET /products/search/ endpoint."""

    def test_search_products_basic(self, client: TestClient):
        """Test basic product search."""
        from app.product_models import ProductSearchResponse, ProductSearchResult

        mock_response = ProductSearchResponse(
            query="milk",
            total_results=2,
            page=0,
            page_size=20,
            products=[
                ProductSearchResult(
                    product_id="1",
                    webshop_id="wi1",
                    title="Whole Milk 1L",
                    brand="AH",
                    price=1.29,
                    unit_size="1L",
                    is_bonus=False,
                ),
                ProductSearchResult(
                    product_id="2",
                    webshop_id="wi2",
                    title="Skim Milk 1L",
                    brand="AH",
                    price=1.19,
                    unit_size="1L",
                    is_bonus=True,
                ),
            ],
        )

        with patch("app.product_routes.get_product_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.search_products = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            response = client.get("/products/search/?q=milk")
            assert response.status_code == 200
            data = response.json()
            assert data["query"] == "milk"
            assert data["total_results"] == 2
            assert len(data["products"]) == 2
            assert data["products"][0]["title"] == "Whole Milk 1L"

    def test_search_products_pagination(self, client: TestClient):
        """Test search with pagination parameters."""
        from app.product_models import ProductSearchResponse

        mock_response = ProductSearchResponse(
            query="bread",
            total_results=50,
            page=2,
            page_size=10,
            products=[],
        )

        with patch("app.product_routes.get_product_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.search_products = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            response = client.get("/products/search/?q=bread&page=2&size=10")
            assert response.status_code == 200
            data = response.json()
            assert data["page"] == 2
            assert data["page_size"] == 10

    def test_search_products_sort_options(self, client: TestClient):
        """Test search with different sort options."""
        from app.product_models import ProductSearchResponse

        mock_response = ProductSearchResponse(
            query="cheese",
            total_results=10,
            page=0,
            page_size=20,
            products=[],
        )

        with patch("app.product_routes.get_product_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.search_products = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            # Test valid sort options
            for sort in ["RELEVANCE", "PRICE_ASC", "PRICE_DESC"]:
                response = client.get(f"/products/search/?q=cheese&sort={sort}")
                assert response.status_code == 200

    def test_search_products_invalid_sort(self, client: TestClient):
        """Test search with invalid sort option."""
        response = client.get("/products/search/?q=test&sort=INVALID")
        assert response.status_code == 400
        assert "Invalid sort" in response.json()["detail"]

    def test_search_products_empty_query(self, client: TestClient):
        """Test search with empty query."""
        response = client.get("/products/search/?q=")
        assert response.status_code == 422  # Validation error

    def test_search_products_api_error(self, client: TestClient):
        """Test handling search API errors."""
        with patch("app.product_routes.get_product_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.search_products = AsyncMock(side_effect=Exception("Search failed"))
            mock_get_client.return_value = mock_client

            response = client.get("/products/search/?q=test")
            assert response.status_code == 502


class TestProductBarcode:
    """Tests for GET /products/barcode/{barcode} endpoint."""

    def test_get_product_by_barcode(self, client: TestClient):
        """Test getting product by barcode."""
        mock_product = ProductDetail(
            product_id="123456",
            webshop_id="wi123456",
            title="Barcode Product",
            brand="Test Brand",
        )

        with patch("app.product_routes.get_product_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_product_by_barcode = AsyncMock(return_value=mock_product)
            mock_get_client.return_value = mock_client

            response = client.get("/products/barcode/8710400000000")
            assert response.status_code == 200
            data = response.json()
            assert data["title"] == "Barcode Product"

    def test_get_product_by_barcode_not_found(self, client: TestClient):
        """Test getting non-existent barcode."""
        with patch("app.product_routes.get_product_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_product_by_barcode = AsyncMock(return_value=None)
            mock_get_client.return_value = mock_client

            response = client.get("/products/barcode/0000000000000")
            assert response.status_code == 404


class TestProductBatch:
    """Tests for GET /products/batch/ endpoint."""

    def test_get_products_batch(self, client: TestClient, db_session):
        """Test getting multiple products by IDs."""
        mock_product = ProductDetail(
            product_id="batch-1",
            webshop_id="wi-batch-1",
            title="Batch Product 1",
            brand="Brand",
            images=[ProductImage(url="https://example.com/1.jpg")],
        )

        with patch("app.product_routes.get_product_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_product = AsyncMock(return_value=mock_product)
            mock_get_client.return_value = mock_client

            response = client.get("/products/batch/?ids=batch-1,batch-2")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_get_products_batch_empty_ids(self, client: TestClient):
        """Test batch with empty IDs."""
        response = client.get("/products/batch/?ids=")
        assert response.status_code == 400
        assert "No product IDs" in response.json()["detail"]

    def test_get_products_batch_too_many(self, client: TestClient):
        """Test batch with too many IDs."""
        ids = ",".join([f"id-{i}" for i in range(51)])
        response = client.get(f"/products/batch/?ids={ids}")
        assert response.status_code == 400
        assert "Maximum 50" in response.json()["detail"]

    def test_get_products_batch_from_cache(self, client: TestClient):
        """Test batch returns cached products."""
        from tests.conftest import TestingSessionLocal

        # Use same session factory as client to add cache entry
        with TestingSessionLocal() as session:
            cache_entry = ProductCache(
                product_id="cached-batch-1",
                webshop_id="wi-cached-batch-1",
                title="Cached Batch Product",
                brand="Cached Brand",
                price=5.99,
                fetched_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )
            session.add(cache_entry)
            session.commit()

        response = client.get("/products/batch/?ids=cached-batch-1")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["product_id"] == "cached-batch-1"
        assert data[0]["title"] == "Cached Batch Product"


class TestProductCache:
    """Tests for product cache management endpoints."""

    def test_cache_stats(self, client: TestClient, db_session):
        """Test getting cache statistics."""
        # Add some cached products
        now = datetime.now(timezone.utc)
        valid_entry = ProductCache(
            product_id="valid-1",
            webshop_id="wi-valid-1",
            title="Valid Product",
            fetched_at=now,
            expires_at=now + timedelta(days=7),
        )
        expired_entry = ProductCache(
            product_id="expired-1",
            webshop_id="wi-expired-1",
            title="Expired Product",
            fetched_at=now - timedelta(days=14),
            expires_at=now - timedelta(days=7),
        )
        db_session.add(valid_entry)
        db_session.add(expired_entry)
        db_session.commit()

        response = client.get("/products/cache/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_cached"] == 2
        assert data["valid"] == 1
        assert data["expired"] == 1
        assert data["cache_duration_days"] == 30

    def test_clear_expired_cache(self, client: TestClient, db_session):
        """Test clearing expired cache entries."""
        now = datetime.now(timezone.utc)
        # Add expired entry
        expired_entry = ProductCache(
            product_id="to-delete-1",
            webshop_id="wi-to-delete-1",
            title="To Delete",
            fetched_at=now - timedelta(days=14),
            expires_at=now - timedelta(days=7),
        )
        db_session.add(expired_entry)
        db_session.commit()

        response = client.delete("/products/cache/expired")
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] >= 1

        # Verify deleted
        remaining = db_session.query(ProductCache).filter(
            ProductCache.product_id == "to-delete-1"
        ).first()
        assert remaining is None


class TestProductWebshopId:
    """Tests for GET /products/webshop/{webshop_id} endpoint."""

    def test_get_product_by_webshop_id(self, client: TestClient):
        """Test getting product by webshop ID."""
        mock_product = ProductDetail(
            product_id="123456",
            webshop_id="wi123456",
            title="Webshop Product",
            brand="Test Brand",
        )

        with patch("app.product_routes.get_product_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_product = AsyncMock(return_value=mock_product)
            mock_get_client.return_value = mock_client

            response = client.get("/products/webshop/wi123456")
            assert response.status_code == 200
            data = response.json()
            assert data["webshop_id"] == "wi123456"
            assert data["title"] == "Webshop Product"

    def test_get_product_by_webshop_id_cached(self, client: TestClient):
        """Test getting webshop product from cache."""
        from tests.conftest import TestingSessionLocal

        now = datetime.now(timezone.utc)
        with TestingSessionLocal() as session:
            cache_entry = ProductCache(
                product_id="ws-cached-1",
                webshop_id="wi-ws-cached-1",
                title="Cached Webshop Product",
                brand="Cached Brand",
                fetched_at=now,
                expires_at=now + timedelta(days=7),
            )
            session.add(cache_entry)
            session.commit()

        response = client.get("/products/webshop/wi-ws-cached-1")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Cached Webshop Product"
