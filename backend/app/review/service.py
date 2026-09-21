from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.app.comparison.persistence import PersistedComparisonService
from backend.app.comparison.service import COMPARISON_VERSION, ComparisonService
from backend.app.extraction.extractor import DeterministicDocumentExtractor
from backend.app.extraction.models import CanonicalField, DocumentExtractionResult, FieldStatus
from backend.app.storage.models import (
    ComparisonResultRecord,
    EmailMessageRecord,
    ExtractedFieldRecord,
    FieldComparisonRecord,
    HumanReviewCaseRecord,
    HumanReviewEventRecord,
    HumanReviewFieldOverrideRecord,
)
from backend.app.storage.repositories import ComparisonResultRepository, DocumentExtractionRepository
from backend.app.storage.transitions import transition


ACTIVE_REVIEW_STATUSES = frozenset({"OPEN", "IN_REVIEW"})
ACTIONABLE_BLOCK_REASONS = frozenset(
    {
        "READINESS_UNRESOLVED",
        "MISSING_REQUIRED_ATTACHMENT",
        "WRONG_DOCUMENT_TYPE",
        "UNREADABLE_ATTACHMENT",
        "UNSUPPORTED_ATTACHMENT",
        "CORRUPTED_ATTACHMENT",
        "MULTIPLE_CANDIDATES",
        "DOCUMENT_ROLE_UNRESOLVED",
        "COMPARISON_UNRESOLVED",
    }
)


class ReviewConflictError(ValueError):
    """The requested mutation conflicts with the review lifecycle."""


class HumanReviewService:
    """Own active review cases without mutating extraction or comparison history."""

    def __init__(self, session: Session):
        self.session = session

    def ensure_actionable_case(
        self,
        email: EmailMessageRecord,
        *,
        reason_code: str,
        source_comparison_id: UUID | None = None,
        document_id: UUID | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> HumanReviewCaseRecord | None:
        if email.processing_status != "BLOCKED" or reason_code not in ACTIONABLE_BLOCK_REASONS:
            return None
        workflow_identity = self._workflow_identity(email, reason_code, source_comparison_id)
        existing = self.session.scalar(
            select(HumanReviewCaseRecord).where(
                HumanReviewCaseRecord.email_id == email.id,
                HumanReviewCaseRecord.reason_code == reason_code,
                HumanReviewCaseRecord.workflow_identity == workflow_identity,
                HumanReviewCaseRecord.status.in_(ACTIVE_REVIEW_STATUSES),
            )
        )
        if existing is not None:
            return existing

        case = HumanReviewCaseRecord(
            email_id=email.id,
            document_id=document_id,
            source_comparison_id=source_comparison_id,
            reason_code=reason_code,
            reason_text=self._reason_text(reason_code),
            evidence={"processing_status": email.processing_status, **(evidence or {})},
            candidate_scores={},
            status="OPEN",
            case_origin="ACTIVE",
            workflow_identity=workflow_identity,
        )
        try:
            with self.session.begin_nested():
                self.session.add(case)
                self.session.flush()
                self._event(case, "CASE_CREATED", details={"reason_code": reason_code})
        except IntegrityError:
            case = self.session.scalar(
                select(HumanReviewCaseRecord).where(
                    HumanReviewCaseRecord.email_id == email.id,
                    HumanReviewCaseRecord.reason_code == reason_code,
                    HumanReviewCaseRecord.workflow_identity == workflow_identity,
                    HumanReviewCaseRecord.status.in_(ACTIVE_REVIEW_STATUSES),
                )
            )
            if case is None:
                raise
        return case

    def claim(self, case_id: UUID, *, reviewer_name: str) -> HumanReviewCaseRecord:
        case = self._locked_case(case_id)
        reviewer = self._required_text(reviewer_name, "reviewer_name", 255)
        if case.status == "IN_REVIEW" and case.reviewer_name == reviewer:
            return case
        if case.status != "OPEN":
            raise ReviewConflictError(f"Cannot claim review case in {case.status} state")
        case.status = "IN_REVIEW"
        case.reviewer_name = reviewer
        case.updated_at = self._now()
        self._event(case, "CASE_CLAIMED", actor_name=reviewer)
        self.session.flush()
        return case

    def add_override(
        self,
        case_id: UUID,
        *,
        document_side: str,
        field_name: str,
        corrected_value: Any,
        corrected_canonical_value: Any | None,
        reviewer_name: str | None,
        note: str | None,
    ) -> HumanReviewFieldOverrideRecord:
        case = self._locked_case(case_id)
        if case.status not in ACTIVE_REVIEW_STATUSES:
            raise ReviewConflictError(f"Cannot change overrides in {case.status} state")
        side = document_side.strip().upper()
        if side not in {"SI", "BL"}:
            raise ValueError("document_side must be SI or BL")
        try:
            canonical_field = CanonicalField(field_name)
        except ValueError as exc:
            raise ValueError("field_name must be one of the seven canonical fields") from exc
        canonical = self._canonical_override(
            canonical_field,
            corrected_value,
            corrected_canonical_value,
        )
        source_comparison = self._source_comparison(case)
        comparison_field = next(
            (row for row in source_comparison.fields if row.field_name == canonical_field.value),
            None,
        )
        if comparison_field is None:
            raise ReviewConflictError("Review source comparison has no matching field")
        original_field_id = (
            comparison_field.si_field_id if side == "SI" else comparison_field.bl_field_id
        )
        previous = self.session.scalar(
            select(HumanReviewFieldOverrideRecord).where(
                HumanReviewFieldOverrideRecord.review_case_id == case.id,
                HumanReviewFieldOverrideRecord.document_side == side,
                HumanReviewFieldOverrideRecord.field_name == canonical_field.value,
                HumanReviewFieldOverrideRecord.active.is_(True),
            )
        )
        if previous is not None:
            previous.active = False
            self.session.flush()
        override = HumanReviewFieldOverrideRecord(
            review_case_id=case.id,
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
        case.overrides.append(override)
        case.status = "IN_REVIEW"
        if override.reviewer_name:
            case.reviewer_name = override.reviewer_name
        case.updated_at = self._now()
        self.session.flush()
        self._event(
            case,
            "FIELD_OVERRIDE_REPLACED" if previous else "FIELD_OVERRIDE_ADDED",
            actor_name=override.reviewer_name,
            details={
                "override_id": str(override.id),
                "document_side": side,
                "field_name": canonical_field.value,
            },
        )
        self.session.flush()
        return override

    def resolve_and_recompare(
        self,
        case_id: UUID,
        *,
        reviewer_name: str | None = None,
        notes: str | None = None,
    ) -> tuple[HumanReviewCaseRecord, ComparisonResultRecord]:
        case = self._locked_case(case_id)
        if case.status == "RESOLVED":
            existing = self.session.scalar(
                select(ComparisonResultRecord)
                .where(ComparisonResultRecord.review_case_id == case.id)
                .order_by(ComparisonResultRecord.created_at.desc(), ComparisonResultRecord.id.desc())
            )
            if existing is None:
                raise ReviewConflictError("Resolved case has no review comparison")
            return case, existing
        if case.status == "DISMISSED":
            raise ReviewConflictError("Dismissed cases cannot be resolved")

        actor = self._optional_text(reviewer_name, "reviewer_name", 255) or case.reviewer_name
        case.status = "IN_REVIEW"
        if actor:
            case.reviewer_name = actor
        if notes is not None:
            case.notes = self._optional_text(notes, "notes", 4000)
        case.updated_at = self._now()
        self._event(case, "RESOLVE_REQUESTED", actor_name=actor)

        source = self._source_comparison(case)
        si_record = DocumentExtractionRepository(self.session).get(source.si_extraction_id)
        bl_record = DocumentExtractionRepository(self.session).get(source.bl_extraction_id)
        if si_record is None or bl_record is None:
            raise ReviewConflictError("Review source extraction no longer exists")
        si_result, si_fields = PersistedComparisonService._to_domain(si_record, "SI")
        bl_result, bl_fields = PersistedComparisonService._to_domain(bl_record, "DRAFT_BL")

        active_overrides = self.session.scalars(
            select(HumanReviewFieldOverrideRecord)
            .where(
                HumanReviewFieldOverrideRecord.review_case_id == case.id,
                HumanReviewFieldOverrideRecord.active.is_(True),
            )
            .order_by(HumanReviewFieldOverrideRecord.created_at, HumanReviewFieldOverrideRecord.id)
        ).all()
        si_result = self._overlay(si_result, active_overrides, side="SI")
        bl_result = self._overlay(bl_result, active_overrides, side="BL")
        email = self.session.get(EmailMessageRecord, case.email_id)
        if email is None:
            raise ReviewConflictError("Review email no longer exists")

        transition(self.session, email, "COMPARING", "HUMAN_REVIEW_RECOMPARISON_STARTED")
        batch = ComparisonService().compare(si_result, bl_result)
        version = self._review_version(case.id, active_overrides)
        record = ComparisonResultRepository(self.session).upsert_result(
            email_id=email.id,
            si_extraction_id=source.si_extraction_id,
            bl_extraction_id=source.bl_extraction_id,
            comparison_version=version,
            batch=batch,
            si_fields=si_fields,
            bl_fields=bl_fields,
        )
        record.review_case_id = case.id
        record.supersedes_comparison_id = source.id
        transition(self.session, email, batch.comparison_state, batch.reason_code)
        self._event(
            case,
            "RECOMPARISON_COMPLETED",
            actor_name=actor,
            details={
                "comparison_result_id": str(record.id),
                "comparison_state": batch.comparison_state,
                "unresolved_fields": [field.value for field in batch.unresolved_fields],
            },
        )
        if batch.all_fields_definite:
            case.status = "RESOLVED"
            case.resolution = "RECOMPARISON_COMPLETED"
            case.resolved_at = self._now()
            self._event(case, "CASE_RESOLVED", actor_name=actor)
        else:
            case.status = "IN_REVIEW"
            case.resolution = None
            case.resolved_at = None
        case.updated_at = self._now()
        self.session.flush()
        return case, record

    def dismiss(
        self,
        case_id: UUID,
        *,
        reviewer_name: str | None,
        reason: str,
        notes: str | None = None,
    ) -> HumanReviewCaseRecord:
        case = self._locked_case(case_id)
        if case.status == "DISMISSED":
            return case
        if case.status == "RESOLVED":
            raise ReviewConflictError("Resolved cases cannot be dismissed")
        actor = self._optional_text(reviewer_name, "reviewer_name", 255) or case.reviewer_name
        case.status = "DISMISSED"
        case.reviewer_name = actor
        case.resolution = self._required_text(reason, "reason", 80)
        case.notes = self._optional_text(notes, "notes", 4000)
        case.resolved_at = self._now()
        case.updated_at = case.resolved_at
        self._event(case, "CASE_DISMISSED", actor_name=actor, details={"reason": case.resolution})
        self.session.flush()
        return case

    def _source_comparison(self, case: HumanReviewCaseRecord) -> ComparisonResultRecord:
        statement = (
            select(ComparisonResultRecord)
            .where(ComparisonResultRecord.email_id == case.email_id)
            .options(selectinload(ComparisonResultRecord.fields))
            .order_by(ComparisonResultRecord.created_at.desc(), ComparisonResultRecord.id.desc())
        )
        if case.source_comparison_id is not None:
            statement = statement.where(ComparisonResultRecord.id == case.source_comparison_id)
        record = self.session.scalar(statement)
        if record is None or len(record.fields) != 7:
            raise ReviewConflictError("This review case has no complete source comparison")
        return record

    def _locked_case(self, case_id: UUID) -> HumanReviewCaseRecord:
        case = self.session.scalar(
            select(HumanReviewCaseRecord)
            .where(HumanReviewCaseRecord.id == case_id)
            .with_for_update()
        )
        if case is None:
            raise LookupError("Human review case not found")
        return case

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
                raw_value=override.corrected_value,
                canonical_value=override.corrected_canonical_value,
                status=FieldStatus.RESOLVED,
                confidence=1.0,
                evidence={
                    **original.evidence,
                    "review_override_id": str(override.id),
                    "review_override": True,
                },
            )
        return DocumentExtractionResult(
            document_role=result.document_role,
            fields=fields,
            extractor_version=result.extractor_version,
        )

    @staticmethod
    def _canonical_override(
        field_name: CanonicalField,
        corrected_value: Any,
        corrected_canonical_value: Any | None,
    ) -> Any:
        if corrected_value is None or (isinstance(corrected_value, str) and not corrected_value.strip()):
            raise ValueError("corrected_value must not be empty")
        canonical = corrected_canonical_value
        if canonical is None:
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
    def _workflow_identity(
        email: EmailMessageRecord,
        reason_code: str,
        source_comparison_id: UUID | None,
    ) -> str:
        if source_comparison_id is not None:
            return f"comparison:{source_comparison_id}"
        return f"workflow:{email.content_hash}:{reason_code}"

    @staticmethod
    def _review_version(
        case_id: UUID,
        overrides: list[HumanReviewFieldOverrideRecord],
    ) -> str:
        payload = json.dumps(
            [(str(item.id), item.corrected_canonical_value) for item in overrides],
            sort_keys=True,
            default=str,
        ).encode()
        digest = hashlib.sha256(payload).hexdigest()[:12]
        return f"{COMPARISON_VERSION}+review-{case_id.hex[:12]}-{digest}"

    def _event(
        self,
        case: HumanReviewCaseRecord,
        action: str,
        *,
        actor_name: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.session.add(
            HumanReviewEventRecord(
                review_case_id=case.id,
                action=action,
                actor_name=actor_name,
                details=details or {},
            )
        )
        self.session.flush()

    @staticmethod
    def _reason_text(reason_code: str) -> str:
        return reason_code.replace("_", " ").title()

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
