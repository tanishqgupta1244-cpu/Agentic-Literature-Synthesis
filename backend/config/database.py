"""
Database configuration and connection management.

The SQLAlchemy engine is created LAZILY — only when a connection is first
requested. This allows the application and its tests to import this module
without requiring PostgreSQL or a database driver to be installed yet.

Driver note:
    psycopg2-binary has no pre-built wheel for Python 3.12 on Windows.
    psycopg (v3, pure-Python) is the current-generation adapter and works
    on all platforms. It requires libpq (PostgreSQL client libraries) to be
    present at runtime — install PostgreSQL to satisfy this.
    DATABASE_URL format: postgresql+psycopg://user:password@host:port/dbname
"""
import os
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_RAW_URL: Optional[str] = os.getenv("DATABASE_URL")

# Normalise the URL to use the psycopg (v3) driver prefix.
# Accepts plain postgresql:// or explicit postgresql+psycopg2:// from legacy configs.
if _RAW_URL:
    if _RAW_URL.startswith("postgresql+psycopg2://"):
        DATABASE_URL: Optional[str] = _RAW_URL.replace(
            "postgresql+psycopg2://", "postgresql+psycopg://"
        )
    elif _RAW_URL.startswith("postgresql://"):
        DATABASE_URL = _RAW_URL.replace(
            "postgresql://", "postgresql+psycopg://"
        )
    else:
        DATABASE_URL = _RAW_URL
else:
    DATABASE_URL = None

# ---------------------------------------------------------------------------
# Lazy engine — created only on first use, not at import time
# ---------------------------------------------------------------------------
_engine = None
_SessionLocal = None


def _get_engine():
    """
    Return the SQLAlchemy engine, creating it on first call.

    Raises:
        ValueError: If DATABASE_URL is not configured.
        ImportError: If the psycopg driver / libpq is not available.
    """
    global _engine
    if _engine is None:
        if not DATABASE_URL:
            raise ValueError(
                "DATABASE_URL environment variable is not set. "
                "Copy .env.example to .env and configure your credentials."
            )
        from sqlalchemy import create_engine
        from sqlalchemy.pool import NullPool

        _engine = create_engine(
            DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            poolclass=NullPool,
        )
        logger.info("SQLAlchemy engine created")
    return _engine


def _get_session_factory():
    """Return the session factory, creating it on first call."""
    global _SessionLocal
    if _SessionLocal is None:
        from sqlalchemy.orm import sessionmaker
        _SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=_get_engine()
        )
    return _SessionLocal


def get_db():
    """
    FastAPI dependency — provides a database session per request.

    Yields:
        Session: SQLAlchemy database session
    """
    SessionLocal = _get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def check_database_connection() -> bool:
    """
    Verify that the database is reachable with a minimal SELECT 1 query.

    Returns:
        bool: True if the query succeeds, False on any error.
    """
    try:
        from sqlalchemy import text
        engine = _get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


def verify_pgvector_support() -> bool:
    """
    Check whether the pgvector extension is available on the connected database.

    This is a best-effort, non-fatal check for Phase 0.

    Returns:
        bool: True if CREATE EXTENSION IF NOT EXISTS vector succeeds.
    """
    try:
        from sqlalchemy import text
        engine = _get_engine()
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        logger.info("pgvector extension is available")
        return True
    except Exception as e:
        logger.warning(f"pgvector not available: {e}")
        return False
