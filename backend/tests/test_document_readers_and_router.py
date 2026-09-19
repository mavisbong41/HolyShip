from __future__ import annotations

from pathlib import Path
import pytest

from backend.app.documents.models import DocumentFormat, DocumentType
from backend.app.documents.readers.composite import CompositeDocumentReader
from backend.app.documents.readers.docx_reader import DocxReader
from backend.app.documents.readers.ocr_reader import OcrReader
from backend.app.documents.readers.pdf_text import PdfTextReader
from backend.app.documents.readers.plain_text import PlainTextReader
from backend.app.documents.readers.vision_reader import VisionReader, VisionResolver
from backend.app.documents.readers.xlsx_reader import XlsxReader
from backend.app.documents.router import DocumentRouter
from backend.app.ingestion.models import AttachmentMetadata

BUNDLE_ATTACHMENTS = Path("sdoc-hackathon-bundle/attachments")


# ---------------------------------------------------------------------------
# Reader Tests
# ---------------------------------------------------------------------------

def test_plain_text_reader_reads_txt_file():
    path = BUNDLE_ATTACHMENTS / "email_001_SI.txt"
    reader = PlainTextReader()
    doc = reader.read(path.read_bytes(), path.name, str(path))

    assert doc.format == DocumentFormat.PLAIN_TEXT
    assert doc.reader_used == "PlainTextReader"
    assert doc.extraction_status == "EXTRACTED"
    assert "SHIPPING INSTRUCTION" in doc.raw_text
    assert "APRIL FAR EAST" in doc.raw_text
    assert len(doc.pages) == 1


def test_pdf_text_reader_reads_text_pdf():
    path = BUNDLE_ATTACHMENTS / "email_059_SI.pdf"
    reader = PdfTextReader()
    doc = reader.read(path.read_bytes(), path.name, str(path))

    assert doc.format == DocumentFormat.PDF_TEXT
    assert doc.reader_used == "PdfTextReader"
    assert doc.extraction_status == "EXTRACTED"
    assert len(doc.pages) == 1
    assert "BILL OF LADING INSTRUCTION" in doc.raw_text or "APRIL FINE PAPER" in doc.raw_text


def test_docx_reader_reads_paragraphs_and_tables():
    path = BUNDLE_ATTACHMENTS / "email_055_BL.docx"
    reader = DocxReader()
    doc = reader.read(path.read_bytes(), path.name, str(path))

    assert doc.format == DocumentFormat.DOCX
    assert doc.reader_used == "DocxReader"
    assert doc.extraction_status == "EXTRACTED"
    assert len(doc.tables) >= 1
    assert "APRIL FINE PAPER" in doc.raw_text


def test_xlsx_reader_reads_sheet_rows_into_tables():
    path = BUNDLE_ATTACHMENTS / "email_005_SI.xlsx"
    reader = XlsxReader()
    doc = reader.read(path.read_bytes(), path.name, str(path))

    assert doc.format == DocumentFormat.XLSX
    assert doc.reader_used == "XlsxReader"
    assert doc.extraction_status == "EXTRACTED"
    assert len(doc.tables) >= 1
    assert "ASIA PACIFIC PAPERBOARD" in doc.raw_text


def test_ocr_reader_handles_missing_tesseract_gracefully():
    reader = OcrReader(tesseract_cmd=None)
    assert not reader.is_available()

    doc = reader.read(b"dummy image bytes", "test_scan.png")
    assert doc.extraction_status == "FAILED"
    assert "not installed" in doc.error_message


def test_composite_reader_routes_by_extension_and_extracts_native():
    composite = CompositeDocumentReader()

    # TXT
    txt_path = BUNDLE_ATTACHMENTS / "email_001_BL.txt"
    doc_txt = composite.read(txt_path.read_bytes(), txt_path.name)
    assert doc_txt.reader_used == "PlainTextReader"
    assert "BILL OF LADING (DRAFT)" in doc_txt.raw_text

    # DOCX
    docx_path = BUNDLE_ATTACHMENTS / "email_055_BL.docx"
    doc_docx = composite.read(docx_path.read_bytes(), docx_path.name)
    assert doc_docx.reader_used == "DocxReader"

    # XLSX
    xlsx_path = BUNDLE_ATTACHMENTS / "email_005_SI.xlsx"
    doc_xlsx = composite.read(xlsx_path.read_bytes(), xlsx_path.name)
    assert doc_xlsx.reader_used == "XlsxReader"


def test_composite_reader_handles_corrupted_pdf_without_crashing():
    composite = CompositeDocumentReader()
    path = BUNDLE_ATTACHMENTS / "email_511_BL.pdf"
    doc = composite.read(path.read_bytes(), path.name)

    # Should not raise an uncaught exception, but gracefully report failure or unreadable
    assert doc.extraction_status in ("FAILED", "UNREADABLE", "PARTIAL")


# ---------------------------------------------------------------------------
# Router Tests
# ---------------------------------------------------------------------------

def test_router_identifies_si_and_bl():
    router = DocumentRouter()
    atts = [
        AttachmentMetadata(filename="email_001_SI.txt", source_reference="email_001_SI.txt"),
        AttachmentMetadata(filename="email_001_BL.txt", source_reference="email_001_BL.txt"),
    ]

    result = router.route_attachments(atts)

    assert not result.human_review_required
    assert result.si_attachment is not None
    assert result.si_attachment.document_type == DocumentType.SI
    assert result.bl_attachment is not None
    assert result.bl_attachment.document_type == DocumentType.DRAFT_BL


def test_router_handles_missing_si():
    router = DocumentRouter()
    atts = [
        AttachmentMetadata(filename="email_001_BL.txt", source_reference="email_001_BL.txt"),
    ]

    result = router.route_attachments(atts)

    assert result.human_review_required
    assert result.human_review_reason_code == "MISSING_SI"
    assert result.si_attachment is None
    assert result.bl_attachment is not None


def test_router_handles_missing_bl():
    router = DocumentRouter()
    atts = [
        AttachmentMetadata(filename="email_001_SI.txt", source_reference="email_001_SI.txt"),
    ]

    result = router.route_attachments(atts)

    assert result.human_review_required
    assert result.human_review_reason_code == "MISSING_BL"
    assert result.bl_attachment is None
    assert result.si_attachment is not None


def test_router_handles_both_missing():
    router = DocumentRouter()
    atts = [
        AttachmentMetadata(filename="commercial_invoice.pdf", source_reference="commercial_invoice.pdf"),
    ]

    result = router.route_attachments(atts)

    assert result.human_review_required
    assert result.human_review_reason_code in ("MISSING_SI", "DOCUMENT_TYPE_UNCERTAIN")


def test_router_handles_multiple_si_candidates():
    router = DocumentRouter()
    atts = [
        AttachmentMetadata(filename="doc1_SI.txt", source_reference="doc1_SI.txt"),
        AttachmentMetadata(filename="doc2_SI.pdf", source_reference="doc2_SI.pdf"),
        AttachmentMetadata(filename="doc3_BL.txt", source_reference="doc3_BL.txt"),
    ]

    result = router.route_attachments(atts)

    assert result.human_review_required
    assert result.human_review_reason_code == "MULTIPLE_SI_CANDIDATES"


def test_router_handles_multiple_bl_candidates():
    router = DocumentRouter()
    atts = [
        AttachmentMetadata(filename="doc1_SI.txt", source_reference="doc1_SI.txt"),
        AttachmentMetadata(filename="doc2_BL.pdf", source_reference="doc2_BL.pdf"),
        AttachmentMetadata(filename="doc3_BL.docx", source_reference="doc3_BL.docx"),
    ]

    result = router.route_attachments(atts)

    assert result.human_review_required
    assert result.human_review_reason_code == "MULTIPLE_BL_CANDIDATES"
