from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from backend.app.ai_review.providers import DisabledProvider, HTTPProvider
from backend.app.ai_review.safety import evaluate_safety_gate
from backend.app.ai_review.schema import (
    AISuggestionPayload,
    AIStructuredResponse,
    ALLOWED_REVIEW_FIELDS,
)
from backend.app.ai_review.service import AIReviewService
from backend.app.main import app
from backend.app.review.service import ReviewConflictError
from backend.app.storage.models import (
    AISuggestionRecord,
    ComparisonResultRecord,
    EmailMessageRecord,
    ExtractedFieldRecord,
    FieldComparisonRecord,
    HumanReviewCaseRecord,
    HumanReviewEventRecord,
    HumanReviewFieldOverrideRecord,
)


def test_schema_valid_modes():
    # Explanation only
    resp_exp = AIStructuredResponse(
        message="This is a safe explanation.",
        mode="EXPLANATION_ONLY",
        suggestion=None,
    )
    assert resp_exp.mode == "EXPLANATION_ONLY"
    assert resp_exp.suggestion is None

    # Insufficient evidence
    resp_ins = AIStructuredResponse(
        message="Evidence is missing or inconclusive.",
        mode="INSUFFICIENT_EVIDENCE",
        suggestion=None,
    )
    assert resp_ins.mode == "INSUFFICIENT_EVIDENCE"

    # Actionable suggestion
    sugg = AISuggestionPayload(
        action="FIELD_OVERRIDE",
        document_side="BL",
        field="gross_weight_kg",
        current_value="22,O00 KG",
        suggested_value="22000",
        confidence=0.95,
        reason="OCR character repair",
        evidence_refs=["Draft BL section 4"],
    )
    resp_act = AIStructuredResponse(
        message="Proposed correction for gross weight.",
        mode="ACTIONABLE_SUGGESTION",
        suggestion=sugg,
    )
    assert resp_act.mode == "ACTIONABLE_SUGGESTION"
    assert resp_act.suggestion.suggested_value == "22000"


def test_schema_rejects_extra_fields():
    with pytest.raises(ValidationError):
        AIStructuredResponse(
            message="Test",
            mode="EXPLANATION_ONLY",
            extra_field="not_allowed",  # type: ignore
        )


def test_schema_rejects_invalid_field_or_empty_evidence():
    with pytest.raises(ValidationError):
        AISuggestionPayload(
            action="FIELD_OVERRIDE",
            document_side="BL",
            field="invalid_custom_field",  # type: ignore
            current_value="val1",
            suggested_value="val2",
            confidence=0.9,
            reason="test",
            evidence_refs=["ref1"],
        )

    with pytest.raises(ValidationError):
        AISuggestionPayload(
            action="FIELD_OVERRIDE",
            document_side="BL",
            field="gross_weight_kg",
            current_value="val1",
            suggested_value="val2",
            confidence=0.9,
            reason="test",
            evidence_refs=[],  # empty evidence forbidden
        )


def test_schema_rejects_suggestion_on_explanation_only():
    sugg = AISuggestionPayload(
        action="FIELD_OVERRIDE",
        document_side="BL",
        field="gross_weight_kg",
        current_value="22,O00 KG",
        suggested_value="22000",
        confidence=0.95,
        reason="OCR character repair",
        evidence_refs=["Draft BL section 4"],
    )
    with pytest.raises(ValidationError):
        AIStructuredResponse(
            message="Explanation only message",
            mode="EXPLANATION_ONLY",
            suggestion=sugg,  # suggestion forbidden when mode is EXPLANATION_ONLY
        )


def test_safety_gate_downgrades_when_case_blocked_or_missing_docs():
    sugg = AISuggestionPayload(
        action="FIELD_OVERRIDE",
        document_side="BL",
        field="gross_weight_kg",
        current_value="22,O00 KG",
        suggested_value="22000",
        confidence=0.95,
        reason="OCR repair",
        evidence_refs=["Draft BL span"],
    )
    act_resp = AIStructuredResponse(
        message="Proposed correction",
        mode="ACTIONABLE_SUGGESTION",
        suggestion=sugg,
    )

    # 1. Blocked because required attachment missing
    ctx_missing_att = {
        "reason_code": "MISSING_REQUIRED_ATTACHMENT",
        "presentation_title": "Required shipping document is missing",
        "si_document": {"filename": "SI.txt"},
        "bl_document": None,
    }
    downgraded = evaluate_safety_gate(ctx_missing_att, act_resp)
    assert downgraded.mode == "EXPLANATION_ONLY"
    assert downgraded.suggestion is None

    # 2. Low confidence
    low_conf_sugg = sugg.model_copy(update={"confidence": 0.5})
    low_conf_resp = AIStructuredResponse(
        message="Low confidence",
        mode="ACTIONABLE_SUGGESTION",
        suggestion=low_conf_sugg,
    )
    ctx_safe = {
        "reason_code": "COMPARISON_MISMATCH",
        "presentation_title": "The SI and BL contain different values",
        "si_document": {"filename": "SI.txt"},
        "bl_document": {"filename": "BL.txt"},
    }
    downgraded_conf = evaluate_safety_gate(ctx_safe, low_conf_resp, confidence_threshold=0.8)
    assert downgraded_conf.mode == "EXPLANATION_ONLY"
    assert downgraded_conf.suggestion is None


def test_disabled_provider_deterministic_answers():
    provider = DisabledProvider()
    ctx = {
        "case_id": "11111111-1111-1111-1111-111111111111",
        "subject": "Booking Ref 12345",
        "presentation_title": "Gross weight mismatch",
        "human_explanation": "Draft BL has OCR error.",
        "affected_fields": ["gross_weight_kg"],
        "comparison": {
            "state": "BLOCKED",
            "fields": [
                {
                    "field": "gross_weight_kg",
                    "status": "MISMATCH",
                    "si_value": "22000 KG",
                    "bl_value": "22,O00 KG",
                }
            ],
        },
    }

    raw, name, model = provider.generate_review_response(ctx, "Why is this case blocked?")
    assert "Gross weight mismatch" in raw

    raw_sugg, _, _ = provider.generate_review_response(ctx, "Can you suggest a correction for gross weight?")
    assert "ACTIONABLE_SUGGESTION" in raw_sugg
    assert "22000" in raw_sugg


def test_service_ask_and_events():
    mock_session = MagicMock()
    case_id = uuid.uuid4()
    mock_case = MagicMock(spec=HumanReviewCaseRecord)
    mock_case.id = case_id
    mock_session.get.return_value = mock_case

    ctx = {
        "case_id": str(case_id),
        "reason_code": "COMPARISON_MISMATCH",
        "presentation_title": "Field Mismatch",
        "human_explanation": "Explanation",
        "affected_fields": ["gross_weight_kg"],
        "documents": [],
        "si_document": {"filename": "si.txt"},
        "bl_document": {"filename": "bl.txt"},
        "comparison": {
            "state": "BLOCKED",
            "fields": [{"field": "gross_weight_kg", "status": "MISMATCH", "si_value": "22000 KG", "bl_value": "22,O00 KG"}],
        },
    }

    with patch("backend.app.ai_review.service.build_case_context", return_value=ctx):
        svc = AIReviewService(session=mock_session, provider=DisabledProvider())
        resp, suggestion, provider_name, provider_model = svc.ask(case_id, "Can you suggest the correct BL gross weight?")
        assert resp.mode == "ACTIONABLE_SUGGESTION"
        assert suggestion is not None
        assert suggestion.field == "gross_weight_kg"
        assert suggestion.suggested_value == "22000"

        # Check recorded events
        assert mock_session.add.called
        assert mock_session.flush.called


def test_service_dismiss():
    mock_session = MagicMock()
    case_id = uuid.uuid4()
    suggestion_id = uuid.uuid4()

    mock_sugg = MagicMock(spec=AISuggestionRecord)
    mock_sugg.id = suggestion_id
    mock_sugg.human_review_case_id = case_id
    mock_sugg.status = "PENDING"
    mock_sugg.document_side = "BL"
    mock_sugg.field = "gross_weight_kg"
    mock_session.scalar.return_value = mock_sugg

    svc = AIReviewService(session=mock_session, provider=DisabledProvider())
    dismissed = svc.dismiss(case_id, suggestion_id, reviewer_label="Alice")

    assert dismissed.status == "DISMISSED"
    assert mock_session.flush.called


def test_service_accept():
    mock_session = MagicMock()
    case_id = uuid.uuid4()
    suggestion_id = uuid.uuid4()

    mock_sugg = MagicMock(spec=AISuggestionRecord)
    mock_sugg.id = suggestion_id
    mock_sugg.human_review_case_id = case_id
    mock_sugg.status = "PENDING"
    mock_sugg.document_side = "BL"
    mock_sugg.field = "gross_weight_kg"
    mock_sugg.suggested_value = "22000"
    mock_sugg.reason = "OCR fix"
    mock_session.scalar.return_value = mock_sugg

    mock_override = MagicMock(spec=HumanReviewFieldOverrideRecord)
    mock_override.id = uuid.uuid4()

    mock_case = MagicMock(spec=HumanReviewCaseRecord)
    mock_comp = MagicMock(spec=ComparisonResultRecord)

    with patch("backend.app.ai_review.service.HumanReviewService") as MockHR:
        hr_inst = MockHR.return_value
        hr_inst.add_override.return_value = mock_override
        hr_inst.resolve_and_recompare.return_value = (mock_case, mock_comp)

        svc = AIReviewService(session=mock_session, provider=DisabledProvider())
        case_res, comp_res = svc.accept(case_id, suggestion_id, reviewer_label="Bob")

        assert mock_sugg.status == "ACCEPTED"
        assert mock_override.ai_suggestion_id == suggestion_id
        hr_inst.add_override.assert_called_once()
        hr_inst.resolve_and_recompare.assert_called_once_with(case_id, reviewer_name="Bob")


def test_service_apply_edited():
    mock_session = MagicMock()
    case_id = uuid.uuid4()
    suggestion_id = uuid.uuid4()

    mock_sugg = MagicMock(spec=AISuggestionRecord)
    mock_sugg.id = suggestion_id
    mock_sugg.human_review_case_id = case_id
    mock_sugg.status = "PENDING"
    mock_sugg.document_side = "BL"
    mock_sugg.field = "gross_weight_kg"
    mock_sugg.suggested_value = "22000"
    mock_session.scalar.return_value = mock_sugg

    mock_override = MagicMock(spec=HumanReviewFieldOverrideRecord)
    mock_override.id = uuid.uuid4()

    mock_case = MagicMock(spec=HumanReviewCaseRecord)
    mock_comp = MagicMock(spec=ComparisonResultRecord)

    with patch("backend.app.ai_review.service.HumanReviewService") as MockHR:
        hr_inst = MockHR.return_value
        hr_inst.add_override.return_value = mock_override
        hr_inst.resolve_and_recompare.return_value = (mock_case, mock_comp)

        svc = AIReviewService(session=mock_session, provider=DisabledProvider())
        case_res, comp_res = svc.apply_edited(
            case_id,
            suggestion_id,
            reviewer_value="22500",
            reviewer_label="Bob",
            note="Manual adjustment",
        )

        assert mock_sugg.status == "EDITED_APPLIED"
        assert mock_override.ai_suggestion_id == suggestion_id
        hr_inst.add_override.assert_called_once()
        hr_inst.resolve_and_recompare.assert_called_once_with(case_id, reviewer_name="Bob")


def test_service_conflict_on_non_pending():
    mock_session = MagicMock()
    case_id = uuid.uuid4()
    suggestion_id = uuid.uuid4()

    mock_sugg = MagicMock(spec=AISuggestionRecord)
    mock_sugg.id = suggestion_id
    mock_sugg.human_review_case_id = case_id
    mock_sugg.status = "ACCEPTED"  # already accepted
    mock_session.scalar.return_value = mock_sugg

    svc = AIReviewService(session=mock_session, provider=DisabledProvider())
    with pytest.raises(ReviewConflictError):
        svc.accept(case_id, suggestion_id, reviewer_label="Bob")

    with pytest.raises(ReviewConflictError):
        svc.dismiss(case_id, suggestion_id, reviewer_label="Bob")


def test_api_routes_integration():
    mock_session = MagicMock()
    from backend.app.api.deps import get_session
    app.dependency_overrides[get_session] = lambda: mock_session

    case_id = uuid.uuid4()
    suggestion_id = uuid.uuid4()

    with TestClient(app) as client:
        # Test ask with mock
        with patch.object(AIReviewService, "ask") as mock_ask:
            mock_sugg = MagicMock()
            mock_sugg.id = suggestion_id
            mock_ask.return_value = (
                AIStructuredResponse(message="Hello", mode="EXPLANATION_ONLY", suggestion=None),
                None,
                "disabled",
                "deterministic_rule_v1",
            )
            resp = client.post(f"/api/v1/human-review/{case_id}/ai/ask", json={"question": "Why is this blocked?"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["mode"] == "EXPLANATION_ONLY"
            assert data["message"] == "Hello"

        # Test empty question -> 422
        resp_empty = client.post(f"/api/v1/human-review/{case_id}/ai/ask", json={"question": ""})
        assert resp_empty.status_code == 422

    app.dependency_overrides.clear()

