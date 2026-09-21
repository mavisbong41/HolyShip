from types import SimpleNamespace

from backend.app.api.presentation import present_processing_status, present_reason
from backend.app.api.review_helper import compute_human_explanation, compute_review_presentation


def test_reason_mapping_is_user_facing_and_deterministic():
    presentation = present_reason("COMPARISON_UNRESOLVED", affected_fields=["gross_weight_kg"])
    assert presentation.title == "One or more document fields could not be verified"
    assert "Gross Weight" in presentation.explanation
    assert presentation.affected_area == "Document fields"
    assert presentation.suggested_action == "Review the unresolved fields"


def test_non_field_issue_does_not_claim_zero_affected_fields():
    row = SimpleNamespace(reason_code="MISSING_REQUIRED_ATTACHMENT", field_name=None)
    assert compute_human_explanation(row, []) == "A required shipping document is not available for comparison."
    presentation = compute_review_presentation(row, [])
    assert presentation.affected_area == "Documents"


def test_processing_states_have_product_language():
    failed = present_processing_status("FAILED")
    waiting = present_processing_status("AWAITING_DOCUMENTS")
    assert failed.title == "Processing failed"
    assert failed.suggested_action == "Retry / Reprocess"
    assert waiting.title == "Waiting for required documents"


def test_historical_status_is_non_actionable_language():
    historical = present_reason("RESOLVED")
    assert historical.title == "Review completed"
    assert historical.suggested_action == "View comparison result"


def test_required_part1_reason_mappings_are_exact():
    expected = {
        "CLASSIFICATION_UNRESOLVED": "Email type unclear",
        "COMPARISON_UNRESOLVED": "One or more document fields could not be verified",
        "COMPARISON_MISMATCH": "The SI and BL contain different values",
        "DOCUMENT_ROLE_UNRESOLVED": "Document role unclear",
        "WRONG_DOCUMENT_TYPE": "Wrong document type",
        "MISSING_REQUIRED_ATTACHMENT": "Required shipping document is missing",
        "UNREADABLE_ATTACHMENT": "Document could not be read reliably",
        "MULTIPLE_CANDIDATES": "More than one document may match",
        "READINESS_UNRESOLVED": "Document readiness unclear",
    }
    for reason_code, title in expected.items():
        assert present_reason(reason_code).title == title


def test_processing_failure_is_not_review_copy():
    presentation = present_processing_status("FAILED")
    assert presentation.title == "Processing failed"
    assert presentation.suggested_action == "Retry / Reprocess"
    assert presentation.affected_area == "Processing"


def test_record_summary_excludes_failed_and_legacy_open_from_human_review():
    from backend.app.api.product_queries import _summary_from_record

    email = SimpleNamespace(
        id="email-id",
        external_message_id="external-id",
        source_type="TEST",
        sender=None,
        subject="Test",
        received_at=None,
        created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        processing_status="FAILED",
        attachments=[],
    )
    legacy_open = SimpleNamespace(
        id="review-id",
        case_origin="LEGACY",
        status="OPEN",
        reason_code="CLASSIFICATION_UNRESOLVED",
    )
    summary = _summary_from_record(
        email,
        classification=None,
        comparison=None,
        review=legacy_open,
    )
    assert summary.needs_review is False


def test_record_summary_counts_active_in_review_as_actionable():
    from backend.app.api.product_queries import _summary_from_record

    email = SimpleNamespace(
        id="email-id",
        external_message_id="external-id",
        source_type="TEST",
        sender=None,
        subject="Test",
        received_at=None,
        created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        processing_status="COMPLETED",
        attachments=[],
    )
    active_claimed = SimpleNamespace(
        id="review-id",
        case_origin="ACTIVE",
        status="IN_REVIEW",
        reason_code="COMPARISON_UNRESOLVED",
    )
    summary = _summary_from_record(
        email,
        classification=None,
        comparison=None,
        review=active_claimed,
    )
    assert summary.needs_review is True


def test_correction_analytics_query_is_scoped_to_active_cases():
    from pathlib import Path

    source = Path("backend/app/api/analytics_helper.py").read_text(encoding="utf-8")
    correction_section = source.split("# Correction insights", 1)[1]
    assert 'HumanReviewCaseRecord.case_origin == "ACTIVE"' in correction_section
    assert "HumanReviewFieldOverrideRecord.active.is_(True)" in correction_section
    assert "extracted.raw_value_json" in correction_section
