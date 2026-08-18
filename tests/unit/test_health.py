"""
Unit tests for backend health endpoints.

These tests do NOT require a running database — database connectivity
is patched via fixtures defined in conftest.py.

Run with:
    pytest tests/unit/
"""
import pytest


@pytest.mark.unit
class TestHealthEndpoint:
    """Tests for GET /health"""

    def test_returns_200(self, client):
        """GET /health must return HTTP 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_response_has_status_field(self, client):
        """Response body must contain a 'status' key."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data

    def test_status_value_is_ok(self, client):
        """Response status must equal 'ok'."""
        response = client.get("/health")
        assert response.json()["status"] == "ok"

    def test_content_type_is_json(self, client):
        """Response Content-Type must be application/json."""
        response = client.get("/health")
        assert "application/json" in response.headers["content-type"]


@pytest.mark.unit
class TestHealthDbEndpoint:
    """Tests for GET /health/db"""

    def test_returns_200_when_db_connected(self, client, mock_db_connected):
        """When DB is reachable, /health/db must return 200."""
        response = client.get("/health/db")
        assert response.status_code == 200

    def test_response_contains_database_field_when_connected(
        self, client, mock_db_connected
    ):
        """Connected response must include database: connected."""
        response = client.get("/health/db")
        data = response.json()
        assert data.get("database") == "connected"
        assert data.get("status") == "ok"

    def test_returns_503_when_db_disconnected(self, client, mock_db_disconnected):
        """When DB is unreachable, /health/db must return 503."""
        response = client.get("/health/db")
        assert response.status_code == 503

    def test_accepts_valid_status_codes(self, client):
        """
        With a real or mocked DB, /health/db must return 200 or 503 —
        never anything unexpected.
        """
        response = client.get("/health/db")
        assert response.status_code in (200, 503)


@pytest.mark.unit
class TestMissingEnvironmentVariables:
    """Verify the application surfaces missing config clearly."""

    def test_database_url_env_var_produces_error_when_absent(self, monkeypatch):
        """
        If DATABASE_URL is removed, check_database_connection should return False
        (it logs the error internally) and the lazy engine should raise ValueError
        when directly called.
        """
        import asyncio
        monkeypatch.delenv("DATABASE_URL", raising=False)

        import backend.config.database as db_module
        db_module._engine = None
        db_module.DATABASE_URL = None

        # _get_engine() must raise ValueError when DATABASE_URL is absent
        with pytest.raises(ValueError, match="DATABASE_URL"):
            db_module._get_engine()

        # check_database_connection must return False gracefully (not raise)
        result = asyncio.run(db_module.check_database_connection())
        assert result is False
