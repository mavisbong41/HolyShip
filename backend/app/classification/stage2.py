from __future__ import annotations

"""
Stage 2 — Deeper resolver.

Called when Stage 1 cannot confidently finalise:
  - confidence below threshold
  - top-2 margin too small
  - subject/body conflict detected
  - mixed-intent body

For Batch 1 Stage 2 applies rule-based heuristics:
  1. Body-wins rule: if body score for one category clearly dominates the
     subject score for a different category, trust the body.
  2. Recency-weighted re-score: re-weight by giving body 1.5× vs subject 0.5×.
  3. If still inconclusive, return the highest supported category with a
     low-confidence reason code.

Stage 2 is a clean service class with a stable interface so it can be
replaced by an LLM resolver in a later batch without touching the pipeline.
"""

from dataclasses import dataclass

from backend.app.classification.signals import EmailCategory
from backend.app.classification.stage1 import Stage1Scores, normalise_to_probabilities
from backend.app.classification.config import STAGE2_RESOLUTION_THRESHOLD, STAGE2_MARGIN_THRESHOLD, STAGE2_SUBJECT_WEIGHT, STAGE2_BODY_WEIGHT


@dataclass
class Stage2Result:
    resolved: bool
    category: str
    confidence: float
    candidate_scores: dict[str, float]
    reason: str
    conflict_detected: bool
    reason_code: str = "STAGE2_RESOLVED"
    human_review_reason_code: str | None = None
    human_review_reason_text: str | None = None


class Stage2Resolver:
    """
    Stateless resolver.  Call resolve() with the Stage-1 scores and the
    conflict/ambiguity context provided by the pipeline.
    """

    BODY_DOMINANCE_MARGIN = 0.35   # body-only normalised lead must exceed this
    RESOLUTION_THRESHOLD  = STAGE2_RESOLUTION_THRESHOLD

    def resolve(
        self,
        stage1_scores: Stage1Scores,
        conflict_detected: bool,
        conflict_reason: str,
        subject: str,
        body: str,
    ) -> Stage2Result:
        """
        Returns a Stage2Result with resolved=True if Stage 2 can commit to a
        category, or resolved=False if the email should go to Human Review.
        """
        # ------------------------------------------------------------------ #
        # Re-score: body 1.5× / subject 0.5× / attachment remains 0.3× but
        # is already baked into combined_scores as 0.3×.
        # We re-derive from the per-source scores stored in stage1_scores.
        # ------------------------------------------------------------------ #
        reweighted: dict[str, float] = {}
        for cat in stage1_scores.combined_scores:
            s = stage1_scores.subject_scores.get(cat, 0.0) * STAGE2_SUBJECT_WEIGHT
            b = stage1_scores.body_scores.get(cat, 0.0) * STAGE2_BODY_WEIGHT
            reweighted[cat] = round(s + b, 4)

        probs = normalise_to_probabilities(reweighted)

        # A uniform all-zero score vector contains no supported specialized
        # intent. Resolve it explicitly to the neutral five-category outcome;
        # never let mapping/enum insertion order manufacture a comparison.
        if not any(value > 0.0 for value in reweighted.values()):
            return Stage2Result(
                resolved=True,
                category=EmailCategory.GENERAL_MESSAGE.value,
                confidence=probs[EmailCategory.GENERAL_MESSAGE.value],
                candidate_scores=probs,
                reason="No supported category signal was detected; applied the explicit neutral zero-signal policy.",
                conflict_detected=conflict_detected,
                reason_code="ZERO_SIGNAL_GENERAL",
            )

        # For evidence-bearing ties, prefer stronger body evidence, then
        # subject evidence, and finally lexical category name. The last key is
        # an explicit deterministic fallback rather than incidental map order.
        sorted_cats = sorted(
            probs.items(),
            key=lambda item: (
                -item[1],
                -stage1_scores.body_scores.get(item[0], 0.0),
                -stage1_scores.subject_scores.get(item[0], 0.0),
                item[0],
            ),
        )
        top_cat, top_conf = sorted_cats[0]
        second_conf = sorted_cats[1][1] if len(sorted_cats) > 1 else 0.0
        margin = round(top_conf - second_conf, 4)

        if top_conf >= self.RESOLUTION_THRESHOLD and margin >= STAGE2_MARGIN_THRESHOLD:
            return Stage2Result(
                resolved=True,
                category=top_cat,
                confidence=top_conf,
                candidate_scores=probs,
                reason=(
                    f"Stage 2 resolved by body-dominant re-weighting. "
                    f"Top category: {top_cat} ({top_conf:.2f}), margin: {margin:.2f}. "
                    f"Original conflict: {conflict_reason}"
                ),
                conflict_detected=conflict_detected,
            )

        # Still ambiguous: preserve ambiguity in confidence/reason while choosing
        # the best supported final category. This is never a sixth category or
        # a blanket general-message fallback.
        return Stage2Result(
            resolved=True,
            category=top_cat,
            confidence=top_conf,
            candidate_scores=probs,
            reason=(
                f"Stage 2 could not resolve ambiguity. "
                f"Top: {top_cat} ({top_conf:.2f}), margin: {margin:.2f}. "
                f"Conflict: {conflict_reason}"
            ),
            conflict_detected=conflict_detected,
            reason_code="STAGE2_LOW_CONFIDENCE",
        )
