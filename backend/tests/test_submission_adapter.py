import json
from pathlib import Path

import pytest

from backend.app.submission_adapter import (
    AWAITING_DOCUMENTS_MAPPING_VALIDATED,
    SubmissionWorkflowOutcome,
    build_submission,
    to_submission_entry,
)


@pytest.mark.req("SUB-01")
@pytest.mark.req("SCP-07")
def test_adapter_emits_every_required_public_field_and_supported_category():
    result = build_submission([
        ("email_001", "GENERAL_MAIL", {}),
        ("email_002", "DOCUMENT_COMPARISON", {}),
        ("email_003", "UNCERTAIN", {"SPAM": 0.9, "GENERAL_MAIL": 0.1}),
    ])

    expected_fields = set(json.loads(Path("data/bundle/sample_submission.json").read_text())["email_001"])
    assert set(result) == {"email_001", "email_002", "email_003"}
    assert all(set(entry) == expected_fields for entry in result.values())
    assert result["email_001"]["category"] == "GENERAL"
    assert result["email_002"] == {
        "category": "BL_COMPARISON", "status": "NEEDS_REVIEW",
        "review_reason": "missing_value", "defect_fields": [], "has_defect": False,
    }
    assert result["email_003"]["category"] == "SPAM"


@pytest.mark.req("SUB-02")
@pytest.mark.parametrize(
    ("workflow", "expected"),
    [
        (
            SubmissionWorkflowOutcome("COMPLETED", "COMPARISON_COMPLETE", False, (), ()),
            ("OK", None, [], False),
        ),
        (
            SubmissionWorkflowOutcome("COMPLETED", "COMPARISON_COMPLETE", True, ("consignee",), ()),
            ("MISMATCH", None, ["consignee"], True),
        ),
        (
            SubmissionWorkflowOutcome("BLOCKED", "WRONG_DOCUMENT_TYPE", False, (), ()),
            ("NEEDS_REVIEW", "wrong_doc_type", [], False),
        ),
        (
            SubmissionWorkflowOutcome("BLOCKED", "MISSING_REQUIRED_ATTACHMENT", False, (), ()),
            ("NEEDS_REVIEW", "missing_attachment", [], False),
        ),
        (
            SubmissionWorkflowOutcome("BLOCKED", "UNREADABLE_ATTACHMENT", False, (), ()),
            ("NEEDS_REVIEW", "unreadable", [], False),
        ),
        (
            SubmissionWorkflowOutcome("BLOCKED", "COMPARISON_UNRESOLVED", False, (), ("shipper",)),
            ("NEEDS_REVIEW", "missing_value", [], False),
        ),
    ],
)
def test_explicit_public_mapping_covers_supported_comparison_and_review_outcomes(
    workflow,
    expected,
):
    entry = to_submission_entry("document_comparison", workflow=workflow)
    assert (
        entry["status"],
        entry["review_reason"],
        entry["defect_fields"],
        entry["has_defect"],
    ) == expected
    assert set(entry) == {
        "category",
        "status",
        "review_reason",
        "defect_fields",
        "has_defect",
    }


@pytest.mark.req("SUB-02")
def test_awaiting_documents_boundary_mapping_remains_explicitly_unvalidated():
    entry = to_submission_entry(
        "document_comparison",
        workflow=SubmissionWorkflowOutcome(
            "AWAITING_DOCUMENTS",
            "AWAITING_DOCUMENTS",
            False,
            (),
            (),
        ),
    )
    assert AWAITING_DOCUMENTS_MAPPING_VALIDATED is True
    assert entry == {
        "category": "BL_COMPARISON",
        "status": "OK",
        "review_reason": None,
        "defect_fields": [],
        "has_defect": False,
    }


@pytest.mark.req("SUB-03")
def test_public_adapter_compresses_mixed_state_without_mutating_richer_internal_input():
    workflow = SubmissionWorkflowOutcome(
        processing_status="BLOCKED",
        reason_code="COMPARISON_UNRESOLVED",
        mismatch_found=True,
        mismatched_fields=("container_count",),
        unresolved_fields=("notify_party",),
    )
    entry = to_submission_entry("document_comparison", workflow=workflow)

    assert entry == {
        "category": "BL_COMPARISON",
        "status": "NEEDS_REVIEW",
        "review_reason": "missing_value",
        "defect_fields": [],
        "has_defect": False,
    }
    assert workflow.mismatch_found is True
    assert workflow.mismatched_fields == ("container_count",)
    assert workflow.unresolved_fields == ("notify_party",)
