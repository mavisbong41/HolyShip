from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.ai_review.context import build_case_context
from backend.app.ai_review.providers import AIReviewProvider, get_ai_review_provider
from backend.app.ai_review.safety import evaluate_safety_gate
from backend.app.ai_review.schema import AIStructuredResponse
from backend.app.core.config import Settings, get_settings
from backend.app.review.service import HumanReviewService, ReviewConflictError
from backend.app.storage.models import (
    AISuggestionRecord,
    ComparisonResultRecord,
    HumanReviewCaseRecord,
    HumanReviewEventRecord,
)


def _clean_json_str(text: str) -> str:
    cleaned = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if match:
        cleaned = match.group(1).strip()
    return cleaned


class AIReviewService:
    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        provider: AIReviewProvider | None = None,
    ):
        self.session = session
        self.settings = settings or get_settings()
        self.provider = provider or get_ai_review_provider(self.settings)

    def ask(
        self,
        case_id: UUID,
        question: str,
    ) -> tuple[AIStructuredResponse, AISuggestionRecord | None, str, str]:
        case = self.session.get(HumanReviewCaseRecord, case_id)
        if case is None:
            raise LookupError(f"Human review case {case_id} not found")

        q_clean = question.strip()
        if not q_clean:
            raise ValueError("question must not be empty")

        context = build_case_context(self.session, case_id)
        raw_text, provider_name, provider_model = self.provider.generate_review_response(
            context,
            q_clean,
        )
        gateway_audit = dict(getattr(self.provider, "last_audit_metadata", {}) or {})

        try:
            parsed = json.loads(_clean_json_str(raw_text))
            structured = AIStructuredResponse.model_validate(parsed)
        except Exception:
            clean_msg = raw_text.strip() if raw_text and raw_text.strip() else "AI explanation provided, but structured output was inconclusive."
            structured = AIStructuredResponse(
                message=clean_msg,
                mode="EXPLANATION_ONLY" if clean_msg and not clean_msg.startswith("AI explanation") else "INSUFFICIENT_EVIDENCE",
                suggestion=None,
            )

        # Apply safety gate
        safe_response = evaluate_safety_gate(
            context,
            structured,
            confidence_threshold=self.settings.ai_review_confidence_threshold,
        )

        suggestion_record: AISuggestionRecord | None = None
        if safe_response.mode == "ACTIONABLE_SUGGESTION" and safe_response.suggestion:
            suggestion_payload = safe_response.suggestion
            suggestion_record = AISuggestionRecord(
                human_review_case_id=case.id,
                mode=safe_response.mode,
                message=safe_response.message,
                document_side=suggestion_payload.document_side,
                field=suggestion_payload.field,
                current_value=suggestion_payload.current_value,
                suggested_value=suggestion_payload.suggested_value,
                confidence=suggestion_payload.confidence,
                reason=suggestion_payload.reason,
                evidence_refs=suggestion_payload.evidence_refs,
                provider_name=provider_name,
                provider_model=provider_model,
                status="PENDING",
            )
            self.session.add(suggestion_record)
            self.session.flush()

            self._record_event(
                case_id=case.id,
                action="AI_SUGGESTION_CREATED",
                details={
                    "suggestion_id": str(suggestion_record.id),
                    "document_side": suggestion_record.document_side,
                    "field": suggestion_record.field,
                    "suggested_value": suggestion_record.suggested_value,
                    "confidence": suggestion_record.confidence,
                    "evidence_refs": suggestion_record.evidence_refs,
                    "provider_name": provider_name,
                    "provider_model": provider_model,
                    "ai_gateway": gateway_audit,
                },
            )

        self._record_event(
            case_id=case.id,
            action="AI_ASSISTANT_ASKED",
            details={
                "question_sha256": hashlib.sha256(q_clean.encode("utf-8")).hexdigest(),
                "question_length": len(q_clean),
                "mode": safe_response.mode,
                "provider_name": provider_name,
                "provider_model": provider_model,
                "ai_gateway": gateway_audit,
            },
        )
        self.session.flush()

        return safe_response, suggestion_record, provider_name, provider_model

    def accept(
        self,
        case_id: UUID,
        suggestion_id: UUID,
        *,
        reviewer_label: str,
    ) -> tuple[HumanReviewCaseRecord, ComparisonResultRecord]:
        suggestion = self._locked_suggestion(case_id, suggestion_id)
        if suggestion.status != "PENDING":
            raise ReviewConflictError(f"Suggestion {suggestion_id} is already in {suggestion.status} status")

        reviewer = reviewer_label.strip() if isinstance(reviewer_label, str) else ""
        if not reviewer:
            raise ValueError("reviewer_label must not be empty")

        if not suggestion.document_side or not suggestion.field or suggestion.suggested_value is None:
            raise ReviewConflictError("Suggestion is missing actionable field data")

        hr_svc = HumanReviewService(self.session)
        override = hr_svc.add_override(
            case_id,
            document_side=suggestion.document_side,
            field_name=suggestion.field,
            corrected_value=suggestion.suggested_value,
            corrected_canonical_value=None,
            reviewer_name=reviewer,
            note=f"Applied from AI Suggestion ({suggestion.reason or 'Verified'})",
        )
        override.ai_suggestion_id = suggestion.id

        suggestion.status = "ACCEPTED"
        self.session.flush()

        self._record_event(
            case_id=case_id,
            action="AI_SUGGESTION_ACCEPTED",
            actor_name=reviewer,
            details={
                "suggestion_id": str(suggestion.id),
                "document_side": suggestion.document_side,
                "field": suggestion.field,
                "suggested_value": suggestion.suggested_value,
                "override_id": str(override.id),
            },
        )

        case, comparison = hr_svc.resolve_and_recompare(case_id, reviewer_name=reviewer)
        return case, comparison

    def apply_edited(
        self,
        case_id: UUID,
        suggestion_id: UUID,
        *,
        reviewer_value: str,
        reviewer_label: str,
        note: str | None = None,
    ) -> tuple[HumanReviewCaseRecord, ComparisonResultRecord]:
        suggestion = self._locked_suggestion(case_id, suggestion_id)
        if suggestion.status != "PENDING":
            raise ReviewConflictError(f"Suggestion {suggestion_id} is already in {suggestion.status} status")

        reviewer = reviewer_label.strip() if isinstance(reviewer_label, str) else ""
        if not reviewer:
            raise ValueError("reviewer_label must not be empty")

        val_clean = reviewer_value.strip() if isinstance(reviewer_value, str) else ""
        if not val_clean:
            raise ValueError("reviewer_value must not be empty")

        if not suggestion.document_side or not suggestion.field:
            raise ReviewConflictError("Suggestion is missing field target")

        hr_svc = HumanReviewService(self.session)
        override = hr_svc.add_override(
            case_id,
            document_side=suggestion.document_side,
            field_name=suggestion.field,
            corrected_value=val_clean,
            corrected_canonical_value=None,
            reviewer_name=reviewer,
            note=note or f"Edited from AI Suggestion (proposed: {suggestion.suggested_value})",
        )
        override.ai_suggestion_id = suggestion.id

        suggestion.status = "EDITED_APPLIED"
        self.session.flush()

        self._record_event(
            case_id=case_id,
            action="AI_SUGGESTION_EDITED",
            actor_name=reviewer,
            details={
                "suggestion_id": str(suggestion.id),
                "document_side": suggestion.document_side,
                "field": suggestion.field,
                "ai_proposed_value": suggestion.suggested_value,
                "reviewer_applied_value": val_clean,
                "note": note,
                "override_id": str(override.id),
            },
        )

        case, comparison = hr_svc.resolve_and_recompare(case_id, reviewer_name=reviewer)
        return case, comparison

    def dismiss(
        self,
        case_id: UUID,
        suggestion_id: UUID,
        *,
        reviewer_label: str,
    ) -> AISuggestionRecord:
        suggestion = self._locked_suggestion(case_id, suggestion_id)
        if suggestion.status != "PENDING":
            raise ReviewConflictError(f"Suggestion {suggestion_id} is already in {suggestion.status} status")

        reviewer = reviewer_label.strip() if isinstance(reviewer_label, str) else ""
        if not reviewer:
            raise ValueError("reviewer_label must not be empty")

        suggestion.status = "DISMISSED"
        self.session.flush()

        self._record_event(
            case_id=case_id,
            action="AI_SUGGESTION_DISMISSED",
            actor_name=reviewer,
            details={
                "suggestion_id": str(suggestion.id),
                "document_side": suggestion.document_side,
                "field": suggestion.field,
            },
        )
        self.session.flush()
        return suggestion

    def _locked_suggestion(self, case_id: UUID, suggestion_id: UUID) -> AISuggestionRecord:
        suggestion = self.session.scalar(
            select(AISuggestionRecord)
            .where(
                AISuggestionRecord.id == suggestion_id,
                AISuggestionRecord.human_review_case_id == case_id,
            )
            .with_for_update()
        )
        if suggestion is None:
            raise LookupError(f"AI suggestion {suggestion_id} not found for case {case_id}")
        return suggestion

    def _record_event(
        self,
        case_id: UUID,
        action: str,
        *,
        actor_name: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.session.add(
            HumanReviewEventRecord(
                review_case_id=case_id,
                action=action,
                actor_name=actor_name,
                details=details or {},
            )
        )
        self.session.flush()
