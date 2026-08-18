"""
Paper ingestion endpoints.

Phase 1 exposes a single synchronous endpoint:

    POST /papers/upload

It validates the upload, stores the raw PDF, parses it with the ingestion
pipeline, and persists the papers + chunks rows.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.config.database import get_db
from backend.config.settings import get_max_upload_bytes
from ingestion.parser import PDFParserError
from ingestion.service import IngestionError, IngestionService, safe_filename

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/papers", tags=["papers"])

MAX_FILENAME_LENGTH = 255


class UploadResponse(BaseModel):
    paper_id: int
    filename: str
    page_count: int
    chunks_created: int
    status: str = "processed"


def _validate_filename(filename: Optional[str]) -> str:
    if not filename or not filename.strip():
        raise HTTPException(status_code=400, detail="A filename is required.")

    # Reject non-PDF uploads based on the ORIGINAL name, before sanitisation.
    original = filename.replace("\\", "/")
    base = Path(original).name
    if not base.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400, detail="Only PDF files (.pdf) are supported."
        )

    safe = safe_filename(filename)
    if len(safe) > MAX_FILENAME_LENGTH:
        raise HTTPException(status_code=400, detail="Filename is too long.")
    return safe


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=201,
    summary="Upload and ingest a research PDF",
    description=(
        "Accepts a PDF file, validates it, stores it under data/raw, extracts "
        "page-aware text, detects sections, splits it into deterministic "
        "chunks and persists a papers row plus chunk rows."
    ),
)
def upload_paper(
    file: UploadFile = File(..., description="PDF file to ingest"),
    db=Depends(get_db),
):
    safe = _validate_filename(file.filename)

    try:
        content = file.file.read()
    except Exception as exc:
        logger.error(f"Could not read uploaded file: {exc}")
        raise HTTPException(status_code=400, detail="Could not read the uploaded file.")

    max_bytes = get_max_upload_bytes()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds the maximum allowed size of {max_bytes} bytes.",
        )
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    service = IngestionService()
    try:
        paper, parsed, chunk_count = service.ingest(db, content, safe)
    except PDFParserError as exc:
        logger.error(f"Malformed PDF rejected: {exc.message}")
        raise HTTPException(
            status_code=422,
            detail=f"The uploaded file is not a readable PDF: {exc.message}",
        ) from exc
    except IngestionError as exc:
        if exc.reason == "DATABASE_FAILURE":
            logger.error(exc.message)
            raise HTTPException(
                status_code=500,
                detail="Failed to persist the paper to the database.",
            ) from exc
        logger.error(exc.message)
        raise HTTPException(status_code=400, detail=exc.message) from exc
    except Exception as exc:
        logger.exception("Unexpected upload failure")
        raise HTTPException(
            status_code=500, detail="An internal error occurred while processing the file."
        ) from exc

    return UploadResponse(
        paper_id=paper.id,
        filename=safe,
        page_count=parsed.page_count,
        chunks_created=chunk_count,
        status="processed",
    )
