"""
Unit tests for the Phase 1 database schema and the persistence service.

These use an in-memory SQLite engine with the same SQLAlchemy models so they
run without PostgreSQL. Real-PostgreSQL coverage lives in the integration
tests.
"""
import pytest
from sqlalchemy import func, select

from backend.models import Chunk, Paper
from ingestion.chunker import SectionChunker
from ingestion.models import ParsedPage, ParsedPaper
from ingestion.service import IngestionService, persist_paper


def _parsed_paper(pages: list[tuple[int, str]], title="Saved Paper") -> ParsedPaper:
    return ParsedPaper(
        filename="saved.pdf",
        page_count=len(pages),
        pages=[ParsedPage(page_number=n, text=t) for n, t in pages],
        storage_path="/tmp/raw/abc123_saved.pdf",
    ).model_copy(update={"metadata": _meta(title)})


def _meta(title: str):
    from ingestion.models import PDFMetadata

    return PDFMetadata(title=title, authors=["Alice Smith"], year=2023)


@pytest.mark.unit
class TestPaperModel:
    def test_paper_insertion(self, db_session):
        paper = Paper(
            title="The Paper",
            authors=["A", "B"],
            year=2024,
            filename="the-paper.pdf",
            storage_path="/tmp/raw/x_the-paper.pdf",
            page_count=5,
        )
        db_session.add(paper)
        db_session.commit()
        db_session.refresh(paper)

        assert paper.id is not None
        assert paper.title == "The Paper"
        assert paper.page_count == 5
        assert paper.created_at is not None
        assert paper.updated_at is not None

    def test_paper_defaults_are_nullable(self, db_session):
        paper = Paper(title="Minimal", filename="minimal.pdf")
        db_session.add(paper)
        db_session.commit()
        db_session.refresh(paper)
        assert paper.authors is None
        assert paper.doi is None
        assert paper.year is None


@pytest.mark.unit
class TestPaperChunkRelationship:
    def test_chunks_attach_to_paper(self, db_session):
        paper = Paper(title="P", filename="p.pdf", page_count=1)
        db_session.add(paper)
        db_session.flush()

        db_session.add_all(
            [
                Chunk(
                    paper_id=paper.id,
                    page_number=1,
                    section="Abstract",
                    chunk_index=0,
                    text="chunk zero",
                ),
                Chunk(
                    paper_id=paper.id,
                    page_number=1,
                    section="Introduction",
                    chunk_index=1,
                    text="chunk one",
                ),
            ]
        )
        db_session.commit()

        count = db_session.scalar(
            select(func.count()).select_from(Chunk).where(Chunk.paper_id == paper.id)
        )
        assert count == 2

        # Relationship navigation paper -> chunks
        db_session.refresh(paper)
        assert [c.chunk_index for c in paper.chunks] == [0, 1]

    def test_cascade_delete_removes_chunks(self, db_session):
        paper = Paper(title="P", filename="p.pdf", page_count=1)
        db_session.add(paper)
        db_session.flush()
        db_session.add(
            Chunk(paper_id=paper.id, page_number=1, section="X", chunk_index=0, text="t")
        )
        db_session.commit()

        db_session.delete(paper)
        db_session.commit()

        remaining = db_session.scalar(select(func.count()).select_from(Chunk))
        assert remaining == 0


@pytest.mark.unit
class TestPersistService:
    def test_persist_paper_creates_rows(self, db_session):
        parsed = _parsed_paper([(1, "Abstract\nHello abstract."), (2, "Results\nWow.")])
        chunks = SectionChunker(chunk_size=100).chunk_paper(parsed)

        paper, chunk_count = persist_paper(db_session, parsed, chunks)

        assert chunk_count == len(chunks)
        assert paper.id is not None
        assert paper.filename == "saved.pdf"
        assert paper.title == "Saved Paper"

        rows = db_session.scalars(
            select(Chunk).where(Chunk.paper_id == paper.id).order_by(Chunk.chunk_index)
        ).all()
        assert len(rows) == chunk_count
        assert [r.section for r in rows] == [c.section for c in chunks]
        assert all(r.page_number >= 1 for r in rows)

    def test_ingest_service_full_pipeline(self, db_session, sample_pdf_bytes, monkeypatch, tmp_path):
        monkeypatch.setenv("PDF_STORAGE_DIR", str(tmp_path / "raw"))
        service = IngestionService(chunk_size=80)
        paper, parsed, chunk_count = service.ingest(
            db_session, sample_pdf_bytes, "../uploaded/sample.pdf"
        )

        assert paper.id is not None
        assert paper.page_count == 4
        assert chunk_count > 0
        assert parsed.page_count == 4

        rows = db_session.scalars(
            select(Chunk).where(Chunk.paper_id == paper.id)
        ).all()
        assert len(rows) == chunk_count
        # The safe filename drops any directory components (path-traversal guard).
        assert paper.filename == "sample.pdf"
