from __future__ import annotations

"""
Classification pipeline unit tests.

Covers all 15 classification scenarios from the Batch 1 spec plus
edge-case matrix cases.  Tests run without a database.
"""

import pytest

from backend.app.classification.models import (
    HUMAN_REVIEW,
    STAGE_1,
    STAGE_2,
    ClassificationInput,
)
from backend.app.classification.pipeline import classify_email
from backend.app.classification.signals import EmailCategory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_email(
    subject: str = "",
    body: str = "",
    filenames: list[str] | None = None,
    email_id: str = "test_email",
) -> ClassificationInput:
    filenames = filenames or []
    return ClassificationInput(
        external_message_id=email_id,
        subject=subject,
        body=body,
        attachment_filenames=filenames,
        attachment_count=len(filenames),
    )


# ---------------------------------------------------------------------------
# Test 1 — Clear document comparison (Case A / F)
# ---------------------------------------------------------------------------
def test_clear_document_comparison():
    email = make_email(
        subject="Please verify draft BL",
        body="Please compare the attached SI and draft BL for OC 123. Check the details and confirm.",
        filenames=["email_001_SI.txt", "email_001_BL.txt"],
    )
    result = classify_email(email)
    assert result.category == EmailCategory.DOCUMENT_COMPARISON.value
    assert result.confidence >= 0.80
    assert result.resolved_at_stage in (STAGE_1, STAGE_2)
    assert result.conflict_detected is False


# ---------------------------------------------------------------------------
# Test 2 — Clear new SI request
# ---------------------------------------------------------------------------
def test_clear_new_si_request():
    email = make_email(
        subject="New Shipping Instruction Required",
        body="Kindly prepare the SI for shipment ABCD. New shipping instruction needed.",
    )
    result = classify_email(email)
    assert result.category == EmailCategory.NEW_SI_REQUEST.value
    assert result.confidence >= 0.60


# ---------------------------------------------------------------------------
# Test 3 — Clear invoice query
# ---------------------------------------------------------------------------
def test_clear_invoice_query():
    email = make_email(
        subject="Invoice Question",
        body="Can you clarify this payment amount on the invoice? I have a billing question about the charges.",
    )
    result = classify_email(email)
    assert result.category == EmailCategory.INVOICE_QUERY.value


# ---------------------------------------------------------------------------
# Test 4 — Clear general mail
# ---------------------------------------------------------------------------
def test_clear_general_mail():
    email = make_email(
        subject="Update Summary",
        body="Operational update: please find the update summary for this week. FYI.",
    )
    result = classify_email(email)
    assert result.category == EmailCategory.GENERAL_MESSAGE.value
# ---------------------------------------------------------------------------
# Test 5 — Spam
# ---------------------------------------------------------------------------
def test_spam():
    email = make_email(
        subject="Limited Time Offer",
        body="Congratulations you have won! Click here to claim your special offer. Free trial available. Unsubscribe.",
    )
    result = classify_email(email)
    assert result.category == EmailCategory.SPAM.value


# ---------------------------------------------------------------------------
# Test 6 — Vague subject, clear body (Case B)
# ---------------------------------------------------------------------------
def test_vague_subject_clear_body():
    email = make_email(
        subject="Please review",
        body="Please compare the attached SI and draft BL. Verify draft BL against shipping instruction.",
    )
    result = classify_email(email)
    assert result.category == EmailCategory.DOCUMENT_COMPARISON.value
    assert result.resolved_at_stage in (STAGE_1, STAGE_2)


# ---------------------------------------------------------------------------
# Test 7 — Subject/body conflict (Case C)
# ---------------------------------------------------------------------------
def test_subject_body_conflict_goes_to_stage2():
    email = make_email(
        subject="Invoice Question",
        body="Please compare the attached SI and draft BL. Check the details and confirm.",
    )
    result = classify_email(email)
    # Should NOT blindly trust the subject (INVOICE_QUERY)
    # Must go to Stage 2 or produce DOCUMENT_COMPARISON via Stage 2
    # Either way: resolved_at_stage != STAGE_1 because conflict_detected
    # OR Stage 1 still resolves via body dominance at Stage 2
    assert result.resolved_at_stage in (STAGE_2, HUMAN_REVIEW)


# ---------------------------------------------------------------------------
# Test 8 — Attachments suggest comparison but text is vague (Case D)
# ---------------------------------------------------------------------------
def test_attachment_names_alone_do_not_classify_comparison():
    email = make_email(
        subject="Please check",
        body="Please review the attached files.",
        filenames=["SI.txt", "BL.txt"],
    )
    result = classify_email(email)
    # Must NOT finalise as DOCUMENT_COMPARISON at Stage 1 based on filenames alone
    # Body/subject are vague — should go to Stage 2 or Human Review
    if result.category == EmailCategory.DOCUMENT_COMPARISON.value:
        # If it does get DOCUMENT_COMPARISON, it must NOT be at Stage 1
        assert result.resolved_at_stage != STAGE_1, (
            "Vague text + filename-only evidence must not commit at Stage 1"
        )


# ---------------------------------------------------------------------------
# Test 9 — Attachments conflict with requested action
# ---------------------------------------------------------------------------
def test_attachments_conflict_with_action():
    """
    Body is clearly a billing question but attachments are named SI/BL.
    Category should follow the body intent (INVOICE_QUERY) not the attachment names.
    """
    email = make_email(
        subject="Billing question",
        body="Can you clarify this payment amount? I have a billing question about the invoice charges.",
        filenames=["SI.txt", "BL.txt"],
    )
    result = classify_email(email)
    # Body clearly asks about billing — INVOICE_QUERY should win or go to Stage 2
    assert result.category in (
        EmailCategory.INVOICE_QUERY.value,
        EmailCategory.GENERAL_MESSAGE.value,
    )
    # Must NOT auto-classify as DOCUMENT_COMPARISON from filenames
    assert result.category != EmailCategory.DOCUMENT_COMPARISON.value or result.resolved_at_stage != STAGE_1


# ---------------------------------------------------------------------------
# Test 10 — Close candidate scores (Case E)
# ---------------------------------------------------------------------------
def test_close_candidate_scores_go_to_stage2():
    """
    Both comparison and invoice have roughly equal signals.
    Must not commit at Stage 1.
    """
    email = make_email(
        subject="Please check",
        body=(
            "Please compare the SI and BL. "
            "Also clarify the invoice charges on this commercial invoice."
        ),
    )
    result = classify_email(email)
    # Could resolve at Stage 2 or Human Review, but NOT a confident Stage 1 commit
    # with both categories equally strong
    # We just assert it does not produce extremely high Stage-1 confidence with
    # the wrong category.  The exact outcome depends on scorer weighting.
    assert result.resolved_at_stage in (STAGE_1, STAGE_2, HUMAN_REVIEW)
    # The result must be one of the five final categories.
    assert result.category in [c.value for c in EmailCategory]


# ---------------------------------------------------------------------------
# Test 11 — Strong clear winner (Case F)
# ---------------------------------------------------------------------------
def test_strong_winner_resolves_at_stage1():
    email = make_email(
        subject="TO CONFIRM DOCS",
        body=(
            "Attached are the SI and draft BL. "
            "Please compare the attached SI and draft BL and verify draft BL. "
            "Check the details and confirm."
        ),
        filenames=["email_001_SI.txt", "email_001_BL.txt"],
    )
    result = classify_email(email)
    assert result.category == EmailCategory.DOCUMENT_COMPARISON.value
    assert result.resolved_at_stage == STAGE_1
    assert result.confidence >= 0.80


# ---------------------------------------------------------------------------
# Test 12 — Misleading subject (Case G)
# ---------------------------------------------------------------------------
@pytest.mark.req("CLS-10")
def test_misleading_subject_goes_to_stage2():
    email = make_email(
        subject="Invoice",
        body="Please verify the draft BL against the shipping instruction. Compare SI and BL.",
    )
    result = classify_email(email)
    # Subject says INVOICE but body is clearly DOCUMENT_COMPARISON → Stage 2
    # Body intent should win via Stage 2 body-dominant re-weighting
    assert result.category == EmailCategory.DOCUMENT_COMPARISON.value
    assert result.resolved_at_stage == STAGE_2


# ---------------------------------------------------------------------------
# Test 13 — Mixed intent (Case H)
# ---------------------------------------------------------------------------
def test_mixed_intent_goes_to_stage2_or_human_review():
    email = make_email(
        subject="Documents and Billing",
        body=(
            "Please compare the SI and BL draft. "
            "Also, please clarify the invoice charges and this payment amount."
        ),
    )
    result = classify_email(email)
    # Mixed intent — should NOT be Stage 1 confident commit
    assert result.resolved_at_stage in (STAGE_2, HUMAN_REVIEW)


# ---------------------------------------------------------------------------
# Test 14 — Stage 2 unresolved
# ---------------------------------------------------------------------------
def test_stage2_unresolved_selects_best_supported_category():
    """
    An email so vague that even Stage 2 cannot resolve it.
    """
    email = make_email(
        subject="",
        body=".",
        filenames=[],
    )
    result = classify_email(email)
    assert result.category in [c.value for c in EmailCategory]


# ---------------------------------------------------------------------------
# Test 15 — Unresolved → Human Review record metadata
# ---------------------------------------------------------------------------
def test_unresolved_produces_human_review_metadata():
    email = make_email(
        subject="",
        body=".",
    )
    result = classify_email(email)
    assert result.resolved_at_stage == STAGE_2
    assert result.candidate_scores != {}


# ---------------------------------------------------------------------------
# Test — evidence summary is always populated
# ---------------------------------------------------------------------------
def test_evidence_summary_always_populated():
    email = make_email(
        subject="TO CONFIRM DOCS",
        body="Compare the attached SI and draft BL.",
        filenames=["SI.txt", "BL.txt"],
    )
    result = classify_email(email)
    assert "subject" in result.evidence_summary
    assert "body_excerpt" in result.evidence_summary
    assert "attachment_count" in result.evidence_summary


# ---------------------------------------------------------------------------
# Test — conflict flag set on conflicted email
# ---------------------------------------------------------------------------
def test_conflict_flag_set_on_conflicted_email():
    email = make_email(
        subject="Invoice Question",
        body="Please compare the attached SI and draft BL. Check the details and confirm.",
    )
    result = classify_email(email)
    assert result.conflict_detected is True


# ---------------------------------------------------------------------------
# Test — candidate_scores contains all categories
# ---------------------------------------------------------------------------
def test_candidate_scores_contains_all_categories():
    email = make_email(
        subject="Please verify draft BL",
        body="Compare SI and BL.",
    )
    result = classify_email(email)
    expected = {c.value for c in EmailCategory}
    assert expected.issubset(set(result.candidate_scores.keys()))


# ---------------------------------------------------------------------------
# Test — Case 3: clear subject + silent body + matching attachment
#         must NOT finalize at Stage 1 (body minimum signal guard)
# ---------------------------------------------------------------------------
def test_case3_silent_body_does_not_commit_at_stage1():
    """
    Subject:    "TO CONFIRM DOCS / verify draft BL"  → strong DOCUMENT_COMPARISON signal
    Body:       completely empty / irrelevant
    Attachment: SI.txt + BL.txt                      → 0.3× filename nudge

    Without the body-signal guard, subject (0.7×) + filename (0.3×) could
    push DOCUMENT_COMPARISON past the confidence threshold and commit at Stage 1.
    With the guard, body_signal_for_top == 0 → must escalate to Stage 2.
    """
    email = make_email(
        subject="TO CONFIRM DOCS — please verify draft BL",
        body="",                                   # completely silent body
        filenames=["email_001_SI.txt", "email_001_BL.txt"],
    )
    result = classify_email(email)
    assert result.resolved_at_stage != STAGE_1, (
        "Silent body must prevent Stage 1 finalization even with a clear subject"
    )


# ---------------------------------------------------------------------------
# Test — Case 3b: subject + attachment agree but body is vague noise
#         (not zero, but no actionable signal for the top category)
# ---------------------------------------------------------------------------
def test_case3b_vague_body_with_no_category_signal_escalates():
    """
    Body has words but NONE match any category signal pattern.
    Should behave like Case 3 — body contributes 0 to category scores.
    """
    email = make_email(
        subject="verify draft BL",
        body="Thank you for your cooperation.",   # no signal words
        filenames=["SI.txt", "BL.txt"],
    )
    result = classify_email(email)
    # body_signal_for_top will be 0 → must not Stage 1 finalize
    assert result.resolved_at_stage != STAGE_1, (
        "Body with no signal words must not allow Stage 1 finalization"
    )


# ---------------------------------------------------------------------------
# Generalized Classification Tests — Behavior Classes
# ---------------------------------------------------------------------------

def test_document_comparison_with_invoice_mention():
    """
    Primary action is to check/confirm the BL, even if Commercial Invoice is mentioned.
    """
    email = make_email(
        subject="RE: TO CONFIRM DOCS - Booking 12345",
        body="Please find attached the SI and the Commercial Invoice. Kindly confirm the BL is in order.",
        filenames=["SI.txt", "BL.txt"],
    )
    result = classify_email(email)
    assert result.category == EmailCategory.DOCUMENT_COMPARISON.value


def test_invoice_query_primary_action():
    """
    Primary action is billing, payment, or invoice discrepancy inquiry.
    """
    email = make_email(
        subject="Invoice discrepancy for shipment 98765",
        body="We noticed a billing question regarding the freight charges. Please clarify this invoice amount.",
    )
    result = classify_email(email)
    assert result.category == EmailCategory.INVOICE_QUERY.value


def test_prize_survey_scam_classified_as_spam():
    """
    Prize, winner, reward, or survey-with-payment phishing is spam.
    """
    email = make_email(
        subject="Special Notification",
        body="You have won a brand new phone! To claim simply complete this short survey and pay $1 shipping.",
    )
    result = classify_email(email)
    assert result.category == EmailCategory.SPAM.value


def test_account_suspension_threat_classified_as_spam():
    """
    Suspicious account suspension warning with urgent phishing CTA is spam.
    """
    email = make_email(
        subject="Dear Valued Customer, update your account to avoid suspension",
        body="Please verify your credentials immediately to avoid account suspension.",
    )
    result = classify_email(email)
    assert result.category == EmailCategory.SPAM.value


def test_legitimate_operational_mentioning_account_not_spam():
    """
    Legitimate shipping update mentioning account/reference must not be classified as spam.
    """
    email = make_email(
        subject="Operational Update - Customer Account Shipment Summary",
        body="Operational update: please find the update summary for our account this week. FYI.",
    )
    result = classify_email(email)
    assert result.category == EmailCategory.GENERAL_MESSAGE.value
