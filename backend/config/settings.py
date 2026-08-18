"""
Runtime configuration for the Phase 1 ingestion pipeline.

Values are read from environment variables at call time so that tests can
override them with monkeypatching and the application keeps its lazy,
configuration-light behavior from Phase 0.
"""
from __future__ import annotations

import os
from pathlib import Path

# Default storage location for uploaded research PDFs (git-ignored).
DEFAULT_RAW_DIR = "data/raw"

# Default maximum upload size in megabytes.
DEFAULT_MAX_UPLOAD_MB = 50


def get_raw_storage_dir() -> Path:
    """Return the configured directory for uploaded PDFs, creating it if needed."""
    configured = os.getenv("PDF_STORAGE_DIR", DEFAULT_RAW_DIR)
    path = Path(configured)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_max_upload_bytes() -> int:
    """Return the maximum allowed upload size in bytes."""
    raw = os.getenv("MAX_UPLOAD_MB", str(DEFAULT_MAX_UPLOAD_MB))
    try:
        mb = int(raw)
    except ValueError:
        mb = DEFAULT_MAX_UPLOAD_MB
    return max(1, mb) * 1024 * 1024
