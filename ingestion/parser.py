"""
PDF parsing service.

Provides a clean parser abstraction over the underlying PDF library so that
the extraction engine can be replaced later (e.g. GROBID or Marker) without
touching the rest of the pipeline.

Phase 1 ships a single implementation backed by PyMuPDF (``import fitz``).

Output contract: :class:`ingestion.models.ParsedPaper` — page numbers are
always preserved for future citation traceability.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import List, Optional, Protocol, Union

import fitz  # PyMuPDF — pinned in requirements.txt

from ingestion.models import PDFMetadata, ParsedPage, ParsedPaper

logger = logging.getLogger(__name__)

Source = Union[str, Path, bytes]


class PDFParserError(Exception):
    """
    Application-level error raised when a PDF cannot be parsed.

    ``reason`` is a stable, machine-readable category. The full message is
    logged server-side; the API never exposes stack traces.
    """

    def __init__(self, message: str, reason: str = "PDF_PARSE_FAILED") -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


class PDFParser(Protocol):
    """Interface every PDF parser implementation must satisfy."""

    def parse(self, source: Source, filename: Optional[str] = None) -> ParsedPaper:
        """Parse a PDF from a path or raw bytes into a ParsedPaper."""
        ...


class PyMuPDFParser:
    """
    PyMuPDF-based implementation of the PDF parser.

    Responsibilities:
      - open a PDF from a file path or raw bytes
      - report the page count
      - extract text per page, preserving the 1-based page number
      - treat blank pages gracefully (empty string, not an error)
      - read the PDF's own metadata (title, author, creation date)
      - close the document reliably
    """

    def parse(self, source: Source, filename: Optional[str] = None) -> ParsedPaper:
        if filename is None and isinstance(source, (str, Path)):
            filename = Path(source).name

        doc = self._open(source)

        try:
            page_count = doc.page_count
            if page_count <= 0:
                raise PDFParserError(
                    f"PDF has no pages: {filename}", reason="PDF_EMPTY"
                )

            pages = self._extract_pages(doc)
            metadata = self._extract_metadata(doc)

            return ParsedPaper(
                filename=filename or "unnamed.pdf",
                page_count=page_count,
                pages=pages,
                metadata=metadata,
            )
        finally:
            doc.close()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _open(self, source: Source) -> "fitz.Document":
        if not self._has_pdf_header(source):
            raise PDFParserError(
                "The file does not appear to be a PDF.",
                reason="PDF_INVALID",
            )
        # A structurally intact PDF always contains the %%EOF trailer marker.
        # Checking for it catches truncated / cut-off files that PyMuPDF would
        # otherwise silently attempt to repair.
        if not self._has_eof_marker(source):
            raise PDFParserError(
                "The file is truncated or corrupted (missing PDF EOF marker).",
                reason="PDF_CORRUPTED",
            )
        try:
            if isinstance(source, (str, Path)):
                return fitz.open(str(source))
            return fitz.open(stream=bytes(source), filetype="pdf")
        except Exception as exc:
            logger.error(f"Could not open PDF: {exc}")
            raise PDFParserError(
                f"Could not open the file as a valid PDF: {exc}",
                reason="PDF_INVALID",
            ) from exc

    @staticmethod
    def _has_pdf_header(source: Source) -> bool:
        """The %PDF- magic header must appear within the first 1 KiB."""
        try:
            if isinstance(source, (str, Path)):
                with open(source, "rb") as handle:
                    head = handle.read(1024)
            else:
                head = bytes(source)[:1024]
        except (OSError, TypeError):
            return False
        return b"%PDF-" in head

    @staticmethod
    def _has_eof_marker(source: Source) -> bool:
        try:
            if isinstance(source, (str, Path)):
                with open(source, "rb") as handle:
                    # The %%EOF marker always sits near the physical end of an
                    # intact PDF; 64 KiB of tail is more than enough.
                    handle.seek(0, 2)
                    size = handle.tell()
                    handle.seek(max(0, size - 64 * 1024))
                    tail = handle.read()
            else:
                tail = bytes(source)
        except (OSError, TypeError):
            return False
        return b"%%EOF" in tail

    def _extract_pages(self, doc: "fitz.Document") -> List[ParsedPage]:
        pages: List[ParsedPage] = []
        for index in range(doc.page_count):
            page_number = index + 1
            try:
                page = doc.load_page(index)
                text = page.get_text() or ""
            except Exception as exc:
                # Do not swallow silently: log the failure and keep the page
                # with empty text so the overall parse can still complete.
                logger.warning(f"Text extraction failed on page {page_number}: {exc}")
                text = ""
            pages.append(ParsedPage(page_number=page_number, text=text))
        return pages

    def _extract_metadata(self, doc: "fitz.Document") -> PDFMetadata:
        raw = doc.metadata or {}
        title = self._clean(raw.get("title"))
        author_raw = self._clean(raw.get("author"))
        authors = self._split_authors(author_raw)

        return PDFMetadata(
            title=title,
            authors=authors,
            year=self._parse_year(raw.get("creationDate")),
            doi=self._clean(raw.get("doi")),
            source_url=None,
        )

    @staticmethod
    def _clean(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        value = value.strip()
        return value or None

    @staticmethod
    def _split_authors(value: Optional[str]) -> List[str]:
        if not value:
            return []
        parts = re.split(r"[;,]| and ", value)
        authors = [part.strip() for part in parts if part.strip()]
        return authors

    @staticmethod
    def _parse_year(creation_date: Optional[str]) -> Optional[int]:
        """
        Extract the year from a PDF creation date.

        PyMuPDF reports creation dates in the form
        ``D:YYYYMMDDHHMMSS+HH'MM'``. Anything unparseable returns None.
        """
        if not creation_date:
            return None
        match = re.search(r"(\d{4})", creation_date)
        if not match:
            return None
        year = int(match.group(1))
        if 1900 <= year <= 2100:
            return year
        return None


def parse_pdf(source: Source, filename: Optional[str] = None) -> ParsedPaper:
    """Convenience factory: parse a PDF with the default PyMuPDF parser."""
    return PyMuPDFParser().parse(source, filename)
