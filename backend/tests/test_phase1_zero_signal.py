from __future__ import annotations

import pytest

from backend.app.classification.models import ClassificationInput
from backend.app.classification.pipeline import classify_email
from backend.app.classification.signals import EmailCategory
from backend.app.classification.stage1 import Stage1Scores
from backend.app.classification.stage2 import Stage2Resolver


ALLOWED_CATEGORIES = {category.value for category in EmailCategory}


def email(subject: str, body: str) -> ClassificationInput:
    return ClassificationInput(
        external_message_id="synthetic-zero-signal",
        subject=subject,
        body=body,
        attachment_filenames=[],
        attachment_count=0,
    )


def zero_scores(categories: list[str]) -> Stage1Scores:
    scores = {category: 0.0 for category in categories}
    return Stage1Scores(
        subject_scores=dict(scores),
        body_scores=dict(scores),
        combined_scores=dict(scores),
    )


def test_zero_evidence_ordinary_message_uses_explicit_neutral_policy():
    result = classify_email(email("Hello", "Please see the message below. Thank you."))

    assert result.category in ALLOWED_CATEGORIES
    assert result.category != EmailCategory.DOCUMENT_COMPARISON.value
    assert result.low_confidence is True
    assert result.reason_code == "ZERO_SIGNAL_GENERAL"


def test_zero_evidence_stage2_result_is_independent_of_candidate_order():
    categories = [category.value for category in EmailCategory]
    resolver = Stage2Resolver()

    forward = resolver.resolve(zero_scores(categories), False, "", "Hello", "Thank you.")
    reverse = resolver.resolve(zero_scores(list(reversed(categories))), False, "", "Hello", "Thank you.")

    assert forward.category == reverse.category == EmailCategory.GENERAL_MESSAGE.value
    assert forward.confidence == reverse.confidence == pytest.approx(0.2)
    assert forward.reason_code == reverse.reason_code == "ZERO_SIGNAL_GENERAL"


def test_supported_spam_evidence_is_not_neutralized():
    result = classify_email(
        email(
            "Limited time promotion",
            "Congratulations you have won. Click here to claim this special offer.",
        )
    )

    assert result.category == EmailCategory.SPAM.value
    assert result.reason_code != "ZERO_SIGNAL_GENERAL"


@pytest.mark.req("CLS-01")
def test_obvious_prize_promotion_is_classified_as_spam():
    result = classify_email(
        email(
            "WIN A PRIZE NOW",
            "Click here for an unrelated promotion.",
        )
    )

    assert result.category == EmailCategory.SPAM.value


@pytest.mark.req("CLS-07")
def test_no_attachment_and_bare_draft_bl_mention_is_not_sufficient():
    result = classify_email(
        email(
            "Status note",
            "This note mentions the draft BL for reference only.",
        )
    )

    assert result.category != EmailCategory.DOCUMENT_COMPARISON.value
    assert result.comparison_readiness is None
