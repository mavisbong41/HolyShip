from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.documents.materialization import PreExtractionOutcome
from backend.app.documents.models import DocumentFormat, DocumentType, UnifiedDocument
from backend.app.documents.readers.composite import CompositeDocumentReader
from backend.app.documents.role_validation import DocumentRoleValidator, RoleValidationOutcome


BUNDLE_ATTACHMENTS = Path("data/bundle/attachments")


def _document(text: str, filename: str) -> UnifiedDocument:
    return UnifiedDocument(
        raw_text=text,
        format=DocumentFormat.PLAIN_TEXT,
        reader_used="PlainTextReader",
        filename=filename,
    )


@pytest.mark.req("DOC-04")
@pytest.mark.req("DOC-05")
@pytest.mark.req("DOC-06")
def test_native_readers_cover_txt_pdf_docx_and_preserve_xlsx_numeric_cells():
    reader = CompositeDocumentReader()

    txt = BUNDLE_ATTACHMENTS / "email_001_SI.txt"
    pdf = BUNDLE_ATTACHMENTS / "email_059_BL.pdf"
    docx = BUNDLE_ATTACHMENTS / "email_055_BL.docx"
    xlsx = BUNDLE_ATTACHMENTS / "email_005_SI.xlsx"

    txt_doc = reader.read(txt.read_bytes(), txt.name, str(txt))
    pdf_doc = reader.read(pdf.read_bytes(), pdf.name, str(pdf))
    docx_doc = reader.read(docx.read_bytes(), docx.name, str(docx))
    xlsx_doc = reader.read(xlsx.read_bytes(), xlsx.name, str(xlsx))

    assert (txt_doc.format, txt_doc.reader_used) == (DocumentFormat.PLAIN_TEXT, "PlainTextReader")
    assert (pdf_doc.format, pdf_doc.reader_used) == (DocumentFormat.PDF_TEXT, "PdfTextReader")
    assert docx_doc.format == DocumentFormat.DOCX and docx_doc.tables
    assert xlsx_doc.format == DocumentFormat.XLSX and xlsx_doc.tables
    assert any(
        isinstance(cell, (int, float)) and not isinstance(cell, bool)
        for table in xlsx_doc.tables
        for row in table.rows
        for cell in row
    )


@pytest.mark.req("DOC-03")
@pytest.mark.req("DOC-07a")
def test_image_and_image_only_pdf_route_directly_to_ocr_path():
    class SpyReader:
        def __init__(self, result):
            self.result = result
            self.calls = 0

        def read(self, *_args, **_kwargs):
            self.calls += 1
            return self.result

    def result(fmt, reader_used, status, text=""):
        return UnifiedDocument(
            raw_text=text,
            format=fmt,
            reader_used=reader_used,
            extraction_status=status,
        )

    plain = SpyReader(result(DocumentFormat.PLAIN_TEXT, "plain", "EXTRACTED", "wrong"))
    docx = SpyReader(result(DocumentFormat.DOCX, "docx", "EXTRACTED", "wrong"))
    xlsx = SpyReader(result(DocumentFormat.XLSX, "xlsx", "EXTRACTED", "wrong"))
    pdf = SpyReader(result(DocumentFormat.SCANNED_PDF, "pdf", "PARTIAL"))
    ocr = SpyReader(result(DocumentFormat.SCANNED_PDF, "ocr", "UNREADABLE"))
    vision = SpyReader(result(DocumentFormat.SCANNED_PDF, "vision", "FAILED"))
    reader = CompositeDocumentReader(
        plain_reader=plain,
        pdf_reader=pdf,
        docx_reader=docx,
        xlsx_reader=xlsx,
        ocr_reader=ocr,
        vision_reader=vision,
    )

    pdf_result = reader.read(b"scanned", "scan.pdf")
    assert (pdf.calls, ocr.calls, vision.calls) == (1, 1, 1)
    assert (plain.calls, docx.calls, xlsx.calls) == (0, 0, 0)
    assert pdf_result.extraction_status == "UNREADABLE"

    image_result = reader.read(b"image", "scan.png")
    assert pdf.calls == 1
    assert ocr.calls == 2
    assert image_result.extraction_status == "UNREADABLE"


@pytest.mark.req("DOC-08")
def test_empty_corrupt_and_unsupported_inputs_have_defined_outcomes():
    reader = CompositeDocumentReader()

    empty = reader.read(b"", "empty.txt")
    corrupt_path = BUNDLE_ATTACHMENTS / "email_511_BL.pdf"
    corrupt = reader.read(corrupt_path.read_bytes(), corrupt_path.name)
    unsupported = reader.read(b"not a document", "payload.bin")

    assert empty.extraction_status == "UNREADABLE"
    assert corrupt.extraction_status == "FAILED"
    assert unsupported.extraction_status == "FAILED"
    assert {
        PreExtractionOutcome.CORRUPTED_ATTACHMENT,
        PreExtractionOutcome.UNSUPPORTED_ATTACHMENT,
    }.issubset(set(PreExtractionOutcome))


@pytest.mark.req("DOC-10")
@pytest.mark.req("DOC-11")
@pytest.mark.req("DOC-13")
def test_content_evidence_overrides_filename_and_inconclusive_content_is_not_guessed():
    validator = DocumentRoleValidator()

    si_under_bl_name = validator.validate(
        _document("SHIPPING INSTRUCTION\nShipper: A\nConsignee: B", "misleading_BL.txt")
    )
    wrong_under_bl_name = validator.validate(
        _document("COMMERCIAL INVOICE\nInvoice Number: 42\nAmount: 500", "looks_like_BL.txt")
    )
    inconclusive_si_name = validator.validate(
        _document("Reference 42\nPlease process this document.", "looks_like_SI.txt")
    )

    assert si_under_bl_name.document_type == DocumentType.SI
    assert si_under_bl_name.outcome == RoleValidationOutcome.VALID
    assert wrong_under_bl_name.document_type == DocumentType.OTHER
    assert wrong_under_bl_name.outcome == RoleValidationOutcome.WRONG_DOCUMENT_TYPE
    assert "COMMERCIAL INVOICE" in wrong_under_bl_name.markers
    assert inconclusive_si_name.document_type == DocumentType.UNKNOWN
    assert inconclusive_si_name.outcome == RoleValidationOutcome.INCONCLUSIVE


@pytest.mark.req("DOC-06")
@pytest.mark.req("DOC-10")
def test_xlsx_cell_headers_prove_roles_without_using_filenames():
    reader = CompositeDocumentReader()
    validator = DocumentRoleValidator()
    si_path = BUNDLE_ATTACHMENTS / "email_005_SI.xlsx"
    bl_path = BUNDLE_ATTACHMENTS / "email_005_BL.xlsx"

    si = reader.read(si_path.read_bytes(), "misleading_BL.xlsx")
    bl = reader.read(bl_path.read_bytes(), "misleading_SI.xlsx")

    assert validator.validate(si).document_type == DocumentType.SI
    assert validator.validate(bl).document_type == DocumentType.DRAFT_BL
