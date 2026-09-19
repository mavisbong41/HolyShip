import json
from pathlib import Path

import pytest

from backend.app.submission_adapter import build_submission, to_submission_entry


@pytest.mark.req("SUB-01")
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
