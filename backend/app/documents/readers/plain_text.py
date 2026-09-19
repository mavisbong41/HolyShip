from __future__ import annotations

from pathlib import Path

from backend.app.documents.models import DocumentFormat, DocumentPage, UnifiedDocument
from backend.app.documents.readers.base import DocumentReader


class PlainTextReader(DocumentReader):
    def can_read(self, filename: str, content_bytes: bytes | None = None) -> bool:
        ext = Path(filename).suffix.lower()
        return ext in (".txt", ".text", ".csv", ".log", "")

    def read(self, content_bytes: bytes, filename: str, source_reference: str = "") -> UnifiedDocument:
        try:
            text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content_bytes.decode("latin-1")
            except Exception:
                text = content_bytes.decode("utf-8", errors="replace")

        page = DocumentPage(page_number=1, text=text)
        return UnifiedDocument(
            raw_text=text,
            pages=[page],
            tables=[],
            format=DocumentFormat.PLAIN_TEXT,
            reader_used="PlainTextReader",
            filename=filename,
            source_reference=source_reference,
            extraction_quality=1.0 if text.strip() else 0.0,
            extraction_status="EXTRACTED" if text.strip() else "UNREADABLE",
        )
