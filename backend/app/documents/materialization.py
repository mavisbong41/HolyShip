from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session

from backend.app.comparison.persistence import PersistedComparisonService
from backend.app.documents.models import DocumentFormat, DocumentType, UnifiedDocument
from backend.app.documents.readers.composite import CompositeDocumentReader
from backend.app.documents.role_validation import (
    DocumentRoleValidator,
    RoleValidationOutcome,
    RoleValidationResult,
)
from backend.app.extraction.extractor import DeterministicDocumentExtractor
from backend.app.extraction.service import (
    DocumentFieldExtractionService,
    ExtractionTarget,
)
from backend.app.ingestion.models import EmailMessage
from backend.app.ingestion.sources import EmailSource
from backend.app.storage.models import (
    AttachmentRecord,
    DocumentExtractionRecord,
    DocumentRecord,
    EmailMessageRecord,
)
from backend.app.storage.repositories import (
    DocumentExtractionRepository,
    DocumentRepository,
    ExtractedFieldRepository,
)
from backend.app.storage.transitions import transition


logger = logging.getLogger(__name__)


class PreExtractionOutcome(str, Enum):
    SI_FOUND = "SI_FOUND"
    BL_FOUND = "BL_FOUND"
    MULTIPLE_CANDIDATES = "MULTIPLE_CANDIDATES"
    MISSING_REQUIRED_ATTACHMENT = "MISSING_REQUIRED_ATTACHMENT"
    UNSUPPORTED_ATTACHMENT = "UNSUPPORTED_ATTACHMENT"
    CORRUPTED_ATTACHMENT = "CORRUPTED_ATTACHMENT"
    UNREADABLE_ATTACHMENT = "UNREADABLE_ATTACHMENT"
    WRONG_DOCUMENT_TYPE = "WRONG_DOCUMENT_TYPE"
    ROLE_INCONCLUSIVE = "ROLE_INCONCLUSIVE"


@dataclass(frozen=True)
class MaterializationResult:
    processing_status: str
    reason_code: str
    technical_failure: bool = False


@dataclass
class _PersistedDocument:
    record: DocumentRecord
    extraction: DocumentExtractionRecord
    document: UnifiedDocument
    content_sha256: str
    role: DocumentType
    outcome: PreExtractionOutcome


class DocumentMaterializationService:
    """Lazy Phase-2 materialization and role validation for ready comparisons."""

    def __init__(
        self,
        session: Session,
        reader: CompositeDocumentReader | None = None,
        role_validator: DocumentRoleValidator | None = None,
        field_extractor: DeterministicDocumentExtractor | None = None,
    ):
        self.session = session
        self.reader = reader or CompositeDocumentReader()
        self.role_validator = role_validator or DocumentRoleValidator()
        self.field_extractor = field_extractor or DeterministicDocumentExtractor()
        self.document_repo = DocumentRepository(session)
        self.extraction_repo = DocumentExtractionRepository(session)
        self.field_repo = ExtractedFieldRepository(session)
        self.comparison_service = PersistedComparisonService(session)

    def process(
        self,
        email_record: EmailMessageRecord,
        message: EmailMessage,
        source: EmailSource | None,
    ) -> MaterializationResult:
        transition(
            self.session,
            email_record,
            "RETRIEVING_ATTACHMENTS",
            "ATTACHMENT_RETRIEVAL_STARTED",
        )

        if not message.attachments:
            return self._blocked(email_record, PreExtractionOutcome.MISSING_REQUIRED_ATTACHMENT.value)

        attachment_records = list(email_record.attachments)
        persisted: list[_PersistedDocument] = []
        technical_failure: str | None = None

        for index, attachment in enumerate(message.attachments):
            attachment_record = self._attachment_record(attachment_records, attachment.source_reference, index)
            try:
                if source is None:
                    raise FileNotFoundError("No source adapter is available to load attachment content")
                content = source.get_attachment_content(attachment)
            except Exception as exc:
                attachment_record.retrieval_status = "FAILED"
                attachment_record.retrieval_reason_code = "ATTACHMENT_READ_FAILED"
                technical_failure = technical_failure or "ATTACHMENT_READ_FAILED"
                self.session.flush()
                continue

            attachment_record.content_sha256 = hashlib.sha256(content).hexdigest()
            attachment_record.retrieval_status = "MATERIALIZED"
            attachment_record.retrieval_reason_code = None

            started = time.perf_counter()
            try:
                document = self.reader.read(
                    content,
                    attachment.filename,
                    attachment.source_reference,
                )
            except Exception as exc:
                document = UnifiedDocument(
                    raw_text="",
                    format=self.reader.detect_format(attachment.filename),
                    reader_used=type(self.reader).__name__,
                    filename=attachment.filename,
                    source_reference=attachment.source_reference,
                    extraction_quality=0.0,
                    extraction_status="FAILED",
                    error_message=f"Reader exception: {type(exc).__name__}: {exc}",
                )
                technical_failure = technical_failure or "DOCUMENT_READER_FAILED"
            parse_duration_ms = (time.perf_counter() - started) * 1000.0

            validation, outcome = self._classify_materialization(content, document)
            document.document_type = validation.document_type
            document_record = self.document_repo.create(
                email_id=email_record.id,
                attachment_id=attachment_record.id,
                document_type=validation.document_type.value,
                format=document.format.value,
                filename=attachment.filename,
                source_reference=attachment.source_reference,
                routing_outcome=outcome.value,
                role_confidence=validation.confidence,
                role_evidence={"markers": validation.markers, "summary": validation.evidence},
                validation_outcome=validation.outcome.value,
                parse_duration_ms=parse_duration_ms,
            )
            extraction_record = self.extraction_repo.create(
                document_id=document_record.id,
                reader_used=document.reader_used,
                extraction_quality=document.extraction_quality,
                raw_text=document.raw_text,
                pages_count=document.total_pages,
                metadata_json={
                    **document.metadata,
                    "error": document.error_message,
                    "pages": [
                        {"page_number": page.page_number, "text": page.text}
                        for page in document.pages
                    ],
                    "tables": [
                        {
                            "title": table.title,
                            "page_number": table.page_number,
                            "rows": self._json_safe(table.rows),
                            "cells": [
                                [self._json_safe(cell.to_dict()) for cell in row]
                                for row in table.cells
                            ],
                        }
                        for table in document.tables
                    ],
                },
                extraction_status=(
                    "PENDING"
                    if validation.outcome == RoleValidationOutcome.VALID
                    and validation.document_type in {DocumentType.SI, DocumentType.DRAFT_BL}
                    else document.extraction_status
                ),
                extractor_version=(
                    self.field_extractor.version
                    if validation.outcome == RoleValidationOutcome.VALID
                    and validation.document_type in {DocumentType.SI, DocumentType.DRAFT_BL}
                    else "materialization-v1"
                ),
            )
            persisted.append(
                _PersistedDocument(
                    record=document_record,
                    extraction=extraction_record,
                    document=document,
                    content_sha256=attachment_record.content_sha256,
                    role=validation.document_type,
                    outcome=outcome,
                )
            )

        if technical_failure:
            transition(self.session, email_record, "FAILED", technical_failure)
            return MaterializationResult("FAILED", technical_failure, technical_failure=True)

        precedence = (
            PreExtractionOutcome.WRONG_DOCUMENT_TYPE,
            PreExtractionOutcome.UNSUPPORTED_ATTACHMENT,
            PreExtractionOutcome.CORRUPTED_ATTACHMENT,
            PreExtractionOutcome.UNREADABLE_ATTACHMENT,
        )
        for outcome in precedence:
            if any(item.outcome == outcome for item in persisted):
                return self._blocked(email_record, outcome.value)

        si_documents = [item for item in persisted if item.role == DocumentType.SI]
        bl_documents = [item for item in persisted if item.role == DocumentType.DRAFT_BL]
        if len(si_documents) > 1 or len(bl_documents) > 1:
            duplicate_role = si_documents if len(si_documents) > 1 else bl_documents
            for item in duplicate_role:
                item.record.routing_outcome = PreExtractionOutcome.MULTIPLE_CANDIDATES.value
            self.session.flush()
            return self._blocked(email_record, PreExtractionOutcome.MULTIPLE_CANDIDATES.value)

        if any(item.outcome == PreExtractionOutcome.ROLE_INCONCLUSIVE for item in persisted):
            return self._blocked(email_record, "DOCUMENT_ROLE_UNRESOLVED")

        if len(si_documents) != 1 or len(bl_documents) != 1:
            return self._blocked(email_record, PreExtractionOutcome.MISSING_REQUIRED_ATTACHMENT.value)

        transition(self.session, email_record, "EXTRACTING", "DOCUMENTS_MATERIALIZED")
        field_service = DocumentFieldExtractionService(
            self.session,
            self.field_extractor,
            max_workers=2,
        )
        batch = field_service.extract(
            [
                ExtractionTarget(
                    document=item.document,
                    content_sha256=item.content_sha256,
                    extraction=item.extraction,
                )
                for item in (si_documents[0], bl_documents[0])
            ]
        )
        if batch.failed:
            transition(
                self.session,
                email_record,
                "FAILED",
                "DOCUMENT_FIELD_EXTRACTION_FAILED",
            )
            return MaterializationResult(
                "FAILED",
                "DOCUMENT_FIELD_EXTRACTION_FAILED",
                technical_failure=True,
            )
        try:
            with self.session.begin_nested():
                comparison = self.comparison_service.compare_and_persist(
                    email_record,
                    si_extraction_id=si_documents[0].extraction.id,
                    bl_extraction_id=bl_documents[0].extraction.id,
                )
        except Exception:
            logger.exception("Comparison failed for email %s", email_record.id)
            transition(
                self.session,
                email_record,
                "FAILED",
                "COMPARISON_FAILED",
            )
            return MaterializationResult(
                "FAILED",
                "COMPARISON_FAILED",
                technical_failure=True,
            )
        return MaterializationResult(
            comparison.record.comparison_state,
            comparison.record.reason_code,
        )

    def _classify_materialization(
        self,
        content: bytes,
        document: UnifiedDocument,
    ) -> tuple[RoleValidationResult, PreExtractionOutcome]:
        if document.format == DocumentFormat.UNKNOWN:
            return self._unvalidated("Unsupported attachment format"), PreExtractionOutcome.UNSUPPORTED_ATTACHMENT
        if not content:
            return self._unvalidated("Attachment is empty"), PreExtractionOutcome.CORRUPTED_ATTACHMENT
        if document.extraction_status == "FAILED":
            return self._unvalidated(document.error_message or "Reader failed"), PreExtractionOutcome.CORRUPTED_ATTACHMENT
        if document.extraction_status in {"UNREADABLE", "PARTIAL"} and not document.raw_text.strip():
            return self._unvalidated(document.error_message or "No readable content"), PreExtractionOutcome.UNREADABLE_ATTACHMENT

        validation = self.role_validator.validate(document)
        if validation.outcome == RoleValidationOutcome.WRONG_DOCUMENT_TYPE:
            return validation, PreExtractionOutcome.WRONG_DOCUMENT_TYPE
        if validation.outcome == RoleValidationOutcome.INCONCLUSIVE:
            return validation, PreExtractionOutcome.ROLE_INCONCLUSIVE
        if validation.document_type == DocumentType.SI:
            return validation, PreExtractionOutcome.SI_FOUND
        return validation, PreExtractionOutcome.BL_FOUND

    @staticmethod
    def _unvalidated(evidence: str) -> RoleValidationResult:
        return RoleValidationResult(
            document_type=DocumentType.UNKNOWN,
            outcome=RoleValidationOutcome.INCONCLUSIVE,
            confidence=0.0,
            evidence=evidence,
        )

    def _blocked(self, email_record: EmailMessageRecord, reason_code: str) -> MaterializationResult:
        transition(self.session, email_record, "BLOCKED", reason_code)
        return MaterializationResult("BLOCKED", reason_code)

    @staticmethod
    def _attachment_record(
        records: list[AttachmentRecord],
        source_reference: str,
        fallback_index: int,
    ) -> AttachmentRecord:
        for record in records:
            if record.source_reference == source_reference:
                return record
        return records[fallback_index]

    @classmethod
    def _json_safe(cls, value):
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [cls._json_safe(item) for item in value]
        if isinstance(value, tuple):
            return [cls._json_safe(item) for item in value]
        if isinstance(value, dict):
            return {str(key): cls._json_safe(item) for key, item in value.items()}
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)
