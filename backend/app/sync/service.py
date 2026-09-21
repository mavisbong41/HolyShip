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
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Callable

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.app.classification.adapters import email_message_to_classification_input
from backend.app.classification.pipeline import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_MARGIN_THRESHOLD,
    classify_email,
)
from backend.app.classification.models import HUMAN_REVIEW
from backend.app.documents.materialization import DocumentMaterializationService
from backend.app.ingestion.models import EmailMessage
from backend.app.ingestion.sources import EmailSource
from backend.app.review.service import HumanReviewService
from backend.app.storage.repositories import (
    ClassificationResultRepository,
    ComparisonResultRepository,
    EmailRepository,
    HumanReviewRepository,
    ProcessingJobRepository,
)
from backend.app.storage.transitions import transition
from backend.app.resolution.service import ResolutionExecutor
from backend.app.documents.readers.ocr_reader import OcrSharedState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class EmailSyncOutcome:
    external_message_id: str
    status: str          # SKIPPED | CLASSIFIED | HUMAN_REVIEW_REQUIRED | FAILED
    error: str | None = None
    duration_ms: float = 0.0
    retry_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    reader_calls: int = 0
    extractor_calls: int = 0
    ocr_calls: int = 0
    vision_calls: int = 0
    resolver_calls: int = 0
    resolver_accepted: int = 0
    resolver_rejected: int = 0
    resolver_cache_hits: int = 0
    resolver_failures: int = 0
    resolver_malformed: int = 0
    escalated_cases: int = 0


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
    wall_seconds: float = 0.0
    throughput_emails_per_second: float | None = None
    p50_per_email_ms: float | None = None
    p95_per_email_ms: float | None = None
    max_workers: int = 1
    retries: int = 0
    source_retry_attempts: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    reader_calls: int = 0
    extractor_calls: int = 0
    ocr_calls: int = 0
    vision_calls: int = 0
    resolver_calls: int = 0
    resolver_accepted: int = 0
    resolver_rejected: int = 0
    resolver_cache_hits: int = 0
    resolver_failures: int = 0
    resolver_malformed: int = 0
    escalated_cases: int = 0
    unhandled_exceptions: int = 0


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
        *,
        max_workers: int = 1,
        session_factory: Callable[[], Session] | None = None,
        retry_max_attempts: int = 1,
        semantic_resolver_timeout_seconds: float | None = None,
        extraction_max_workers: int = 2,
        resolution_executor_factory: Callable[[Session], ResolutionExecutor] | None = None,
        ocr_timeout_seconds: float = 15.0,
        ocr_max_calls: int = 8,
        ocr_max_concurrent_calls: int = 2,
        ocr_shared_state: OcrSharedState | None = None,
        ocr_tesseract_cmd: str | None = None,
    ):
        if not 1 <= max_workers <= 32:
            raise ValueError("max_workers must be between 1 and 32")
        if retry_max_attempts < 1:
            raise ValueError("retry_max_attempts must be at least one")
        self.session = session
        self.confidence_threshold = confidence_threshold
        self.margin_threshold = margin_threshold
        self.max_workers = max_workers
        self.session_factory = session_factory
        self.retry_max_attempts = retry_max_attempts
        self.semantic_resolver_timeout_seconds = semantic_resolver_timeout_seconds
        self.extraction_max_workers = extraction_max_workers
        self.resolution_executor_factory = resolution_executor_factory
        self.ocr_timeout_seconds = ocr_timeout_seconds
        self.ocr_max_calls = ocr_max_calls
        self.ocr_max_concurrent_calls = ocr_max_concurrent_calls
        self.ocr_tesseract_cmd = ocr_tesseract_cmd
        self.ocr_shared_state = ocr_shared_state or OcrSharedState(
            max_calls=ocr_max_calls,
            max_concurrent_calls=ocr_max_concurrent_calls,
        )

        self._email_repo = EmailRepository(session)
        self._job_repo = ProcessingJobRepository(session)
        self._cls_repo = ClassificationResultRepository(session)
        self._review_repo = HumanReviewRepository(session)
        self._active_review_service = HumanReviewService(session)
        self._comparison_repo = ComparisonResultRepository(session)
        self._document_service = DocumentMaterializationService(
            session,
            semantic_resolver_timeout_seconds=semantic_resolver_timeout_seconds,
            resolution_executor=(
                resolution_executor_factory(session)
                if resolution_executor_factory is not None
                else None
            ),
            extraction_max_workers=extraction_max_workers,
            ocr_timeout_seconds=ocr_timeout_seconds,
            ocr_max_calls=ocr_max_calls,
            ocr_max_concurrent_calls=ocr_max_concurrent_calls,
            ocr_shared_state=self.ocr_shared_state,
            ocr_tesseract_cmd=ocr_tesseract_cmd,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def sync(self, source: EmailSource, *, force: bool = False) -> SyncReport:
        """
        Pull all emails from *source*, persist new/changed, classify them.
        Returns a SyncReport summarising what happened.
        One bad email is caught, logged, and recorded as FAILED.
        """
        report = SyncReport(max_workers=self.max_workers if self.session_factory else 1)
        started = time.perf_counter()

        if self.max_workers > 1 and self.session_factory is not None:
            self._sync_parallel(source, report, force=force)
        else:
            self._sync_sequential(source, report, force=force)

        report.wall_seconds = time.perf_counter() - started
        if report.wall_seconds > 0:
            report.throughput_emails_per_second = report.total / report.wall_seconds
        durations = sorted(
            outcome.duration_ms
            for outcome in report.outcomes
            if outcome.duration_ms > 0
        )
        if durations:
            report.p50_per_email_ms = _percentile(durations, 0.50)
            report.p95_per_email_ms = _percentile(durations, 0.95)
        report.retries = sum(outcome.retry_count for outcome in report.outcomes)
        report.source_retry_attempts = len(getattr(source, "retry_events", ()))
        report.cache_hits = sum(outcome.cache_hits for outcome in report.outcomes)
        report.cache_misses = sum(outcome.cache_misses for outcome in report.outcomes)
        report.reader_calls = sum(outcome.reader_calls for outcome in report.outcomes)
        report.extractor_calls = sum(outcome.extractor_calls for outcome in report.outcomes)
        report.ocr_calls = sum(outcome.ocr_calls for outcome in report.outcomes)
        report.vision_calls = sum(outcome.vision_calls for outcome in report.outcomes)
        report.resolver_calls = sum(outcome.resolver_calls for outcome in report.outcomes)
        report.resolver_accepted = sum(outcome.resolver_accepted for outcome in report.outcomes)
        report.resolver_rejected = sum(outcome.resolver_rejected for outcome in report.outcomes)
        report.resolver_cache_hits = sum(outcome.resolver_cache_hits for outcome in report.outcomes)
        report.resolver_failures = sum(outcome.resolver_failures for outcome in report.outcomes)
        report.resolver_malformed = sum(outcome.resolver_malformed for outcome in report.outcomes)
        report.escalated_cases = sum(outcome.escalated_cases for outcome in report.outcomes)
        return report

    def _sync_sequential(self, source: EmailSource, report: SyncReport, *, force: bool = False) -> None:

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
            outcome = self._process_one(message, source, force=force)
            # Each materialized email has its own durable boundary. This
            # prevents a later _process_one() rollback from undoing prior
            # successful work in the shared session.
            self.session.commit()
            self._record_outcome(report, outcome)

    def _sync_parallel(self, source: EmailSource, report: SyncReport, *, force: bool = False) -> None:
        """Process a bounded in-flight window using one DB session per worker."""

        assert self.session_factory is not None
        iterator = iter(source.iter_messages())
        pending: dict[Future[EmailSyncOutcome], EmailMessage] = {}
        source_exhausted = False

        def submit_next() -> None:
            nonlocal source_exhausted
            if source_exhausted or len(pending) >= self.max_workers:
                return
            try:
                message = next(iterator)
            except StopIteration:
                source_exhausted = True
                return
            except Exception as exc:
                source_exhausted = True
                report.source_failed += 1
                report.source_failures.append(
                    SourceSyncFailure(
                        reason_code="SOURCE_ITERATION_FAILED",
                        error=str(exc),
                    )
                )
                return
            report.total += 1
            future = pool.submit(self._process_parallel_one, message, source, force=force)
            pending[future] = message

        with ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="holyship-email",
        ) as pool:
            while len(pending) < self.max_workers and not source_exhausted:
                submit_next()
            while pending:
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    message = pending.pop(future)
                    try:
                        outcome = future.result()
                    except Exception as exc:
                        # A worker boundary must never abort unrelated cases.
                        report.unhandled_exceptions += 1
                        outcome = EmailSyncOutcome(
                            external_message_id=(
                                message.external_message_id
                            ),
                            status="FAILED",
                            error=f"WORKER_UNHANDLED: {exc}",
                        )
                    self._record_outcome(report, outcome)
                    submit_next()

    def _process_parallel_one(
        self,
        message: EmailMessage,
        source: EmailSource,
        *,
        force: bool = False,
    ) -> EmailSyncOutcome:
        assert self.session_factory is not None
        with self.session_factory() as session:
            worker = SyncService(
                session,
                confidence_threshold=self.confidence_threshold,
                margin_threshold=self.margin_threshold,
                max_workers=1,
                retry_max_attempts=self.retry_max_attempts,
                semantic_resolver_timeout_seconds=self.semantic_resolver_timeout_seconds,
                extraction_max_workers=self.extraction_max_workers,
                resolution_executor_factory=self.resolution_executor_factory,
                ocr_timeout_seconds=self.ocr_timeout_seconds,
                ocr_max_calls=self.ocr_max_calls,
                ocr_max_concurrent_calls=self.ocr_max_concurrent_calls,
                ocr_shared_state=self.ocr_shared_state,
                ocr_tesseract_cmd=self.ocr_tesseract_cmd,
            )
            return worker.sync_one(message, source, force=force)

    @staticmethod
    def _record_outcome(report: SyncReport, outcome: EmailSyncOutcome) -> None:
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

    def sync_one(
        self,
        message: EmailMessage,
        source: EmailSource | None = None,
        *,
        force: bool = False,
    ) -> EmailSyncOutcome:
        """
        Process a single EmailMessage (used by POST /api/email/incoming).
        Commits immediately.
        """
        outcome = self._process_one(message, source, force=force)
        self.session.commit()
        return outcome

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _process_one(
        self,
        message: EmailMessage,
        source: EmailSource | None = None,
        *,
        force: bool = False,
    ) -> EmailSyncOutcome:
        ext_id = message.external_message_id
        started = time.perf_counter()
        for attempt in range(1, self.retry_max_attempts + 1):
            try:
                outcome = self._ingest_and_classify(message, source, force=force)
                outcome.duration_ms = (time.perf_counter() - started) * 1000.0
                outcome.retry_count = attempt - 1
                return outcome
            except Exception as exc:
                if attempt < self.retry_max_attempts and _is_retryable_processing_error(exc):
                    self.session.rollback()
                    continue
                logger.exception("Failed to process email %s", ext_id)
                return self._record_failure(
                    message,
                    exc,
                    duration_ms=(time.perf_counter() - started) * 1000.0,
                    retry_count=attempt - 1,
                )
        raise AssertionError("processing retry loop must return")

    def _record_failure(
        self,
        message: EmailMessage,
        error: Exception,
        *,
        duration_ms: float,
        retry_count: int,
    ) -> EmailSyncOutcome:
        try:
            self.session.rollback()
            record, _ = self._email_repo.upsert_message(message)
            self._job_repo.create(
                email_id=record.id,
                job_type="CLASSIFICATION",
                status="FAILED",
                source_metadata={
                    "error": str(error),
                    "error_type": type(error).__name__,
                    "retry_count": retry_count,
                },
                source_content_hash=message.content_hash,
            )
            self.session.flush()
        except Exception as inner:
            logger.error("Could not record failure for %s: %s", message.external_message_id, inner)
            self.session.rollback()
        return EmailSyncOutcome(
            external_message_id=message.external_message_id,
            status="FAILED",
            error=str(error),
            duration_ms=duration_ms,
            retry_count=retry_count,
        )

    def _ingest_and_classify(
        self,
        message: EmailMessage,
        source: EmailSource | None,
        *,
        force: bool = False,
    ) -> EmailSyncOutcome:
        ext_id = message.external_message_id

        # ---- INGEST --------------------------------------------------- #
        record, changed = self._email_repo.upsert_message(message)

        resumable = {
            "NEW",
            "QUEUED",
            "CLASSIFYING",
            "RETRIEVING_ATTACHMENTS",
            "EXTRACTING",
            "COMPARING",
        }
        if not changed and not force and record.processing_status not in resumable:
            # Unchanged — skip reclassification
            logger.debug("Email %s unchanged — skipping classification", ext_id)
            return EmailSyncOutcome(external_message_id=ext_id, status="SKIPPED")

        # Create / update processing job → INGESTED
        job = self._job_repo.create(
            email_id=record.id,
            job_type="CLASSIFICATION",
            status="INGESTED",
            source_content_hash=record.content_hash,
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
            source_content_hash=record.content_hash,
        )
        transition(self.session, record, "CLASSIFIED", "CLASSIFICATION_COMPLETE")

        cache_hits = 0
        cache_misses = 0
        reader_calls = extractor_calls = ocr_calls = vision_calls = 0
        resolver_delta: dict[str, int | float] = {}
        if result.category != "document_comparison":
            transition(self.session, record, "COMPLETED", "NON_COMPARISON_COMPLETE")
        elif result.comparison_readiness == "AWAITING_DOCUMENTS":
            transition(self.session, record, "AWAITING_DOCUMENTS", "AWAITING_DOCUMENTS")
        elif result.comparison_readiness == "UNRESOLVED":
            transition(self.session, record, "BLOCKED", "READINESS_UNRESOLVED")
            self._active_review_service.ensure_actionable_case(
                record,
                reason_code="READINESS_UNRESOLVED",
                evidence={"comparison_readiness": "UNRESOLVED"},
            )
        elif result.comparison_readiness == "READY_FOR_COMPARISON":
            resolver_before = self._resolution_metrics()
            materialization = self._document_service.process(record, message, source)
            resolver_delta = _metric_delta(resolver_before, self._resolution_metrics())
            cache_hits = materialization.cache_hits
            cache_misses = materialization.cache_misses
            reader_calls = materialization.reader_calls
            extractor_calls = materialization.extractor_calls
            ocr_calls = materialization.ocr_calls
            vision_calls = materialization.vision_calls
            if materialization.technical_failure:
                job.status = "FAILED"
                job.error_message = materialization.reason_code
                self.session.flush()
                return EmailSyncOutcome(
                    external_message_id=ext_id,
                    status="FAILED",
                    error=materialization.reason_code,
                    cache_hits=materialization.cache_hits,
                    cache_misses=materialization.cache_misses,
                    reader_calls=materialization.reader_calls,
                    extractor_calls=materialization.extractor_calls,
                    ocr_calls=materialization.ocr_calls,
                    vision_calls=materialization.vision_calls,
                    **_outcome_resolution_metrics(resolver_delta),
                )
            if materialization.processing_status == "BLOCKED":
                job.status = "BLOCKED"
                job.error_message = materialization.reason_code
                source_comparison = (
                    self._comparison_repo.get_latest_by_email_id(record.id)
                    if materialization.reason_code == "COMPARISON_UNRESOLVED"
                    else None
                )
                self._active_review_service.ensure_actionable_case(
                    record,
                    reason_code=materialization.reason_code,
                    source_comparison_id=(source_comparison.id if source_comparison else None),
                    evidence={
                        "comparison_id": str(source_comparison.id) if source_comparison else None,
                    },
                )

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
        if job.status not in {"BLOCKED", "FAILED"}:
            job.status = "CLASSIFIED"
        self.session.flush()

        logger.info(
            "Email %s → %s (conf=%.2f, stage=%s)",
            ext_id,
            result.category,
            result.confidence,
            result.resolved_at_stage,
        )
        return EmailSyncOutcome(
            external_message_id=ext_id,
            status="CLASSIFIED",
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            reader_calls=reader_calls,
            extractor_calls=extractor_calls,
            ocr_calls=ocr_calls,
            vision_calls=vision_calls,
            **_outcome_resolution_metrics(resolver_delta),
        )

    def _resolution_metrics(self) -> dict[str, int | float]:
        executor = self._document_service.comparison_service.resolution_executor
        return executor.metrics.snapshot() if executor is not None else {}


def _is_retryable_processing_error(error: Exception) -> bool:
    return isinstance(error, (ConnectionError, TimeoutError, OperationalError))


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return values[lower] + (values[upper] - values[lower]) * weight


def _metric_delta(
    before: dict[str, int | float],
    after: dict[str, int | float],
) -> dict[str, int | float]:
    return {
        key: after.get(key, 0) - before.get(key, 0)
        for key in after
        if key != "average_calls_per_escalated_case"
    }


def _outcome_resolution_metrics(metrics: dict[str, int | float]) -> dict[str, int]:
    return {
        "resolver_calls": int(metrics.get("provider_calls", 0)),
        "resolver_accepted": int(metrics.get("accepted", 0)),
        "resolver_rejected": int(metrics.get("rejected", 0)),
        "resolver_cache_hits": int(metrics.get("cache_hits", 0)),
        "resolver_failures": int(metrics.get("provider_failures", 0)),
        "resolver_malformed": int(metrics.get("malformed_responses", 0)),
        "escalated_cases": int(metrics.get("escalated_cases", 0)),
    }
