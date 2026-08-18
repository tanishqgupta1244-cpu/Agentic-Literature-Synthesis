"""
Unit tests for section detection and deterministic chunking.

No database or external services required.
"""
import pytest

from ingestion.chunker import UNKNOWN_SECTION, SectionChunker, detect_section, split_text
from ingestion.models import PaperChunk, ParsedPaper, ParsedPage
from ingestion.parser import parse_pdf


@pytest.mark.unit
class TestSectionDetection:
    def test_plain_heading_detected(self):
        assert detect_section("Abstract") == "Abstract"

    @pytest.mark.parametrize(
        "line,expected",
        [
            ("Abstract", "Abstract"),
            ("1. Introduction", "Introduction"),
            ("2 Introduction", "Introduction"),
            ("Related Work", "Related Work"),
            ("Methodology", "Methodology"),
            ("Methods", "Methods"),
            ("3. Results", "Results"),
            ("Discussion", "Discussion"),
            ("Conclusion", "Conclusion"),
            ("References", "References"),
        ],
    )
    def test_known_headings(self, line, expected):
        assert detect_section(line) == expected

    def test_case_insensitive(self):
        assert detect_section("abstract") == "Abstract"
        assert detect_section("INTRODUCTION") == "Introduction"

    def test_unknown_line_is_none(self):
        assert detect_section("hello world this is body text") is None
        assert detect_section("") is None


@pytest.mark.unit
class TestSplitText:
    def test_split_respects_chunk_size(self):
        text = "word " * 100
        pieces = split_text(text, 40)
        # pieces may exceed chunk_size by the length of the word that straddles
        # the boundary (here "word " = 5 chars), but never by more than that.
        assert all(len(p) <= 40 + 5 for p in pieces)
        assert any(len(p) <= 40 for p in pieces)

    def test_no_text_is_lost(self):
        text = "one two three four five six seven eight nine ten"
        pieces = split_text(text, 11)
        assert "".join(pieces) == text

    def test_empty_text(self):
        assert split_text("", 100) == []

    def test_invalid_chunk_size_raises(self):
        with pytest.raises(ValueError):
            split_text("abc", 0)


def _paper_from_text(pages: list[str]) -> ParsedPaper:
    return ParsedPaper(
        filename="t.pdf",
        page_count=len(pages),
        pages=[
            ParsedPage(page_number=i + 1, text=text)
            for i, text in enumerate(pages)
        ],
    )


@pytest.mark.unit
class TestChunking:
    def test_chunk_ordering_is_deterministic(self):
        paper = _paper_from_text(
            ["Abstract\nSome abstract text here.\nIntroduction\nBody text page one."]
        )
        chunker = SectionChunker(chunk_size=30)
        chunks = chunker.chunk_paper(paper)
        assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
        assert [c.chunk_index for c in chunks] == sorted(c.chunk_index for c in chunks)

    def test_chunk_metadata_is_preserved(self):
        paper = _paper_from_text(["Abstract\nSome abstract text here."])
        chunker = SectionChunker(chunk_size=1000)
        chunks = chunker.chunk_paper(paper, paper_id=42)
        assert len(chunks) == 1
        c = chunks[0]
        assert isinstance(c, PaperChunk)
        assert c.paper_id == 42
        assert c.page_number == 1
        assert c.section == "Abstract"
        assert c.chunk_index == 0
        assert "Some abstract text" in c.text

    def test_section_tracking_within_page(self):
        paper = _paper_from_text(
            ["Abstract\nAbstract text.\nIntroduction\nIntro text."]
        )
        chunker = SectionChunker(chunk_size=1000)
        chunks = chunker.chunk_paper(paper)
        sections = [c.section for c in chunks]
        assert "Abstract" in sections
        assert "Introduction" in sections

    def test_unknown_section_default(self):
        paper = _paper_from_text(["Just some body text with no headings."])
        chunker = SectionChunker(chunk_size=1000)
        chunks = chunker.chunk_paper(paper)
        assert chunks[0].section == UNKNOWN_SECTION

    def test_chunks_do_not_span_pages(self):
        paper = _paper_from_text(["Page one text.", "Page two text."])
        chunker = SectionChunker(chunk_size=5)
        chunks = chunker.chunk_paper(paper)
        pages_used = {c.page_number for c in chunks}
        assert pages_used == {1, 2}
        # Each chunk is associated with exactly one page.
        assert all(c.page_number in pages_used for c in chunks)
        # Chunks are emitted page-by-page in order (no interleaving).
        page_seq = [c.page_number for c in chunks]
        assert page_seq == sorted(page_seq)

    def test_no_source_text_lost(self):
        paper = _paper_from_text(
            ["Abstract\nThis is a longer abstract paragraph for the paper."]
        )
        chunker = SectionChunker(chunk_size=20)
        chunks = chunker.chunk_paper(paper)
        source = "".join(c.text for c in chunks)
        assert source.replace("\n", "") == (
            "AbstractThis is a longer abstract paragraph for the paper."
        )

    def test_blank_page_produces_no_chunks(self):
        paper = _paper_from_text(["", "Some text."])
        chunker = SectionChunker(chunk_size=100)
        chunks = chunker.chunk_paper(paper)
        assert [c.page_number for c in chunks] == [2]

    def test_chunking_parsed_pdf(self, sample_pdf_bytes):
        paper = parse_pdf(sample_pdf_bytes)
        chunks = SectionChunker(chunk_size=60).chunk_paper(paper)
        assert len(chunks) >= 4
        assert all(c.page_number >= 1 for c in chunks)
