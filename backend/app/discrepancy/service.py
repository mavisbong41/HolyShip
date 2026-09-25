from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from backend.app.comparison.persistence import PersistedComparisonService
from backend.app.comparison.service import COMPARISON_VERSION, ComparisonService
from backend.app.extraction.extractor import DeterministicDocumentExtractor
from backend.app.extraction.models import CanonicalField, DocumentExtractionResult, FieldStatus
from backend.app.storage.models import (
    ComparisonResultRecord,
    DocumentExtractionRecord,
    EmailMessageRecord,
    FieldComparisonRecord,
    HumanReviewFieldOverrideRecord,
    ProcessingEventRecord,
)
from backend.app.storage.repositories import ComparisonResultRepository, DocumentExtractionRepository
from backend.app.storage.transitions import transition


DiscrepancyResolutionStatus = Literal["OPEN", "ACKNOWLEDGED", "RESOLVED"]


class DiscrepancyConflictError(ValueError):
    """The requested operation conflicts with discrepancy lifecycle or data state."""


class DiscrepancyService:
    def __init__(self, session: Session):
        self.session = session

    def _latest_comparison_subquery(self) -> Any:
        return (
            select(
                ComparisonResultRecord,
                func.row_number()
                .over(
                    partition_by=ComparisonResultRecord.email_id,
                    order_by=[ComparisonResultRecord.created_at.desc(), ComparisonResultRecord.id.desc()],
                )
                .label("rank"),
            )
            .subquery()
        )

    def list_discrepancies(
        self,
        *,
        status: DiscrepancyResolutionStatus | Literal["ALL"] | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[ComparisonResultRecord], int, dict[str, int]]:
        comp = self._latest_comparison_subquery()

        base_filter = and_(
            comp.c.rank == 1,
            comp.c.mismatch_found.is_(True),
            comp.c.comparison_state == "COMPLETED",
            EmailMessageRecord.processing_status == "COMPLETED",
        )

        counts_query = (
            select(
                func.count().label("total"),
                func.count().filter(comp.c.resolution_status == "OPEN").label("open_count"),
                func.count().filter(comp.c.resolution_status == "ACKNOWLEDGED").label("acknowledged_count"),
                func.count().filter(comp.c.resolution_status == "RESOLVED").label("resolved_count"),
            )
            .select_from(EmailMessageRecord)
            .join(comp, comp.c.email_id == EmailMessageRecord.id)
            .where(base_filter)
        )
        counts_row = self.session.execute(counts_query).one()
        counts = {
            "total": int(counts_row.total or 0),
            "open_count": int(counts_row.open_count or 0),
            "acknowledged_count": int(counts_row.acknowledged_count or 0),
            "resolved_count": int(counts_row.resolved_count or 0),
        }

        statement = (
            select(ComparisonResultRecord)
            .join(EmailMessageRecord, EmailMessageRecord.id == ComparisonResultRecord.email_id)
            .where(
                ComparisonResultRecord.id == comp.c.id,
                base_filter,
            )
            .options(
                selectinload(ComparisonResultRecord.fields),
                selectinload(ComparisonResultRecord.email),
                selectinload(ComparisonResultRecord.overrides),
            )
            .order_by(ComparisonResultRecord.created_at.desc(), ComparisonResultRecord.id.desc())
        )

        if status and status != "ALL":
            statement = statement.where(comp.c.resolution_status == status)

        if search:
            pattern = f"%{search}%"
            statement = statement.where(
                or_(
                    EmailMessageRecord.subject.ilike(pattern),
                    EmailMessageRecord.sender.ilike(pattern),
                    EmailMessageRecord.external_message_id.ilike(pattern),
                )
            )

        filtered_count_query = select(func.count()).select_from(statement.order_by(None).subquery())
        total_filtered = int(self.session.scalar(filtered_count_query) or 0)

        rows = self.session.scalars(statement.offset(skip).limit(limit)).all()
        return rows, total_filtered, counts

    def get_discrepancy(self, comparison_id_or_email_id: UUID) -> ComparisonResultRecord | None:
        comp = self.session.scalar(
            select(ComparisonResultRecord)
            .where(
                or_(
                    ComparisonResultRecord.id == comparison_id_or_email_id,
                    ComparisonResultRecord.email_id == comparison_id_or_email_id,
                )
            )
            .options(
                selectinload(ComparisonResultRecord.fields),
                selectinload(ComparisonResultRecord.email).selectinload(EmailMessageRecord.attachments),
                selectinload(ComparisonResultRecord.email).selectinload(EmailMessageRecord.documents),
                selectinload(ComparisonResultRecord.email).selectinload(EmailMessageRecord.processing_events),
                selectinload(ComparisonResultRecord.overrides),
            )
            .order_by(ComparisonResultRecord.created_at.desc(), ComparisonResultRecord.id.desc())
        )
        return comp

    def acknowledge(
        self,
        comparison_id: UUID,
        *,
        operator_name: str | None = None,
    ) -> ComparisonResultRecord:
        record = self._locked_comparison(comparison_id)
        if not record.mismatch_found:
            raise DiscrepancyConflictError("Cannot acknowledge a comparison that is not a mismatch")

        # Idempotent return if already acknowledged or resolved
        if record.resolution_status == "ACKNOWLEDGED":
            return record
        if record.resolution_status == "RESOLVED":
            # Disallowed backwards transition from RESOLVED to ACKNOWLEDGED
            return record

        now = self._now()
        record.resolution_status = "ACKNOWLEDGED"
        record.acknowledged_at = now
        record.acknowledged_by = self._optional_text(operator_name, "operator_name", 255)
        record.updated_at = now

        self._event(
            record.email_id,
            "DISCREPANCY_ACKNOWLEDGED",
            actor_name=record.acknowledged_by,
            details={"comparison_id": str(record.id)},
        )
        self.session.flush()
        return record

    def resolve(
        self,
        comparison_id: UUID,
        *,
        operator_name: str | None = None,
        notes: str | None = None,
    ) -> ComparisonResultRecord:
        record = self._locked_comparison(comparison_id)
        if not record.mismatch_found:
            raise DiscrepancyConflictError("Cannot resolve a comparison that is not a mismatch")

        # Idempotent return if already resolved with same notes
        if record.resolution_status == "RESOLVED" and (notes is None or record.resolution_notes == notes):
            return record

        now = self._now()
        actor = self._optional_text(operator_name, "operator_name", 255) or record.acknowledged_by
        record.resolution_status = "RESOLVED"
        record.resolved_at = now
        record.resolved_by = actor
        if notes is not None:
            record.resolution_notes = self._optional_text(notes, "notes", 4000)
        record.updated_at = now

        self._event(
            record.email_id,
            "DISCREPANCY_RESOLVED",
            actor_name=actor,
            details={
                "comparison_id": str(record.id),
                "notes": record.resolution_notes,
            },
        )
        self.session.flush()
        return record

    def add_override(
        self,
        comparison_id: UUID,
        *,
        document_side: str,
        field_name: str,
        corrected_value: Any,
        reviewer_name: str | None = None,
        note: str | None = None,
    ) -> HumanReviewFieldOverrideRecord:
        record = self._locked_comparison(comparison_id)
        side = document_side.strip().upper()
        if side not in {"SI", "BL"}:
            raise ValueError("document_side must be SI or BL")
        try:
            canonical_field = CanonicalField(field_name)
        except ValueError as exc:
            raise ValueError("field_name must be one of the seven canonical fields") from exc

        canonical = self._canonical_override(canonical_field, corrected_value)

        comp_field = next(
            (row for row in record.fields if row.field_name == canonical_field.value),
            None,
        )
        if comp_field is None:
            raise DiscrepancyConflictError("Comparison has no matching field for override")
        original_field_id = comp_field.si_field_id if side == "SI" else comp_field.bl_field_id

        # Deactivate previous active override for this comparison + side + field
        previous = self.session.scalar(
            select(HumanReviewFieldOverrideRecord).where(
                HumanReviewFieldOverrideRecord.comparison_result_id == record.id,
                HumanReviewFieldOverrideRecord.document_side == side,
                HumanReviewFieldOverrideRecord.field_name == canonical_field.value,
                HumanReviewFieldOverrideRecord.active.is_(True),
            )
        )
        if previous is not None:
            previous.active = False
            self.session.flush()

        override = HumanReviewFieldOverrideRecord(
            review_case_id=None,
            comparison_result_id=record.id,
            document_side=side,
            field_name=canonical_field.value,
            original_field_id=original_field_id,
            corrected_value=corrected_value,
            corrected_canonical_value=canonical,
            reviewer_name=self._optional_text(reviewer_name, "reviewer_name", 255),
            note=self._optional_text(note, "note", 4000),
            active=True,
            supersedes_override_id=previous.id if previous else None,
        )
        self.session.add(override)
        self.session.flush()

        self._event(
            record.email_id,
            "FIELD_OVERRIDE_REPLACED" if previous else "FIELD_OVERRIDE_ADDED",
            actor_name=override.reviewer_name,
            details={
                "override_id": str(override.id),
                "comparison_id": str(record.id),
                "document_side": side,
                "field_name": canonical_field.value,
            },
        )
        return override

    def recompare(
        self,
        comparison_id: UUID,
        *,
        reviewer_name: str | None = None,
    ) -> ComparisonResultRecord:
        source = self._locked_comparison(comparison_id)
        email = self.session.get(EmailMessageRecord, source.email_id)
        if email is None:
            raise DiscrepancyConflictError("Owning email message not found")

        si_record = DocumentExtractionRepository(self.session).get(source.si_extraction_id)
        bl_record = DocumentExtractionRepository(self.session).get(source.bl_extraction_id)
        if si_record is None or bl_record is None:
            raise DiscrepancyConflictError("Source extractions no longer exist")

        si_result, si_fields = PersistedComparisonService._to_domain(si_record, "SI")
        bl_result, bl_fields = PersistedComparisonService._to_domain(bl_record, "DRAFT_BL")

        # Collect active overrides for this comparison chain
        active_overrides = self.session.scalars(
            select(HumanReviewFieldOverrideRecord)
            .where(
                HumanReviewFieldOverrideRecord.comparison_result_id == source.id,
                HumanReviewFieldOverrideRecord.active.is_(True),
            )
            .order_by(HumanReviewFieldOverrideRecord.created_at, HumanReviewFieldOverrideRecord.id)
        ).all()

        si_result = self._overlay(si_result, active_overrides, side="SI")
        bl_result = self._overlay(bl_result, active_overrides, side="BL")

        transition(self.session, email, "COMPARING", "DISCREPANCY_RECOMPARISON_STARTED")
        batch = ComparisonService().compare(si_result, bl_result)
        version = self._discrepancy_version(source.id, active_overrides)

        new_record = ComparisonResultRepository(self.session).upsert_result(
            email_id=email.id,
            si_extraction_id=source.si_extraction_id,
            bl_extraction_id=source.bl_extraction_id,
            comparison_version=version,
            batch=batch,
            si_fields=si_fields,
            bl_fields=bl_fields,
        )
        new_record.supersedes_comparison_id = source.id
        new_record.review_case_id = None

        # Carry forward / link active overrides to the new comparison result
        for override in active_overrides:
            override.comparison_result_id = new_record.id

        if batch.mismatch_found:
            new_record.resolution_status = "OPEN"
        else:
            new_record.resolution_status = None
            new_record.acknowledged_at = None
            new_record.acknowledged_by = None
            new_record.resolved_at = None
            new_record.resolved_by = None
            new_record.resolution_notes = None

        transition(self.session, email, batch.comparison_state, batch.reason_code)

        actor = self._optional_text(reviewer_name, "reviewer_name", 255)
        self._event(
            email.id,
            "RECOMPARISON_COMPLETED",
            actor_name=actor,
            details={
                "previous_comparison_id": str(source.id),
                "new_comparison_id": str(new_record.id),
                "mismatch_found": batch.mismatch_found,
                "mismatched_fields": [f.value for f in batch.mismatched_fields],
            },
        )
        self.session.flush()
        return new_record

    def _locked_comparison(self, comparison_id: UUID) -> ComparisonResultRecord:
        record = self.session.scalar(
            select(ComparisonResultRecord)
            .where(
                or_(
                    ComparisonResultRecord.id == comparison_id,
                    ComparisonResultRecord.email_id == comparison_id,
                )
            )
            .order_by(ComparisonResultRecord.created_at.desc(), ComparisonResultRecord.id.desc())
            .options(
                selectinload(ComparisonResultRecord.fields),
                selectinload(ComparisonResultRecord.overrides),
            )
            .with_for_update()
        )
        if record is None:
            raise LookupError("Comparison result not found")
        return record

    @staticmethod
    def _overlay(
        result: DocumentExtractionResult,
        overrides: list[HumanReviewFieldOverrideRecord],
        *,
        side: str,
    ) -> DocumentExtractionResult:
        fields = dict(result.fields)
        for override in overrides:
            if override.document_side != side:
                continue
            name = CanonicalField(override.field_name)
            original = fields[name]
            fields[name] = replace(
                original,
                raw_value=original.raw_value,
                canonical_value=override.corrected_canonical_value,
                status=FieldStatus.RESOLVED,
                confidence=1.0,
                evidence={
                    **original.evidence,
                    "discrepancy_override_id": str(override.id),
                    "discrepancy_override": True,
                    "human_override_value": override.corrected_value,
                },
            )
        return DocumentExtractionResult(
            document_role=result.document_role,
            fields=fields,
            extractor_version=result.extractor_version,
        )

    @staticmethod
    def _canonical_override(field_name: CanonicalField, corrected_value: Any) -> Any:
        if corrected_value is None or (isinstance(corrected_value, str) and not corrected_value.strip()):
            raise ValueError("corrected_value must not be empty")
        canonical, _ = DeterministicDocumentExtractor._canonicalize(field_name, corrected_value)
        if canonical is None:
            raise ValueError("corrected value cannot be canonicalized safely")
        if field_name == CanonicalField.CONTAINER_COUNT:
            if isinstance(canonical, bool) or not isinstance(canonical, int) or canonical < 0:
                raise ValueError("container_count canonical value must be a non-negative integer")
        elif field_name == CanonicalField.GROSS_WEIGHT_KG:
            if isinstance(canonical, bool) or not isinstance(canonical, (int, float)) or canonical < 0:
                raise ValueError("gross_weight_kg canonical value must be a non-negative number")
        elif not isinstance(canonical, str) or not canonical.strip():
            raise ValueError(f"{field_name.value} canonical value must be a non-empty string")
        return canonical

    @staticmethod
    def _discrepancy_version(comparison_id: UUID, overrides: list[HumanReviewFieldOverrideRecord]) -> str:
        payload = json.dumps(
            [(str(item.id), item.corrected_canonical_value) for item in overrides],
            sort_keys=True,
            default=str,
        ).encode()
        digest = hashlib.sha256(payload).hexdigest()[:12]
        return f"{COMPARISON_VERSION}+discrepancy-{comparison_id.hex[:12]}-{digest}"

    def _event(
        self,
        email_id: UUID,
        action: str,
        *,
        actor_name: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.session.add(
            ProcessingEventRecord(
                email_id=email_id,
                old_status="COMPLETED",
                new_status="COMPLETED",
                reason_code=action,
            )
        )
        self.session.flush()

    @staticmethod
    def _required_text(value: str, field: str, max_length: int) -> str:
        resolved = value.strip() if isinstance(value, str) else ""
        if not resolved:
            raise ValueError(f"{field} must not be empty")
        if len(resolved) > max_length:
            raise ValueError(f"{field} must be at most {max_length} characters")
        return resolved

    @classmethod
    def _optional_text(cls, value: str | None, field: str, max_length: int) -> str | None:
        if value is None:
            return None
        return cls._required_text(value, field, max_length)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
