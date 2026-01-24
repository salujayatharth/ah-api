"""
Tests for receipt endpoints (/receipts/*).
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from httpx import HTTPStatusError, Response, Request

from app.client import AHClient, TOKEN_FILE
from app.routes import get_client
from app.config import Settings


class TestAuthStatus:
    """Tests for /receipts/auth/status endpoint."""

    def test_auth_status_not_authenticated(self, client: TestClient):
        """Test auth status when not authenticated."""
        # Create a mock client that is not authenticated
        mock_client = MagicMock(spec=AHClient)
        mock_client.is_authenticated.return_value = False

        def mock_get_client():
            return mock_client

        from app.main import app
        app.dependency_overrides[get_client] = mock_get_client

        response = client.get("/receipts/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert data == {"authenticated": False}

        # Clean up
        del app.dependency_overrides[get_client]

    def test_auth_status_authenticated(self, client: TestClient):
        """Test auth status when authenticated."""
        mock_client = MagicMock(spec=AHClient)
        mock_client.is_authenticated.return_value = True

        def mock_get_client():
            return mock_client

        from app.main import app
        app.dependency_overrides[get_client] = mock_get_client

        response = client.get("/receipts/auth/status")
        assert response.status_code == 200
        data = response.json()
        assert data == {"authenticated": True}

        # Clean up
        del app.dependency_overrides[get_client]


class TestAuthentication:
    """Tests for /receipts/auth endpoint."""

    def test_authenticate_with_code(self, client: TestClient):
        """Test authentication with authorization code."""
        mock_client = MagicMock(spec=AHClient)
        mock_client.exchange_code = AsyncMock(return_value={
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_in": 7200,
        })

        def mock_get_client():
            return mock_client

        from app.main import app
        app.dependency_overrides[get_client] = mock_get_client

        response = client.post("/receipts/auth", json={"code": "test-auth-code"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "authenticated"
        assert data["expires_in"] == 7200

        mock_client.exchange_code.assert_called_once_with("test-auth-code")

        # Clean up
        del app.dependency_overrides[get_client]

    def test_authenticate_with_invalid_code(self, client: TestClient):
        """Test authentication with invalid code."""
        mock_client = MagicMock(spec=AHClient)

        # Create a mock HTTPStatusError
        mock_request = Request("POST", "https://api.ah.nl/mobile-auth/v1/auth/token")
        mock_response = Response(401, json={"error": "invalid_code"}, request=mock_request)
        mock_client.exchange_code = AsyncMock(
            side_effect=HTTPStatusError("Invalid code", request=mock_request, response=mock_response)
        )

        def mock_get_client():
            return mock_client

        from app.main import app
        app.dependency_overrides[get_client] = mock_get_client

        response = client.post("/receipts/auth", json={"code": "invalid-code"})
        assert response.status_code == 401

        # Clean up
        del app.dependency_overrides[get_client]

    def test_authenticate_missing_code(self, client: TestClient):
        """Test authentication without code field."""
        response = client.post("/receipts/auth", json={})
        assert response.status_code == 422  # Validation error


class TestLogout:
    """Tests for /receipts/auth (DELETE) endpoint."""

    def test_logout(self, client: TestClient):
        """Test logout clears tokens."""
        response = client.delete("/receipts/auth")
        assert response.status_code == 200
        data = response.json()
        assert data == {"status": "logged out"}


class TestListReceipts:
    """Tests for GET /receipts endpoint."""

    def test_list_receipts_unauthenticated(self, client: TestClient):
        """Test listing receipts when not authenticated."""
        mock_client = MagicMock(spec=AHClient)
        mock_client.is_authenticated.return_value = False

        def mock_get_client():
            return mock_client

        from app.main import app
        app.dependency_overrides[get_client] = mock_get_client

        response = client.get("/receipts")
        assert response.status_code == 401
        data = response.json()
        assert "Not authenticated" in data["detail"]

        # Clean up
        del app.dependency_overrides[get_client]

    def test_list_receipts_authenticated(self, client: TestClient):
        """Test listing receipts when authenticated."""
        mock_client = MagicMock(spec=AHClient)
        mock_client.is_authenticated.return_value = True
        mock_client.get_receipts = AsyncMock(return_value={
            "pagination": {"offset": 0, "limit": 20, "totalElements": 2},
            "posReceipts": [
                {
                    "id": "receipt-001",
                    "dateTime": "2024-01-15T10:30:00",
                    "totalAmount": {"amount": 45.67, "formatted": "45,67"},
                    "storeAddress": {"city": "Amsterdam", "street": "123 Test St"},
                },
                {
                    "id": "receipt-002",
                    "dateTime": "2024-01-20T14:45:00",
                    "totalAmount": {"amount": 32.50, "formatted": "32,50"},
                    "storeAddress": {"city": "Rotterdam", "street": "456 Main St"},
                },
            ],
        })

        def mock_get_client():
            return mock_client

        from app.main import app
        app.dependency_overrides[get_client] = mock_get_client

        response = client.get("/receipts")
        assert response.status_code == 200
        data = response.json()
        assert "pagination" in data
        assert "posReceipts" in data
        assert len(data["posReceipts"]) == 2

        # Clean up
        del app.dependency_overrides[get_client]

    def test_list_receipts_with_pagination(self, client: TestClient):
        """Test listing receipts with custom pagination."""
        mock_client = MagicMock(spec=AHClient)
        mock_client.is_authenticated.return_value = True
        mock_client.get_receipts = AsyncMock(return_value={
            "pagination": {"offset": 10, "limit": 5, "totalElements": 50},
            "posReceipts": [],
        })

        def mock_get_client():
            return mock_client

        from app.main import app
        app.dependency_overrides[get_client] = mock_get_client

        response = client.get("/receipts?offset=10&limit=5")
        assert response.status_code == 200

        mock_client.get_receipts.assert_called_once_with(offset=10, limit=5)

        # Clean up
        del app.dependency_overrides[get_client]

    def test_list_receipts_invalid_pagination(self, client: TestClient):
        """Test listing receipts with invalid pagination values."""
        mock_client = MagicMock(spec=AHClient)
        mock_client.is_authenticated.return_value = True

        def mock_get_client():
            return mock_client

        from app.main import app
        app.dependency_overrides[get_client] = mock_get_client

        # Negative offset should fail validation
        response = client.get("/receipts?offset=-1")
        assert response.status_code == 422

        # Limit over 100 should fail validation
        response = client.get("/receipts?limit=150")
        assert response.status_code == 422

        # Clean up
        del app.dependency_overrides[get_client]


class TestGetReceipt:
    """Tests for GET /receipts/{receipt_id} endpoint."""

    def test_get_receipt_unauthenticated(self, client: TestClient):
        """Test getting receipt when not authenticated."""
        mock_client = MagicMock(spec=AHClient)
        mock_client.is_authenticated.return_value = False

        def mock_get_client():
            return mock_client

        from app.main import app
        app.dependency_overrides[get_client] = mock_get_client

        response = client.get("/receipts/receipt-001")
        assert response.status_code == 401

        # Clean up
        del app.dependency_overrides[get_client]

    def test_get_receipt_authenticated(self, client: TestClient):
        """Test getting receipt when authenticated."""
        mock_client = MagicMock(spec=AHClient)
        mock_client.is_authenticated.return_value = True
        mock_client.get_receipt = AsyncMock(return_value={
            "id": "receipt-001",
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
            "total": {"amount": 3.00, "formatted": "3,00"},
        })

        def mock_get_client():
            return mock_client

        from app.main import app
        app.dependency_overrides[get_client] = mock_get_client

        response = client.get("/receipts/receipt-001")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "receipt-001"
        assert "products" in data

        mock_client.get_receipt.assert_called_once_with("receipt-001")

        # Clean up
        del app.dependency_overrides[get_client]


class TestGetReceiptPDF:
    """Tests for GET /receipts/{receipt_id}/pdf endpoint."""

    def test_get_receipt_pdf_unauthenticated(self, client: TestClient):
        """Test getting receipt PDF when not authenticated."""
        mock_client = MagicMock(spec=AHClient)
        mock_client.is_authenticated.return_value = False

        def mock_get_client():
            return mock_client

        from app.main import app
        app.dependency_overrides[get_client] = mock_get_client

        response = client.get("/receipts/receipt-001/pdf")
        assert response.status_code == 401

        # Clean up
        del app.dependency_overrides[get_client]

    def test_get_receipt_pdf_authenticated(self, client: TestClient):
        """Test getting receipt PDF when authenticated."""
        mock_client = MagicMock(spec=AHClient)
        mock_client.is_authenticated.return_value = True
        mock_client.get_receipt_pdf = AsyncMock(return_value={
            "url": "https://example.com/receipt-001.pdf"
        })

        def mock_get_client():
            return mock_client

        from app.main import app
        app.dependency_overrides[get_client] = mock_get_client

        response = client.get("/receipts/receipt-001/pdf")
        assert response.status_code == 200
        data = response.json()
        assert "url" in data
        assert data["url"] == "https://example.com/receipt-001.pdf"

        mock_client.get_receipt_pdf.assert_called_once_with("receipt-001")

        # Clean up
        del app.dependency_overrides[get_client]


class TestSyncReceipts:
    """Tests for POST /receipts/sync endpoint."""

    def test_sync_receipts_unauthenticated(self, client: TestClient):
        """Test syncing receipts when not authenticated."""
        mock_client = MagicMock(spec=AHClient)
        mock_client.is_authenticated.return_value = False

        def mock_get_client():
            return mock_client

        from app.main import app
        app.dependency_overrides[get_client] = mock_get_client

        response = client.post("/receipts/sync")
        assert response.status_code == 401

        # Clean up
        del app.dependency_overrides[get_client]

    def test_sync_receipts_authenticated_empty(self, client: TestClient, db_session):
        """Test syncing receipts when authenticated but no receipts."""
        mock_client = MagicMock(spec=AHClient)
        mock_client.is_authenticated.return_value = True
        mock_client.get_receipts = AsyncMock(return_value={
            "pagination": {"offset": 0, "limit": 20, "totalElements": 0},
            "posReceipts": [],
        })

        def mock_get_client():
            return mock_client

        from app.main import app
        app.dependency_overrides[get_client] = mock_get_client

        response = client.post("/receipts/sync")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["synced_count"] == 0
        assert data["skipped_count"] == 0
        assert data["error_count"] == 0

        # Clean up
        del app.dependency_overrides[get_client]

    def test_sync_receipts_full_sync_parameter(self, client: TestClient, db_session):
        """Test sync with full_sync parameter."""
        mock_client = MagicMock(spec=AHClient)
        mock_client.is_authenticated.return_value = True
        mock_client.get_receipts = AsyncMock(return_value={
            "pagination": {"offset": 0, "limit": 20, "totalElements": 0},
            "posReceipts": [],
        })

        def mock_get_client():
            return mock_client

        from app.main import app
        app.dependency_overrides[get_client] = mock_get_client

        response = client.post("/receipts/sync?full_sync=true")
        assert response.status_code == 200

        # Clean up
        del app.dependency_overrides[get_client]
