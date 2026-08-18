"""
Shared fixtures for the Phase 1 unit tests.

All PDFs used here are generated programmatically with PyMuPDF at test time —
no research papers are committed to the repository.
"""
from __future__ import annotations

import pytest
import fitz


# ---------------------------------------------------------------------------
# Programmatic PDF helpers
# ---------------------------------------------------------------------------

def _build_pdf(pages: list[list[str]], metadata: dict | None = None) -> bytes:
    """
    Build a small PDF from a list of pages; each page is a list of text lines.
    Each line is placed on its own line so extracted text keeps line breaks.
    """
    doc = fitz.open()
    for lines in pages:
        page = doc.new_page()
        y = 72.0
        for line in lines:
            page.insert_text((72, y), line)
            y += 16.0
    if metadata:
        doc.set_metadata(metadata)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture(scope="session")
def sample_pdf_bytes() -> bytes:
    """A 3-page PDF with recognizable section headings and one blank page."""
    return _build_pdf(
        [
            [
                "A Sample Research Paper",
                "Abstract",
                "This paper proposes a deterministic ingestion method.",
                "Introduction",
                "Research on automated literature review is important.",
            ],
            [
                "Methodology",
                "We use a simple, reproducible approach.",
                "Results",
                "The results show the pipeline works as expected.",
            ],
            [],  # blank page
            [
                "Conclusion",
                "We conclude that page-aware chunking is viable.",
            ],
        ]
    )


@pytest.fixture(scope="session")
def sample_pdf_with_metadata() -> bytes:
    """A 1-page PDF carrying title/author/creation-date metadata."""
    return _build_pdf(
        [["A Metadata Carrying Paper", "Abstract", "Some text here."]],
        metadata={
            "title": "A Metadata Carrying Paper",
            "author": "Alice Smith; Bob Jones",
            "creationDate": "D:20240115103000+00'00'",
        },
    )


@pytest.fixture(scope="session")
def blank_pdf_bytes() -> bytes:
    """A single blank PDF page (no text at all)."""
    return _build_pdf([[]])


@pytest.fixture(scope="session")
def invalid_pdf_bytes() -> bytes:
    """Bytes that are not a PDF at all."""
    return b"This is definitely not a PDF file."


@pytest.fixture(scope="session")
def corrupted_pdf_bytes(sample_pdf_bytes) -> bytes:
    """A valid PDF truncated in the middle — must be rejected by the parser."""
    return sample_pdf_bytes[: len(sample_pdf_bytes) // 2]


@pytest.fixture(scope="session")
def sample_pdf_path(sample_pdf_bytes, tmp_path_factory) -> str:
    """Write the sample PDF to a temp file and return its path."""
    path = tmp_path_factory.mktemp("pdfs") / "sample.pdf"
    path.write_bytes(sample_pdf_bytes)
    return str(path)


# ---------------------------------------------------------------------------
# SQLite-backed database session (no PostgreSQL required for these tests)
# ---------------------------------------------------------------------------

@pytest.fixture()
def sqlite_engine(tmp_path):
    """
    A file-backed SQLite engine with the Phase 1 schema and FK enforcement.

    File-backed (not ``:memory:``) so that the TestClient worker thread and
    the test thread share the same database.
    """
    from sqlalchemy import create_engine, event
    from backend.models import Base

    db_path = tmp_path / "unit_test.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    event.listen(
        engine,
        "connect",
        lambda dbapi_conn, _: dbapi_conn.execute("PRAGMA foreign_keys=ON"),
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(sqlite_engine):
    """A SQLAlchemy session bound to the in-memory SQLite engine."""
    from sqlalchemy.orm import Session

    with Session(sqlite_engine) as session:
        yield session


# ---------------------------------------------------------------------------
# TestClient for the upload endpoint with the DB dependency overridden
# ---------------------------------------------------------------------------

@pytest.fixture()
def upload_client(db_session, sample_pdf_bytes, monkeypatch, tmp_path):
    """A TestClient whose get_db dependency serves the SQLite session."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from fastapi.testclient import TestClient
    from backend.config import database as db_config
    from backend.main import app

    monkeypatch.setenv("PDF_STORAGE_DIR", str(tmp_path / "raw"))

    def override_get_db():
        yield db_session

    app.dependency_overrides[db_config.get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
