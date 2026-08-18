"""
Integration tests — full Phase 1 pipeline against a real PostgreSQL instance.

    PDF → upload → parser → papers row → chunks rows

Requires a reachable PostgreSQL (DATABASE_URL in .env). The whole module is
skipped automatically when PostgreSQL is unreachable, so this file never breaks
the unit-test suite.

Run with:
    pytest tests/integration/ -m integration -v
"""
import pytest
import fitz

pytestmark = pytest.mark.integration


def _build_sample_pdf() -> bytes:
    """Generate a tiny 2-page PDF programmatically — no research papers needed."""
    doc = fitz.open()
    for lines in (
        ["Abstract", "This is the abstract of the integration paper."],
        ["Introduction", "Integration test body text goes here."],
    ):
        page = doc.new_page()
        y = 72.0
        for line in lines:
            page.insert_text((72, y), line)
            y += 16.0
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture(scope="module")
def postgres_engine():
    """Real engine + schema; skips the whole module when PostgreSQL is down."""
    from sqlalchemy import text
    from backend.config.database import _get_engine
    from backend.models import Base

    try:
        engine = _get_engine()
    except ValueError:
        pytest.skip("DATABASE_URL is not configured")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("PostgreSQL is not reachable — skipping integration tests")

    Base.metadata.create_all(engine)
    yield engine


@pytest.fixture()
def db_session(postgres_engine):
    from sqlalchemy.orm import Session

    with Session(postgres_engine) as session:
        yield session
        session.rollback()


class TestIngestionPipeline:
    def test_full_pipeline_creates_rows(self, db_session, tmp_path, monkeypatch):
        from sqlalchemy import select

        from backend.models import Chunk, Paper
        from ingestion.service import IngestionService

        monkeypatch.setenv("PDF_STORAGE_DIR", str(tmp_path / "raw"))
        pdf_bytes = _build_sample_pdf()

        service = IngestionService(chunk_size=200)
        paper, parsed, chunk_count = service.ingest(
            db_session, pdf_bytes, "integration-paper.pdf"
        )

        try:
            assert paper.id is not None
            assert parsed.page_count == 2
            assert chunk_count >= 2

            stored = db_session.get(Paper, paper.id)
            assert stored is not None
            assert stored.filename == "integration-paper.pdf"
            assert stored.page_count == 2

            rows = db_session.scalars(
                select(Chunk)
                .where(Chunk.paper_id == paper.id)
                .order_by(Chunk.chunk_index)
            ).all()
            assert len(rows) == chunk_count

            # Paper → chunks relationship works through the ORM.
            db_session.refresh(stored)
            assert len(stored.chunks) == chunk_count

            # Every chunk retains paper_id, page_number, section, chunk_index, text.
            for row in rows:
                assert row.paper_id == paper.id
                assert row.page_number in (1, 2)
                assert row.section in ("Abstract", "Introduction", "Unknown")
                assert isinstance(row.chunk_index, int)
                assert row.text

            # chunk ordering is deterministic and unique per paper
            indices = [r.chunk_index for r in rows]
            assert indices == sorted(indices)
            assert len(set(indices)) == len(indices)
        finally:
            db_session.delete(paper)
            db_session.commit()

    def test_foreign_key_cascade(self, db_session, tmp_path, monkeypatch):
        from sqlalchemy import func, select

        from backend.models import Chunk
        from ingestion.service import IngestionService

        monkeypatch.setenv("PDF_STORAGE_DIR", str(tmp_path / "raw"))
        service = IngestionService(chunk_size=200)
        paper, _, chunk_count = service.ingest(
            db_session, _build_sample_pdf(), "cascade-paper.pdf"
        )

        total_before = db_session.scalar(select(func.count()).select_from(Chunk))

        db_session.delete(paper)
        db_session.commit()

        total_after = db_session.scalar(select(func.count()).select_from(Chunk))
        assert total_before >= chunk_count
        assert total_after == total_before - chunk_count
