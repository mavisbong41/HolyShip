from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Stage / Resolution identifiers
# ---------------------------------------------------------------------------
STAGE_1       = "STAGE_1"
STAGE_2       = "STAGE_2"
HUMAN_REVIEW  = "HUMAN_REVIEW"

# ---------------------------------------------------------------------------
# Human-review reason codes
# ---------------------------------------------------------------------------
REASON_LOW_CONFIDENCE       = "LOW_CONFIDENCE"
REASON_SMALL_MARGIN         = "SMALL_MARGIN"
REASON_SUBJECT_BODY_CONFLICT = "SUBJECT_BODY_CONFLICT"
REASON_MIXED_INTENT         = "MIXED_INTENT"
REASON_VAGUE_EVIDENCE       = "VAGUE_EVIDENCE"
REASON_STAGE2_UNRESOLVED    = "STAGE2_UNRESOLVED"


@dataclass
class ClassificationInput:
    """
    The data that goes INTO the classification pipeline.

    Only subject, body, and attachment *metadata* are used.
    Attachment contents are never inspected at this stage.
    """
    external_message_id: str
    subject: str
    body: str
    attachment_filenames: list[str]
    attachment_count: int


@dataclass
class CandidateScore:
    category: str
    score: float


@dataclass
class ClassificationOutput:
    """
    The data that comes OUT of the classification pipeline.

    This maps 1-to-1 to what is persisted in ClassificationResultRecord.
    """
    category: str
    confidence: float
    candidate_scores: dict[str, float]
    reason: str
    evidence_summary: dict
    conflict_detected: bool
    resolved_at_stage: str          # STAGE_1 | STAGE_2 | HUMAN_REVIEW
    comparison_readiness: Optional[str] = None
    classifier_version: str = "batch1-rule-v1"
    reason_code: str = "CLASSIFICATION_RESOLVED"

    # If the result is HUMAN_REVIEW, these hold the review metadata
    human_review_reason_code: Optional[str] = None
    human_review_reason_text: Optional[str] = None

    @property
    def low_confidence(self) -> bool:
        """Whether this result is below the centralized Stage-1 confidence gate."""
        from backend.app.classification.config import STAGE1_CONFIDENCE_THRESHOLD

        return self.confidence < STAGE1_CONFIDENCE_THRESHOLD
