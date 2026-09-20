from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class DocumentType(str, Enum):
    SI = "SI"
    DRAFT_BL = "DRAFT_BL"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class DocumentFormat(str, Enum):
    PLAIN_TEXT = "PLAIN_TEXT"
    PDF_TEXT = "PDF_TEXT"
    DOCX = "DOCX"
    XLSX = "XLSX"
    SCANNED_PDF = "SCANNED_PDF"
    IMAGE = "IMAGE"
    UNKNOWN = "UNKNOWN"


@dataclass
class DocumentPage:
    page_number: int
    text: str
    width: Optional[float] = None
    height: Optional[float] = None


@dataclass
class DocumentTable:
    rows: list[list[Any]] = field(default_factory=list)
    page_number: int = 1
    title: Optional[str] = None


@dataclass
class UnifiedDocument:
    raw_text: str
    pages: list[DocumentPage] = field(default_factory=list)
    tables: list[DocumentTable] = field(default_factory=list)
    format: DocumentFormat = DocumentFormat.UNKNOWN
    reader_used: str = "UnknownReader"
    document_type: DocumentType = DocumentType.UNKNOWN
    filename: str = ""
    source_reference: str = ""
    extraction_quality: float = 1.0
    extraction_status: str = "EXTRACTED"  # EXTRACTED | FAILED | PARTIAL | UNREADABLE
    error_message: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_pages(self) -> int:
        return len(self.pages) if self.pages else 1


@dataclass
class RoutedAttachment:
    filename: str
    source_reference: str
    document_type: DocumentType
    format: DocumentFormat
    confidence: float
    evidence: str


@dataclass
class DocumentRoutingResult:
    si_attachment: Optional[RoutedAttachment] = None
    bl_attachment: Optional[RoutedAttachment] = None
    other_attachments: list[RoutedAttachment] = field(default_factory=list)
    human_review_required: bool = False
    human_review_reason_code: Optional[str] = None
    human_review_reason_text: Optional[str] = None
