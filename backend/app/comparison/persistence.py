from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.comparison.service import COMPARISON_VERSION, ComparisonService
from backend.app.extraction.models import (
    CANONICAL_FIELDS,
    CanonicalField,
    DocumentExtractionResult,
    ExtractedField,
    FieldStatus,
    MappingMethod,
    SourceLocation,
)
from backend.app.storage.models import (
    ComparisonResultRecord,
    DocumentExtractionRecord,
    EmailMessageRecord,
    ExtractedFieldRecord,
)
from backend.app.storage.repositories import (
    ComparisonResultRepository,
    DocumentExtractionRepository,
)
from backend.app.storage.transitions import transition


@dataclass(frozen=True)
class PersistedComparisonOutcome:
    record: ComparisonResultRecord
    reused: bool


class PersistedComparisonService:
    """Compare the two persisted Phase-3 extraction payloads without reopening files."""

    def __init__(
        self,
        session: Session,
        comparator: ComparisonService | None = None,
        *,
        comparison_version: str = COMPARISON_VERSION,
    ) -> None:
        self.session = session
        self.comparator = comparator if comparator is not None else ComparisonService()
        self.comparison_version = comparison_version
        self.extraction_repo = DocumentExtractionRepository(session)
        self.comparison_repo = ComparisonResultRepository(session)

    def compare_and_persist(
        self,
        email: EmailMessageRecord,
        *,
        si_extraction_id: UUID,
        bl_extraction_id: UUID,
    ) -> PersistedComparisonOutcome:
        existing = self.comparison_repo.get_by_identity(
            email_id=email.id,
            si_extraction_id=si_extraction_id,
            bl_extraction_id=bl_extraction_id,
            comparison_version=self.comparison_version,
        )
        if existing is not None and len(existing.fields) == len(CANONICAL_FIELDS):
            if email.processing_status != existing.comparison_state:
                transition(
                    self.session,
                    email,
                    existing.comparison_state,
                    existing.reason_code,
                )
            return PersistedComparisonOutcome(existing, reused=True)

        si_record = self._load_extraction(si_extraction_id, expected_role="SI", email_id=email.id)
        bl_record = self._load_extraction(
            bl_extraction_id,
            expected_role="DRAFT_BL",
            email_id=email.id,
        )
        si_result, si_fields = self._to_domain(si_record, "SI")
        bl_result, bl_fields = self._to_domain(bl_record, "DRAFT_BL")

        transition(self.session, email, "COMPARING", "COMPARISON_STARTED")
        batch = self.comparator.compare(si_result, bl_result)
        record = self.comparison_repo.upsert_result(
            email_id=email.id,
            si_extraction_id=si_extraction_id,
            bl_extraction_id=bl_extraction_id,
            comparison_version=self.comparison_version,
            batch=batch,
            si_fields=si_fields,
            bl_fields=bl_fields,
        )
        transition(
            self.session,
            email,
            batch.comparison_state,
            batch.reason_code,
        )
        return PersistedComparisonOutcome(record, reused=False)

    def _load_extraction(
        self,
        extraction_id: UUID,
        *,
        expected_role: str,
        email_id: UUID,
    ) -> DocumentExtractionRecord:
        record = self.extraction_repo.get(extraction_id)
        if record is None:
            raise ValueError(f"{expected_role} extraction does not exist")
        if record.extraction_status != "EXTRACTED":
            raise ValueError(f"{expected_role} extraction is not complete")
        if record.document.document_type != expected_role:
            raise ValueError(f"{expected_role} extraction role does not match")
        if record.document.email_id != email_id:
            raise ValueError(f"{expected_role} extraction belongs to another email")
        if len(record.fields) != len(CANONICAL_FIELDS):
            raise ValueError(f"{expected_role} extraction must contain seven fields")
        return record

    @staticmethod
    def _to_domain(
        extraction: DocumentExtractionRecord,
        role: str,
    ) -> tuple[DocumentExtractionResult, dict[CanonicalField, ExtractedFieldRecord]]:
        records: dict[CanonicalField, ExtractedFieldRecord] = {}
        fields: dict[CanonicalField, ExtractedField] = {}
        for record in extraction.fields:
            field_name = CanonicalField(record.field_name)
            if field_name in records:
                raise ValueError(f"duplicate persisted field: {field_name.value}")
            records[field_name] = record
            fields[field_name] = ExtractedField(
                canonical_field=field_name,
                raw_label=record.raw_label,
                raw_value=record.raw_value_json,
                canonical_value=record.canonical_value,
                status=FieldStatus(record.status),
                confidence=record.confidence,
                mapping_method=(
                    MappingMethod(record.mapping_method)
                    if record.mapping_method is not None
                    else None
                ),
                source_location=SourceLocation(**record.source_location),
                evidence=record.evidence,
            )
        if set(fields) != set(CANONICAL_FIELDS):
            raise ValueError(f"{role} extraction must contain the seven canonical fields")
        return (
            DocumentExtractionResult(
                document_role=role,
                fields=fields,
                extractor_version=extraction.extractor_version,
            ),
            records,
        )
