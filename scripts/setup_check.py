"""
scripts/setup_check.py
======================
Developer environment verification script.

Checks that every prerequisite for running the project locally is satisfied.
This script is READ-ONLY — it performs no destructive actions.

Usage:
    python scripts/setup_check.py

Exit codes:
    0  — all checks passed
    1  — one or more checks failed
"""

import importlib
import os
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
PASS = "\033[32m OK \033[0m"
FAIL = "\033[31mFAIL\033[0m"
WARN = "\033[33mWARN\033[0m"
SKIP = "\033[90mSKIP\033[0m"

_failures: list[str] = []


def _row(label: str, status: str, detail: str = "") -> None:
    detail_str = f"  ({detail})" if detail else ""
    print(f"  {label:<30} [{status}]{detail_str}")


def _fail(label: str, detail: str = "") -> None:
    _failures.append(label)
    _row(label, FAIL, detail)


def _ok(label: str, detail: str = "") -> None:
    _row(label, PASS, detail)


def _warn(label: str, detail: str = "") -> None:
    _row(label, WARN, detail)


def _skip(label: str, detail: str = "") -> None:
    _row(label, SKIP, detail)


# ---------------------------------------------------------------------------
# Check 1 — Python version
# ---------------------------------------------------------------------------

def check_python() -> None:
    print("\n[1] Python")
    v = sys.version_info
    version_str = f"{v.major}.{v.minor}.{v.micro}"
    if v.major == 3 and v.minor >= 11:
        _ok("Python version", version_str)
    elif v.major == 3 and v.minor == 10:
        _warn("Python version", f"{version_str} — 3.11+ preferred")
    else:
        _fail("Python version", f"{version_str} — requires Python 3.11+")


# ---------------------------------------------------------------------------
# Check 2 — Required packages
# ---------------------------------------------------------------------------

REQUIRED_PACKAGES = [
    ("fastapi",           "fastapi"),
    ("uvicorn",           "uvicorn"),
    ("sqlalchemy",        "sqlalchemy"),
    ("psycopg",           "psycopg"),
    ("dotenv",            "python-dotenv"),
    ("pydantic",          "pydantic"),
    ("pydantic_settings", "pydantic-settings"),
    ("pytest",            "pytest"),
    ("httpx",             "httpx"),
    ("fitz",              "pymupdf"),  # PyMuPDF — Phase 1 PDF processing
]


def check_packages() -> None:
    print("\n[2] Python Dependencies")
    for import_name, pip_name in REQUIRED_PACKAGES:
        try:
            importlib.import_module(import_name)
            _ok(pip_name)
        except ImportError:
            _fail(pip_name, f"run: pip install {pip_name}")


# ---------------------------------------------------------------------------
# Check 3 — Environment configuration
# ---------------------------------------------------------------------------

REQUIRED_ENV_VARS = [
    "DATABASE_URL",
    "APP_ENV",
    "BACKEND_PORT",
]

OPTIONAL_ENV_VARS = [
    "FRONTEND_URL",
    "FRONTEND_PORT",
]


def check_environment() -> None:
    print("\n[3] Environment Configuration")

    env_file = ROOT / ".env"
    env_example = ROOT / ".env.example"

    if env_file.exists():
        _ok(".env file", "found")
    else:
        _fail(".env file", f"not found — copy {env_example.name} to .env and fill in values")

    # Load .env so we can check its contents
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
    except ImportError:
        pass  # already flagged in package check

    for var in REQUIRED_ENV_VARS:
        val = os.getenv(var, "")
        if val:
            # Mask passwords / URLs that may contain credentials
            display = val if "password" not in var.lower() and "url" not in var.lower() else "***"
            _ok(var, display)
        else:
            _fail(var, "not set in .env")

    for var in OPTIONAL_ENV_VARS:
        val = os.getenv(var, "")
        if val:
            _ok(var, val)
        else:
            _warn(var, "not set (optional)")


# ---------------------------------------------------------------------------
# Check 4 — Project directory structure
# ---------------------------------------------------------------------------

REQUIRED_DIRS = [
    "backend",
    "backend/api",
    "backend/config",
    "frontend",
    "data/raw",
    "data/processed",
    "data/test_corpus",
    "agents",
    "ingestion",
    "evaluation",
    "scripts",
    "tests/unit",
    "tests/integration",
    "docs",
]

REQUIRED_FILES = [
    ".env.example",
    ".gitignore",
    "requirements.txt",
    "pytest.ini",
    "backend/main.py",
    "backend/api/health.py",
    "backend/config/database.py",
    "frontend/package.json",
    "frontend/src/app/page.tsx",
]


def check_structure() -> None:
    print("\n[4] Project Structure")
    for d in REQUIRED_DIRS:
        path = ROOT / d
        if path.is_dir():
            _ok(d)
        else:
            _fail(d, "directory missing")

    for f in REQUIRED_FILES:
        path = ROOT / f
        if path.is_file():
            _ok(f)
        else:
            _fail(f, "file missing")


# ---------------------------------------------------------------------------
# Check 5 — PostgreSQL reachability
# ---------------------------------------------------------------------------

def check_postgres() -> None:
    print("\n[5] PostgreSQL")
    try:
        import asyncio
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")

        # Import here so missing DATABASE_URL raises clearly
        sys.path.insert(0, str(ROOT))
        from backend.config.database import check_database_connection  # type: ignore

        connected = asyncio.run(check_database_connection())
        if connected:
            _ok("PostgreSQL connection", "SELECT 1 succeeded")
        else:
            _fail("PostgreSQL connection", "could not reach database")
    except ValueError as e:
        _fail("PostgreSQL connection", str(e))
    except Exception as e:
        _fail("PostgreSQL connection", f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Check 5b — Phase 1 schema presence (best-effort, non-fatal)
# ---------------------------------------------------------------------------

def check_schema() -> None:
    print("\n[5b] Phase 1 Database Schema (papers / chunks)")
    try:
        import asyncio
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")

        sys.path.insert(0, str(ROOT))
        from backend.config.database import check_database_connection
        from backend.config.database import _get_engine  # type: ignore

        connected = asyncio.run(check_database_connection())
        if not connected:
            _skip("schema check", "PostgreSQL not reachable — run scripts/init_db.py when it is")
            return

        from sqlalchemy import inspect
        engine = _get_engine()
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        required = {"papers", "chunks"}
        if required.issubset(tables):
            _ok("schema", "papers + chunks tables present")
        else:
            _fail("schema", f"missing tables: {sorted(required - tables)} — run: python scripts/init_db.py")
    except Exception as e:
        _skip("schema check", f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Check 6 — Node.js / npm (optional — required for frontend)
# ---------------------------------------------------------------------------

def check_node() -> None:
    print("\n[6] Node.js / npm (frontend)")
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            _ok("node", result.stdout.strip())
        else:
            _warn("node", "not found — frontend cannot be started")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        _warn("node", "not found — frontend cannot be started")

    try:
        # Try npm via .cmd on Windows, plain npm elsewhere
        npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
        result = subprocess.run(
            [npm_cmd, "--version"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            _ok("npm", result.stdout.strip())
        else:
            _warn("npm", "not found")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        _warn("npm", "not found")

    node_modules = ROOT / "frontend" / "node_modules"
    if node_modules.is_dir():
        _ok("frontend/node_modules", "installed")
    else:
        _warn("frontend/node_modules", "run: cd frontend && npm install")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 52)
    print("  Automated Literature Review — Setup Check")
    print("=" * 52)

    check_python()
    check_packages()
    check_environment()
    check_structure()
    check_postgres()
    check_schema()
    check_node()

    print("\n" + "=" * 52)
    if _failures:
        print(f"  Result: {len(_failures)} check(s) FAILED\n")
        for f in _failures:
            print(f"    ✗ {f}")
        print()
        return 1
    else:
        print("  Result: All checks passed")
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main())
