from __future__ import annotations

import hashlib
import os
import threading
from collections import Counter

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

from backend.app.documents.models import DocumentFormat, DocumentType, UnifiedDocument
from backend.app.extraction.extractor import DeterministicDocumentExtractor, EXTRACTOR_VERSION
from backend.app.extraction.service import DocumentFieldExtractionService, ExtractionTarget
from backend.app.ingestion.models import AttachmentMetadata, EmailMessage
from backend.app.ingestion.sources import EmailSource
from backend.app.storage.database import Base
from backend.app.storage.models import (
    AttachmentRecord,
    DocumentExtractionRecord,
    DocumentRecord,
    EmailMessageRecord,
    ExtractedFieldRecord,
    ProcessingEventRecord,
)
from backend.app.storage.repositories import DocumentExtractionRepository, DocumentRepository
from backend.app.sync.service import SyncService


pytestmark = pytest.mark.skipif(
    not os.environ.get("HOLYSHIP_TEST_DATABASE_URL"),
    reason="HOLYSHIP_TEST_DATABASE_URL is required",
)


@pytest.fixture()
def db_context():
    engine = create_engine(os.environ["HOLYSHIP_TEST_DATABASE_URL"], pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield engine, factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def _email(session, external_id: str = "phase3-orchestration") -> EmailMessageRecord:
    record = EmailMessageRecord(
        external_message_id=external_id,
        source_type="INCOMING_API",
        sender="sender@example.com",
        recipients=["ops@example.com"],
        subject="comparison",
        body="compare",
        source_metadata={},
        content_hash=hashlib.sha256(external_id.encode()).hexdigest(),
        processing_status="EXTRACTING",
    )
    session.add(record)
    session.flush()
    return record


def _target(
    session,
    email: EmailMessageRecord,
    *,
    filename: str,
    content: bytes,
    role: DocumentType,
    version: str = EXTRACTOR_VERSION,
) -> ExtractionTarget:
    digest = hashlib.sha256(content).hexdigest()
    attachment = AttachmentRecord(
        email_id=email.id,
        filename=filename,
        content_type="text/plain",
        source_reference=f"memory/{email.external_message_id}/{filename}/{digest[:8]}",
        external_attachment_id=f"{email.external_message_id}:{filename}:{digest[:8]}",
        content_sha256=digest,
        retrieval_status="MATERIALIZED",
    )
    session.add(attachment)
    session.flush()
    raw_text = content.decode("utf-8")
    document_record = DocumentRepository(session).create(
        email_id=email.id,
        attachment_id=attachment.id,
        document_type=role.value,
        format=DocumentFormat.PLAIN_TEXT.value,
        filename=filename,
        source_reference=attachment.source_reference,
        routing_outcome="SI_FOUND" if role == DocumentType.SI else "BL_FOUND",
        role_confidence=1.0,
        validation_outcome="VALID",
    )
    extraction = DocumentExtractionRepository(session).create(
        document_id=document_record.id,
        reader_used="PlainTextReader",
        extraction_status="PENDING",
        raw_text=raw_text,
        extractor_version=version,
    )
    document = UnifiedDocument(
        raw_text=raw_text,
        format=DocumentFormat.PLAIN_TEXT,
        reader_used="PlainTextReader",
        filename=filename,
        source_reference=attachment.source_reference,
        document_type=role,
    )
    return ExtractionTarget(
        document=document,
        content_sha256=digest,
        extraction=extraction,
    )


class BarrierExtractor:
    version = EXTRACTOR_VERSION

    def __init__(self) -> None:
        self.delegate = DeterministicDocumentExtractor()
        self.barrier = threading.Barrier(2)
        self.thread_ids: list[int] = []

    def extract(self, document):
        self.thread_ids.append(threading.get_ident())
        self.barrier.wait(timeout=5)
        return self.delegate.extract(document)


class SelectiveExtractor:
    def __init__(self, fail_roles: set[DocumentType], *, version: str = EXTRACTOR_VERSION):
        self.fail_roles = fail_roles
        self.version = version
        self.delegate = DeterministicDocumentExtractor(version=version)
        self.calls: Counter[DocumentType] = Counter()

    def extract(self, document):
        self.calls[document.document_type] += 1
        if document.document_type in self.fail_roles:
            raise RuntimeError(f"synthetic {document.document_type.value} extraction failure")
        return self.delegate.extract(document)


@pytest.mark.req("EXT-03")
def test_si_and_bl_start_concurrently_without_worker_thread_database_access(db_context):
    engine, factory = db_context
    extractor = BarrierExtractor()
    main_thread = threading.get_ident()
    sql_threads: list[int] = []

    def observe_sql(*_args, **_kwargs):
        sql_threads.append(threading.get_ident())

    with factory() as session:
        email = _email(session)
        si = _target(
            session,
            email,
            filename="si.txt",
            content=b"SHIPPING INSTRUCTION\nShipper: Alpha",
            role=DocumentType.SI,
        )
        bl = _target(
            session,
            email,
            filename="bl.txt",
            content=b"BILL OF LADING (DRAFT)\nShipper: Alpha",
            role=DocumentType.DRAFT_BL,
        )
        event.listen(engine, "before_cursor_execute", observe_sql)
        try:
            result = DocumentFieldExtractionService(session, extractor).extract([si, bl])
        finally:
            event.remove(engine, "before_cursor_execute", observe_sql)

        assert not result.failed
        assert result.computations == 2
        assert len(set(extractor.thread_ids)) == 2
        assert main_thread not in extractor.thread_ids
        assert sql_threads and set(sql_threads) == {main_thread}
        assert session.query(ExtractedFieldRecord).count() == 14


@pytest.mark.req("REL-03")
@pytest.mark.req("EXT-03")
@pytest.mark.parametrize("failed_role", [DocumentType.SI, DocumentType.DRAFT_BL])
def test_one_side_failure_preserves_other_side_and_retry_is_idempotent(
    db_context,
    failed_role,
):
    _engine, factory = db_context
    successful_role = (
        DocumentType.DRAFT_BL if failed_role == DocumentType.SI else DocumentType.SI
    )
    extractor = SelectiveExtractor({failed_role})

    with factory() as session:
        email = _email(session, f"retry-{failed_role.value}")
        si = _target(
            session,
            email,
            filename="si.txt",
            content=b"SHIPPING INSTRUCTION\nShipper: Alpha\nGross Weight: 22,000 KG",
            role=DocumentType.SI,
        )
        bl = _target(
            session,
            email,
            filename="bl.txt",
            content=b"BILL OF LADING (DRAFT)\nShipper: Alpha\nContainer Count: 6 x 40'HC",
            role=DocumentType.DRAFT_BL,
        )
        targets = [si, bl]
        first = DocumentFieldExtractionService(session, extractor).extract(targets)
        session.commit()

        by_role = {target.document.document_type: target for target in targets}
        success_target = by_role[successful_role]
        failed_target = by_role[failed_role]
        successful_rows = session.scalars(
            select(ExtractedFieldRecord).where(
                ExtractedFieldRecord.extraction_id == success_target.extraction.id
            )
        ).all()
        original_success_ids = {row.id for row in successful_rows}

        assert len(first.failed) == 1
        assert first.failed[0].extraction_id == failed_target.extraction.id
        assert success_target.extraction.extraction_status == "EXTRACTED"
        assert failed_target.extraction.extraction_status == "FAILED"
        assert len(successful_rows) == 7
        assert session.scalar(
            select(ExtractedFieldRecord).where(
                ExtractedFieldRecord.extraction_id == failed_target.extraction.id
            )
        ) is None

        extractor.fail_roles.clear()
        before_success_calls = extractor.calls[successful_role]
        retry = DocumentFieldExtractionService(session, extractor).extract(targets)
        session.commit()

        assert not retry.failed
        assert retry.computations == 1
        assert extractor.calls[successful_role] == before_success_calls
        assert extractor.calls[failed_role] == 2
        assert {
            row.id
            for row in session.scalars(
                select(ExtractedFieldRecord).where(
                    ExtractedFieldRecord.extraction_id == success_target.extraction.id
                )
            ).all()
        } == original_success_ids
        counts = dict(
            session.execute(
                select(
                    ExtractedFieldRecord.extraction_id,
                    func.count(ExtractedFieldRecord.id),
                )
                .where(
                    ExtractedFieldRecord.extraction_id.in_(
                        [target.extraction.id for target in targets]
                    )
                )
                .group_by(ExtractedFieldRecord.extraction_id)
            ).all()
        )
        assert counts == {target.extraction.id: 7 for target in targets}


@pytest.mark.req("PRF-04")
@pytest.mark.req("EXT-06")
def test_sha_version_cache_reuses_payload_with_current_document_provenance(db_context):
    _engine, factory = db_context
    content = b"SHIPPING INSTRUCTION\nShipper: Cache Corp\nGross Weight: 22,000 KG"
    other_content = b"SHIPPING INSTRUCTION\nShipper: Different Corp\nGross Weight: 12 KG"
    extractor_v1 = SelectiveExtractor(set())

    with factory() as session:
        email = _email(session, "cache-source")
        first = _target(
            session,
            email,
            filename="original-name.txt",
            content=content,
            role=DocumentType.SI,
        )
        second = _target(
            session,
            email,
            filename="different-name.txt",
            content=content,
            role=DocumentType.SI,
        )
        batch = DocumentFieldExtractionService(session, extractor_v1).extract([first, second])
        session.commit()

        assert batch.computations == 1
        assert batch.cache_hits == 1 and batch.cache_misses == 1
        assert sum(extractor_v1.calls.values()) == 1
        assert first.extraction.document_id != second.extraction.document_id
        assert first.extraction.id != second.extraction.id
        first_fields = session.scalars(
            select(ExtractedFieldRecord)
            .where(ExtractedFieldRecord.extraction_id == first.extraction.id)
            .order_by(ExtractedFieldRecord.field_name)
        ).all()
        second_fields = session.scalars(
            select(ExtractedFieldRecord)
            .where(ExtractedFieldRecord.extraction_id == second.extraction.id)
            .order_by(ExtractedFieldRecord.field_name)
        ).all()
        assert len(first_fields) == len(second_fields) == 7
        assert [
            (row.raw_label, row.raw_value_json, row.canonical_value, row.source_location)
            for row in first_fields
        ] == [
            (row.raw_label, row.raw_value_json, row.canonical_value, row.source_location)
            for row in second_fields
        ]

        third_email = _email(session, "cache-consumer")
        third = _target(
            session,
            third_email,
            filename="third-identity.txt",
            content=content,
            role=DocumentType.SI,
        )
        cached = DocumentFieldExtractionService(session, extractor_v1).extract([third])
        assert cached.computations == 0
        assert cached.cache_hits == 1 and sum(extractor_v1.calls.values()) == 1
        assert third.extraction.document_id not in {
            first.extraction.document_id,
            second.extraction.document_id,
        }
        assert len(
            session.scalars(
                select(ExtractedFieldRecord).where(
                    ExtractedFieldRecord.extraction_id == third.extraction.id
                )
            ).all()
        ) == 7

        extractor_v2 = SelectiveExtractor(set(), version="phase3-deterministic-v2-test")
        versioned = _target(
            session,
            third_email,
            filename="version-bump.txt",
            content=content,
            role=DocumentType.SI,
            version=extractor_v2.version,
        )
        invalidated = DocumentFieldExtractionService(session, extractor_v2).extract([versioned])
        assert invalidated.computations == 1
        assert sum(extractor_v2.calls.values()) == 1

        same_name_different_bytes = _target(
            session,
            third_email,
            filename="original-name.txt",
            content=other_content,
            role=DocumentType.SI,
        )
        different = DocumentFieldExtractionService(session, extractor_v1).extract(
            [same_name_different_bytes]
        )
        assert different.computations == 1
        assert sum(extractor_v1.calls.values()) == 2
        session.commit()

        counts = session.execute(
            select(
                ExtractedFieldRecord.extraction_id,
                func.count(ExtractedFieldRecord.id),
            )
            .group_by(ExtractedFieldRecord.extraction_id)
        ).all()
        assert counts and all(count == 7 for _extraction_id, count in counts)
        cached_extraction_id = third.extraction.id
        cached_document_id = third.extraction.document_id
        cached_payload = [
            (
                row.field_name,
                row.raw_label,
                row.raw_value_json,
                row.canonical_value,
                row.source_location,
            )
            for row in session.scalars(
                select(ExtractedFieldRecord)
                .where(ExtractedFieldRecord.extraction_id == cached_extraction_id)
                .order_by(ExtractedFieldRecord.field_name)
            ).all()
        ]

    with factory() as fresh_session:
        reloaded = DocumentExtractionRepository(fresh_session).get(cached_extraction_id)
        assert reloaded is not None
        assert reloaded.document_id == cached_document_id
        assert reloaded.extractor_version == EXTRACTOR_VERSION
        assert reloaded.metadata_json["field_extraction"]["cache_status"] == "HIT"
        assert [
            (
                row.field_name,
                row.raw_label,
                row.raw_value_json,
                row.canonical_value,
                row.source_location,
            )
            for row in sorted(reloaded.fields, key=lambda item: item.field_name)
        ] == cached_payload
        assert len(reloaded.fields) == 7


class MemorySource(EmailSource):
    def __init__(self, message: EmailMessage, content: dict[str, bytes]):
        self.message = message
        self.content = content

    def iter_messages(self):
        yield self.message

    def get_message(self, external_message_id: str):
        return self.message

    def get_attachment_content(self, attachment: AttachmentMetadata) -> bytes:
        return self.content[attachment.source_reference]


@pytest.mark.req("EXT-03")
@pytest.mark.parametrize("failed_role", [DocumentType.SI, DocumentType.DRAFT_BL])
def test_pipeline_marks_field_failure_and_commits_other_side(db_context, failed_role):
    _engine, factory = db_context
    eid = f"pipeline-fails-{failed_role.value}"
    attachments = [
        AttachmentMetadata(
            filename="si.txt",
            source_reference=f"memory/{eid}/si.txt",
            content_type="text/plain",
        ),
        AttachmentMetadata(
            filename="bl.txt",
            source_reference=f"memory/{eid}/bl.txt",
            content_type="text/plain",
        ),
    ]
    message = EmailMessage(
        external_message_id=eid,
        source_type="INCOMING_API",
        sender="sender@example.com",
        recipients=["ops@example.com"],
        subject="Compare attached SI and draft BL",
        body="Please compare the attached SI and draft BL now.",
        attachments=attachments,
        source_metadata={},
        content_hash=hashlib.sha256(eid.encode()).hexdigest(),
    )
    source = MemorySource(
        message,
        {
            f"memory/{eid}/si.txt": b"SHIPPING INSTRUCTION\nShipper: Alpha",
            f"memory/{eid}/bl.txt": b"BILL OF LADING (DRAFT)\nShipper: Alpha",
        },
    )

    with factory() as session:
        service = SyncService(session)
        service._document_service.field_extractor = SelectiveExtractor({failed_role})
        report = service.sync(source)

    with factory() as session:
        email = session.scalar(
            select(EmailMessageRecord).where(EmailMessageRecord.external_message_id == eid)
        )
        rows = session.execute(
            select(
                DocumentRecord.document_type,
                DocumentExtractionRecord.extraction_status,
                func.count(ExtractedFieldRecord.id),
            )
            .join(DocumentExtractionRecord, DocumentExtractionRecord.document_id == DocumentRecord.id)
            .outerjoin(ExtractedFieldRecord, ExtractedFieldRecord.extraction_id == DocumentExtractionRecord.id)
            .where(DocumentRecord.email_id == email.id)
            .group_by(DocumentRecord.document_type, DocumentExtractionRecord.extraction_status)
        ).all()
        last_event = session.scalar(
            select(ProcessingEventRecord)
            .where(ProcessingEventRecord.email_id == email.id)
            .order_by(ProcessingEventRecord.created_at.desc(), ProcessingEventRecord.id.desc())
        )

        assert report.failed == 1
        assert report.outcomes[0].error == "DOCUMENT_FIELD_EXTRACTION_FAILED"
        assert email.processing_status == "FAILED"
        assert last_event.reason_code == "DOCUMENT_FIELD_EXTRACTION_FAILED"
        assert sorted(count for _role, _status, count in rows) == [0, 7]
        by_role = {DocumentType(role): (status, count) for role, status, count in rows}
        assert by_role[failed_role] == ("FAILED", 0)
        other = DocumentType.DRAFT_BL if failed_role == DocumentType.SI else DocumentType.SI
        assert by_role[other] == ("EXTRACTED", 7)
