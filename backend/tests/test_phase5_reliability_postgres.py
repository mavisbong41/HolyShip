from __future__ import annotations

import hashlib
import json
import os
import threading

import pytest
from sqlalchemy import func, select
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.ingestion.models import EmailMessage
from backend.app.ingestion.sources import EmailSource
from backend.app.storage.database import Base
from backend.app.storage.models import (
    ClassificationResultRecord,
    EmailMessageRecord,
    ProcessingJobRecord,
)
from backend.app.sync.service import SyncService


pytestmark = pytest.mark.skipif(
    not os.environ.get("HOLYSHIP_TEST_DATABASE_URL"),
    reason="HOLYSHIP_TEST_DATABASE_URL is required",
)


class _MemorySource(EmailSource):
    def __init__(self, messages: list[EmailMessage]):
        self.messages = messages

    def iter_messages(self):
        yield from self.messages

    def get_message(self, external_message_id: str):
        return next(message for message in self.messages if message.external_message_id == external_message_id)


@pytest.fixture()
def db_factory():
    engine = create_engine(os.environ["HOLYSHIP_TEST_DATABASE_URL"], pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def _message(external_id: str, *, subject: str = "Invoice question", body: str = "Please clarify this invoice.") -> EmailMessage:
    content_hash = hashlib.sha256(
        json.dumps([external_id, subject, body], sort_keys=True).encode("utf-8")
    ).hexdigest()
    return EmailMessage(
        external_message_id=external_id,
        source_type="INCOMING_API",
        sender="sender@example.com",
        recipients=["ops@example.com"],
        subject=subject,
        body=body,
        content_hash=content_hash,
    )


def _snapshot(factory):
    with factory() as session:
        emails = session.scalars(
            select(EmailMessageRecord).order_by(EmailMessageRecord.external_message_id)
        ).all()
        return [
            (
                email.external_message_id,
                email.processing_status,
                session.scalar(
                    select(ClassificationResultRecord.category)
                    .where(ClassificationResultRecord.email_id == email.id)
                    .order_by(ClassificationResultRecord.created_at.desc())
                ),
                session.scalar(
                    select(func.count(ProcessingJobRecord.id))
                    .where(ProcessingJobRecord.email_id == email.id)
                ),
            )
            for email in emails
        ]


def test_repeated_initial_sync_converges_without_duplicate_graph(db_factory):
    messages = [_message("repeat-1"), _message("repeat-2", subject="General update", body="The vessel departed.")]
    source = _MemorySource(messages)

    with db_factory() as session:
        first = SyncService(session).sync(source)
        second = SyncService(session).sync(source)
        assert first.classified == 2
        assert second.skipped == 2

        assert session.scalar(select(func.count(EmailMessageRecord.id))) == 2
        assert session.scalar(select(func.count(ClassificationResultRecord.id))) == 2
        assert session.scalar(select(func.count(ProcessingJobRecord.id))) == 2


def test_concurrent_duplicate_ingestion_creates_one_logical_case(db_factory):
    message = _message("concurrent-duplicate")
    barrier = threading.Barrier(2)
    errors: list[Exception] = []

    def ingest_once() -> None:
        try:
            with db_factory() as session:
                barrier.wait(timeout=5)
                SyncService(session).sync_one(message)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=ingest_once) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert errors == []
    with db_factory() as session:
        assert session.scalar(select(func.count(EmailMessageRecord.id))) == 1
        assert session.scalar(select(func.count(ClassificationResultRecord.id))) == 1
        assert session.scalar(select(func.count(ProcessingJobRecord.id))) == 1


def test_restart_resumes_interrupted_classification_without_new_email(db_factory):
    message = _message("restart-me")
    with db_factory() as session:
        row = EmailMessageRecord(
            external_message_id=message.external_message_id,
            source_type=message.source_type,
            sender=message.sender,
            recipients=message.recipients,
            subject=message.subject,
            body=message.body,
            source_metadata={},
            content_hash=message.content_hash,
            processing_status="CLASSIFYING",
        )
        session.add(row)
        session.commit()

    with db_factory() as session:
        report = SyncService(session).sync(_MemorySource([message]))
        assert report.classified == 1

    with db_factory() as session:
        row = session.scalar(
            select(EmailMessageRecord).where(
                EmailMessageRecord.external_message_id == message.external_message_id
            )
        )
        assert row.processing_status == "COMPLETED"
        assert session.scalar(select(func.count(EmailMessageRecord.id))) == 1
        assert session.scalar(select(func.count(ClassificationResultRecord.id))) == 1
        assert session.scalar(select(func.count(ProcessingJobRecord.id))) == 1


def test_single_worker_and_parallel_worker_snapshots_match(db_factory):
    messages = [
        _message("parallel-1"),
        _message("parallel-2", subject="General update", body="The vessel departed."),
        _message("parallel-3", subject="Invoice question", body="Please send the invoice copy."),
    ]

    with db_factory() as session:
        single = SyncService(
            session,
            max_workers=1,
            session_factory=db_factory,
        ).sync(_MemorySource(messages))
    single_snapshot = _snapshot(db_factory)

    with db_factory() as session:
        Base.metadata.drop_all(session.bind)
        Base.metadata.create_all(session.bind)
        parallel = SyncService(
            session,
            max_workers=3,
            session_factory=db_factory,
        ).sync(_MemorySource(messages))
    parallel_snapshot = _snapshot(db_factory)

    assert single.unhandled_exceptions == 0
    assert parallel.unhandled_exceptions == 0
    assert single_snapshot == parallel_snapshot
