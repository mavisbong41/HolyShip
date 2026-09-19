from __future__ import annotations

from typing import Optional

from backend.app.documents.models import DocumentFormat, DocumentPage, UnifiedDocument
from backend.app.documents.readers.base import DocumentReader


class VisionResolver:
    """
    Clean interface for Vision/LLM document resolution when native parsing and OCR fail.
    Can be backed by Gemini / Claude / GPT Vision in future batches without changing pipeline logic.
    """

    def resolve(self, content_bytes: bytes, filename: str, previous_error: str = "") -> Optional[UnifiedDocument]:
        # Batch 2 baseline: returns None unless a vision backend is enabled
        return None


class VisionReader(DocumentReader):
    def __init__(self, resolver: VisionResolver | None = None):
        self.resolver = resolver or VisionResolver()

    def can_read(self, filename: str, content_bytes: bytes | None = None) -> bool:
        return True

    def read(self, content_bytes: bytes, filename: str, source_reference: str = "") -> UnifiedDocument:
        resolved = self.resolver.resolve(content_bytes, filename)
        if resolved:
            return resolved

        return UnifiedDocument(
            raw_text="",
            pages=[],
            tables=[],
            format=DocumentFormat.UNKNOWN,
            reader_used="VisionReader",
            filename=filename,
            source_reference=source_reference,
            extraction_quality=0.0,
            extraction_status="FAILED",
            error_message="Vision/LLM resolver not configured or could not resolve document",
            metadata={"resolved": False},
        )
