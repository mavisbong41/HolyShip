from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import Settings
from backend.app.ingestion.graph_client import GraphClientError
from backend.app.ingestion.graph_sync import GraphLifecycleSyncService, GraphSyncRuntime
from backend.app.storage.database import Base
from backend.app.storage.models import EmailMessageRecord, IngestionCheckpointRecord
from backend.app.sync.service import SyncService


pytestmark = pytest.mark.skipif(
    not os.environ.get("HOLYSHIP_TEST_DATABASE_URL"),
    reason="HOLYSHIP_TEST_DATABASE_URL is required",
)


def _message(message_id: str, subject: str) -> dict:
    return {
        "id": message_id,
        "internetMessageId": f"<{message_id}@example.com>",
        "subject": subject,
        "body": {"contentType": "text", "content": "General operational update."},
        "from": {"emailAddress": {"address": "sender@example.com"}},
        "toRecipients": [{"emailAddress": {"address": "ops@example.com"}}],
        "receivedDateTime": "2026-09-25T00:00:00Z",
        "isRead": False,
        "categories": [],
        "parentFolderId": "inbox",
        "attachments": [],
    }


class FakeGraphClient:
    def __init__(self, pages: dict[str | None, tuple[list[dict], str | None, str | None]], details: dict[str, dict]):
        self.settings = SimpleNamespace(microsoft_graph_mailbox="ops@example.com")
        self.pages = pages
        self.details = details
        self.requested_cursors: list[str | None] = []

    def delta(self, cursor=None):
        self.requested_cursors.append(cursor)
        return self.pages[cursor]

    def message(self, message_id: str):
        return self.details[message_id]


class FakeSubscriptionClient(FakeGraphClient):
    def __init__(self):
        super().__init__({}, {})
        self.created = 0
        self.renewed: list[str] = []

    def create_subscription(self, _url: str, _client_state: str):
        self.created += 1
        return {"id": f"sub-{self.created}", "expirationDateTime": "2026-09-25T08:00:00+00:00"}

    def renew_subscription(self, subscription_id: str):
        self.renewed.append(subscription_id)
        return {"id": subscription_id, "expirationDateTime": "2026-09-25T09:00:00+00:00"}


def test_graph_cursor_survives_restart_and_new_messages_use_shared_pipeline():
    engine = create_engine(os.environ["HOLYSHIP_TEST_DATABASE_URL"], pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        first_client = FakeGraphClient(
            {None: ([{"id": "g1", "isRead": False, "categories": [], "parentFolderId": "inbox"}], None, "cursor-A")},
            {"g1": _message("g1", "First Graph message")},
        )
        with factory() as session:
            service = GraphLifecycleSyncService(
                session, first_client,
                processor=lambda message, source, **kwargs: SyncService(session).sync_one(message, source, **kwargs),
            )
            result = service.sync_once()
            assert result["ingested"] == 1

        second_client = FakeGraphClient(
            {
                "cursor-A": ([
                    {"id": "g1", "isRead": True, "categories": ["Reviewed"], "parentFolderId": "archive"},
                    {"id": "g2", "isRead": False, "categories": [], "parentFolderId": "inbox"},
                ], None, "cursor-B")
            },
            {"g2": _message("g2", "Second Graph message")},
        )
        with factory() as session:
            service = GraphLifecycleSyncService(
                session, second_client,
                processor=lambda message, source, **kwargs: SyncService(session).sync_one(message, source, **kwargs),
            )
            result = service.sync_once()
            assert second_client.requested_cursors == ["cursor-A"]
            assert result["ingested"] == 1
            assert session.scalar(select(func.count()).select_from(EmailMessageRecord)) == 2
            first = session.scalar(select(EmailMessageRecord).where(EmailMessageRecord.external_message_id == "g1"))
            assert first.outlook_read_state == "READ"
            assert first.outlook_categories == ["Reviewed"]
            checkpoint = session.scalar(select(IngestionCheckpointRecord).where(IngestionCheckpointRecord.source_type == "MICROSOFT_GRAPH"))
            assert checkpoint.cursor_value == "cursor-B"

        lifecycle_client = FakeGraphClient(
            {"cursor-B": ([{"id": "g1", "@removed": {"reason": "deleted"}}], None, "cursor-C")},
            {},
        )
        with factory() as session:
            GraphLifecycleSyncService(session, lifecycle_client, processor=lambda message, source, **kwargs: None).sync_once()
            first = session.scalar(select(EmailMessageRecord).where(EmailMessageRecord.external_message_id == "g1"))
            assert first.lifecycle_status == "DELETED"

        restore_client = FakeGraphClient(
            {"cursor-C": ([{"id": "g1", "isRead": True, "categories": [], "parentFolderId": "inbox"}], None, "cursor-D")},
            {},
        )
        with factory() as session:
            GraphLifecycleSyncService(session, restore_client, processor=lambda message, source, **kwargs: None).sync_once()
            first = session.scalar(select(EmailMessageRecord).where(EmailMessageRecord.external_message_id == "g1"))
            assert first.lifecycle_status == "ACTIVE"
            assert first.restored_at is not None
            assert session.scalar(select(func.count()).select_from(EmailMessageRecord)) == 2
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_graph_failure_retains_cursor_and_retry_ingests_message():
    engine = create_engine(os.environ["HOLYSHIP_TEST_DATABASE_URL"], pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    page = {None: ([{"id": "retry-1", "isRead": False}], None, "cursor-after-retry")}
    try:
        with factory() as session:
            failing = GraphLifecycleSyncService(
                session,
                FakeGraphClient(page, {"retry-1": _message("retry-1", "Retry me")}),
                processor=lambda *_args, **_kwargs: SimpleNamespace(status="FAILED"),
            )
            with pytest.raises(GraphClientError):
                failing.sync_once()
            checkpoint = session.scalar(select(IngestionCheckpointRecord))
            assert checkpoint.cursor_value is None
            assert checkpoint.last_error_code == "GRAPH_DELTA_SYNC_FAILED"

        with factory() as session:
            retrying = GraphLifecycleSyncService(
                session,
                FakeGraphClient(page, {"retry-1": _message("retry-1", "Retry me")}),
                processor=lambda message, source, **kwargs: SyncService(session).sync_one(message, source, **kwargs),
            )
            assert retrying.sync_once()["ingested"] == 1
            assert session.scalar(select(func.count()).select_from(EmailMessageRecord)) == 1
            assert session.scalar(select(IngestionCheckpointRecord)).cursor_value == "cursor-after-retry"
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_graph_subscription_is_created_renewed_and_recreated_after_expiry():
    engine = create_engine(os.environ["HOLYSHIP_TEST_DATABASE_URL"], pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    settings = Settings(
        _env_file=None,
        microsoft_graph_webhook_url="https://example.com/api/v1/graph/notifications",
        microsoft_graph_webhook_client_state=SecretStr("opaque-state"),
        microsoft_graph_subscription_renew_before_minutes=30,
    )
    client = FakeSubscriptionClient()
    runtime = GraphSyncRuntime(settings, factory, lambda _session: lambda *_args, **_kwargs: None)
    runtime.clock = lambda: datetime(2026, 9, 25, 7, 0, tzinfo=timezone.utc)
    try:
        with factory() as session:
            runtime._ensure_subscription(session, client)
            checkpoint = session.scalar(select(IngestionCheckpointRecord))
            assert client.created == 1
            assert checkpoint.metadata_json["subscription_id"] == "sub-1"

            checkpoint.metadata_json = {
                "subscription_id": "sub-1",
                "subscription_expires_at": (runtime.clock() + timedelta(minutes=10)).isoformat(),
            }
            session.commit()
            runtime._ensure_subscription(session, client)
            assert client.renewed == ["sub-1"]

            checkpoint.metadata_json = {
                "subscription_id": "sub-1",
                "subscription_expires_at": (runtime.clock() - timedelta(minutes=1)).isoformat(),
            }
            session.commit()
            runtime._ensure_subscription(session, client)
            assert client.created == 2
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
