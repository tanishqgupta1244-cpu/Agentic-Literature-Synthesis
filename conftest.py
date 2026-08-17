"""
Root conftest.py — shared fixtures and test configuration.

Loaded automatically by pytest before any test module runs.
"""
import os
import pytest
from unittest.mock import AsyncMock, patch


# ---------------------------------------------------------------------------
# Environment isolation
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True, scope="session")
def set_test_environment():
    """
    Ensure tests always run with APP_ENV=test so no real .env values
    leak into unit tests.  Integration tests may override individual
    env vars inside their own fixtures.
    """
    os.environ.setdefault("APP_ENV", "test")
    # Provide a safe fallback DATABASE_URL so importing database.py
    # during unit tests does not raise ValueError if no .env is present.
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql://test_user:test_password@localhost:5432/literature_review_test",
    )
    os.environ.setdefault("BACKEND_PORT", "8000")
    os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")


# ---------------------------------------------------------------------------
# FastAPI test client
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_app():
    """
    Return the FastAPI application instance.
    Imported here so the session-level env vars above are already set.
    """
    from backend.main import app
    return app


@pytest.fixture(scope="session")
def client(test_app):
    """
    Synchronous TestClient for unit tests.
    """
    from fastapi.testclient import TestClient
    with TestClient(test_app) as c:
        yield c


# ---------------------------------------------------------------------------
# Database mock — used by unit tests to avoid a real DB connection
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db_connected():
    """Patch database check to simulate a healthy connection."""
    with patch(
        "backend.api.health.check_database_connection",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock:
        yield mock


@pytest.fixture
def mock_db_disconnected():
    """Patch database check to simulate a failed connection."""
    with patch(
        "backend.api.health.check_database_connection",
        new_callable=AsyncMock,
        return_value=False,
    ) as mock:
        yield mock
