from __future__ import annotations

import hashlib
import os

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.ingestion.models import AttachmentMetadata, EmailMessage
from backend.app.ingestion.sources import EmailSource
from backend.app.documents.models import DocumentFormat
from backend.app.storage.database import Base
from backend.app.storage.models import (
    AttachmentRecord,
    DocumentExtractionRecord,
    DocumentRecord,
    EmailMessageRecord,
    ProcessingEventRecord,
)
from backend.app.sync.service import SyncService


pytestmark = pytest.mark.skipif(
    not os.environ.get("HOLYSHIP_TEST_DATABASE_URL"),
    reason="HOLYSHIP_TEST_DATABASE_URL is required",
)


class MemorySource(EmailSource):
    def __init__(self, messages: list[EmailMessage], content: dict[str, bytes]):
        self.messages = messages
        self.content = content
        self.reads: list[str] = []

    def iter_messages(self):
        yield from self.messages

    def get_message(self, external_message_id: str):
        return next(message for message in self.messages if message.external_message_id == external_message_id)

    def get_attachment_content(self, attachment: AttachmentMetadata) -> bytes:
        self.reads.append(attachment.source_reference)
        return self.content[attachment.source_reference]


@pytest.fixture()
def db_factory():
    engine = create_engine(os.environ["HOLYSHIP_TEST_DATABASE_URL"], pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def _message(eid: str, body: str, filenames: list[str]) -> EmailMessage:
    return EmailMessage(
        external_message_id=eid,
        source_type="INCOMING_API",
        sender="sender@example.com",
        recipients=["ops@example.com"],
        subject="Please compare SI and draft BL",
        body=body,
        attachments=[
            AttachmentMetadata(
                filename=name,
                source_reference=f"memory/{eid}/{name}",
                content_type="text/plain" if name.endswith(".txt") else None,
                external_attachment_id=f"{eid}:{name}",
            )
            for name in filenames
        ],
        source_metadata={"fixture": "phase2"},
        content_hash=hashlib.sha256(eid.encode()).hexdigest(),
    )


def _run(factory, message: EmailMessage, content: dict[str, bytes]):
    source = MemorySource([message], content)
    with factory() as session:
        report = SyncService(session).sync(source)
    return report, source


@pytest.mark.req("ING-11")
@pytest.mark.req("DOC-01")
@pytest.mark.req("PRF-01")
def test_only_ready_comparisons_retrieve_attachment_content(db_factory):
    non_comparison = EmailMessage(
        **{
            **_message("invoice", "Please clarify this invoice charge.", ["invoice.txt"]).model_dump(),
            "subject": "Invoice query",
        }
    )
    awaiting = _message("awaiting", "Please send the draft BL for booking 42 for checking.", [])
    ready = _message("ready", "Please compare the attached SI and draft BL now.", ["a.txt", "b.txt"])
    content = {
        "memory/invoice/invoice.txt": b"COMMERCIAL INVOICE",
        "memory/ready/a.txt": b"SHIPPING INSTRUCTION\nShipper: A",
        "memory/ready/b.txt": b"BILL OF LADING (DRAFT)\nShipper: A",
    }
    source = MemorySource([non_comparison, awaiting, ready], content)

    with db_factory() as session:
        report = SyncService(session).sync(source)
        states = dict(
            session.execute(
                select(EmailMessageRecord.external_message_id, EmailMessageRecord.processing_status)
            ).all()
        )

    assert report.failed == 0
    assert source.reads == ["memory/ready/a.txt", "memory/ready/b.txt"]
    assert states == {"invoice": "COMPLETED", "awaiting": "AWAITING_DOCUMENTS", "ready": "EXTRACTING"}


@pytest.mark.req("DOC-02")
@pytest.mark.req("DOC-09")
@pytest.mark.req("STA-03")
def test_valid_pair_preserves_identity_hashes_raw_materialization_and_state_events(db_factory):
    message = _message("valid", "Please compare the attached SI and draft BL now.", ["candidate_BL.txt", "candidate_SI.txt"])
    content = {
        "memory/valid/candidate_BL.txt": b"SHIPPING INSTRUCTION\nShipper: A\nConsignee: B",
        "memory/valid/candidate_SI.txt": b"BILL OF LADING (DRAFT)\nShipper: A\nConsignee: B",
    }

    report, _source = _run(db_factory, message, content)
    assert report.failed == 0 and report.classified == 1

    with db_factory() as session:
        email = session.scalar(select(EmailMessageRecord).where(EmailMessageRecord.external_message_id == "valid"))
        attachments = list(session.scalars(select(AttachmentRecord).where(AttachmentRecord.email_id == email.id)))
        documents = list(session.scalars(select(DocumentRecord).where(DocumentRecord.email_id == email.id)))
        extractions = list(
            session.scalars(
                select(DocumentExtractionRecord)
                .join(DocumentRecord)
                .where(DocumentRecord.email_id == email.id)
            )
        )
        events = list(
            session.scalars(
                select(ProcessingEventRecord)
                .where(ProcessingEventRecord.email_id == email.id)
                .order_by(ProcessingEventRecord.created_at, ProcessingEventRecord.id)
            )
        )

        assert email.processing_status == "EXTRACTING"
        assert {row.document_type for row in documents} == {"SI", "DRAFT_BL"}
        assert {row.routing_outcome for row in documents} == {"SI_FOUND", "BL_FOUND"}
        assert all(row.content_sha256 == hashlib.sha256(content[row.source_reference]).hexdigest() for row in attachments)
        assert {row.source_reference for row in attachments} == set(content)
        assert {row.raw_text.splitlines()[0] for row in extractions} == {
            "SHIPPING INSTRUCTION",
            "BILL OF LADING (DRAFT)",
        }
        assert [event.new_status for event in events][-2:] == ["RETRIEVING_ATTACHMENTS", "EXTRACTING"]


@pytest.mark.req("CLS-09")
@pytest.mark.req("DOC-08")
@pytest.mark.req("DOC-09")
@pytest.mark.req("DOC-11")
@pytest.mark.req("DOC-13")
@pytest.mark.req("STA-03")
@pytest.mark.parametrize(
    ("eid", "filenames", "payloads", "expected_reason"),
    [
        ("missing-both", [], {}, "MISSING_REQUIRED_ATTACHMENT"),
        ("missing-si", ["only.txt"], {"only.txt": b"BILL OF LADING (DRAFT)\nShipper: A"}, "MISSING_REQUIRED_ATTACHMENT"),
        ("missing-bl", ["only.txt"], {"only.txt": b"SHIPPING INSTRUCTION\nShipper: A"}, "MISSING_REQUIRED_ATTACHMENT"),
        ("wrong", ["si.txt", "bl.txt"], {"si.txt": b"SHIPPING INSTRUCTION\nShipper: A", "bl.txt": b"COMMERCIAL INVOICE\nInvoice: 42"}, "WRONG_DOCUMENT_TYPE"),
        ("multiple-si", ["a.txt", "b.txt", "bl.txt"], {"a.txt": b"SHIPPING INSTRUCTION", "b.txt": b"SHIPPING INSTRUCTION", "bl.txt": b"BILL OF LADING (DRAFT)"}, "MULTIPLE_CANDIDATES"),
        ("unsupported", ["si.txt", "bl.bin"], {"si.txt": b"SHIPPING INSTRUCTION", "bl.bin": b"BILL OF LADING (DRAFT)"}, "UNSUPPORTED_ATTACHMENT"),
        ("empty", ["si.txt", "bl.txt"], {"si.txt": b"SHIPPING INSTRUCTION", "bl.txt": b""}, "CORRUPTED_ATTACHMENT"),
        ("inconclusive", ["si.txt", "bl.txt"], {"si.txt": b"SHIPPING INSTRUCTION", "bl.txt": b"Reference only"}, "DOCUMENT_ROLE_UNRESOLVED"),
    ],
)
def test_blocking_cases_are_structured_persisted_and_do_not_escape(
    db_factory,
    eid,
    filenames,
    payloads,
    expected_reason,
):
    message = _message(eid, "Please compare the attached SI and draft BL now; the documents are expected here.", filenames)
    content = {f"memory/{eid}/{name}": value for name, value in payloads.items()}

    report, _source = _run(db_factory, message, content)

    assert report.failed == 0
    assert report.outcomes[0].status == "CLASSIFIED"
    with db_factory() as session:
        email = session.scalar(select(EmailMessageRecord).where(EmailMessageRecord.external_message_id == eid))
        last_event = session.scalar(
            select(ProcessingEventRecord)
            .where(ProcessingEventRecord.email_id == email.id)
            .order_by(ProcessingEventRecord.created_at.desc(), ProcessingEventRecord.id.desc())
        )
        assert email.processing_status == "BLOCKED"
        assert last_event.reason_code == expected_reason


@pytest.mark.req("DOC-08")
def test_attachment_read_failure_is_structured_and_later_email_still_completes(db_factory):
    broken = _message("read-fails", "Please compare the attached SI and draft BL now.", ["si.txt", "bl.txt"])
    later = EmailMessage(
        **{
            **_message("later", "Please clarify this invoice charge.", []).model_dump(),
            "subject": "Invoice question",
        }
    )
    source = MemorySource([broken, later], {})

    with db_factory() as session:
        report = SyncService(session).sync(source)
        states = dict(
            session.execute(
                select(EmailMessageRecord.external_message_id, EmailMessageRecord.processing_status)
            ).all()
        )
        failed_email = session.scalar(
            select(EmailMessageRecord).where(EmailMessageRecord.external_message_id == "read-fails")
        )
        failed_event = session.scalar(
            select(ProcessingEventRecord)
            .where(ProcessingEventRecord.email_id == failed_email.id)
            .order_by(ProcessingEventRecord.created_at.desc(), ProcessingEventRecord.id.desc())
        )

    assert (report.failed, report.classified) == (1, 1)
    assert states == {"read-fails": "FAILED", "later": "COMPLETED"}
    assert failed_event.reason_code == "ATTACHMENT_READ_FAILED"


@pytest.mark.req("DOC-08")
def test_unexpected_reader_exception_is_persisted_without_escaping(db_factory):
    class ExplodingReader:
        @staticmethod
        def detect_format(_filename):
            return DocumentFormat.PLAIN_TEXT

        @staticmethod
        def read(*_args, **_kwargs):
            raise RuntimeError("synthetic reader failure")

    message = _message("reader-fails", "Please compare the attached SI and draft BL now.", ["si.txt", "bl.txt"])
    source = MemorySource(
        [message],
        {
            "memory/reader-fails/si.txt": b"SHIPPING INSTRUCTION",
            "memory/reader-fails/bl.txt": b"BILL OF LADING (DRAFT)",
        },
    )

    with db_factory() as session:
        service = SyncService(session)
        service._document_service.reader = ExplodingReader()
        report = service.sync(source)
        email = session.scalar(
            select(EmailMessageRecord).where(EmailMessageRecord.external_message_id == "reader-fails")
        )
        last_event = session.scalar(
            select(ProcessingEventRecord)
            .where(ProcessingEventRecord.email_id == email.id)
            .order_by(ProcessingEventRecord.created_at.desc(), ProcessingEventRecord.id.desc())
        )

    assert report.failed == 1
    assert report.outcomes[0].error == "DOCUMENT_READER_FAILED"
    assert email.processing_status == "FAILED"
    assert last_event.reason_code == "DOCUMENT_READER_FAILED"
