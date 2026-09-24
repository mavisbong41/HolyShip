from __future__ import annotations

import os
from datetime import timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.data_lifecycle.service import DataLifecyclePolicy, DataLifecycleService, REDACTED_MARKER
from backend.app.storage.database import Base
from backend.app.storage.models import (
    AISuggestionRecord,
    AttachmentRecord,
    AuditEventRecord,
    DataLifecycleRunRecord,
    EmailMessageRecord,
    HumanReviewCaseRecord,
    HumanReviewEventRecord,
    ProcessingEventRecord,
    ProcessingJobRecord,
    utcnow,
)


pytestmark = pytest.mark.skipif(
    not os.environ.get("HOLYSHIP_TEST_DATABASE_URL"),
    reason="HOLYSHIP_TEST_DATABASE_URL is required",
)


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


def _policy() -> DataLifecyclePolicy:
    return DataLifecyclePolicy(
        raw_email_body_days=30,
        attachment_days=90,
        cache_days=7,
        processing_jobs_days=30,
        processing_events_days=90,
        ai_suggestions_days=30,
        ingestion_checkpoints_days=90,
    )


def _seed_case(session):
    now = utcnow()
    old = now - timedelta(days=120)
    email = EmailMessageRecord(
        external_message_id="retention-email-1",
        source_type="STATIC_BUNDLE",
        sender="customer@example.com",
        recipients=[],
        subject="Shipment update",
        body="Sensitive raw email body with customer details",
        received_at=old,
        source_metadata={},
        content_hash="a" * 64,
        processing_status="COMPLETED",
        created_at=old,
        updated_at=old,
    )
    session.add(email)
    session.flush()

    attachment = AttachmentRecord(
        email_id=email.id,
        filename="draft-bl.pdf",
        content_type="application/pdf",
        source_reference="data/bundle/inbox/draft-bl.pdf",
        external_attachment_id="att-1",
        content_sha256="b" * 64,
        retrieval_status="MATERIALIZED",
        created_at=old,
    )
    job = ProcessingJobRecord(
        email_id=email.id,
        job_type="CLASSIFY",
        status="COMPLETED",
        source_metadata={},
        source_content_hash=email.content_hash,
        attempt_count=1,
        created_at=old,
        updated_at=old,
    )
    event = ProcessingEventRecord(
        email_id=email.id,
        old_status="CLASSIFYING",
        new_status="CLASSIFIED",
        reason_code="CLASSIFICATION_COMPLETE",
        created_at=old,
    )
    review = HumanReviewCaseRecord(
        email_id=email.id,
        reason_code="COMPARISON_UNRESOLVED",
        reason_text="Needs review",
        candidate_scores={},
        evidence={},
        status="OPEN",
        workflow_identity="retention-review",
        created_at=old,
        updated_at=old,
    )
    session.add_all([attachment, job, event, review])
    session.flush()

    review_event = HumanReviewEventRecord(
        review_case_id=review.id,
        action="CASE_CREATED",
        details={"reason_code": review.reason_code},
        created_at=old,
    )
    suggestion = AISuggestionRecord(
        human_review_case_id=review.id,
        mode="ACTIONABLE_SUGGESTION",
        message="Use the BL value",
        document_side="BL",
        field="gross_weight_kg",
        current_value="1000 KG",
        suggested_value="1000.0",
        confidence=0.91,
        reason="OCR normalization",
        evidence_refs=["field-1"],
        provider_name="gemini",
        provider_model="gemini-2.5-flash",
        status="ACCEPTED",
        created_at=old,
    )
    session.add_all([review_event, suggestion])
    session.commit()
    return email.id, attachment.id, review.id


@pytest.mark.req("DLM-01")
def test_data_lifecycle_dry_run_records_summary_without_mutating_data(db_factory):
    with db_factory() as session:
        email_id, attachment_id, _review_id = _seed_case(session)

        run = DataLifecycleService(session, _policy(), now=utcnow()).run(dry_run=True)

        assert run.status == "DRY_RUN"
        assert run.dry_run is True
        assert run.summary["protected_records_preserved"]["human_review_history"] == "preserved"
        assert run.summary["delete_candidates"]["processing_jobs"] == 1
        assert run.summary["delete_candidates"]["processing_events"] == 1
        assert run.summary["redaction_candidates"]["raw_email_bodies"] == 1
        assert run.summary["redaction_candidates"]["attachment_source_references"] == 1
        assert run.summary["redaction_candidates"]["ai_suggestion_payloads"] == 1

        email = session.get(EmailMessageRecord, email_id)
        attachment = session.get(AttachmentRecord, attachment_id)
        assert email is not None and email.body.startswith("Sensitive raw email")
        assert attachment is not None and attachment.source_reference == "data/bundle/inbox/draft-bl.pdf"
        assert session.scalar(select(DataLifecycleRunRecord).where(DataLifecycleRunRecord.id == run.id)) is not None
        audit = session.scalar(select(AuditEventRecord).where(AuditEventRecord.entity_id == run.id))
        assert audit is not None
        assert audit.event_type == "DATA_LIFECYCLE_RUN_RECORDED"
        assert audit.source == "COMMAND"
        assert audit.metadata_json["status"] == "DRY_RUN"
        assert audit.metadata_json["summary"]["protected_records_preserved"]["audit_history"] == "preserved"


@pytest.mark.req("DLM-01")
def test_data_lifecycle_apply_cleans_transient_data_and_preserves_review_audit(db_factory):
    with db_factory() as session:
        email_id, attachment_id, review_id = _seed_case(session)

        run = DataLifecycleService(session, _policy(), now=utcnow()).run(dry_run=False)

        assert run.status == "APPLIED"
        assert session.scalar(select(ProcessingJobRecord)) is None
        assert session.scalar(select(ProcessingEventRecord)) is None

        email = session.get(EmailMessageRecord, email_id)
        attachment = session.get(AttachmentRecord, attachment_id)
        suggestion = session.scalar(select(AISuggestionRecord))
        assert email is not None and email.body == REDACTED_MARKER
        assert attachment is not None
        assert attachment.source_reference.startswith(REDACTED_MARKER)
        assert attachment.content_sha256 is None
        assert suggestion is not None
        assert suggestion.message == REDACTED_MARKER
        assert suggestion.current_value is None
        assert suggestion.suggested_value is None

        assert session.get(HumanReviewCaseRecord, review_id) is not None
        assert session.scalar(select(HumanReviewEventRecord)) is not None
        audit = session.scalar(select(AuditEventRecord).where(AuditEventRecord.entity_id == run.id))
        assert audit is not None
        assert audit.metadata_json["status"] == "APPLIED"
        assert audit.metadata_json["dry_run"] is False
