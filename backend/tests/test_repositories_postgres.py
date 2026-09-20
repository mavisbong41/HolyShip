import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.ingestion.models import AttachmentMetadata, EmailMessage
from backend.app.storage.database import Base
from backend.app.storage.repositories import (
    ClassificationResultRepository,
    EmailRepository,
    HumanReviewRepository,
    ProcessingJobRepository,
)


pytestmark = pytest.mark.skipif(
    not os.environ.get("HOLYSHIP_TEST_DATABASE_URL"),
    reason="HOLYSHIP_TEST_DATABASE_URL is required for PostgreSQL repository integration tests",
)


@pytest.fixture()
def session():
    engine = create_engine(os.environ["HOLYSHIP_TEST_DATABASE_URL"], pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with SessionLocal() as db:
        yield db
        db.rollback()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_repositories_write_and_read_batch1_foundation_records(session):
    email_repo = EmailRepository(session)
    message = EmailMessage(
        external_message_id="email_001",
        source_type="STATIC_BUNDLE",
        sender="docs@example.com",
        subject="Please verify draft BL",
        body="Please compare the attached SI and draft BL.",
        attachments=[
            AttachmentMetadata(
                filename="email_001_SI.txt",
                source_reference="attachments/email_001_SI.txt",
                content_type="text/plain",
                external_attachment_id="attachments/email_001_SI.txt",
            )
        ],
        source_metadata={"source_file": "email_001.json"},
        content_hash="a" * 64,
    )

    email, changed = email_repo.upsert_message(message)
    job = ProcessingJobRepository(session).create(email_id=email.id, job_type="INITIAL_SYNC", status="CLASSIFIED")
    classification = ClassificationResultRepository(session).create(
        email_id=email.id,
        category="document_comparison",
        confidence=0.92,
        candidate_scores={"DOCUMENT_COMPARISON": 0.92, "INVOICE_QUERY": 0.05},
        reason="Body explicitly requests SI/BL comparison.",
        evidence_summary={"body": "compare the attached SI and draft BL"},
        conflict_detected=False,
        resolved_at_stage="STAGE_1",
    )
    review = HumanReviewRepository(session).create(
        email_id=email.id,
        reason_code="LOW_CONFIDENCE",
        reason_text="Classification confidence below threshold.",
        candidate_scores={"DOCUMENT_COMPARISON": 0.52, "INVOICE_QUERY": 0.49},
        evidence={"subject": "Please review"},
        confidence=0.52,
    )
    session.commit()

    loaded = email_repo.get_by_source_external_id("STATIC_BUNDLE", "email_001")

    assert changed is True
    assert loaded is not None
    assert loaded.id == email.id
    assert len(loaded.attachments) == 1
    assert job.status == "CLASSIFIED"
    assert classification.category == "document_comparison"
    assert review.status == "OPEN"


def test_email_upsert_does_not_rewrite_unchanged_message(session):
    repo = EmailRepository(session)
    message = EmailMessage(
        external_message_id="email_002",
        source_type="STATIC_BUNDLE",
        subject="FYI",
        body="Operational update.",
        content_hash="b" * 64,
    )

    first, first_changed = repo.upsert_message(message)
    second, second_changed = repo.upsert_message(message)

    assert first_changed is True
    assert second_changed is False
    assert first.id == second.id

