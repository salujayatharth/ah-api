"""
Tests for health check and basic endpoints.
"""
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    def test_health_check_returns_200(self, client: TestClient):
        """Test that health check returns 200 status."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_check_returns_healthy_status(self, client: TestClient):
        """Test that health check returns healthy status with db check."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"
        assert data["checks"]["database"] == "healthy"

    def test_health_check_unhealthy_database(self, client: TestClient):
        """Test that health check returns 503 when database is unreachable."""
        mock_session = MagicMock()
        mock_session.execute.side_effect = Exception("connection refused")

        with patch("app.main.SessionLocal", return_value=mock_session):
            response = client.get("/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["checks"]["database"] == "unhealthy"


class TestDashboardEndpoint:
    """Tests for the dashboard/home page endpoints."""

    def test_root_returns_html(self, client: TestClient):
        """Test that root endpoint returns HTML page."""
        response = client.get("/")
        assert response.status_code == 200
        # Should return HTML content
        assert "text/html" in response.headers.get("content-type", "")

    def test_dashboard_returns_html(self, client: TestClient):
        """Test that /dashboard endpoint returns HTML page."""
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_root_and_dashboard_return_same_content(self, client: TestClient):
        """Test that / and /dashboard return the same page."""
        root_response = client.get("/")
        dashboard_response = client.get("/dashboard")

        assert root_response.status_code == dashboard_response.status_code
        assert root_response.content == dashboard_response.content


class TestAPIDocumentation:
    """Tests for API documentation endpoints."""

    def test_openapi_json_available(self, client: TestClient):
        """Test that OpenAPI JSON is available."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
        assert "info" in data

    def test_docs_redirect(self, client: TestClient):
        """Test that /docs endpoint is accessible."""
        response = client.get("/docs", follow_redirects=False)
        # /docs should return 200 or redirect
        assert response.status_code in [200, 307]

    def test_redoc_accessible(self, client: TestClient):
        """Test that /redoc endpoint is accessible."""
        response = client.get("/redoc", follow_redirects=False)
        # /redoc should return 200 or redirect
        assert response.status_code in [200, 307]
