import io

import pytest
from docx import Document

from utils.document_parser import ExtractionError, extract_text


def test_txt_ok_and_cp1252():
    assert "hello world" in extract_text("a.txt", b"hello world this is a plain text file").text
    assert "caf\u00e9" in extract_text("a.txt", "caf\u00e9 au lait is a nice drink".encode("cp1252")).text


def test_docx_roundtrip():
    d = Document()
    d.add_paragraph("A paragraph about writing and revision that is long enough.")
    buf = io.BytesIO()
    d.save(buf)
    assert "writing and revision" in extract_text("a.docx", buf.getvalue()).text


@pytest.mark.parametrize("name,data", [("a.exe", b"x" * 50), ("a.doc", b"x" * 50), ("a.txt", b""), ("a.pdf", b"not a pdf at all, just text"),
                                       ("a.docx", b"not a zip file at all"), ("a.txt", b"\x00\x01\x02" * 50)])
def test_unsupported_or_invalid_rejected(name, data):
    with pytest.raises(ExtractionError):
        extract_text(name, data)


def test_size_limit():
    with pytest.raises(ExtractionError):
        extract_text("a.txt", b"a" * (2 * 1024 * 1024), max_mb=1)


def test_image_only_pdf_is_rejected_not_saved_empty():
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(200, 200)
    buf = io.BytesIO()
    w.write(buf)
    with pytest.raises(ExtractionError, match="OCR"):
        extract_text("scan.pdf", buf.getvalue())
