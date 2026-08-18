"""
Unit tests for upload-file validation (filename sanitisation, PDF-only rule).
"""
import pytest

from ingestion.service import safe_filename


@pytest.mark.unit
class TestFilenameSanitisation:
    def test_plain_pdf_accepted(self):
        assert safe_filename("mypaper.pdf") == "mypaper.pdf"

    def test_path_traversal_stripped(self):
        # Directory components are dropped entirely — only the basename survives.
        assert safe_filename("../../etc/passwd") == "passwd.pdf"

    def test_windows_path_stripped(self):
        assert safe_filename("C:\\Users\\evil\\paper.pdf") == "paper.pdf"

    def test_non_pdf_gets_pdf_extension(self):
        assert safe_filename("scan.txt") == "scan.txt.pdf"

    def test_nested_pdf_strips_directories(self):
        assert safe_filename("/some/long/path/deep/paper.pdf") == "paper.pdf"

    def test_unsafe_characters_replaced(self):
        assert safe_filename("my paper(1).pdf") == "my_paper_1_.pdf"

    def test_empty_name_falls_back(self):
        assert safe_filename("")
        assert safe_filename("....")
        assert safe_filename("/")
