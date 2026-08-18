"""
scripts/init_db.py
==================
Initialise the Phase 1 database schema (idempotent).

Creates the ``papers`` and ``chunks`` tables in the database referenced by
DATABASE_URL. Safe to run repeatedly — ``create_all`` only creates tables
that do not already exist.

Usage:
    python scripts/init_db.py

Exit codes:
    0  — schema is present
    1  — failed (database unreachable or misconfigured)
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def main() -> int:
    print("=" * 52)
    print("  Automated Literature Review — Database Schema Init")
    print("=" * 52)

    from backend.config.database import _get_engine
    from backend.models import Base

    try:
        engine = _get_engine()
    except ValueError as exc:
        print(f"\n  FAIL  {exc}")
        return 1

    try:
        # Verify connectivity before touching anything.
        connected = asyncio.run(check_connection(engine))
        if not connected:
            print("\n  FAIL  Could not reach the database.")
            return 1

        Base.metadata.create_all(engine)
        tables = sorted(Base.metadata.tables.keys())
        print("\n  Schema initialised. Tables present:")
        for table in tables:
            print(f"    - {table}")
        print("\n  Result: OK")
        return 0
    except Exception as exc:
        print(f"\n  FAIL  {type(exc).__name__}: {exc}")
        return 1


async def check_connection(engine) -> bool:
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        print(f"    (database check: {type(exc).__name__}: {exc})")
        return False


if __name__ == "__main__":
    sys.exit(main())
