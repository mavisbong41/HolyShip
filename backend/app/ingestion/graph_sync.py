from __future__ import annotations

import hmac
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.ingestion.graph_client import GraphClientError, MicrosoftGraphClient
from backend.app.ingestion.graph_source import MicrosoftGraphSource
from backend.app.ingestion.models import EmailMessage
from backend.app.storage.models import AuditEventRecord, EmailMessageRecord, IngestionCheckpointRecord

logger = logging.getLogger(__name__)


class GraphLifecycleSyncService:
    """Delta convergence boundary using the shared HolyShip processing pipeline."""

    def __init__(
        self,
        session: Session,
        client: MicrosoftGraphClient,
        *,
        processor: Callable[..., object] | None = None,
        clock: Callable[[], datetime] | None = None,
    ):
        self.session = session
        self.client = client
        self.processor = processor
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.source_key = f"MICROSOFT_GRAPH:{client.settings.microsoft_graph_mailbox}"

    def checkpoint(self) -> IngestionCheckpointRecord:
        checkpoint = self.session.scalar(
            select(IngestionCheckpointRecord).where(IngestionCheckpointRecord.source_key == self.source_key)
        )
        if checkpoint is None:
            checkpoint = IngestionCheckpointRecord(
                source_key=self.source_key,
                source_type="MICROSOFT_GRAPH",
                poll_count=0,
                metadata_json={},
            )
            self.session.add(checkpoint)
            self.session.flush()
        return checkpoint

    def sync_once(self, delta_url: str | None = None) -> dict[str, object]:
        checkpoint = self.checkpoint()
        current_url = delta_url or checkpoint.cursor_value
        changed = deleted = restored = ingested = skipped = 0
        final_cursor = current_url
        try:
            while True:
                rows, next_url, page_delta = self.client.delta(current_url)
                for payload in rows:
                    graph_id = str(payload.get("id") or "")
                    if not graph_id:
                        continue
                    record = self.session.scalar(
                        select(EmailMessageRecord).where(
                            EmailMessageRecord.source_type == "MICROSOFT_GRAPH",
                            EmailMessageRecord.external_message_id == graph_id,
                        )
                    )
                    retry_failed = record is not None and record.processing_status == "FAILED"
                    if (record is None or retry_failed) and payload.get("@removed") is None:
                        if self.processor is None:
                            raise GraphClientError("Graph discovered a new message but no shared pipeline processor is configured")
                        detail = self.client.message(graph_id)
                        source = MicrosoftGraphSource([detail])
                        message = source.get_message(graph_id)
                        outcome = self.processor(message, source, force=retry_failed)
                        if getattr(outcome, "status", None) == "FAILED":
                            raise GraphClientError(f"HolyShip processing failed for Graph message {graph_id}")
                        ingested += int(getattr(outcome, "status", None) != "SKIPPED")
                        skipped += int(getattr(outcome, "status", None) == "SKIPPED")
                        record = self.session.scalar(
                            select(EmailMessageRecord).where(
                                EmailMessageRecord.source_type == "MICROSOFT_GRAPH",
                                EmailMessageRecord.external_message_id == graph_id,
                            )
                        )
                    if record is None:
                        continue
                    before = record.lifecycle_status
                    if payload.get("@removed") is not None:
                        record.lifecycle_status = "DELETED"
                        record.deleted_at = record.deleted_at or self.clock()
                        deleted += int(before != "DELETED")
                    else:
                        if before == "DELETED":
                            record.lifecycle_status = "ACTIVE"
                            record.restored_at = self.clock()
                            restored += 1
                        record.outlook_read_state = "READ" if payload.get("isRead") else "UNREAD"
                        record.outlook_categories = list(payload.get("categories") or [])
                        record.outlook_folder_id = payload.get("parentFolderId")
                    record.last_outlook_sync_at = self.clock()
                    record.outlook_sync_error = None
                    changed += 1
                    self.session.add(AuditEventRecord(
                        event_type="OUTLOOK_BACKGROUND_RECONCILED",
                        actor_type="SYSTEM", source="MICROSOFT_GRAPH",
                        entity_type="EMAIL", entity_id=record.id,
                        metadata_json={"previous_lifecycle": before, "lifecycle": record.lifecycle_status},
                    ))

                final_cursor = next_url or page_delta
                if not final_cursor:
                    raise GraphClientError("Microsoft Graph delta page did not return nextLink or deltaLink")
                checkpoint = self.checkpoint()
                checkpoint.cursor_value = final_cursor
                checkpoint.cursor_updated_at = self.clock()
                checkpoint.last_successful_poll_at = self.clock()
                checkpoint.poll_count += 1
                checkpoint.last_error_code = None
                checkpoint.last_error_message = None
                self.session.commit()
                if not next_url:
                    break
                current_url = next_url
        except Exception as exc:
            self.session.rollback()
            checkpoint = self.checkpoint()
            checkpoint.last_error_code = "GRAPH_DELTA_SYNC_FAILED"
            checkpoint.last_error_message = f"{type(exc).__name__}: {exc}"[:4000]
            self.session.commit()
            raise
        return {
            "changed": changed, "deleted": deleted, "restored": restored,
            "ingested": ingested, "skipped": skipped, "delta_url": final_cursor,
        }


class GraphSyncRuntime:
    def __init__(
        self,
        settings: Settings,
        session_factory: Callable[[], Session],
        processor_factory: Callable[[Session], Callable[[EmailMessage, MicrosoftGraphSource], object]],
    ):
        self.settings = settings
        self.session_factory = session_factory
        self.processor_factory = processor_factory
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not (self.settings.microsoft_graph_enabled and self.settings.microsoft_graph_sync_enabled):
            return
        self._thread = threading.Thread(target=self._run, name="holyship-graph-sync", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=5)

    def wake(self) -> None:
        self._wake.set()

    def validate_client_state(self, supplied: str | None) -> bool:
        expected = self.settings.microsoft_graph_webhook_client_state
        return bool(expected and supplied and hmac.compare_digest(expected.get_secret_value(), supplied))

    def _ensure_subscription(self, session: Session, client: MicrosoftGraphClient) -> None:
        if not self.settings.microsoft_graph_webhook_url or not self.settings.microsoft_graph_webhook_client_state:
            return
        service = GraphLifecycleSyncService(session, client, processor=self.processor_factory(session))
        checkpoint = service.checkpoint()
        metadata = dict(checkpoint.metadata_json or {})
        subscription_id = metadata.get("subscription_id")
        expires_text = metadata.get("subscription_expires_at")
        try:
            expires = datetime.fromisoformat(str(expires_text).replace("Z", "+00:00")) if expires_text else None
        except ValueError:
            expires = None
        renew_before = self.clock() + timedelta(minutes=self.settings.microsoft_graph_subscription_renew_before_minutes)
        if subscription_id and expires and expires > renew_before:
            return
        if subscription_id and expires and expires > self.clock():
            payload = client.renew_subscription(str(subscription_id))
        else:
            payload = client.create_subscription(
                self.settings.microsoft_graph_webhook_url,
                self.settings.microsoft_graph_webhook_client_state.get_secret_value(),
            )
        metadata.update({
            "subscription_id": payload.get("id", subscription_id),
            "subscription_expires_at": payload.get("expirationDateTime"),
        })
        checkpoint.metadata_json = metadata
        session.commit()

    @staticmethod
    def clock() -> datetime:
        return datetime.now(timezone.utc)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                with self.session_factory() as session:
                    client = MicrosoftGraphClient(self.settings)
                    self._ensure_subscription(session, client)
                    GraphLifecycleSyncService(
                        session, client, processor=self.processor_factory(session)
                    ).sync_once()
            except Exception:
                logger.exception("Microsoft Graph lifecycle synchronization failed")
            self._wake.wait(self.settings.microsoft_graph_sync_interval_seconds)
            self._wake.clear()
