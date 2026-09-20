from __future__ import annotations

import io
import hashlib
import shutil
import threading
from pathlib import Path
from typing import Callable

from backend.app.core.reliability import run_with_timeout
from backend.app.documents.models import DocumentFormat, DocumentPage, UnifiedDocument
from backend.app.documents.readers.base import DocumentReader


class OcrSharedState:
    """Process-local OCR budget, cache, and concurrency coordination."""

    def __init__(self, *, max_calls: int, max_concurrent_calls: int) -> None:
        if max_calls < 1 or max_concurrent_calls < 1:
            raise ValueError("OCR budgets must be positive")
        self.max_calls = max_calls
        self.provider_calls = 0
        self.cache_hits = 0
        self.cache: dict[str, UnifiedDocument] = {}
        self.key_locks: dict[str, threading.Lock] = {}
        self.lock = threading.RLock()
        self.slots = threading.BoundedSemaphore(max_concurrent_calls)


class OcrReader(DocumentReader):
    """
    Pluggable OCR Reader for scanned PDFs and images.
    Prefers tesseract when installed; gracefully flags when OCR backend is unavailable.
    """

    def __init__(
        self,
        tesseract_cmd: str | None = None,
        *,
        engine: Callable[[bytes, str], str | list[str]] | None = None,
        auto_detect_tesseract: bool = True,
        timeout_seconds: float = 15.0,
        max_calls: int = 8,
        max_concurrent_calls: int = 2,
        shared_state: OcrSharedState | None = None,
    ):
        if timeout_seconds <= 0 or max_calls < 1 or max_concurrent_calls < 1:
            raise ValueError("OCR timeout and budgets must be positive")
        self.engine = engine
        self.tesseract_cmd = (
            tesseract_cmd
            if tesseract_cmd is not None
            else (shutil.which("tesseract") if auto_detect_tesseract else None)
        )
        self.timeout_seconds = timeout_seconds
        self.shared_state = shared_state or OcrSharedState(
            max_calls=max_calls,
            max_concurrent_calls=max_concurrent_calls,
        )
        self.max_calls = self.shared_state.max_calls
        self._cache = self.shared_state.cache
        self._lock = self.shared_state.lock
        self._slots = self.shared_state.slots

    @property
    def provider_calls(self) -> int:
        return self.shared_state.provider_calls

    @property
    def cache_hits(self) -> int:
        return self.shared_state.cache_hits

    def is_available(self) -> bool:
        return self.engine is not None or self.tesseract_cmd is not None

    def can_read(self, filename: str, content_bytes: bytes | None = None) -> bool:
        ext = Path(filename).suffix.lower()
        return ext in (".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp")

    def read(self, content_bytes: bytes, filename: str, source_reference: str = "") -> UnifiedDocument:
        cache_key = f"{hashlib.sha256(content_bytes).hexdigest()}:{Path(filename).suffix.lower()}"
        with self._lock:
            if cache_key in self._cache:
                self.shared_state.cache_hits += 1
                return self._cache[cache_key]
            key_lock = self.shared_state.key_locks.setdefault(cache_key, threading.Lock())

        with key_lock:
            return self._read_uncached(
                content_bytes,
                filename,
                source_reference,
                cache_key,
            )

    def _read_uncached(
        self,
        content_bytes: bytes,
        filename: str,
        source_reference: str,
        cache_key: str,
    ) -> UnifiedDocument:
        with self._lock:
            if cache_key in self._cache:
                self.shared_state.cache_hits += 1
                return self._cache[cache_key]

        if not self.is_available():
            return self._failure(
                filename,
                source_reference,
                "OCR engine (tesseract) is not installed or not found in PATH",
                reason_code="OCR_BACKEND_UNAVAILABLE",
                ocr_available=False,
            )

        with self._lock:
            if self.shared_state.provider_calls >= self.max_calls:
                return self._failure(
                    filename,
                    source_reference,
                    "OCR call budget exhausted",
                    reason_code="OCR_CALL_BUDGET_EXHAUSTED",
                    fallback_allowed=False,
                )
            self.shared_state.provider_calls += 1

        ext = Path(filename).suffix.lower()
        def invoke() -> UnifiedDocument:
            with self._slots:
                if self.engine is not None:
                    return self._read_injected(content_bytes, filename, source_reference)
                if ext == ".pdf":
                    return self._read_pdf_ocr(content_bytes, filename, source_reference)
                return self._read_image_ocr(content_bytes, filename, source_reference)

        try:
            result = run_with_timeout(invoke, timeout_seconds=self.timeout_seconds)
        except TimeoutError:
            result = self._failure(
                filename,
                source_reference,
                f"OCR operation timed out after {self.timeout_seconds:.3f}s",
                reason_code="OCR_TIMEOUT",
                fallback_allowed=False,
            )
        except Exception as exc:
            result = self._failure(
                filename,
                source_reference,
                f"OCR error: {type(exc).__name__}: {exc}",
                reason_code="OCR_ENGINE_FAILED",
            )

        with self._lock:
            self._cache[cache_key] = result
        return result

    def _read_injected(
        self,
        content_bytes: bytes,
        filename: str,
        source_reference: str,
    ) -> UnifiedDocument:
        assert self.engine is not None
        output = self.engine(content_bytes, filename)
        texts = output if isinstance(output, list) else [output]
        if not all(isinstance(text, str) for text in texts):
            raise TypeError("OCR engine must return text or a list of page texts")
        combined = "\n\n".join(texts)
        document_format = (
            DocumentFormat.SCANNED_PDF
            if Path(filename).suffix.lower() == ".pdf"
            else DocumentFormat.IMAGE
        )
        return UnifiedDocument(
            raw_text=combined,
            pages=[DocumentPage(page_number=index, text=text) for index, text in enumerate(texts, start=1)],
            tables=[],
            format=document_format,
            reader_used="OcrReader",
            filename=filename,
            source_reference=source_reference,
            extraction_quality=0.85 if combined.strip() else 0.0,
            extraction_status="EXTRACTED" if combined.strip() else "UNREADABLE",
            metadata={"ocr_engine": "injected", "ocr_pages": len(texts)},
        )

    @staticmethod
    def _failure(
        filename: str,
        source_reference: str,
        message: str,
        *,
        reason_code: str,
        fallback_allowed: bool = True,
        ocr_available: bool = True,
    ) -> UnifiedDocument:
        document_format = (
            DocumentFormat.SCANNED_PDF
            if Path(filename).suffix.lower() == ".pdf"
            else DocumentFormat.IMAGE
        )
        return UnifiedDocument(
            raw_text="",
            pages=[],
            tables=[],
            format=document_format,
            reader_used="OcrReader",
            filename=filename,
            source_reference=source_reference,
            extraction_quality=0.0,
            extraction_status="FAILED",
            error_message=message,
            metadata={
                "reason_code": reason_code,
                "fallback_allowed": fallback_allowed,
                "ocr_available": ocr_available,
            },
        )

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
