from backend.app.reply.policy import evaluate_reply_policy


def test_applied_with_unresolved_remaining_allows_request_information():
    policy = evaluate_reply_policy(
        email_id="email-1", processing_status="COMPLETED", comparison_state="COMPLETED",
        mismatched_fields=[], unresolved_fields=["consignee"], reason_code="COMPARISON_UNRESOLVED",
    )
    assert policy.allowed is True
    assert policy.mode == "REQUEST_INFORMATION"
    assert "consignee" in policy.missing_or_required_items


def test_blocked_requestable_reason_allows_request_information():
    policy = evaluate_reply_policy(
        email_id="email-2", processing_status="BLOCKED", comparison_state="BLOCKED",
        mismatched_fields=[], unresolved_fields=[], reason_code="MISSING_REQUIRED_ATTACHMENT",
    )
    assert policy.allowed is True
    assert policy.mode == "REQUEST_INFORMATION"


def test_clean_completed_comparison_allows_resolution_reply():
    policy = evaluate_reply_policy(
        email_id="email-3", processing_status="COMPLETED", comparison_state="COMPLETED",
        mismatched_fields=[], unresolved_fields=[], reason_code=None,
    )
    assert policy.allowed is True
    assert policy.mode == "RESOLUTION_REPLY"


def test_internal_block_and_missing_email_id_remain_unavailable():
    blocked = evaluate_reply_policy(
        email_id="email-4", processing_status="BLOCKED", comparison_state="BLOCKED",
        mismatched_fields=[], unresolved_fields=[], reason_code="INTERNAL_ERROR",
    )
    missing_id = evaluate_reply_policy(
        email_id=None, processing_status="COMPLETED", comparison_state="COMPLETED",
        mismatched_fields=[], unresolved_fields=[], reason_code=None,
    )
    assert blocked.allowed is False
    assert missing_id.allowed is False
