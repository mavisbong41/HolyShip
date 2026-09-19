from __future__ import annotations

"""
Stage 1 — Fast keyword/pattern classifier.

Responsibilities:
  - Normalise subject and body text.
  - Score each category against the centralised signal patterns.
  - Separately score subject signals and body signals.
  - Return raw candidate scores (NOT a final decision).

Stage 1 does NOT make routing decisions.
Routing (confidence gate, conflict detection, Stage-2 escalation) lives
in the pipeline layer.
"""

import re
from dataclasses import dataclass

from backend.app.classification.signals import (
    CATEGORY_SIGNALS,
    EmailCategory,
    SignalPattern,
)


def _normalise(text: str) -> str:
    """Lower-case and collapse whitespace/punctuation runs to a single space."""
    text = text.lower()
    text = re.sub(r"[_\-/|]", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _score_text(text: str, patterns: list[SignalPattern]) -> float:
    """
    Return the cumulative match score of *patterns* found in *text*.

    Each matching phrase contributes its weight.  A phrase matches if all
    its tokens appear as a contiguous subsequence in the normalised token list.
    """
    if not text:
        return 0.0
    normalised = _normalise(text)
    tokens = normalised.split()
    total = 0.0
    for sp in patterns:
        phrase_tokens = sp.phrase.split()
        n = len(phrase_tokens)
        for i in range(len(tokens) - n + 1):
            if tokens[i : i + n] == phrase_tokens:
                total += sp.weight
                break                   # count each pattern at most once per text
    return total


@dataclass
class Stage1Scores:
    """Per-category raw scores broken down by signal source."""
    subject_scores: dict[str, float]
    body_scores: dict[str, float]
    combined_scores: dict[str, float]


def score_email(
    subject: str,
    body: str,
    attachment_filenames: list[str],
) -> Stage1Scores:
    """
    Compute raw category scores for a single email.

    Body signals carry 1.0× weight.
    Subject signals carry 0.7× weight (body is more reliable for intent).
    Attachment-filename signals carry 0.3× weight and can only reinforce,
    never solely determine, a category.

    NOTE: attachment *presence* alone must never determine the category.
    Attachment filenames add a small nudge only.
    """
    subject_scores: dict[str, float] = {}
    body_scores: dict[str, float] = {}
    combined_scores: dict[str, float] = {}

    # Build a virtual "attachment text" from filenames (names only, no content)
    attachment_text = " ".join(attachment_filenames)

    for category, patterns in CATEGORY_SIGNALS.items():
        s_score = _score_text(subject, patterns) * 0.7
        b_score = _score_text(body, patterns) * 1.0
        a_score = _score_text(attachment_text, patterns) * 0.3

        subject_scores[category.value] = round(s_score, 4)
        body_scores[category.value] = round(b_score, 4)
        combined_scores[category.value] = round(s_score + b_score + a_score, 4)

    return Stage1Scores(
        subject_scores=subject_scores,
        body_scores=body_scores,
        combined_scores=combined_scores,
    )


def normalise_to_probabilities(raw_scores: dict[str, float]) -> dict[str, float]:
    """
    Softmax-like normalisation: scales raw scores to [0, 1] summing to 1.

    If all scores are 0 (empty/no signals), returns a uniform distribution.
    """
    total = sum(raw_scores.values())
    if total == 0.0:
        n = len(raw_scores)
        return {k: round(1.0 / n, 4) for k in raw_scores}
    return {k: round(v / total, 4) for k, v in raw_scores.items()}
