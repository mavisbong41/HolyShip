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
  3. If still inconclusive → UNCERTAIN.

Stage 2 is a clean service class with a stable interface so it can be
replaced by an LLM resolver in a later batch without touching the pipeline.
"""

from dataclasses import dataclass

from backend.app.classification.models import (
    REASON_STAGE2_UNRESOLVED,
    REASON_SUBJECT_BODY_CONFLICT,
    HUMAN_REVIEW,
    STAGE_2,
    ClassificationOutput,
)
from backend.app.classification.signals import EmailCategory
from backend.app.classification.stage1 import Stage1Scores, normalise_to_probabilities


@dataclass
class Stage2Result:
    resolved: bool
    category: str
    confidence: float
    candidate_scores: dict[str, float]
    reason: str
    conflict_detected: bool
    human_review_reason_code: str | None = None
    human_review_reason_text: str | None = None


class Stage2Resolver:
    """
    Stateless resolver.  Call resolve() with the Stage-1 scores and the
    conflict/ambiguity context provided by the pipeline.
    """

    BODY_DOMINANCE_MARGIN = 0.35   # body-only normalised lead must exceed this
    RESOLUTION_THRESHOLD  = 0.65   # minimum confidence after Stage-2 re-weighting

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
            s = stage1_scores.subject_scores.get(cat, 0.0) * 0.5
            b = stage1_scores.body_scores.get(cat, 0.0) * 1.5
            reweighted[cat] = round(s + b, 4)

        probs = normalise_to_probabilities(reweighted)
        sorted_cats = sorted(probs.items(), key=lambda x: x[1], reverse=True)
        top_cat, top_conf = sorted_cats[0]
        second_conf = sorted_cats[1][1] if len(sorted_cats) > 1 else 0.0
        margin = round(top_conf - second_conf, 4)

        if top_conf >= self.RESOLUTION_THRESHOLD and margin >= 0.15:
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

        # Still cannot resolve
        return Stage2Result(
            resolved=False,
            category=EmailCategory.UNCERTAIN.value,
            confidence=top_conf,
            candidate_scores=probs,
            reason=(
                f"Stage 2 could not resolve ambiguity. "
                f"Top: {top_cat} ({top_conf:.2f}), margin: {margin:.2f}. "
                f"Conflict: {conflict_reason}"
            ),
            conflict_detected=conflict_detected,
            human_review_reason_code=REASON_STAGE2_UNRESOLVED,
            human_review_reason_text=(
                f"Classification unresolved after Stage 2. "
                f"Candidates: {dict(sorted_cats[:3])}. "
                f"Original conflict: {conflict_reason}"
            ),
        )
