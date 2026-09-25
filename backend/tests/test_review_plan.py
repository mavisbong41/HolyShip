from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from backend.app.review.plan_service import PlanItemInput, ReviewPlanApplyError, ReviewPlanService
from backend.app.storage.models import ReviewPlanItemRecord, ReviewPlanRecord


def _plan(*, status: str = "DRAFT") -> ReviewPlanRecord:
    plan = ReviewPlanRecord(id=uuid4(), review_case_id=uuid4(), status=status)
    plan.items = [
        ReviewPlanItemRecord(
            id=uuid4(), document_side="SI", field_name="shipper",
            proposed_value="Approved shipper", reason="suggested", status="APPROVED",
        ),
        ReviewPlanItemRecord(
            id=uuid4(), document_side="BL", field_name="consignee",
            proposed_value="Suggested consignee", human_edited_value="Edited consignee",
            reason="corrected", status="EDITED",
        ),
        ReviewPlanItemRecord(
            id=uuid4(), document_side="BL", field_name="gross_weight_kg",
            proposed_value=9000, reason="not accepted", status="REJECTED",
        ),
    ]
    return plan


def test_confirm_applies_only_approved_and_edited_actions_then_recompares():
    session = MagicMock()
    service = ReviewPlanService(session)
    plan = _plan()
    service.get = MagicMock(return_value=plan)
    comparison = SimpleNamespace(id=uuid4())

    with patch("backend.app.review.plan_service.HumanReviewService") as review_type:
        review_type.return_value.resolve_and_recompare.return_value = (object(), comparison)
        result = service.confirm(plan.id, confirmed_by="Reviewer")

    assert result.status == "APPLIED"
    assert [item.status for item in result.items] == ["APPLIED", "APPLIED", "REJECTED"]
    values = [call.kwargs["corrected_value"] for call in review_type.return_value.add_override.call_args_list]
    assert values == ["Approved shipper", "Edited consignee"]
    review_type.return_value.resolve_and_recompare.assert_called_once_with(plan.review_case_id, reviewer_name="Reviewer")


def test_recomparison_failure_keeps_applied_items_and_retry_does_not_duplicate_overrides():
    session = MagicMock()
    service = ReviewPlanService(session)
    plan = _plan()
    service.get = MagicMock(return_value=plan)

    with patch("backend.app.review.plan_service.HumanReviewService") as review_type:
        review_type.return_value.resolve_and_recompare.side_effect = RuntimeError("provider unavailable")
        with pytest.raises(ReviewPlanApplyError):
            service.confirm(plan.id, confirmed_by="Reviewer")

    assert plan.status == "APPLY_FAILED"
    assert [item.status for item in plan.items] == ["APPLIED", "APPLIED", "REJECTED"]
    assert "provider unavailable" in plan.error_message

    comparison = SimpleNamespace(id=uuid4())
    with patch("backend.app.review.plan_service.HumanReviewService") as review_type:
        review_type.return_value.resolve_and_recompare.return_value = (object(), comparison)
        result = service.confirm(plan.id, confirmed_by="Reviewer")

    assert result.status == "APPLIED"
    review_type.return_value.add_override.assert_not_called()


def test_plan_item_can_be_edited_or_rejected_before_confirmation():
    session = MagicMock()
    service = ReviewPlanService(session)
    plan = _plan()
    service.get = MagicMock(return_value=plan)

    service.update_item(plan.id, plan.items[0].id, status="EDITED", edited_value="Manual correction")
    service.update_item(plan.id, plan.items[1].id, status="REJECTED")

    assert plan.items[0].status == "EDITED"
    assert plan.items[0].human_edited_value == "Manual correction"
    assert plan.items[1].status == "REJECTED"
    assert plan.items[1].human_edited_value is None


def test_manual_correction_is_marked_manual_and_can_be_removed_before_confirmation():
    session = MagicMock()
    service = ReviewPlanService(session)
    plan = _plan()
    plan.items = []
    service.get = MagicMock(return_value=plan)

    updated = service.add_item(
        plan.id,
        actor="Reviewer",
        item=PlanItemInput(
            document_side="BL", field_name="notify_party",
            current_value="Old", proposed_value="Corrected", reason="Verified manually",
            status="APPROVED",
        ),
    )
    manual = updated.items[0]
    assert manual.ai_suggestion_id is None
    assert manual.status == "APPROVED"
    assert any(
        getattr(call.args[0], "event_type", None) == "REVIEW_PLAN_MANUAL_ITEM_ADDED"
        and call.args[0].metadata_json["source"] == "MANUAL"
        for call in session.add.call_args_list
    )

    result = service.remove_manual_item(plan.id, manual.id, actor="Reviewer")
    assert result.items == []
    session.delete.assert_called_once_with(manual)
