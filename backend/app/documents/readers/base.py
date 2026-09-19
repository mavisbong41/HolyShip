from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from backend.app.documents.models import DocumentFormat, UnifiedDocument


class DocumentReader(ABC):
    @abstractmethod
    def read(self, content_bytes: bytes, filename: str, source_reference: str = "") -> UnifiedDocument:
        """Reads document bytes and produces a UnifiedDocument."""
        raise NotImplementedError

    def can_read(self, filename: str, content_bytes: bytes | None = None) -> bool:
        """Returns True if this reader can handle the file format."""
        return False
