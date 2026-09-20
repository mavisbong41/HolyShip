"""Generic continuous-ingestion polling with durable source state.

The coordinator deliberately knows only the common ``EmailSource`` contract.
Provider adapters still own listing and attachment retrieval. For sources such
as Organizer HTTP that cannot filter by a cursor, listing is repeated, but
persisted email identity/content state prevents processing or attachment
materialization from repeating.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Event
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.ingestion.models import EmailMessage
from backend.app.ingestion.sources import EmailSource
from backend.app.storage.models import EmailMessageRecord, IngestionCheckpointRecord


logger = logging.getLogger(__name__)

RESTARTABLE_STATUSES = frozenset(
    {
        "NEW",
        "QUEUED",
        "CLASSIFYING",
        "RETRIEVING_ATTACHMENTS",
        "EXTRACTING",
        "COMPARING",
    }
)


@dataclass(frozen=True)
class ExistingEmailState:
    content_hash: str
    processing_status: str


@dataclass(frozen=True)
class PollCycleResult:
    source_key: str
    scanned: int
    submitted: int
    skipped_seen: int
    last_seen_external_id: str | None


class PollingStateStore(Protocol):
    def existing_messages(self, source_type: str) -> dict[str, ExistingEmailState]:
        ...

    def record_success(self, **payload: object) -> None:
        ...

    def record_failure(self, **payload: object) -> None:
        ...


class SqlAlchemyPollingStateStore:
    """Persistence boundary for polling checkpoints and email dedupe state."""

    def __init__(self, session: Session, *, clock: Callable[[], datetime] | None = None):
        self.session = session
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def existing_messages(self, source_type: str) -> dict[str, ExistingEmailState]:
        rows = self.session.execute(
            select(
                EmailMessageRecord.external_message_id,
                EmailMessageRecord.content_hash,
                EmailMessageRecord.processing_status,
            ).where(EmailMessageRecord.source_type == source_type)
        ).all()
        return {
            external_id: ExistingEmailState(content_hash=content_hash, processing_status=status)
            for external_id, content_hash, status in rows
        }

    def record_success(self, **payload: object) -> None:
        source_key = str(payload["source_key"])
        checkpoint = self.session.scalar(
            select(IngestionCheckpointRecord).where(
                IngestionCheckpointRecord.source_key == source_key
            )
        )
        if checkpoint is None:
            checkpoint = IngestionCheckpointRecord(
                source_key=source_key,
                source_type=str(payload["source_type"]),
                poll_count=0,
            )
            self.session.add(checkpoint)
        checkpoint.last_successful_poll_at = payload.get("polled_at") or self.clock()
        checkpoint.last_seen_external_id = _optional_string(payload.get("last_seen_external_id"))
        checkpoint.last_seen_content_hash = _optional_string(payload.get("last_seen_content_hash"))
        checkpoint.poll_count += 1
        checkpoint.last_error_code = None
        checkpoint.last_error_message = None
        self.session.commit()

    def record_failure(self, **payload: object) -> None:
        source_key = str(payload["source_key"])
        checkpoint = self.session.scalar(
            select(IngestionCheckpointRecord).where(
                IngestionCheckpointRecord.source_key == source_key
            )
        )
        if checkpoint is None:
            checkpoint = IngestionCheckpointRecord(
                source_key=source_key,
                source_type=str(payload["source_type"]),
            )
            self.session.add(checkpoint)
        checkpoint.last_error_code = _optional_string(payload.get("error_code"))
        checkpoint.last_error_message = _optional_string(payload.get("error_message"))
        self.session.commit()


class ContinuousIngestionWorker:
    """Poll a generic source and invoke the existing processing pipeline."""

    def __init__(
        self,
        *,
        source_key: str,
        session_factory: Callable[[], Session] | None = None,
        source_factory: Callable[[], EmailSource] | None = None,
        processor_factory: Callable[[Session], Callable[[EmailMessage, EmailSource], Any]] | None = None,
        poll_interval_seconds: float = 60.0,
        backoff_initial_seconds: float = 1.0,
        backoff_max_seconds: float = 60.0,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        if not source_key.strip():
            raise ValueError("source_key must not be empty")
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        if backoff_initial_seconds <= 0:
            raise ValueError("backoff_initial_seconds must be positive")
        if backoff_max_seconds < backoff_initial_seconds:
            raise ValueError("backoff_max_seconds must not be below backoff_initial_seconds")
        self.source_key = source_key
        self.session_factory = session_factory
        self.source_factory = source_factory
        self.processor_factory = processor_factory
        self.poll_interval_seconds = poll_interval_seconds
        self.backoff_initial_seconds = backoff_initial_seconds
        self.backoff_max_seconds = backoff_max_seconds
        self.sleeper = sleeper

    def poll_once(
        self,
        *,
        source: EmailSource,
        processor: Callable[[EmailMessage, EmailSource], Any],
        state_store: PollingStateStore,
    ) -> PollCycleResult:
        """Run one source listing and advance the checkpoint only on success."""

        existing = state_store.existing_messages(source.source_type)
        scanned = 0
        submitted = 0
        skipped_seen = 0
        last_message: EmailMessage | None = None
        processed_in_cycle: set[tuple[str, str]] = set()

        try:
            for message in source.iter_messages():
                scanned += 1
                last_message = message
                identity = (message.source_type, message.external_message_id)
                current = existing.get(message.external_message_id)
                same_content = current is not None and current.content_hash == message.content_hash
                restartable = current is not None and current.processing_status in RESTARTABLE_STATUSES
                if (
                    identity in processed_in_cycle
                    or (current is not None and same_content and not restartable)
                ):
                    skipped_seen += 1
                    continue

                processor(message, source)
                submitted += 1
                processed_in_cycle.add(identity)
                existing[message.external_message_id] = ExistingEmailState(
                    content_hash=message.content_hash,
                    processing_status="COMPLETED",
                )
        except Exception as exc:
            state_store.record_failure(
                source_key=self.source_key,
                source_type=source.source_type,
                error_code="POLL_SOURCE_FAILED",
                error_message=str(exc),
            )
            raise

        state_store.record_success(
            source_key=self.source_key,
            source_type=source.source_type,
            last_seen_external_id=last_message.external_message_id if last_message else None,
            last_seen_content_hash=last_message.content_hash if last_message else None,
        )
        return PollCycleResult(
            source_key=self.source_key,
            scanned=scanned,
            submitted=submitted,
            skipped_seen=skipped_seen,
            last_seen_external_id=last_message.external_message_id if last_message else None,
        )

    def run(
        self,
        stop_event: Event,
        *,
        poll_once: Callable[[], Any] | None = None,
        start_immediately: bool = True,
    ) -> None:
        """Run until shutdown, resetting backoff after a successful poll."""

        consecutive_failures = 0
        if not start_immediately:
            self.sleeper(self.poll_interval_seconds)
        while not stop_event.is_set():
            try:
                if poll_once is None:
                    self._poll_from_configured_dependencies()
                else:
                    poll_once()
            except Exception as exc:
                consecutive_failures += 1
                delay = min(
                    self.backoff_max_seconds,
                    self.backoff_initial_seconds * (2 ** (consecutive_failures - 1)),
                )
                logger.warning(
                    "Continuous ingestion poll failed; retrying in %.2fs (%s)",
                    delay,
                    type(exc).__name__,
                )
            else:
                consecutive_failures = 0
                delay = self.poll_interval_seconds
            self.sleeper(delay)

    def _poll_from_configured_dependencies(self) -> PollCycleResult:
        if self.session_factory is None or self.source_factory is None or self.processor_factory is None:
            raise RuntimeError("session_factory, source_factory, and processor_factory are required for run()")
        with self.session_factory() as session:
            source = self.source_factory()
            processor = self.processor_factory(session)
            state_store = SqlAlchemyPollingStateStore(session)
            return self.poll_once(source=source, processor=processor, state_store=state_store)


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None
