"""
Unit tests for the PyMuPDF-based PDF parser.

No database or external services required.
"""
import pytest

from ingestion.parser import PDFParserError, PyMuPDFParser, parse_pdf


@pytest.mark.unit
class TestValidPdfParsing:
    def test_parses_valid_pdf(self, sample_pdf_bytes):
        paper = parse_pdf(sample_pdf_bytes, filename="sample.pdf")
        assert paper.filename == "sample.pdf"
        assert paper.page_count > 0
        assert len(paper.pages) == paper.page_count

    def test_page_count_extraction(self, sample_pdf_bytes):
        paper = parse_pdf(sample_pdf_bytes)
        assert paper.page_count == 4  # 3 text pages + 1 blank page

    def test_page_numbers_preserved_in_order(self, sample_pdf_bytes):
        paper = parse_pdf(sample_pdf_bytes)
        assert paper.page_numbers() == [1, 2, 3, 4]

    def test_text_is_extracted(self, sample_pdf_bytes):
        paper = parse_pdf(sample_pdf_bytes)
        assert "A Sample Research Paper" in paper.pages[0].text

    def test_parses_from_file_path(self, sample_pdf_path):
        paper = parse_pdf(sample_pdf_path)
        assert paper.page_count == 4
        assert paper.filename == "sample.pdf"

    def test_parser_interface_is_used(self, sample_pdf_bytes):
        parser = PyMuPDFParser()
        paper = parser.parse(sample_pdf_bytes, filename="via_parser.pdf")
        assert paper.filename == "via_parser.pdf"
        assert paper.page_count >= 1


@pytest.mark.unit
class TestEmptyPageHandling:
    def test_blank_page_is_kept_with_empty_text(self, blank_pdf_bytes):
        paper = parse_pdf(blank_pdf_bytes)
        assert paper.page_count == 1
        assert len(paper.pages) == 1
        assert paper.pages[0].page_number == 1
        assert paper.pages[0].text.strip() == ""

    def test_sample_contains_a_blank_page(self, sample_pdf_bytes):
        paper = parse_pdf(sample_pdf_bytes)
        blank = [p for p in paper.pages if p.text.strip() == ""]
        assert len(blank) == 1
        assert blank[0].page_number == 3


@pytest.mark.unit
class TestInvalidPdfHandling:
    def test_non_pdf_bytes_raise(self, invalid_pdf_bytes):
        with pytest.raises(PDFParserError) as excinfo:
            parse_pdf(invalid_pdf_bytes, filename="bad.pdf")
        assert excinfo.value.reason == "PDF_INVALID"

    def test_corrupted_pdf_raises(self, corrupted_pdf_bytes):
        with pytest.raises(PDFParserError) as excinfo:
            parse_pdf(corrupted_pdf_bytes, filename="corrupt.pdf")
        assert excinfo.value.reason == "PDF_CORRUPTED"


@pytest.mark.unit
class TestMetadataExtraction:
    def test_metadata_is_read(self, sample_pdf_with_metadata):
        paper = parse_pdf(sample_pdf_with_metadata)
        assert paper.metadata.title == "A Metadata Carrying Paper"
        assert paper.metadata.authors == ["Alice Smith", "Bob Jones"]
        assert paper.metadata.year == 2024

    def test_metadata_missing_is_nullable(self, sample_pdf_bytes):
        paper = parse_pdf(sample_pdf_bytes)
        # title/authors may be absent on generated PDFs — must not crash.
        assert isinstance(paper.metadata.authors, list)
