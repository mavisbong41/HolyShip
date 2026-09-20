from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from backend.app.extraction.models import DocumentExtractionResult
from backend.app.ingestion.models import EmailMessage
from backend.app.storage.models import (
    AttachmentRecord,
    ClassificationResultRecord,
    DocumentExtractionRecord,
    DocumentRecord,
    EmailMessageRecord,
    ExtractedFieldRecord,
    HumanReviewCaseRecord,
    ProcessingJobRecord,
)


class EmailRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_source_external_id(self, source_type: str, external_message_id: str) -> EmailMessageRecord | None:
        return self.session.scalar(
            select(EmailMessageRecord)
            .where(
                EmailMessageRecord.source_type == source_type,
                EmailMessageRecord.external_message_id == external_message_id,
            )
            .options(selectinload(EmailMessageRecord.attachments))
        )

    def get(self, email_id: UUID) -> EmailMessageRecord | None:
        return self.session.get(
            EmailMessageRecord,
            email_id,
            options=[selectinload(EmailMessageRecord.attachments)],
        )

    def upsert_message(self, message: EmailMessage) -> tuple[EmailMessageRecord, bool]:
        existing = self.get_by_source_external_id(message.source_type, message.external_message_id)
        if existing and existing.content_hash == message.content_hash:
            return existing, False

        record = existing or EmailMessageRecord(
            source_type=message.source_type,
            external_message_id=message.external_message_id,
        )
        record.sender = message.sender
        record.recipients = message.recipients
        record.subject = message.subject
        record.body = message.body
        record.received_at = message.received_at
        record.source_metadata = message.source_metadata
        record.content_hash = message.content_hash
        record.attachments = [
            AttachmentRecord(
                filename=attachment.filename,
                content_type=attachment.content_type,
                source_reference=attachment.source_reference,
                external_attachment_id=attachment.external_attachment_id,
            )
            for attachment in message.attachments
        ]
        self.session.add(record)
        self.session.flush()
        return record, True


class ProcessingJobRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, *, email_id: UUID, job_type: str, status: str = "PENDING", source_metadata: dict | None = None) -> ProcessingJobRecord:
        record = ProcessingJobRecord(
            email_id=email_id,
            job_type=job_type,
            status=status,
            source_metadata=source_metadata or {},
        )
        self.session.add(record)
        self.session.flush()
        return record


class ClassificationResultRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        email_id: UUID,
        category: str,
        confidence: float,
        candidate_scores: dict,
        reason: str,
        evidence_summary: dict,
        conflict_detected: bool,
        resolved_at_stage: str,
        comparison_readiness: str | None = None,
        classifier_version: str = "batch1-rule-v1",
        reason_code: str = "CLASSIFICATION_RESOLVED",
    ) -> ClassificationResultRecord:
        record = ClassificationResultRecord(
            email_id=email_id,
            category=category,
            confidence=confidence,
            candidate_scores=candidate_scores,
            reason=reason,
            reason_code=reason_code,
            evidence_summary=evidence_summary,
            conflict_detected=conflict_detected,
            resolved_at_stage=resolved_at_stage,
            comparison_readiness=comparison_readiness,
            classifier_version=classifier_version,
        )
        self.session.add(record)
        self.session.flush()
        return record


class HumanReviewRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        email_id: UUID,
        reason_code: str,
        reason_text: str,
        candidate_scores: dict | None = None,
        evidence: dict | None = None,
        confidence: float | None = None,
        status: str = "OPEN",
        document_id: UUID | None = None,
        field_name: str | None = None,
    ) -> HumanReviewCaseRecord:
        record = HumanReviewCaseRecord(
            email_id=email_id,
            document_id=document_id,
            field_name=field_name,
            reason_code=reason_code,
            reason_text=reason_text,
            candidate_scores=candidate_scores or {},
            evidence=evidence or {},
            confidence=confidence,
            status=status,
        )
        self.session.add(record)
        self.session.flush()
        return record


class DocumentRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, document_id: UUID) -> DocumentRecord | None:
        return self.session.get(
            DocumentRecord,
            document_id,
            options=[
                selectinload(DocumentRecord.extractions).selectinload(DocumentExtractionRecord.fields)
            ],
        )

    def list_by_email_id(self, email_id: UUID) -> list[DocumentRecord]:
        return list(
            self.session.scalars(
                select(DocumentRecord)
                .where(DocumentRecord.email_id == email_id)
                .options(
                    selectinload(DocumentRecord.extractions).selectinload(DocumentExtractionRecord.fields)
                )
                .order_by(DocumentRecord.created_at.asc())
            ).all()
        )

    def create(
        self,
        *,
        email_id: UUID,
        attachment_id: UUID | None,
        document_type: str,
        format: str,
        filename: str,
        source_reference: str,
        routing_outcome: str = "LEGACY_UNCLASSIFIED",
        role_confidence: float = 0.0,
        role_evidence: dict | None = None,
        validation_outcome: str = "INCONCLUSIVE",
        parse_duration_ms: float | None = None,
    ) -> DocumentRecord:
        record = DocumentRecord(
            email_id=email_id,
            attachment_id=attachment_id,
            document_type=document_type,
            format=format,
            filename=filename,
            source_reference=source_reference,
            routing_outcome=routing_outcome,
            role_confidence=role_confidence,
            role_evidence=role_evidence or {},
            validation_outcome=validation_outcome,
            parse_duration_ms=parse_duration_ms,
        )
        self.session.add(record)
        self.session.flush()
        return record


class DocumentExtractionRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, extraction_id: UUID) -> DocumentExtractionRecord | None:
        return self.session.get(
            DocumentExtractionRecord,
            extraction_id,
            options=[selectinload(DocumentExtractionRecord.fields)],
        )

    def get_latest_by_document_id(self, document_id: UUID) -> DocumentExtractionRecord | None:
        return self.session.scalar(
            select(DocumentExtractionRecord)
            .where(DocumentExtractionRecord.document_id == document_id)
            .options(selectinload(DocumentExtractionRecord.fields))
            .order_by(DocumentExtractionRecord.created_at.desc())
        )

    def find_cached_by_content(
        self,
        *,
        content_sha256: str,
        extractor_version: str,
        exclude_extraction_ids: set[UUID] | None = None,
    ) -> DocumentExtractionRecord | None:
        """Return a complete reusable payload without changing document ownership."""

        statement = (
            select(DocumentExtractionRecord)
            .join(DocumentRecord, DocumentRecord.id == DocumentExtractionRecord.document_id)
            .join(AttachmentRecord, AttachmentRecord.id == DocumentRecord.attachment_id)
            .where(
                AttachmentRecord.content_sha256 == content_sha256,
                DocumentExtractionRecord.extractor_version == extractor_version,
                DocumentExtractionRecord.extraction_status == "EXTRACTED",
            )
            .options(selectinload(DocumentExtractionRecord.fields))
            .order_by(DocumentExtractionRecord.created_at.desc())
        )
        if exclude_extraction_ids:
            statement = statement.where(
                DocumentExtractionRecord.id.not_in(exclude_extraction_ids)
            )
        for candidate in self.session.scalars(statement).unique():
            if len(candidate.fields) == 7 and len({row.field_name for row in candidate.fields}) == 7:
                return candidate
        return None

    def create(
        self,
        *,
        document_id: UUID,
        reader_used: str,
        extraction_status: str = "EXTRACTED",
        extraction_quality: float | None = None,
        raw_text: str = "",
        pages_count: int = 1,
        metadata_json: dict | None = None,
        extractor_version: str = "materialization-v1",
    ) -> DocumentExtractionRecord:
        record = DocumentExtractionRecord(
            document_id=document_id,
            reader_used=reader_used,
            extraction_status=extraction_status,
            extraction_quality=extraction_quality,
            raw_text=raw_text,
            pages_count=pages_count,
            metadata_json=metadata_json or {},
            extractor_version=extractor_version,
        )
        self.session.add(record)
        self.session.flush()
        return record


class ExtractedFieldRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        extraction_id: UUID,
        field_name: str,
        raw_value: str | None,
        raw_label: str | None = None,
        raw_value_json: object | None = None,
        canonical_value: object | None = None,
        status: str = "MISSING",
        confidence: float = 1.0,
        evidence: dict | None = None,
        source_location: dict | None = None,
        mapping_method: str | None = None,
        extraction_method: str = "DETERMINISTIC_ONE_PASS",
    ) -> ExtractedFieldRecord:
        record = ExtractedFieldRecord(
            extraction_id=extraction_id,
            field_name=field_name,
            raw_label=raw_label,
            raw_value=raw_value,
            raw_value_json=raw_value_json,
            canonical_value=canonical_value,
            status=status,
            confidence=confidence,
            evidence=evidence or {},
            source_location=source_location or {},
            mapping_method=mapping_method,
            extraction_method=extraction_method,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def create_result(
        self,
        extraction_id: UUID,
        result: DocumentExtractionResult,
    ) -> list[ExtractedFieldRecord]:
        records: list[ExtractedFieldRecord] = []
        for field_name, field_result in result.fields.items():
            raw_text = None if field_result.raw_value is None else str(field_result.raw_value)
            records.append(
                self.create(
                    extraction_id=extraction_id,
                    field_name=field_name.value,
                    raw_label=field_result.raw_label,
                    raw_value=raw_text,
                    raw_value_json=field_result.raw_value,
                    canonical_value=field_result.canonical_value,
                    status=field_result.status.value,
                    confidence=field_result.confidence,
                    evidence=field_result.evidence,
                    source_location=field_result.source_location.to_dict(),
                    mapping_method=(
                        field_result.mapping_method.value
                        if field_result.mapping_method is not None
                        else None
                    ),
                )
            )
        return records

    def list_by_extraction_id(self, extraction_id: UUID) -> list[ExtractedFieldRecord]:
        return list(
            self.session.scalars(
                select(ExtractedFieldRecord)
                .where(ExtractedFieldRecord.extraction_id == extraction_id)
                .order_by(ExtractedFieldRecord.field_name)
            ).all()
        )

    def has_complete_result(self, extraction_id: UUID) -> bool:
        records = self.list_by_extraction_id(extraction_id)
        return len(records) == 7 and len({record.field_name for record in records}) == 7

    def clear_result(self, extraction_id: UUID) -> None:
        self.session.execute(
            delete(ExtractedFieldRecord).where(
                ExtractedFieldRecord.extraction_id == extraction_id
            )
        )
        self.session.flush()

    def copy_result(
        self,
        *,
        source_extraction_id: UUID,
        target_extraction_id: UUID,
    ) -> list[ExtractedFieldRecord]:
        source = self.list_by_extraction_id(source_extraction_id)
        if len(source) != 7 or len({record.field_name for record in source}) != 7:
            raise ValueError("cached extraction must contain exactly seven unique fields")
        records: list[ExtractedFieldRecord] = []
        for field in source:
            records.append(
                self.create(
                    extraction_id=target_extraction_id,
                    field_name=field.field_name,
                    raw_label=field.raw_label,
                    raw_value=field.raw_value,
                    raw_value_json=field.raw_value_json,
                    canonical_value=field.canonical_value,
                    status=field.status,
                    confidence=field.confidence,
                    evidence=field.evidence,
                    source_location=field.source_location,
                    mapping_method=field.mapping_method,
                    extraction_method=field.extraction_method,
                )
            )
        return records

