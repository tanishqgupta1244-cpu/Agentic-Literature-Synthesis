"""
Integration tests — require a running PostgreSQL instance.

Run with:
    pytest tests/integration/ -m integration

Skip automatically when DATABASE_URL points to a test-only stub or
when PostgreSQL is not reachable.
"""
import os
import pytest


@pytest.mark.integration
class TestDatabaseConnection:
    """Verify a real PostgreSQL connection can be established."""

    def test_database_url_is_configured(self):
        """
        DATABASE_URL must be set before running integration tests.
        A missing value means .env was not configured — fail clearly.
        """
        url = os.getenv("DATABASE_URL", "")
        assert url, (
            "DATABASE_URL is not set. "
            "Copy .env.example to .env and configure your credentials."
        )

    @pytest.mark.asyncio
    async def test_database_connection_succeeds(self):
        """
        Attempt a real SELECT 1 against the configured PostgreSQL instance.
        Requires PostgreSQL to be running with the credentials in .env.
        """
        from backend.config.database import check_database_connection

        connected = await check_database_connection()
        assert connected, (
            "Could not connect to PostgreSQL. "
            "Ensure the database is running and DATABASE_URL is correct."
        )

    @pytest.mark.asyncio
    async def test_pgvector_availability(self):
        """
        Check whether pgvector extension is available.
        This test does NOT fail the suite if pgvector is missing —
        it simply records availability for Phase 0 reporting.
        """
        from backend.config.database import verify_pgvector_support

        available = verify_pgvector_support()
        # We do not assert True here — pgvector is optional in Phase 0.
        # The test passes either way; availability is printed for the report.
        print(f"\npgvector available: {available}")
        assert isinstance(available, bool)
