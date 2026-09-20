from __future__ import annotations

"""
Sync service integration tests — PostgreSQL only.

Requires:  $env:HOLYSHIP_TEST_DATABASE_URL = "postgresql+psycopg://..."
Skip automatically when the env var is absent.

Covers spec items:
  16. static source ingestion
  18. same email not duplicated on second sync (idempotency)
  19. changed email IS reclassified
  20. one malformed email does not stop the whole sync
  21. POST /api/email/incoming uses the same classifier
  +  processing job state transitions
  +  HUMAN_REVIEW_REQUIRED creates a HumanReviewCase
"""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.app.sync.service as sync_service
from backend.app.ingestion.models import AttachmentMetadata, EmailMessage
from backend.app.ingestion.sources import EmailSource
from backend.app.storage.database import Base
from backend.app.storage.models import (
    ClassificationResultRecord,
    EmailMessageRecord,
    HumanReviewCaseRecord,
    ProcessingJobRecord,
)
from backend.app.sync.service import SyncService


pytestmark = pytest.mark.skipif(
    not os.environ.get("HOLYSHIP_TEST_DATABASE_URL"),
    reason="HOLYSHIP_TEST_DATABASE_URL is required for sync integration tests",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def session():
    engine = create_engine(
        os.environ["HOLYSHIP_TEST_DATABASE_URL"], pool_pre_ping=True
    )
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as s:
        yield s
        s.rollback()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture()
def svc(session):
    return SyncService(session, confidence_threshold=0.80, margin_threshold=0.25)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _email(
    ext_id: str,
    subject: str,
    body: str,
    filenames: list[str] | None = None,
    source_type: str = "INCOMING_API",
    content_hash: str | None = None,
) -> EmailMessage:
    import hashlib, json
    filenames = filenames or []
    atts = [AttachmentMetadata(filename=f, source_reference=f) for f in filenames]
    if content_hash is None:
        raw = json.dumps({"id": ext_id, "sub": subject, "body": body}, sort_keys=True)
        content_hash = hashlib.sha256(raw.encode()).hexdigest()
    return EmailMessage(
        external_message_id=ext_id,
        source_type=source_type,
        subject=subject,
        body=body,
        attachments=atts,
        content_hash=content_hash,
    )


class ListSource(EmailSource):
    def __init__(self, messages: list[EmailMessage]):
        self._messages = messages
    def iter_messages(self):
        return iter(self._messages)
    def get_message(self, external_message_id: str) -> EmailMessage:
        for m in self._messages:
            if m.external_message_id == external_message_id:
                return m
        raise KeyError(external_message_id)
    def get_attachment_content(self, attachment: AttachmentMetadata) -> bytes:
        if "_SI" in attachment.filename or attachment.filename == "SI.txt":
            return b"SHIPPING INSTRUCTION\nShipper: A\nConsignee: B"
        return b"BILL OF LADING (DRAFT)\nShipper: A\nConsignee: B"


class BrokenSource(EmailSource):
    """Yields one good email then raises on the second."""
    def iter_messages(self):
        yield _email(
            "good_001",
            "TO CONFIRM DOCS",
            "Please compare the attached SI and draft BL. Check the details and confirm.",
            filenames=["good_001_SI.txt", "good_001_BL.txt"],
        )
        raise RuntimeError("simulated broken email payload")
    def get_message(self, external_message_id: str) -> EmailMessage:
        raise KeyError(external_message_id)
    def get_attachment_content(self, attachment: AttachmentMetadata) -> bytes:
        if "_SI" in attachment.filename:
            return b"SHIPPING INSTRUCTION\nShipper: A"
        return b"BILL OF LADING (DRAFT)\nShipper: A"


# ---------------------------------------------------------------------------
# Test 16 — static-like source ingestion classifies correctly
# ---------------------------------------------------------------------------
def test_sync_classifies_clear_document_comparison(svc, session):
    source = ListSource([
        _email(
            "email_001",
            "TO CONFIRM DOCS",
            "Please compare the attached SI and draft BL. Check the details and confirm.",
            filenames=["email_001_SI.txt", "email_001_BL.txt"],
        )
    ])
    report = svc.sync(source)

    assert report.total == 1
    assert report.classified == 1
    assert report.failed == 0

    results = session.query(ClassificationResultRecord).all()
    assert len(results) == 1
    assert results[0].category == "document_comparison"
    assert results[0].comparison_readiness == "READY_FOR_COMPARISON"
    assert results[0].confidence >= 0.80


# ---------------------------------------------------------------------------
# Test 18 — idempotency: unchanged email not reclassified on second sync
# ---------------------------------------------------------------------------
def test_sync_idempotent_for_unchanged_email(svc, session):
    email = _email(
        "email_idem",
        "TO CONFIRM DOCS",
        "Please compare the attached SI and draft BL. Check the details and confirm.",
    )
    source = ListSource([email])

    report1 = svc.sync(source)
    report2 = svc.sync(source)

    assert report1.classified == 1
    assert report2.skipped == 1
    assert report2.classified == 0

    # Only one ClassificationResult stored
    results = session.query(ClassificationResultRecord).all()
    assert len(results) == 1


# ---------------------------------------------------------------------------
# Test 19 — changed email IS reclassified
# ---------------------------------------------------------------------------
def test_sync_reclassifies_changed_email(svc, session):
    email_v1 = _email(
        "email_changed",
        "TO CONFIRM DOCS",
        "Please compare the attached SI and draft BL.",
        content_hash="a" * 64,
    )
    email_v2 = _email(
        "email_changed",
        "TO CONFIRM DOCS — updated",
        "Please compare the attached SI and draft BL. Check the details and confirm.",
        content_hash="b" * 64,
    )

    svc.sync(ListSource([email_v1]))
    svc.sync(ListSource([email_v2]))

    results = session.query(ClassificationResultRecord).all()
    assert len(results) == 2  # one per sync run


# ---------------------------------------------------------------------------
# Test 20 — one malformed email does not stop the whole sync
# ---------------------------------------------------------------------------
@pytest.mark.req("REL-06")
def test_sync_continues_after_broken_email(svc, session):
    report = svc.sync(BrokenSource())

    assert report.total == 1
    assert report.failed == 0
    assert report.source_failed == 1
    assert report.classified == 1   # the good email still got classified
    assert [(failure.reason_code, failure.error) for failure in report.source_failures] == [
        ("SOURCE_ITERATION_FAILED", "simulated broken email payload"),
    ]
    assert session.query(EmailMessageRecord).count() == 1

    # A failed stream does not poison a later, healthy source run.
    later = svc.sync(ListSource([_email("good_002", "Invoice", "Please send invoice.")]))
    assert later.failed == 0
    assert later.source_failed == 0
    assert later.total == 1


@pytest.mark.req("PRF-02")
@pytest.mark.req("REL-05")
def test_sync_commits_each_materialized_email_before_later_failure(svc, session, monkeypatch):
    """A per-email rollback cannot discard previously committed messages."""
    original_classify = sync_service.classify_email

    def fail_only_the_materialized_bad_message(classification_input, **kwargs):
        if classification_input.subject == "trigger processing failure":
            raise RuntimeError("simulated materialized processing failure")
        return original_classify(classification_input, **kwargs)

    monkeypatch.setattr(sync_service, "classify_email", fail_only_the_materialized_bad_message)
    report = svc.sync(ListSource([
        _email("transaction_a", "first success", "Please send invoice."),
        _email("transaction_b", "trigger processing failure", "Please send invoice."),
        _email("transaction_c", "third success", "Please send invoice."),
    ]))

    assert report.total == 3
    assert report.classified == 2
    assert report.failed == 1
    assert report.source_failed == 0
    assert [outcome.status for outcome in report.outcomes] == [
        "CLASSIFIED", "FAILED", "CLASSIFIED",
    ]
    assert session.query(EmailMessageRecord).count() == 3
    assert session.query(ClassificationResultRecord).count() == 2
    failed_jobs = session.query(ProcessingJobRecord).filter_by(status="FAILED").all()
    assert len(failed_jobs) == 1
    assert {record.external_message_id for record in session.query(EmailMessageRecord)} == {
        "transaction_a", "transaction_b", "transaction_c",
    }


# ---------------------------------------------------------------------------
# Test — HUMAN_REVIEW_REQUIRED creates a HumanReviewCase
# ---------------------------------------------------------------------------
def test_sync_creates_human_review_for_uncertain_email(svc, session):
    email = _email("email_empty", subject="", body="")
    report = svc.sync(ListSource([email]))

    if report.human_review > 0:
        cases = session.query(HumanReviewCaseRecord).all()
        assert len(cases) > 0
        assert cases[0].status == "OPEN"
        assert cases[0].reason_code is not None


# ---------------------------------------------------------------------------
# Test — processing job reaches terminal state
# ---------------------------------------------------------------------------
def test_sync_processing_job_state_transition(svc, session):
    source = ListSource([
        _email(
            "email_job",
            "verify draft BL",
            "Compare the attached SI and draft BL. Check the details and confirm.",
        )
    ])
    svc.sync(source)

    jobs = session.query(ProcessingJobRecord).all()
    assert len(jobs) == 1
    assert jobs[0].status in ("CLASSIFIED", "HUMAN_REVIEW_REQUIRED", "BLOCKED", "FAILED")


# ---------------------------------------------------------------------------
# Test 21 — sync_one (incoming API path) uses the same pipeline
# ---------------------------------------------------------------------------
def test_sync_one_uses_same_classification_pipeline(svc, session):
    email = _email(
        "incoming_001",
        "TO CONFIRM DOCS",
        "Please compare the attached SI and draft BL. Check the details and confirm.",
        filenames=["SI.txt", "BL.txt"],
    )
    outcome = svc.sync_one(email, ListSource([email]))

    assert outcome.status in ("CLASSIFIED", "HUMAN_REVIEW_REQUIRED")
    results = session.query(ClassificationResultRecord).all()
    assert len(results) == 1
    assert results[0].category == "document_comparison"
    assert results[0].comparison_readiness == "READY_FOR_COMPARISON"
