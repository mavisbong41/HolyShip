from __future__ import annotations

import io
import shutil
from pathlib import Path

from backend.app.documents.models import DocumentFormat, DocumentPage, UnifiedDocument
from backend.app.documents.readers.base import DocumentReader


class OcrReader(DocumentReader):
    """
    Pluggable OCR Reader for scanned PDFs and images.
    Prefers tesseract when installed; gracefully flags when OCR backend is unavailable.
    """

    def __init__(self, tesseract_cmd: str | None = None):
        self.tesseract_cmd = tesseract_cmd or shutil.which("tesseract")
        self._cache: dict[str, UnifiedDocument] = {}

    def is_available(self) -> bool:
        return self.tesseract_cmd is not None

    def can_read(self, filename: str, content_bytes: bytes | None = None) -> bool:
        ext = Path(filename).suffix.lower()
        return ext in (".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp")

    def read(self, content_bytes: bytes, filename: str, source_reference: str = "") -> UnifiedDocument:
        cache_key = f"{source_reference}:{len(content_bytes)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        ext = Path(filename).suffix.lower()
        if ext == ".pdf":
            result = self._read_pdf_ocr(content_bytes, filename, source_reference)
        else:
            result = self._read_image_ocr(content_bytes, filename, source_reference)

        self._cache[cache_key] = result
        return result

    def _read_image_ocr(self, content_bytes: bytes, filename: str, source_reference: str) -> UnifiedDocument:
        if not self.is_available():
            return UnifiedDocument(
                raw_text="",
                pages=[],
                tables=[],
                format=DocumentFormat.IMAGE,
                reader_used="OcrReader",
                filename=filename,
                source_reference=source_reference,
                extraction_quality=0.0,
                extraction_status="FAILED",
                error_message="OCR engine (tesseract) is not installed or not found in PATH",
                metadata={"ocr_available": False},
            )

        try:
            import pytesseract
            from PIL import Image

            img = Image.open(io.BytesIO(content_bytes))
            text = pytesseract.image_to_string(img)
            page = DocumentPage(page_number=1, text=text, width=float(img.width), height=float(img.height))
            return UnifiedDocument(
                raw_text=text,
                pages=[page],
                tables=[],
                format=DocumentFormat.IMAGE,
                reader_used="OcrReader",
                filename=filename,
                source_reference=source_reference,
                extraction_quality=0.85 if text.strip() else 0.0,
                extraction_status="EXTRACTED" if text.strip() else "UNREADABLE",
                metadata={"ocr_engine": "pytesseract"},
            )
        except Exception as exc:
            return UnifiedDocument(
                raw_text="",
                pages=[],
                tables=[],
                format=DocumentFormat.IMAGE,
                reader_used="OcrReader",
                filename=filename,
                source_reference=source_reference,
                extraction_quality=0.0,
                extraction_status="FAILED",
                error_message=f"OCR error: {exc}",
                metadata={"error": str(exc)},
            )

    def _read_pdf_ocr(self, content_bytes: bytes, filename: str, source_reference: str) -> UnifiedDocument:
        if not self.is_available():
            return UnifiedDocument(
                raw_text="",
                pages=[],
                tables=[],
                format=DocumentFormat.SCANNED_PDF,
                reader_used="OcrReader",
                filename=filename,
                source_reference=source_reference,
                extraction_quality=0.0,
                extraction_status="FAILED",
                error_message="OCR engine (tesseract) is not installed or not found in PATH",
                metadata={"ocr_available": False},
            )

        try:
            import pypdf
            import pytesseract
            from PIL import Image

            reader = pypdf.PdfReader(io.BytesIO(content_bytes))
            pages: list[DocumentPage] = []
            full_texts: list[str] = []

            for p_idx, page in enumerate(reader.pages, start=1):
                page_text_parts: list[str] = []
                for img_obj in getattr(page, "images", []):
                    img = Image.open(io.BytesIO(img_obj.data))
                    ocr_text = pytesseract.image_to_string(img)
                    if ocr_text.strip():
                        page_text_parts.append(ocr_text.strip())

                page_text = "\n".join(page_text_parts)
                full_texts.append(page_text)
                pages.append(DocumentPage(page_number=p_idx, text=page_text))

            combined = "\n\n".join(full_texts)
            return UnifiedDocument(
                raw_text=combined,
                pages=pages,
                tables=[],
                format=DocumentFormat.SCANNED_PDF,
                reader_used="OcrReader",
                filename=filename,
                source_reference=source_reference,
                extraction_quality=0.85 if combined.strip() else 0.0,
                extraction_status="EXTRACTED" if combined.strip() else "UNREADABLE",
                metadata={"ocr_pages": len(pages)},
            )
        except Exception as exc:
            return UnifiedDocument(
                raw_text="",
                pages=[],
                tables=[],
                format=DocumentFormat.SCANNED_PDF,
                reader_used="OcrReader",
                filename=filename,
                source_reference=source_reference,
                extraction_quality=0.0,
                extraction_status="FAILED",
                error_message=f"PDF OCR error: {exc}",
                metadata={"error": str(exc)},
            )
