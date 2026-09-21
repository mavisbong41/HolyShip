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
        id="11111111-1111-4111-8111-111111111111",
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
        id="22222222-2222-4222-8222-222222222222",
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
        id="11111111-1111-4111-8111-111111111111",
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
        id="22222222-2222-4222-8222-222222222222",
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


def test_product_router_exposes_complete_part1_review_filters():
    from pathlib import Path

    source = Path("backend/app/api/router.py").read_text(encoding="utf-8")
    assert 'review_status: Literal["OPEN", "IN_REVIEW", "RESOLVED", "DISMISSED"]' in source
    assert 'sort: Literal["priority", "age", "oldest", "newest"]' in source


def test_frontend_forwards_part1_review_filters_and_sort():
    from pathlib import Path

    client = Path("frontend/src/api/client.ts").read_text(encoding="utf-8")
    assert 'appendParam(params, "review_status", filters.review_status)' in client
    assert 'appendParam(params, "comparison_state", filters.comparison_state)' in client
    assert 'appendParam(params, "sort", filters.sort)' in client


def test_priority_is_deterministic_and_generalizable():
    from backend.app.api.review_helper import compute_priority

    base = SimpleNamespace(reason_code="COMPARISON_UNRESOLVED")
    assert compute_priority(base, ["shipper", "consignee"]) == "HIGH"
    assert compute_priority(base, ["gross_weight_kg"]) == "MEDIUM"
    assert compute_priority(base, ["container_count"]) == "MEDIUM"
    assert compute_priority(base, ["shipper"]) == "LOW"

    document_issue = SimpleNamespace(reason_code="UNREADABLE_ATTACHMENT")
    assert compute_priority(document_issue, []) == "HIGH"


def test_part1_metric_contract_documents_units_and_populations():
    from pathlib import Path

    semantics = Path("docs/human_review_semantics.md").read_text(encoding="utf-8")
    assert "email-level" in semantics
    assert "review-case-level" in semantics
    assert "ACTIVE" in semantics or "active" in semantics
    assert "legacy" in semantics.lower()
    assert "mismatch" in semantics.lower()


def test_reconciliation_uses_email_level_latest_comparison_semantics():
    from pathlib import Path

    source = Path("backend/app/api/analytics_helper.py").read_text(encoding="utf-8")
    reconciliation = source.split("def get_human_review_reconciliation", 1)[1]
    assert "partition_by=ComparisonResultRecord.email_id" in reconciliation
    assert "latest_comparison.c.rank == 1" in reconciliation
    assert "latest_comparison.c.mismatch_found.is_(True)" in reconciliation
    assert "select(latest_comparison.c.unresolved_fields)" in reconciliation
    assert "sum(1 for (fields,) in latest_unresolved_rows if fields)" in reconciliation
    assert "json_array_length" not in reconciliation
    assert "jsonb_array_length" not in reconciliation


def test_part1_ui_contract_keeps_historical_read_only_and_non_field_copy_human_facing():
    from pathlib import Path

    app = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    assert 'selected.case_origin === "ACTIVE"' in app
    assert "retained for audit history and is read-only" in app
    assert 'review.affected_fields.length ? review.affected_fields.length + " affected field(s)"' in app
    assert '(review.affected_area || "Email-level issue")' in app
    assert '"0 affected field(s)"' not in app


def test_frontend_review_filtering_uses_complete_paginated_population():
    from pathlib import Path

    client = Path("frontend/src/api/client.ts").read_text(encoding="utf-8")
    app = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    assert "export async function getAllHumanReviews" in client
    assert "while (items.length < total)" in client
    assert "getAllHumanReviews({ active_only: !showAllReviews })" in app
