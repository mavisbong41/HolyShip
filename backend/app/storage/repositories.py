from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.app.comparison.models import ComparisonBatchResult
from backend.app.extraction.models import CanonicalField, DocumentExtractionResult
from backend.app.ingestion.models import EmailMessage
from backend.app.storage.models import (
    AttachmentRecord,
    ClassificationResultRecord,
    ComparisonResultRecord,
    DocumentExtractionRecord,
    ExtractionCacheRecord,
    DocumentRecord,
    EmailMessageRecord,
    ExtractedFieldRecord,
    FieldComparisonRecord,
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

        if existing is None:
            record = EmailMessageRecord(
                source_type=message.source_type,
                external_message_id=message.external_message_id,
            )
            try:
                with self.session.begin_nested():
                    self.session.add(record)
                    self.session.flush()
            except IntegrityError:
                # The database uniqueness constraint is the final duplicate
                # protection when two workers ingest the same provider message.
                record = self.get_by_source_external_id(
                    message.source_type,
                    message.external_message_id,
                )
                if record is None:
                    raise
                if record.content_hash == message.content_hash:
                    return record, False
        else:
            record = existing

        record.sender = message.sender
        record.recipients = message.recipients
        record.subject = message.subject
        record.body = message.body
        record.received_at = message.received_at
        record.source_metadata = message.source_metadata
        record.content_hash = message.content_hash
        self._replace_attachments(record, message)
        self.session.flush()
        return record, True

    def _replace_attachments(
        self,
        record: EmailMessageRecord,
        message: EmailMessage,
    ) -> None:
        existing = {attachment.source_reference: attachment for attachment in record.attachments}
        desired: list[AttachmentRecord] = []
        for attachment in message.attachments:
            current = existing.pop(attachment.source_reference, None)
            if current is None:
                current = AttachmentRecord(
                    email_id=record.id,
                    filename=attachment.filename,
                    content_type=attachment.content_type,
                    source_reference=attachment.source_reference,
                    external_attachment_id=attachment.external_attachment_id,
                )
            else:
                current.filename = attachment.filename
                current.content_type = attachment.content_type
                current.external_attachment_id = attachment.external_attachment_id
            desired.append(current)
        for stale in existing.values():
            self.session.delete(stale)
        record.attachments = desired


class ProcessingJobRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_identity(
        self,
        *,
        email_id: UUID,
        job_type: str,
        source_content_hash: str | None,
    ) -> ProcessingJobRecord | None:
        return self.session.scalar(
            select(ProcessingJobRecord).where(
                ProcessingJobRecord.email_id == email_id,
                ProcessingJobRecord.job_type == job_type,
                ProcessingJobRecord.source_content_hash == source_content_hash,
            ).order_by(ProcessingJobRecord.created_at.desc())
        )

    def create(
        self,
        *,
        email_id: UUID,
        job_type: str,
        status: str = "PENDING",
        source_metadata: dict | None = None,
        source_content_hash: str | None = None,
    ) -> ProcessingJobRecord:
        existing = self.get_by_identity(
            email_id=email_id,
            job_type=job_type,
            source_content_hash=source_content_hash,
        )
        if existing is not None:
            existing.status = status
            existing.source_metadata = source_metadata or existing.source_metadata or {}
            existing.attempt_count += 1
            self.session.flush()
            return existing
        record = ProcessingJobRecord(
            email_id=email_id,
            job_type=job_type,
            status=status,
            source_metadata=source_metadata or {},
            source_content_hash=source_content_hash,
            attempt_count=1,
        )
        try:
            with self.session.begin_nested():
                self.session.add(record)
                self.session.flush()
        except IntegrityError:
            record = self.get_by_identity(
                email_id=email_id,
                job_type=job_type,
                source_content_hash=source_content_hash,
            )
            if record is None:
                raise
            record.status = status
            record.source_metadata = source_metadata or record.source_metadata or {}
            record.attempt_count += 1
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
        source_content_hash: str | None = None,
    ) -> ClassificationResultRecord:
        if source_content_hash is not None:
            existing = self.session.scalar(
                select(ClassificationResultRecord).where(
                    ClassificationResultRecord.email_id == email_id,
                    ClassificationResultRecord.source_content_hash == source_content_hash,
                    ClassificationResultRecord.classifier_version == classifier_version,
                )
            )
            if existing is not None:
                return existing
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
            source_content_hash=source_content_hash,
        )
        try:
            with self.session.begin_nested():
                self.session.add(record)
                self.session.flush()
        except IntegrityError:
            if source_content_hash is None:
                raise
            record = self.session.scalar(
                select(ClassificationResultRecord).where(
                    ClassificationResultRecord.email_id == email_id,
                    ClassificationResultRecord.source_content_hash == source_content_hash,
                    ClassificationResultRecord.classifier_version == classifier_version,
                )
            )
            if record is None:
                raise
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
        content_sha256: str | None = None,
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
            content_sha256=content_sha256,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def get_by_attachment_content(
        self,
        *,
        attachment_id: UUID,
        content_sha256: str,
    ) -> DocumentRecord | None:
        return self.session.scalar(
            select(DocumentRecord)
            .where(
                DocumentRecord.attachment_id == attachment_id,
                DocumentRecord.content_sha256 == content_sha256,
            )
            .options(
                selectinload(DocumentRecord.extractions).selectinload(
                    DocumentExtractionRecord.fields
                )
            )
            .order_by(DocumentRecord.created_at.desc())
        )


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

        cache_statement = (
            select(DocumentExtractionRecord)
            .join(
                ExtractionCacheRecord,
                ExtractionCacheRecord.source_extraction_id == DocumentExtractionRecord.id,
            )
            .where(
                ExtractionCacheRecord.content_sha256 == content_sha256,
                ExtractionCacheRecord.extractor_version == extractor_version,
                DocumentExtractionRecord.extraction_status == "EXTRACTED",
            )
            .options(selectinload(DocumentExtractionRecord.fields))
        )
        for candidate in self.session.scalars(cache_statement).unique():
            if len(candidate.fields) == 7 and len({row.field_name for row in candidate.fields}) == 7:
                if not exclude_extraction_ids or candidate.id not in exclude_extraction_ids:
                    return candidate

        # Backward-compatible fallback for extraction rows created before the
        # Phase-5 cache table existed. A later successful persistence claims
        # the durable cache identity.
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

    def register_cache_entry(
        self,
        *,
        content_sha256: str,
        extractor_version: str,
        source_extraction_id: UUID,
    ) -> DocumentExtractionRecord:
        existing = self.session.scalar(
            select(DocumentExtractionRecord)
            .join(
                ExtractionCacheRecord,
                ExtractionCacheRecord.source_extraction_id == DocumentExtractionRecord.id,
            )
            .where(
                ExtractionCacheRecord.content_sha256 == content_sha256,
                ExtractionCacheRecord.extractor_version == extractor_version,
            )
            .options(selectinload(DocumentExtractionRecord.fields))
        )
        if existing is not None:
            return existing

        entry = ExtractionCacheRecord(
            content_sha256=content_sha256,
            extractor_version=extractor_version,
            source_extraction_id=source_extraction_id,
        )
        try:
            with self.session.begin_nested():
                self.session.add(entry)
                self.session.flush()
        except IntegrityError:
            existing = self.session.scalar(
                select(DocumentExtractionRecord)
                .join(
                    ExtractionCacheRecord,
                    ExtractionCacheRecord.source_extraction_id == DocumentExtractionRecord.id,
                )
                .where(
                    ExtractionCacheRecord.content_sha256 == content_sha256,
                    ExtractionCacheRecord.extractor_version == extractor_version,
                )
                .options(selectinload(DocumentExtractionRecord.fields))
            )
            if existing is None:
                raise
            return existing
        return self.get(source_extraction_id)  # type: ignore[return-value]

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


class ComparisonResultRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, result_id: UUID) -> ComparisonResultRecord | None:
        return self.session.get(
            ComparisonResultRecord,
            result_id,
            options=[selectinload(ComparisonResultRecord.fields)],
        )

    def get_by_identity(
        self,
        *,
        email_id: UUID,
        si_extraction_id: UUID,
        bl_extraction_id: UUID,
        comparison_version: str,
    ) -> ComparisonResultRecord | None:
        return self.session.scalar(
            select(ComparisonResultRecord)
            .where(
                ComparisonResultRecord.email_id == email_id,
                ComparisonResultRecord.si_extraction_id == si_extraction_id,
                ComparisonResultRecord.bl_extraction_id == bl_extraction_id,
                ComparisonResultRecord.comparison_version == comparison_version,
            )
            .options(selectinload(ComparisonResultRecord.fields))
        )

    def get_latest_by_email_id(self, email_id: UUID) -> ComparisonResultRecord | None:
        return self.session.scalar(
            select(ComparisonResultRecord)
            .where(ComparisonResultRecord.email_id == email_id)
            .options(selectinload(ComparisonResultRecord.fields))
            .order_by(ComparisonResultRecord.created_at.desc())
        )

    def upsert_result(
        self,
        *,
        email_id: UUID,
        si_extraction_id: UUID,
        bl_extraction_id: UUID,
        comparison_version: str,
        batch: ComparisonBatchResult,
        si_fields: dict[CanonicalField, ExtractedFieldRecord],
        bl_fields: dict[CanonicalField, ExtractedFieldRecord],
    ) -> ComparisonResultRecord:
        record = self.get_by_identity(
            email_id=email_id,
            si_extraction_id=si_extraction_id,
            bl_extraction_id=bl_extraction_id,
            comparison_version=comparison_version,
        )
        if record is None:
            record = ComparisonResultRecord(
                email_id=email_id,
                si_extraction_id=si_extraction_id,
                bl_extraction_id=bl_extraction_id,
                comparison_version=comparison_version,
            )
            self.session.add(record)

        record.comparison_state = batch.comparison_state
        record.mismatch_found = batch.mismatch_found
        record.all_fields_definite = batch.all_fields_definite
        record.mismatched_fields = [name.value for name in batch.mismatched_fields]
        record.unresolved_fields = [name.value for name in batch.unresolved_fields]
        record.reason_code = batch.reason_code
        record.message = batch.message
        self.session.flush()

        existing = {field.field_name: field for field in record.fields}
        expected_names = {name.value for name in batch.fields}
        for stale_name in set(existing) - expected_names:
            self.session.delete(existing[stale_name])

        for field_name, result in batch.fields.items():
            si_source = si_fields[field_name]
            bl_source = bl_fields[field_name]
            field_record = existing.get(field_name.value)
            if field_record is None:
                field_record = FieldComparisonRecord(
                    comparison_result=record,
                    field_name=field_name.value,
                )
                self.session.add(field_record)
            field_record.si_field_id = si_source.id
            field_record.bl_field_id = bl_source.id
            field_record.si_raw_value = si_source.raw_value_json
            field_record.bl_raw_value = bl_source.raw_value_json
            field_record.si_canonical_value = si_source.canonical_value
            field_record.bl_canonical_value = bl_source.canonical_value
            field_record.si_normalized_value = result.normalized_si
            field_record.bl_normalized_value = result.normalized_bl
            field_record.comparison_layer = result.layer.value
            field_record.status = result.status.value
            field_record.reason_code = result.reason_code
            field_record.evidence = {
                "comparison": result.evidence,
                "si_source_location": si_source.source_location,
                "bl_source_location": bl_source.source_location,
            }
        self.session.flush()
        return record

