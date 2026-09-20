from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session

from backend.app.comparison.persistence import PersistedComparisonService
from backend.app.comparison.service import ComparisonService
from backend.app.documents.models import DocumentFormat, DocumentType, UnifiedDocument
from backend.app.documents.readers.composite import CompositeDocumentReader
from backend.app.documents.readers.ocr_reader import OcrReader, OcrSharedState
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
from backend.app.resolution.service import ResolutionExecutor
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
    reader_calls: int = 0
    extractor_calls: int = 0
    ocr_calls: int = 0
    vision_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0


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
        semantic_resolver_timeout_seconds: float | None = None,
        resolution_executor: ResolutionExecutor | None = None,
        extraction_max_workers: int = 2,
        ocr_timeout_seconds: float = 15.0,
        ocr_max_calls: int = 8,
        ocr_max_concurrent_calls: int = 2,
        ocr_shared_state: OcrSharedState | None = None,
    ):
        self.session = session
        self.reader = reader or CompositeDocumentReader(
            ocr_reader=OcrReader(
                timeout_seconds=ocr_timeout_seconds,
                max_calls=ocr_max_calls,
                max_concurrent_calls=ocr_max_concurrent_calls,
                shared_state=ocr_shared_state,
            )
        )
        self.role_validator = role_validator or DocumentRoleValidator()
        self.field_extractor = field_extractor or DeterministicDocumentExtractor()
        self.extraction_max_workers = extraction_max_workers
        self.document_repo = DocumentRepository(session)
        self.extraction_repo = DocumentExtractionRepository(session)
        self.field_repo = ExtractedFieldRepository(session)
        self.comparison_service = PersistedComparisonService(
            session,
            comparator=ComparisonService(
                semantic_timeout_seconds=semantic_resolver_timeout_seconds,
            ),
            resolution_executor=resolution_executor,
        )

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
        reader_calls = 0
        ocr_calls = 0
        vision_calls = 0

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
            reader_calls += 1
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
            reader_name = document.reader_used.casefold()
            ocr_calls += int("ocr" in reader_name)
            vision_calls += int("vision" in reader_name)

            validation, outcome = self._classify_materialization(content, document)
            document.document_type = validation.document_type

            existing_document = self.document_repo.get_by_attachment_content(
                attachment_id=attachment_record.id,
                content_sha256=attachment_record.content_sha256,
            )
            if existing_document is not None and existing_document.extractions:
                # A process restart may have committed materialization but
                # stopped before extraction/comparison. Reuse that durable
                # graph instead of creating a second document/extraction.
                existing_extraction = max(
                    existing_document.extractions,
                    key=lambda item: item.created_at,
                )
                try:
                    existing_role = DocumentType(existing_document.document_type)
                except ValueError:
                    existing_role = DocumentType.UNKNOWN
                try:
                    existing_outcome = PreExtractionOutcome(
                        existing_document.routing_outcome
                    )
                except ValueError:
                    existing_outcome = outcome
                document.document_type = existing_role
                persisted.append(
                    _PersistedDocument(
                        record=existing_document,
                        extraction=existing_extraction,
                        document=document,
                        content_sha256=attachment_record.content_sha256,
                        role=existing_role,
                        outcome=existing_outcome,
                    )
                )
                continue

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
                content_sha256=attachment_record.content_sha256,
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
            return MaterializationResult(
                "FAILED",
                technical_failure,
                technical_failure=True,
                reader_calls=reader_calls,
                ocr_calls=ocr_calls,
                vision_calls=vision_calls,
            )

        precedence = (
            PreExtractionOutcome.WRONG_DOCUMENT_TYPE,
            PreExtractionOutcome.UNSUPPORTED_ATTACHMENT,
            PreExtractionOutcome.CORRUPTED_ATTACHMENT,
            PreExtractionOutcome.UNREADABLE_ATTACHMENT,
        )
        for outcome in precedence:
            if any(item.outcome == outcome for item in persisted):
                return self._blocked(
                    email_record,
                    outcome.value,
                    reader_calls=reader_calls,
                    ocr_calls=ocr_calls,
                    vision_calls=vision_calls,
                )

        si_documents = [item for item in persisted if item.role == DocumentType.SI]
        bl_documents = [item for item in persisted if item.role == DocumentType.DRAFT_BL]
        if len(si_documents) > 1 or len(bl_documents) > 1:
            duplicate_role = si_documents if len(si_documents) > 1 else bl_documents
            for item in duplicate_role:
                item.record.routing_outcome = PreExtractionOutcome.MULTIPLE_CANDIDATES.value
            self.session.flush()
            return self._blocked(
                email_record,
                PreExtractionOutcome.MULTIPLE_CANDIDATES.value,
                reader_calls=reader_calls,
                ocr_calls=ocr_calls,
                vision_calls=vision_calls,
            )

        if any(item.outcome == PreExtractionOutcome.ROLE_INCONCLUSIVE for item in persisted):
            return self._blocked(
                email_record,
                "DOCUMENT_ROLE_UNRESOLVED",
                reader_calls=reader_calls,
                ocr_calls=ocr_calls,
                vision_calls=vision_calls,
            )

        if len(si_documents) != 1 or len(bl_documents) != 1:
            return self._blocked(
                email_record,
                PreExtractionOutcome.MISSING_REQUIRED_ATTACHMENT.value,
                reader_calls=reader_calls,
                ocr_calls=ocr_calls,
                vision_calls=vision_calls,
            )

        transition(self.session, email_record, "EXTRACTING", "DOCUMENTS_MATERIALIZED")
        field_service = DocumentFieldExtractionService(
            self.session,
            self.field_extractor,
            max_workers=self.extraction_max_workers,
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
                reader_calls=reader_calls,
                extractor_calls=batch.computations,
                ocr_calls=ocr_calls,
                vision_calls=vision_calls,
                cache_hits=batch.cache_hits,
                cache_misses=batch.cache_misses,
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
            reader_calls=reader_calls,
            extractor_calls=batch.computations,
            ocr_calls=ocr_calls,
            vision_calls=vision_calls,
            cache_hits=batch.cache_hits,
            cache_misses=batch.cache_misses,
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

    def _blocked(
        self,
        email_record: EmailMessageRecord,
        reason_code: str,
        *,
        reader_calls: int = 0,
        ocr_calls: int = 0,
        vision_calls: int = 0,
    ) -> MaterializationResult:
        transition(self.session, email_record, "BLOCKED", reason_code)
        return MaterializationResult(
            "BLOCKED",
            reason_code,
            reader_calls=reader_calls,
            ocr_calls=ocr_calls,
            vision_calls=vision_calls,
        )

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
