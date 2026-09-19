from __future__ import annotations

"""
Classification pipeline — multi-stage orchestration.

This is the SINGLE entry point for all classification.
It does not care where an email came from (static bundle, HTTP, incoming API).

Flow:
    Email
     ↓
    Stage 1 Fast Classifier  (signals.py + stage1.py)
     ↓
    Decision Gate
     ├─ confident + clear → Stage 1 Final
     └─ ambiguous / conflict
            ↓
         Stage 2 Resolver  (stage2.py)
            ↓
         Decision Gate
           ├─ resolved → Stage 2 Final
           └─ unresolved → UNCERTAIN + Human Review
"""

from backend.app.classification.models import (
    HUMAN_REVIEW,
    REASON_LOW_CONFIDENCE,
    REASON_MIXED_INTENT,
    REASON_SMALL_MARGIN,
    REASON_STAGE2_UNRESOLVED,
    REASON_SUBJECT_BODY_CONFLICT,
    REASON_VAGUE_EVIDENCE,
    STAGE_1,
    STAGE_2,
    ClassificationInput,
    ClassificationOutput,
)
from backend.app.classification.signals import EmailCategory
from backend.app.classification.stage1 import Stage1Scores, normalise_to_probabilities, score_email
from backend.app.classification.stage2 import Stage2Resolver


_DEFAULT_STAGE2 = Stage2Resolver()

# Minimum normalised probability for Stage 1 to commit
DEFAULT_CONFIDENCE_THRESHOLD = 0.80
# Minimum gap between #1 and #2 candidate for Stage 1 to commit
DEFAULT_MARGIN_THRESHOLD = 0.25


def classify_email(
    email: ClassificationInput,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    margin_threshold: float = DEFAULT_MARGIN_THRESHOLD,
    stage2_resolver: Stage2Resolver | None = None,
) -> ClassificationOutput:
    """
    Run the full multi-stage classification pipeline on one email.

    Returns a ClassificationOutput that can be directly persisted.
    """
    resolver = stage2_resolver or _DEFAULT_STAGE2

    # ------------------------------------------------------------------ #
    # Stage 1 — score
    # ------------------------------------------------------------------ #
    stage1: Stage1Scores = score_email(
        subject=email.subject,
        body=email.body,
        attachment_filenames=email.attachment_filenames,
    )

    probs = normalise_to_probabilities(stage1.combined_scores)
    sorted_cats = sorted(probs.items(), key=lambda x: x[1], reverse=True)
    top_cat, top_conf = sorted_cats[0]
    second_conf = sorted_cats[1][1] if len(sorted_cats) > 1 else 0.0
    margin = round(top_conf - second_conf, 4)

    evidence = {
        "subject": email.subject[:200],
        "body_excerpt": email.body[:300],
        "attachment_count": email.attachment_count,
        "attachment_filenames": email.attachment_filenames,
    }

    # ------------------------------------------------------------------ #
    # Conflict detection — Cases C, G, H
    # ------------------------------------------------------------------ #
    conflict_detected, conflict_reason = _detect_conflict(
        stage1=stage1,
        top_cat=top_cat,
        top_conf=top_conf,
        margin=margin,
    )

    # ------------------------------------------------------------------ #
    # Stage 1 gate — Cases A, B, F
    # ------------------------------------------------------------------ #
    if (
        not conflict_detected
        and top_conf >= confidence_threshold
        and margin >= margin_threshold
    ):
        return ClassificationOutput(
            category=top_cat,
            confidence=top_conf,
            candidate_scores=probs,
            reason=_stage1_reason(top_cat, top_conf, margin, email),
            evidence_summary=evidence,
            conflict_detected=False,
            resolved_at_stage=STAGE_1,
        )

    # ------------------------------------------------------------------ #
    # Stage 2 — Cases C, D, E, G, H
    # ------------------------------------------------------------------ #
    s2 = resolver.resolve(
        stage1_scores=stage1,
        conflict_detected=conflict_detected,
        conflict_reason=conflict_reason,
        subject=email.subject,
        body=email.body,
    )

    if s2.resolved:
        return ClassificationOutput(
            category=s2.category,
            confidence=s2.confidence,
            candidate_scores=s2.candidate_scores,
            reason=s2.reason,
            evidence_summary=evidence,
            conflict_detected=s2.conflict_detected,
            resolved_at_stage=STAGE_2,
        )

    # ------------------------------------------------------------------ #
    # Stage 2 unresolved → UNCERTAIN + Human Review — Case I
    # ------------------------------------------------------------------ #
    return ClassificationOutput(
        category=EmailCategory.UNCERTAIN.value,
        confidence=s2.confidence,
        candidate_scores=s2.candidate_scores,
        reason=s2.reason,
        evidence_summary=evidence,
        conflict_detected=s2.conflict_detected,
        resolved_at_stage=HUMAN_REVIEW,
        human_review_reason_code=s2.human_review_reason_code or REASON_STAGE2_UNRESOLVED,
        human_review_reason_text=s2.human_review_reason_text or s2.reason,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _detect_conflict(
    *,
    stage1: Stage1Scores,
    top_cat: str,
    top_conf: float,
    margin: float,
) -> tuple[bool, str]:
    """
    Returns (conflict_detected, conflict_reason).

    Conflict cases:
      - Subject top category ≠ body top category  (Case C / G)
      - Margin too small  (Case E)
      - Confidence too low  (Case D / I)
      - Multiple strong body signals  (Case H — mixed intent)
    """
    subject_scores = stage1.subject_scores
    body_scores = stage1.body_scores

    # Find top subject category (excluding UNCERTAIN)
    top_subject_cat = _top_category(subject_scores)
    top_body_cat = _top_category(body_scores)

    # Case C / G: subject and body disagree on top category
    # Only flag if BOTH have meaningful signal (score > 0)
    subject_has_signal = (subject_scores.get(top_subject_cat, 0.0) > 0.0) if top_subject_cat else False
    body_has_signal = (body_scores.get(top_body_cat, 0.0) > 0.0) if top_body_cat else False

    if (
        top_subject_cat
        and top_body_cat
        and top_subject_cat != top_body_cat
        and subject_has_signal
        and body_has_signal
    ):
        return True, (
            f"Subject signals '{top_subject_cat}' but body signals '{top_body_cat}' "
            f"(subject/body conflict)"
        )

    # Case H: two body categories both have substantial signal (mixed intent).
    # We flag this even when one dominates — if both have positive raw signal,
    # the sender is asking about two different operational concerns.
    body_sorted = sorted(body_scores.items(), key=lambda x: x[1], reverse=True)
    if len(body_sorted) >= 2:
        b_top_raw  = body_sorted[0][1]
        b_sec_raw  = body_sorted[1][1]
        b_top_cat  = body_sorted[0][0]
        b_sec_cat  = body_sorted[1][0]
        if b_top_raw > 0 and b_sec_raw > 0:
            return True, (
                f"Mixed body intent: '{b_top_cat}' (raw={b_top_raw:.2f}) "
                f"vs '{b_sec_cat}' (raw={b_sec_raw:.2f})"
            )

    # Case E: close candidates
    if margin < 0.20:
        return True, (
            f"Candidate scores too close: top={top_conf:.2f}, margin={margin:.2f}"
        )

    return False, ""


def _top_category(scores: dict[str, float]) -> str | None:
    """Return the highest-scoring category key, or None if all scores are 0."""
    if not scores:
        return None
    top = max(scores.items(), key=lambda x: x[1])
    return top[0] if top[1] > 0 else None


def _stage1_reason(
    category: str,
    confidence: float,
    margin: float,
    email: ClassificationInput,
) -> str:
    excerpts = []
    subj = email.subject.strip()[:120]
    if subj:
        excerpts.append(f"subject='{subj}'")
    body_short = email.body.strip()[:200].replace("\n", " ")
    if body_short:
        excerpts.append(f"body_excerpt='{body_short}'")
    evidence_str = "; ".join(excerpts)
    return (
        f"Stage 1 classified as {category} with confidence {confidence:.2f} "
        f"(margin {margin:.2f}). Evidence: {evidence_str}"
    )
