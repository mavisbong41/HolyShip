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
