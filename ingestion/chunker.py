"""
Deterministic section detection and text chunking.

Phase 1 deliberately avoids any LLM or semantic processing. Section detection
is a simple, deterministic heading matcher, and chunking splits text on
character boundaries (preferring whitespace). This keeps output reproducible
and easy to test. The section detector can be swapped for a smarter
implementation in a later phase without changing the chunk contract.

Limitations of the Phase 1 section detector:
  * headings must appear as their own line(s) of text
  * two-column layouts / PDFs without embedded text are not handled
  * section names that do not match a known label become "Unknown"
  * no understanding of section hierarchy or numbering
"""
from __future__ import annotations

import re
from typing import List, Optional

from ingestion.models import PaperChunk, ParsedPaper

UNKNOWN_SECTION = "Unknown"

# ---------------------------------------------------------------------------
# Known section labels and their heading patterns (deterministic, no LLM).
# Each pattern matches a heading line such as:
#   "Abstract", "1. Introduction", "2 Related Work", "Methodology:"
# The optional leading number prefix accepts common numbered layouts.
# ---------------------------------------------------------------------------

_SECTION_PATTERNS: dict[str, str] = {
    "Abstract": r"^\s*(?:[0-9]+[.)]?\s*)?abstract\s*$",
    "Introduction": r"^\s*(?:[0-9]+[.)]?\s*)?introduction\s*$",
    "Related Work": r"^\s*(?:[0-9]+[.)]?\s*)?(?:related\s+work|background)\s*$",
    "Methodology": r"^\s*(?:[0-9]+[.)]?\s*)?(?:methodology|approach)\s*$",
    "Methods": r"^\s*(?:[0-9]+[.)]?\s*)?methods?\s*$",
    "Dataset": r"^\s*(?:[0-9]+[.)]?\s*)?(?:dataset|data)\s*$",
    "Experiments": r"^\s*(?:[0-9]+[.)]?\s*)?experiments?\s*$",
    "Results": r"^\s*(?:[0-9]+[.)]?\s*)?results?\s*$",
    "Discussion": r"^\s*(?:[0-9]+[.)]?\s*)?discussion\s*$",
    "Conclusion": r"^\s*(?:[0-9]+[.)]?\s*)?conclusions?\s*$",
    "References": r"^\s*(?:[0-9]+[.)]?\s*)?references?\s*$",
    "Future Work": r"^\s*(?:[0-9]+[.)]?\s*)?future\s+work\s*$",
    "Limitations": r"^\s*(?:[0-9]+[.)]?\s*)?limitations?\s*$",
    "Acknowledgements": r"^\s*(?:[0-9]+[.)]?\s*)?acknowledg(e|i)ments?\s*$",
}

_COMPILED: dict[str, re.Pattern] = {
    label: re.compile(pattern, re.IGNORECASE) for label, pattern in _SECTION_PATTERNS.items()
}

# Order matters: "Methods" would otherwise match "Methodology" first.
_DETECTION_ORDER: List[str] = [
    "Abstract",
    "Introduction",
    "Related Work",
    "Methodology",
    "Methods",
    "Dataset",
    "Experiments",
    "Results",
    "Discussion",
    "Conclusion",
    "References",
    "Future Work",
    "Limitations",
    "Acknowledgements",
]


def detect_section(line: str) -> Optional[str]:
    """
    Return the section label for a heading line, or None if the line does not
    look like a known section heading.

    ``None`` (rather than UNKNOWN_SECTION) lets the caller distinguish
    "this is body text" from "this is an unclassified heading".
    """
    stripped = line.strip()
    if not stripped:
        return None
    for label in _DETECTION_ORDER:
        if _COMPILED[label].match(stripped):
            return label
    return None


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def split_text(text: str, chunk_size: int) -> List[str]:
    """
    Split ``text`` into pieces of at most ``chunk_size`` characters.

    Splits are aligned to the next whitespace boundary when possible, but no
    characters are ever dropped — concatenating the pieces reproduces the
    input exactly.
    """
    if not text:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")

    chunks: List[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        if end < length:
            # Extend to include the next whitespace boundary instead of
            # cutting mid-word.
            while end < length and not text[end].isspace():
                end += 1
            if end >= length:
                end = length
            else:
                end += 1  # include the boundary whitespace itself
        chunks.append(text[start:end])
        start = end
    return chunks


class SectionChunker:
    """
    Deterministic chunker that walks each page line-by-line, tracks the
    current section via heading detection, and emits fixed-size chunks.

    Rules:
      * chunks never span pages (each chunk keeps a single page_number)
      * a chunk carries the section that was active when it started
      * ``chunk_index`` is a zero-based, strictly increasing global counter
      * no source text is dropped
    """

    def __init__(self, chunk_size: int = 1000) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be a positive integer")
        self.chunk_size = chunk_size

    def chunk_paper(self, paper: ParsedPaper, paper_id: Optional[int] = None) -> List[PaperChunk]:
        """Chunk an entire parsed paper into an ordered list of PaperChunk."""
        chunks: List[PaperChunk] = []
        index = 0
        for page in paper.pages:
            index = self._chunk_page(page.text, page.page_number, paper_id, index, chunks)
        return chunks

    def _chunk_page(
        self,
        text: str,
        page_number: int,
        paper_id: Optional[int],
        start_index: int,
        out: List[PaperChunk],
    ) -> int:
        if not text.strip():
            return start_index  # blank page → no chunks

        index = start_index
        section = UNKNOWN_SECTION
        buffer: List[str] = []
        buffer_size = 0

        def flush() -> None:
            nonlocal buffer, buffer_size, index
            for piece in split_text("\n".join(buffer), self.chunk_size):
                out.append(
                    PaperChunk(
                        paper_id=paper_id,
                        page_number=page_number,
                        section=section,
                        chunk_index=index,
                        text=piece,
                    )
                )
                index += 1
            buffer = []
            buffer_size = 0

        for line in text.splitlines():
            heading = detect_section(line)
            if heading is not None and buffer:
                flush()  # close the previous section before switching
            if heading is not None:
                section = heading
            buffer.append(line)
            buffer_size += len(line) + 1  # +1 for the joining newline

            if buffer_size >= self.chunk_size:
                flush()

        if buffer:
            flush()

        return index
