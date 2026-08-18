"""
scripts/health_check.py
=======================
Full stack health check for the running project.

Unlike setup_check.py (which verifies the environment before startup),
this script checks the LIVE stack — it sends real HTTP requests to the
running backend and frontend.

Usage:
    python scripts/health_check.py

    # Custom URLs:
    BACKEND_URL=http://localhost:8000 python scripts/health_check.py

Exit codes:
    0  — all critical checks passed
    1  — one or more critical checks failed
"""

import asyncio
import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env so values are available even when run outside an activated venv
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass  # If dotenv is missing, env vars must already be set

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# ANSI colours
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
GREY   = "\033[90m"
RESET  = "\033[0m"

_critical_failures: list[str] = []
_warnings: list[str] = []


def _row(label: str, status: str, detail: str = "") -> None:
    pad = 24
    detail_str = f"  {detail}" if detail else ""
    print(f"  {label:<{pad}} {status}{detail_str}{RESET}")


def _ok(label: str, detail: str = "", critical: bool = True) -> None:
    _row(label, f"{GREEN}OK{RESET}", detail)


def _fail(label: str, detail: str = "", critical: bool = True) -> None:
    if critical:
        _critical_failures.append(label)
    else:
        _warnings.append(label)
    colour = RED if critical else YELLOW
    _row(label, f"{colour}{'FAIL' if critical else 'WARN'}{RESET}", detail)


def _skip(label: str, detail: str = "") -> None:
    _row(label, f"{GREY}SKIP{RESET}", detail)


# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------

def check_python() -> None:
    v = sys.version_info
    label = "Python"
    version_str = f"{v.major}.{v.minor}.{v.micro}"
    if v.major == 3 and v.minor >= 11:
        _ok(label, version_str)
    else:
        _fail(label, f"{version_str} — 3.11+ recommended", critical=False)


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

CRITICAL_IMPORTS = ["fastapi", "uvicorn", "sqlalchemy", "psycopg2", "dotenv"]


def check_dependencies() -> None:
    all_ok = True
    for mod in CRITICAL_IMPORTS:
        try:
            importlib.import_module(mod)
        except ImportError:
            all_ok = False
            break
    if all_ok:
        _ok("Dependencies", "all critical packages importable")
    else:
        _fail("Dependencies", "run: pip install -r requirements.txt")


# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------

def check_environment() -> None:
    missing = [v for v in ("DATABASE_URL", "APP_ENV", "BACKEND_PORT") if not os.getenv(v)]
    if not missing:
        _ok("Environment", ".env loaded, required vars set")
    else:
        _fail("Environment", f"missing: {', '.join(missing)}")


# ---------------------------------------------------------------------------
# PostgreSQL (direct connection)
# ---------------------------------------------------------------------------

async def _async_check_postgres() -> tuple[bool, str]:
    try:
        from backend.config.database import check_database_connection
        connected = await check_database_connection()
        return connected, ""
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def check_postgres() -> None:
    connected, detail = asyncio.run(_async_check_postgres())
    if connected:
        _ok("PostgreSQL", "SELECT 1 OK")
    else:
        _fail("PostgreSQL", detail or "connection failed")


# ---------------------------------------------------------------------------
# pgvector
# ---------------------------------------------------------------------------

def check_pgvector() -> None:
    try:
        from backend.config.database import verify_pgvector_support
        available = verify_pgvector_support()
        if available:
            _ok("pgvector", "extension available")
        else:
            # pgvector is optional in Phase 0 — warn, do not fail
            _fail("pgvector", "extension not available — see docs/architecture.md", critical=False)
    except Exception as e:
        _fail("pgvector", str(e), critical=False)


# ---------------------------------------------------------------------------
# Backend HTTP health check
# ---------------------------------------------------------------------------

async def _async_http_get(url: str, timeout: float = 5.0):
    """Minimal async HTTP GET using httpx or urllib fallback."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            return response.status_code, response.json()
    except ImportError:
        # Fallback to urllib (no third-party needed)
        import urllib.request
        import json
        req = urllib.request.urlopen(url, timeout=int(timeout))
        return req.status, json.loads(req.read())


async def _async_check_backend() -> tuple[bool, str]:
    try:
        status, body = await _async_http_get(f"{BACKEND_URL}/health")
        if status == 200 and body.get("status") == "ok":
            return True, f"HTTP {status}"
        return False, f"HTTP {status} — {body}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


async def _async_check_backend_db() -> tuple[bool, str]:
    try:
        status, body = await _async_http_get(f"{BACKEND_URL}/health/db")
        if status == 200 and body.get("database") == "connected":
            return True, f"HTTP {status}"
        return False, f"HTTP {status} — {body}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def check_backend() -> None:
    ok, detail = asyncio.run(_async_check_backend())
    if ok:
        _ok("Backend /health", detail)
    else:
        _fail("Backend /health", detail + f"  →  is the backend running?  uvicorn backend.main:app --reload")

    ok, detail = asyncio.run(_async_check_backend_db())
    if ok:
        _ok("Backend /health/db", detail)
    else:
        _fail("Backend /health/db", detail, critical=False)


# ---------------------------------------------------------------------------
# Frontend HTTP check (optional — only fails as warning)
# ---------------------------------------------------------------------------

async def _async_check_frontend() -> tuple[bool, str]:
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(FRONTEND_URL)
            return response.status_code < 500, f"HTTP {response.status_code}"
    except ImportError:
        import urllib.request
        try:
            req = urllib.request.urlopen(FRONTEND_URL, timeout=5)
            return req.status < 500, f"HTTP {req.status}"
        except Exception as e:
            return False, str(e)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def check_frontend() -> None:
    ok, detail = asyncio.run(_async_check_frontend())
    if ok:
        _ok("Frontend", detail)
    else:
        _fail(
            "Frontend",
            detail + f"  →  run: cd frontend && npm install && npm run dev",
            critical=False,
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print()
    print("=" * 52)
    print("  Automated Literature Review — Health Check")
    print("=" * 52)
    print(f"  Backend  : {BACKEND_URL}")
    print(f"  Frontend : {FRONTEND_URL}")
    print()

    check_python()
    check_dependencies()
    check_environment()

    print()
    check_postgres()
    check_pgvector()

    print()
    check_backend()

    print()
    check_frontend()

    print()
    print("=" * 52)
    if _critical_failures:
        print(f"  {RED}FAILED{RESET}  —  {len(_critical_failures)} critical issue(s):\n")
        for f in _critical_failures:
            print(f"    {RED}✗{RESET}  {f}")
        if _warnings:
            print(f"\n  {YELLOW}WARNINGS{RESET}  —  {len(_warnings)} non-critical:\n")
            for w in _warnings:
                print(f"    {YELLOW}!{RESET}  {w}")
        print()
        return 1
    else:
        if _warnings:
            print(f"  {GREEN}PASSED{RESET}  with {len(_warnings)} warning(s):\n")
            for w in _warnings:
                print(f"    {YELLOW}!{RESET}  {w}")
        else:
            print(f"  {GREEN}All checks passed{RESET}")
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main())
