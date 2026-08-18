"""
Pydantic domain models for the document-ingestion pipeline.

These models describe the *structured, page-aware* representation of a parsed
research paper and its deterministic text chunks. They are the typed contract
between the parser, the chunker, the storage service and the API layer.

Phase 1 uses only deterministic, non-LLM processing.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ParsedPage(BaseModel):
    """A single page of extracted text from a PDF, with its page number."""

    model_config = ConfigDict(extra="ignore")

    page_number: int = Field(ge=1, description="1-based page number in the PDF")
    text: str = Field(default="", description="Raw extracted text for the page")


class PDFMetadata(BaseModel):
    """
    Metadata read directly from the PDF file itself.

    Phase 1 only uses metadata that is already present in the file. Values are
    NOT inferred or completed with an LLM — missing values stay as None/empty.
    """

    model_config = ConfigDict(extra="ignore")

    title: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    doi: Optional[str] = None
    source_url: Optional[str] = None


class ParsedPaper(BaseModel):
    """Structured output of the PDF parser."""

    model_config = ConfigDict(extra="ignore")

    filename: str = Field(description="Original uploaded filename")
    page_count: int = Field(ge=0, description="Total number of pages in the PDF")
    pages: List[ParsedPage] = Field(
        default_factory=list,
        description="Extracted pages, ordered by page_number",
    )
    metadata: PDFMetadata = Field(default_factory=PDFMetadata)
    storage_path: Optional[str] = Field(
        default=None,
        description="Absolute or relative location of the stored PDF",
    )
    extracted_at: datetime = Field(default_factory=_utcnow)

    def page_numbers(self) -> List[int]:
        """Return the ordered page numbers, preserving the source order."""
        return [p.page_number for p in self.pages]


class PaperChunk(BaseModel):
    """A single deterministic text chunk tied to a paper and a page."""

    model_config = ConfigDict(extra="ignore")

    paper_id: Optional[int] = Field(
        default=None, description="Set when the chunk is persisted to the DB"
    )
    page_number: int = Field(ge=1, description="Source page number (traceability)")
    section: str = Field(default="Unknown", description="Detected section label")
    chunk_index: int = Field(ge=0, description="Zero-based global chunk order")
    text: str = Field(description="Chunk text; concatenation preserves the source")
