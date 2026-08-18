"""
Unit tests for POST /papers/upload using an overridden in-memory SQLite DB.

Covers the full request path: success ingestion, non-PDF rejection, malformed
PDF rejection and file-size enforcement — all without PostgreSQL.
"""
import pytest
from sqlalchemy import func, select

from backend.models import Chunk, Paper


@pytest.mark.unit
class TestUploadEndpoint:
    def test_upload_valid_pdf_returns_201(self, upload_client, sample_pdf_bytes):
        response = upload_client.post(
            "/papers/upload", files={"file": ("sample.pdf", sample_pdf_bytes, "application/pdf")}
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "processed"
        assert body["filename"] == "sample.pdf"
        assert body["page_count"] == 4
        assert body["chunks_created"] > 0
        assert isinstance(body["paper_id"], int)

    def test_upload_creates_paper_and_chunk_rows(self, upload_client, db_session, sample_pdf_bytes):
        response = upload_client.post(
            "/papers/upload", files={"file": ("p.pdf", sample_pdf_bytes, "application/pdf")}
        )
        assert response.status_code == 201
        paper_id = response.json()["paper_id"]

        paper = db_session.get(Paper, paper_id)
        assert paper is not None
        assert paper.filename == "p.pdf"
        assert paper.page_count == 4
        assert paper.storage_path is not None

        raw_chunks = db_session.scalar(
            select(func.count())
            .select_from(Chunk)
            .where(Chunk.paper_id == paper_id)
        )
        assert raw_chunks == response.json()["chunks_created"]

    def test_upload_rejects_non_pdf_extension(self, upload_client, sample_pdf_bytes):
        response = upload_client.post(
            "/papers/upload", files={"file": ("notes.txt", b"hello there", "text/plain")}
        )
        assert response.status_code == 400
        assert "PDF" in response.json()["detail"]

    def test_upload_rejects_non_pdf_content(self, upload_client, invalid_pdf_bytes):
        response = upload_client.post(
            "/papers/upload", files={"file": ("fake.pdf", invalid_pdf_bytes, "application/pdf")}
        )
        assert response.status_code == 422

    def test_upload_rejects_malformed_pdf(self, upload_client, corrupted_pdf_bytes):
        response = upload_client.post(
            "/papers/upload", files={"file": ("corrupt.pdf", corrupted_pdf_bytes, "application/pdf")}
        )
        assert response.status_code == 422

    def test_upload_rejects_empty_file(self, upload_client):
        response = upload_client.post(
            "/papers/upload", files={"file": ("empty.pdf", b"", "application/pdf")}
        )
        assert response.status_code == 400

    def test_upload_rejects_oversized_file(self, upload_client, monkeypatch, sample_pdf_bytes):
        # Patch the function the endpoint actually references (imported into
        # backend.api.papers at module load time).
        monkeypatch.setattr("backend.api.papers.get_max_upload_bytes", lambda: 10)
        response = upload_client.post(
            "/papers/upload",
            files={"file": ("big.pdf", b"test_pdf_bytes_that_are_longer_than_ten", "application/pdf")},
        )
        assert response.status_code == 400
        assert "maximum allowed size" in response.json()["detail"]

    def test_path_traversal_filename_is_sanitised(self, upload_client, sample_pdf_bytes):
        response = upload_client.post(
            "/papers/upload",
            files={"file": ("../../../evil.pdf", sample_pdf_bytes, "application/pdf")},
        )
        assert response.status_code == 201, response.text
        assert response.json()["filename"] == "evil.pdf"
