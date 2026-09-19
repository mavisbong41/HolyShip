from __future__ import annotations

from pathlib import Path

from backend.app.documents.models import DocumentFormat, UnifiedDocument
from backend.app.documents.readers.base import DocumentReader
from backend.app.documents.readers.docx_reader import DocxReader
from backend.app.documents.readers.ocr_reader import OcrReader
from backend.app.documents.readers.pdf_text import PdfTextReader
from backend.app.documents.readers.plain_text import PlainTextReader
from backend.app.documents.readers.vision_reader import VisionReader, VisionResolver
from backend.app.documents.readers.xlsx_reader import XlsxReader


class CompositeDocumentReader(DocumentReader):
    """
    Orchestrates the document reading pipeline:
    Native Reader -> OCR Fallback -> Vision Fallback -> UnifiedDocument.
    """

    def __init__(
        self,
        plain_reader: PlainTextReader | None = None,
        pdf_reader: PdfTextReader | None = None,
        docx_reader: DocxReader | None = None,
        xlsx_reader: XlsxReader | None = None,
        ocr_reader: OcrReader | None = None,
        vision_reader: VisionReader | None = None,
    ):
        self.plain_reader = plain_reader or PlainTextReader()
        self.pdf_reader = pdf_reader or PdfTextReader()
        self.docx_reader = docx_reader or DocxReader()
        self.xlsx_reader = xlsx_reader or XlsxReader()
        self.ocr_reader = ocr_reader or OcrReader()
        self.vision_reader = vision_reader or VisionReader()

    def detect_format(self, filename: str) -> DocumentFormat:
        ext = Path(filename).suffix.lower()
        if ext in (".txt", ".text", ".csv", ""):
            return DocumentFormat.PLAIN_TEXT
        if ext == ".pdf":
            return DocumentFormat.PDF_TEXT
        if ext == ".docx":
            return DocumentFormat.DOCX
        if ext in (".xlsx", ".xlsm", ".xltx"):
            return DocumentFormat.XLSX
        if ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
            return DocumentFormat.IMAGE
        return DocumentFormat.UNKNOWN

    def can_read(self, filename: str, content_bytes: bytes | None = None) -> bool:
        return self.detect_format(filename) != DocumentFormat.UNKNOWN

    def read(self, content_bytes: bytes, filename: str, source_reference: str = "") -> UnifiedDocument:
        ext = Path(filename).suffix.lower()

        # 1. Plain text
        if ext in (".txt", ".text", ".csv", ""):
            return self.plain_reader.read(content_bytes, filename, source_reference)

        # 2. DOCX
        if ext == ".docx":
            result = self.docx_reader.read(content_bytes, filename, source_reference)
            if result.extraction_status == "EXTRACTED" and result.raw_text.strip():
                return result
            # Try vision if docx corrupted
            return self._fallback_vision(content_bytes, filename, source_reference, result)

        # 3. XLSX
        if ext in (".xlsx", ".xlsm", ".xltx"):
            result = self.xlsx_reader.read(content_bytes, filename, source_reference)
            if result.extraction_status == "EXTRACTED" and result.raw_text.strip():
                return result
            return self._fallback_vision(content_bytes, filename, source_reference, result)

        # 4. PDF (Native -> OCR -> Vision)
        if ext == ".pdf":
            native_result = self.pdf_reader.read(content_bytes, filename, source_reference)
            if native_result.extraction_status == "EXTRACTED" and len(native_result.raw_text.strip()) >= 30:
                return native_result

            # Native extraction gave empty text or failed -> OCR fallback
            ocr_result = self.ocr_reader.read(content_bytes, filename, source_reference)
            if ocr_result.extraction_status == "EXTRACTED" and ocr_result.raw_text.strip():
                return ocr_result

            # OCR gave no text or failed -> Vision fallback
            return self._fallback_vision(content_bytes, filename, source_reference, ocr_result)

        # 5. Image (OCR -> Vision)
        if ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
            ocr_result = self.ocr_reader.read(content_bytes, filename, source_reference)
            if ocr_result.extraction_status == "EXTRACTED" and ocr_result.raw_text.strip():
                return ocr_result
            return self._fallback_vision(content_bytes, filename, source_reference, ocr_result)

        # Unsupported format
        return UnifiedDocument(
            raw_text="",
            pages=[],
            tables=[],
            format=DocumentFormat.UNKNOWN,
            reader_used="None",
            filename=filename,
            source_reference=source_reference,
            extraction_quality=0.0,
            extraction_status="FAILED",
            error_message=f"Unsupported document format: {ext}",
        )

    def _fallback_vision(
        self,
        content_bytes: bytes,
        filename: str,
        source_reference: str,
        last_result: UnifiedDocument,
    ) -> UnifiedDocument:
        vision_res = self.vision_reader.read(content_bytes, filename, source_reference)
        if vision_res.extraction_status == "EXTRACTED" and vision_res.raw_text.strip():
            return vision_res

        # Preserve the failure from the last reader if vision couldn't resolve
        return UnifiedDocument(
            raw_text=last_result.raw_text,
            pages=last_result.pages,
            tables=last_result.tables,
            format=last_result.format,
            reader_used=last_result.reader_used,
            filename=filename,
            source_reference=source_reference,
            extraction_quality=0.0,
            extraction_status=last_result.extraction_status if last_result.extraction_status != "EXTRACTED" else "UNREADABLE",
            error_message=last_result.error_message or "All extraction methods (native, OCR, vision) failed or yielded unreadable text",
            metadata=last_result.metadata,
        )
