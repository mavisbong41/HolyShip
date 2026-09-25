from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.extraction.models import CanonicalField
from backend.app.review.service import HumanReviewService, ReviewConflictError
from backend.app.storage.models import (
    AISuggestionRecord,
    AuditEventRecord,
    HumanReviewCaseRecord,
    ReviewPlanItemRecord,
    ReviewPlanRecord,
    utcnow,
)


@dataclass(frozen=True)
class PlanItemInput:
    document_side: str
    field_name: str
    proposed_value: Any
    current_value: Any = None
    reason: str = ""
    confidence: float | None = None
    ai_suggestion_id: UUID | None = None
    status: str = "PROPOSED"


class ReviewPlanApplyError(RuntimeError):
    """Re-comparison failed after approved overrides were durably saved."""

    def __init__(self, plan: ReviewPlanRecord, cause: Exception):
        super().__init__(f"Approved overrides were saved, but re-comparison failed: {cause}")
        self.plan = plan
        self.cause = cause


class ReviewPlanService:
    def __init__(self, session: Session):
        self.session = session

    def create(self, case_id: UUID, *, items: list[PlanItemInput], created_by: str | None) -> ReviewPlanRecord:
        case = self.session.get(HumanReviewCaseRecord, case_id)
        if case is None:
            raise LookupError("Human review case not found")
        if case.status not in {"OPEN", "IN_REVIEW"} or case.case_origin != "ACTIVE":
            raise ReviewConflictError("Review plans require an active Human Review case")
        if not items:
            raise ValueError("A review plan must contain at least one action")
        plan = ReviewPlanRecord(review_case_id=case_id, created_by=self._text(created_by))
        self.session.add(plan)
        self.session.flush()
        seen: set[tuple[str, str]] = set()
        for incoming in items:
            side = incoming.document_side.strip().upper()
            if side not in {"SI", "BL"}:
                raise ValueError("document_side must be SI or BL")
            try:
                field = CanonicalField(incoming.field_name).value
            except ValueError as exc:
                raise ValueError("field_name must be one of the seven canonical fields") from exc
            target = (side, field)
            if target in seen:
                raise ValueError(f"Duplicate review plan target: {side}.{field}")
            seen.add(target)
            if incoming.status not in {"PROPOSED", "APPROVED", "REJECTED"}:
                raise ValueError("New plan item status must be PROPOSED, APPROVED, or REJECTED")
            if incoming.ai_suggestion_id is not None:
                suggestion = self.session.get(AISuggestionRecord, incoming.ai_suggestion_id)
                if suggestion is None or suggestion.human_review_case_id != case_id:
                    raise ValueError("AI suggestion does not belong to this review case")
            plan.items.append(ReviewPlanItemRecord(
                ai_suggestion_id=incoming.ai_suggestion_id,
                document_side=side,
                field_name=field,
                current_value=incoming.current_value,
                proposed_value=incoming.proposed_value,
                reason=incoming.reason.strip(),
                confidence=incoming.confidence,
                status=incoming.status,
            ))
        self._audit(
            "REVIEW_PLAN_CREATED",
            plan,
            created_by,
            {
                "item_count": len(items),
                "manual_item_count": sum(1 for item in items if item.ai_suggestion_id is None),
                "sources": sorted({"MANUAL" if item.ai_suggestion_id is None else "AI" for item in items}),
            },
        )
        self.session.flush()
        return self.get(plan.id)

    def get(self, plan_id: UUID, *, lock: bool = False) -> ReviewPlanRecord:
        statement = select(ReviewPlanRecord).where(ReviewPlanRecord.id == plan_id).options(selectinload(ReviewPlanRecord.items))
        if lock:
            statement = statement.with_for_update()
        plan = self.session.scalar(statement)
        if plan is None:
            raise LookupError("Review plan not found")
        return plan

    def list_for_case(self, case_id: UUID) -> list[ReviewPlanRecord]:
        return list(self.session.scalars(
            select(ReviewPlanRecord)
            .where(ReviewPlanRecord.review_case_id == case_id)
            .options(selectinload(ReviewPlanRecord.items))
            .order_by(ReviewPlanRecord.created_at.desc(), ReviewPlanRecord.id.desc())
        ).all())

    def update_item(self, plan_id: UUID, item_id: UUID, *, status: str, edited_value: Any = None) -> ReviewPlanRecord:
        plan = self.get(plan_id, lock=True)
        if plan.status != "DRAFT":
            raise ReviewConflictError("Only a draft review plan can be edited")
        item = next((row for row in plan.items if row.id == item_id), None)
        if item is None:
            raise LookupError("Review plan item not found")
        if status not in {"APPROVED", "EDITED", "REJECTED"}:
            raise ValueError("status must be APPROVED, EDITED, or REJECTED")
        if status == "EDITED" and edited_value is None:
            raise ValueError("edited_value is required for EDITED actions")
        item.status = status
        item.human_edited_value = edited_value if status == "EDITED" else None
        item.updated_at = utcnow()
        self.session.flush()
        return plan

    def add_item(self, plan_id: UUID, *, item: PlanItemInput, actor: str | None) -> ReviewPlanRecord:
        plan = self.get(plan_id, lock=True)
        if plan.status != "DRAFT":
            raise ReviewConflictError("Manual corrections can only be added to a draft review plan")
        side = item.document_side.strip().upper()
        if side not in {"SI", "BL"}:
            raise ValueError("document_side must be SI or BL")
        try:
            field = CanonicalField(item.field_name).value
        except ValueError as exc:
            raise ValueError("field_name must be one of the seven canonical fields") from exc
        if any(row.document_side == side and row.field_name == field for row in plan.items):
            raise ValueError(f"Duplicate review plan target: {side}.{field}")
        if item.ai_suggestion_id is not None:
            raise ValueError("This endpoint only accepts reviewer-authored manual corrections")
        row = ReviewPlanItemRecord(
            ai_suggestion_id=None,
            document_side=side,
            field_name=field,
            current_value=item.current_value,
            proposed_value=item.proposed_value,
            reason=item.reason.strip(),
            confidence=None,
            status=item.status if item.status in {"PROPOSED", "APPROVED", "REJECTED"} else "PROPOSED",
        )
        plan.items.append(row)
        self.session.flush()
        self._audit(
            "REVIEW_PLAN_MANUAL_ITEM_ADDED", plan, actor,
            {"item_id": str(row.id), "document_side": side, "field": field, "source": "MANUAL"},
        )
        return plan

    def remove_manual_item(self, plan_id: UUID, item_id: UUID, *, actor: str | None) -> ReviewPlanRecord:
        plan = self.get(plan_id, lock=True)
        if plan.status != "DRAFT":
            raise ReviewConflictError("Manual corrections can only be removed from a draft review plan")
        item = next((row for row in plan.items if row.id == item_id), None)
        if item is None:
            raise LookupError("Review plan item not found")
        if item.ai_suggestion_id is not None:
            raise ReviewConflictError("AI-proposed actions must be rejected rather than removed")
        self._audit(
            "REVIEW_PLAN_MANUAL_ITEM_REMOVED", plan, actor,
            {"item_id": str(item.id), "document_side": item.document_side, "field": item.field_name, "source": "MANUAL"},
        )
        plan.items.remove(item)
        self.session.delete(item)
        self.session.flush()
        return plan

    def cancel(self, plan_id: UUID, *, actor: str | None) -> ReviewPlanRecord:
        plan = self.get(plan_id, lock=True)
        if plan.status == "CANCELLED":
            return plan
        if plan.status != "DRAFT":
            raise ReviewConflictError("Only a draft review plan can be cancelled")
        plan.status = "CANCELLED"
        self._audit("REVIEW_PLAN_CANCELLED", plan, actor, {"item_count": len(plan.items)})
        self.session.flush()
        return plan

    def confirm(self, plan_id: UUID, *, confirmed_by: str) -> ReviewPlanRecord:
        actor = self._text(confirmed_by)
        if not actor:
            raise ValueError("confirmed_by must not be empty")
        plan = self.get(plan_id, lock=True)
        if plan.status == "APPLIED":
            return plan
        retrying = plan.status == "APPLY_FAILED"
        if plan.status not in {"DRAFT", "APPLY_FAILED"}:
            raise ReviewConflictError(f"Cannot confirm review plan in {plan.status} state")
        selected = [
            item for item in plan.items
            if item.status in ({"APPLIED"} if retrying else {"APPROVED", "EDITED"})
        ]
        if not selected:
            raise ValueError("No approved review-plan actions are available to apply")

        if not retrying:
            review = HumanReviewService(self.session)
            for item in selected:
                value = item.human_edited_value if item.status == "EDITED" else item.proposed_value
                review.add_override(
                    plan.review_case_id,
                    document_side=item.document_side,
                    field_name=item.field_name,
                    corrected_value=value,
                    corrected_canonical_value=None,
                    reviewer_name=actor,
                    note=f"Applied from review plan {plan.id}: {item.reason}".strip(),
                )
                item.status = "APPLIED"
        plan.status = "CONFIRMED"
        plan.confirmed_at = utcnow()
        plan.confirmed_by = actor
        plan.error_message = None
        self._audit(
            "REVIEW_PLAN_RETRY_STARTED" if retrying else "REVIEW_PLAN_CONFIRMED",
            plan,
            actor,
            {"applied_item_count": len(selected)},
        )
        # This commit is intentional: approved human decisions survive a later
        # re-comparison/provider/database failure and can be retried safely.
        self.session.commit()

        try:
            _, comparison = HumanReviewService(self.session).resolve_and_recompare(
                plan.review_case_id, reviewer_name=actor
            )
            plan = self.get(plan.id, lock=True)
            plan.status = "APPLIED"
            plan.applied_comparison_id = comparison.id
            plan.error_message = None
            self._audit("REVIEW_PLAN_APPLIED", plan, actor, {"comparison_result_id": str(comparison.id)})
            self.session.commit()
            return self.get(plan.id)
        except Exception as exc:
            self.session.rollback()
            plan = self.get(plan.id, lock=True)
            plan.status = "APPLY_FAILED"
            plan.error_message = f"{type(exc).__name__}: {exc}"[:4000]
            self._audit("REVIEW_PLAN_RECOMPARISON_FAILED", plan, actor, {"error_type": type(exc).__name__})
            self.session.commit()
            raise ReviewPlanApplyError(plan, exc) from exc

    def _audit(self, event: str, plan: ReviewPlanRecord, actor: str | None, metadata: dict[str, Any]) -> None:
        self.session.add(AuditEventRecord(
            event_type=event,
            actor_type="USER" if actor else "SYSTEM",
            actor_name=self._text(actor),
            source="HUMAN_REVIEW",
            entity_type="REVIEW_PLAN",
            entity_id=plan.id,
            metadata_json={"review_case_id": str(plan.review_case_id), **metadata},
        ))

    @staticmethod
    def _text(value: str | None) -> str | None:
        clean = value.strip() if isinstance(value, str) else ""
        return clean or None
