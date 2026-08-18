"""
Ingestion service — orchestrates the Phase 1 pipeline:

    PDF bytes → safe storage → parse → chunk → persist (papers + chunks)

Kept intentionally synchronous. Later phases may introduce a job queue; the
service interface (``IngestionService.ingest``) is the seam for that change.
"""
from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

from backend.config.settings import get_raw_storage_dir
from backend.models import Chunk, Paper
from ingestion.chunker import SectionChunker
from ingestion.models import PaperChunk, ParsedPaper
from ingestion.parser import PDFParserError, parse_pdf

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 1000

# Characters allowed in a stored filename. Anything else is replaced.
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]")


class IngestionError(Exception):
    """Application-level error raised when the ingestion pipeline fails."""

    def __init__(self, message: str, reason: str = "INGESTION_FAILED") -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


def safe_filename(name: str) -> str:
    """
    Normalise an uploaded filename.

    Drops any directory components (path-traversal guard) and replaces
    characters that are not safe for a plain filename. Both POSIX and Windows
    separators are treated as path separators.
    """
    name = name.replace("\\", "/")
    name = Path(name).name or "document.pdf"
    name = _SAFE_FILENAME_RE.sub("_", name).strip(" ._")
    if not name:
        name = "document.pdf"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


def store_pdf(content: bytes, original_filename: str) -> Path:
    """
    Persist the raw PDF under the configured raw-storage directory using a
    generated, collision-safe name that preserves the original extension.
    """
    base = safe_filename(original_filename)
    storage_name = f"{uuid.uuid4().hex[:8]}_{base}"
    raw_dir = get_raw_storage_dir()
    target = raw_dir / storage_name
    try:
        target.write_bytes(content)
    except OSError as exc:
        logger.error(f"Could not store PDF {target}: {exc}")
        raise IngestionError(
            f"Could not store the uploaded file: {exc}",
            reason="STORAGE_FAILED",
        ) from exc
    logger.info(f"Stored uploaded PDF at {target}")
    return target


def parse_pdf_file(path: Path, filename: Optional[str] = None) -> ParsedPaper:
    """Parse a stored PDF file into a ParsedPaper.

    ``filename`` overrides the parsed filename so the DB stores the original
    upload name rather than the generated storage name.
    """
    try:
        return parse_pdf(path, filename=filename)
    except PDFParserError as exc:
        logger.error(f"PDF parse failed for {path}: {exc.message}")
        raise
    except Exception as exc:
        logger.error(f"Unexpected parse failure for {path}: {exc}")
        raise IngestionError(
            f"Unexpected failure while parsing the PDF: {exc}",
            reason="PDF_EXTRACTION_FAILED",
        ) from exc


def chunk_parsed_paper(
    paper: ParsedPaper, chunk_size: int = DEFAULT_CHUNK_SIZE
) -> List[PaperChunk]:
    """Split a parsed paper into deterministic, page-aware chunks."""
    return SectionChunker(chunk_size=chunk_size).chunk_paper(paper)


def persist_paper(
    db, paper: ParsedPaper, chunks: List[PaperChunk]
) -> Tuple[Paper, int]:
    """
    Create the papers row and all chunk rows in one transaction.

    Returns the created Paper and the number of chunks inserted.
    """
    metadata = paper.metadata
    title = (metadata.title or paper.filename).replace("\x00", "")
    authors = [a.replace("\x00", "") for a in metadata.authors] if metadata.authors else None
    
    model = Paper(
        title=title,
        authors=authors,
        year=metadata.year,
        doi=metadata.doi,
        source_url=metadata.source_url,
        filename=paper.filename,
        storage_path=paper.storage_path,
        page_count=paper.page_count,
        extracted_at=paper.extracted_at,
    )
    try:
        db.add(model)
        db.flush()  # assign model.id so chunks can reference it
        for chunk in chunks:
            chunk.paper_id = model.id
        db.add_all(
            [
                Chunk(
                    paper_id=model.id,
                    page_number=c.page_number,
                    section=c.section,
                    chunk_index=c.chunk_index,
                    text=c.text.replace("\x00", ""),
                )
                for c in chunks
            ]
        )
        db.commit()
        db.refresh(model)
    except Exception as exc:
        db.rollback()
        logger.error(f"Could not persist paper to the database: {exc}")
        raise IngestionError(
            "Could not persist the paper to the database.",
            reason="DATABASE_FAILURE",
        ) from exc
    logger.info(
        f"Persisted paper id={model.id} with {len(chunks)} chunk(s)"
    )
    return model, len(chunks)


class IngestionService:
    """End-to-end ingestion: bytes in → papers + chunks rows out."""

    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
        self.chunk_size = chunk_size

    def ingest(
        self, db, content: bytes, original_filename: str
    ) -> Tuple[Paper, ParsedPaper, int]:
        """
        Run the full Phase 1 pipeline for one uploaded PDF.

        Returns (paper_row, parsed_paper, chunk_count).
        """
        safe = safe_filename(original_filename)
        storage_path = store_pdf(content, safe)
        parsed = parse_pdf_file(storage_path, filename=safe)
        parsed.storage_path = str(storage_path)
        chunks = chunk_parsed_paper(parsed, chunk_size=self.chunk_size)
        try:
            paper, chunk_count = persist_paper(db, parsed, chunks)
        except Exception:
            # Best-effort: remove the stored raw file so a failed ingestion
            # does not leave an orphaned PDF behind.
            try:
                storage_path.unlink(missing_ok=True)
            except OSError:
                logger.warning(f"Could not remove orphaned upload {storage_path}")
            raise
        return paper, parsed, chunk_count
