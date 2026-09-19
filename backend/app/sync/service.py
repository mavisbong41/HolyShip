from __future__ import annotations

"""
Initial Sync Service — Batch 1.

Pulls emails from any EmailSource, persists them, classifies new/changed
ones, and stores results.  One broken email must never stop the whole sync.

State transitions per email:
  PENDING → INGESTED → CLASSIFYING → CLASSIFIED
                                   → HUMAN_REVIEW_REQUIRED
                                   → FAILED  (on exception)
"""

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.app.classification.adapters import email_message_to_classification_input
from backend.app.classification.pipeline import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_MARGIN_THRESHOLD,
    classify_email,
)
from backend.app.classification.models import HUMAN_REVIEW
from backend.app.ingestion.models import EmailMessage
from backend.app.ingestion.sources import EmailSource
from backend.app.storage.repositories import (
    ClassificationResultRepository,
    EmailRepository,
    HumanReviewRepository,
    ProcessingJobRepository,
)
from backend.app.storage.transitions import transition

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class EmailSyncOutcome:
    external_message_id: str
    status: str          # SKIPPED | CLASSIFIED | HUMAN_REVIEW_REQUIRED | FAILED
    error: str | None = None


@dataclass
class SourceSyncFailure:
    """A source-stream failure that occurred before another email materialized."""

    reason_code: str
    error: str


@dataclass
class SyncReport:
    total: int = 0
    ingested: int = 0
    skipped: int = 0          # unchanged — not reclassified
    classified: int = 0
    human_review: int = 0
    failed: int = 0
    source_failed: int = 0
    outcomes: list[EmailSyncOutcome] = field(default_factory=list)
    source_failures: list[SourceSyncFailure] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class SyncService:
    """
    Source-independent sync engine.

    Pass any EmailSource (StaticBundleSource, OrganizerHttpSource, …).
    The classification engine is the same regardless of source.
    """

    def __init__(
        self,
        session: Session,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        margin_threshold: float = DEFAULT_MARGIN_THRESHOLD,
    ):
        self.session = session
        self.confidence_threshold = confidence_threshold
        self.margin_threshold = margin_threshold

        self._email_repo = EmailRepository(session)
        self._job_repo = ProcessingJobRepository(session)
        self._cls_repo = ClassificationResultRepository(session)
        self._review_repo = HumanReviewRepository(session)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sync(self, source: EmailSource) -> SyncReport:
        """
        Pull all emails from *source*, persist new/changed, classify them.
        Returns a SyncReport summarising what happened.
        One bad email is caught, logged, and recorded as FAILED.
        """
        report = SyncReport()

        iterator = iter(source.iter_messages())
        while True:
            try:
                message = next(iterator)
            except StopIteration:
                break
            except Exception as exc:
                # At this boundary there is no materialized EmailMessage to
                # persist. Record the stream failure without inventing one,
                # then commit work completed before the iterator failed.
                logger.exception("Email source iteration failed")
                report.source_failed += 1
                report.source_failures.append(
                    SourceSyncFailure(
                        reason_code="SOURCE_ITERATION_FAILED",
                        error=str(exc),
                    )
                )
                break

            report.total += 1
            outcome = self._process_one(message)
            # Each materialized email has its own durable boundary. This
            # prevents a later _process_one() rollback from undoing prior
            # successful work in the shared session.
            self.session.commit()
            report.outcomes.append(outcome)

            if outcome.status == "SKIPPED":
                report.skipped += 1
            elif outcome.status == "CLASSIFIED":
                report.ingested += 1
                report.classified += 1
            elif outcome.status == "HUMAN_REVIEW_REQUIRED":
                report.ingested += 1
                report.human_review += 1
            elif outcome.status == "FAILED":
                report.failed += 1

        return report

    def sync_one(self, message: EmailMessage) -> EmailSyncOutcome:
        """
        Process a single EmailMessage (used by POST /api/email/incoming).
        Commits immediately.
        """
        outcome = self._process_one(message)
        self.session.commit()
        return outcome

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _process_one(self, message: EmailMessage) -> EmailSyncOutcome:
        ext_id = message.external_message_id
        try:
            return self._ingest_and_classify(message)
        except Exception as exc:
            logger.exception("Failed to process email %s", ext_id)
            # Best-effort: try to record the failure job without crashing
            try:
                self.session.rollback()
                record, _ = self._email_repo.upsert_message(message)
                self._job_repo.create(
                    email_id=record.id,
                    job_type="CLASSIFICATION",
                    status="FAILED",
                    source_metadata={"error": str(exc)},
                )
                self.session.flush()
            except Exception as inner:
                logger.error("Could not record failure for %s: %s", ext_id, inner)
                self.session.rollback()

            return EmailSyncOutcome(
                external_message_id=ext_id,
                status="FAILED",
                error=str(exc),
            )

    def _ingest_and_classify(self, message: EmailMessage) -> EmailSyncOutcome:
        ext_id = message.external_message_id

        # ---- INGEST --------------------------------------------------- #
        record, changed = self._email_repo.upsert_message(message)

        if not changed:
            # Unchanged — skip reclassification
            logger.debug("Email %s unchanged — skipping classification", ext_id)
            return EmailSyncOutcome(external_message_id=ext_id, status="SKIPPED")

        # Create / update processing job → INGESTED
        job = self._job_repo.create(
            email_id=record.id,
            job_type="CLASSIFICATION",
            status="INGESTED",
        )
        transition(self.session, record, "QUEUED", "INGESTED")

        # ---- CLASSIFY ------------------------------------------------- #
        job.status = "CLASSIFYING"
        transition(self.session, record, "CLASSIFYING", "CLASSIFICATION_STARTED")
        self.session.flush()

        cls_input = email_message_to_classification_input(message)
        result = classify_email(
            cls_input,
            confidence_threshold=self.confidence_threshold,
            margin_threshold=self.margin_threshold,
        )

        # Persist classification result
        self._cls_repo.create(
            email_id=record.id,
            category=result.category,
            confidence=result.confidence,
            candidate_scores=result.candidate_scores,
            reason=result.reason,
            reason_code=result.reason_code,
            evidence_summary=result.evidence_summary,
            conflict_detected=result.conflict_detected,
            resolved_at_stage=result.resolved_at_stage,
            comparison_readiness=result.comparison_readiness,
            classifier_version=result.classifier_version,
        )
        transition(self.session, record, "CLASSIFIED", "CLASSIFICATION_COMPLETE")

        if result.category != "document_comparison":
            transition(self.session, record, "COMPLETED", "NON_COMPARISON_COMPLETE")
        elif result.comparison_readiness == "AWAITING_DOCUMENTS":
            transition(self.session, record, "AWAITING_DOCUMENTS", "AWAITING_DOCUMENTS")
        elif result.comparison_readiness == "UNRESOLVED":
            transition(self.session, record, "BLOCKED", "READINESS_UNRESOLVED")

        # ---- HUMAN REVIEW --------------------------------------------- #
        if result.resolved_at_stage == HUMAN_REVIEW:
            self._review_repo.create(
                email_id=record.id,
                reason_code=result.human_review_reason_code or "STAGE2_UNRESOLVED",
                reason_text=result.human_review_reason_text or result.reason,
                candidate_scores=result.candidate_scores,
                evidence=result.evidence_summary,
                confidence=result.confidence,
            )
            job.status = "HUMAN_REVIEW_REQUIRED"
            self.session.flush()

            logger.info(
                "Email %s → HUMAN_REVIEW_REQUIRED (reason: %s)",
                ext_id,
                result.human_review_reason_code,
            )
            return EmailSyncOutcome(
                external_message_id=ext_id,
                status="HUMAN_REVIEW_REQUIRED",
            )

        # ---- CLASSIFIED ----------------------------------------------- #
        job.status = "CLASSIFIED"
        self.session.flush()

        logger.info(
            "Email %s → %s (conf=%.2f, stage=%s)",
            ext_id,
            result.category,
            result.confidence,
            result.resolved_at_stage,
        )
        return EmailSyncOutcome(external_message_id=ext_id, status="CLASSIFIED")
