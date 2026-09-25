from __future__ import annotations

import hashlib
import os

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import selectinload, sessionmaker

from backend.app.api.product_queries import _effective_classification
from backend.app.storage.database import Base
from backend.app.storage.models import ClassificationResultRecord, EmailMessageRecord


pytestmark = pytest.mark.skipif(
    not os.environ.get("HOLYSHIP_TEST_DATABASE_URL"),
    reason="HOLYSHIP_TEST_DATABASE_URL is required",
)


def test_later_machine_prediction_does_not_replace_manual_category():
    engine = create_engine(os.environ["HOLYSHIP_TEST_DATABASE_URL"], pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with factory() as session:
            email = EmailMessageRecord(
                external_message_id="manual-category-sequence",
                source_type="INCOMING_API", recipients=[], subject="Review", body="Review documents",
                source_metadata={}, content_hash=hashlib.sha256(b"manual-category-sequence").hexdigest(),
                processing_status="CLASSIFIED",
            )
            session.add(email)
            session.flush()
            session.add_all([
                ClassificationResultRecord(
                    email_id=email.id, category="general_message", confidence=0.9,
                    candidate_scores={"general_message": 0.9}, reason="initial", reason_code="AUTO_INITIAL",
                    evidence_summary={}, conflict_detected=False, resolved_at_stage="stage1",
                    classifier_version="auto-v1", source_content_hash=email.content_hash,
                ),
                ClassificationResultRecord(
                    email_id=email.id, category="document_comparison", confidence=1.0,
                    candidate_scores={"document_comparison": 1.0}, reason="human", reason_code="MANUAL_CATEGORY_OVERRIDE",
                    evidence_summary={"reviewer": "Human"}, conflict_detected=False, resolved_at_stage="human_override",
                    comparison_readiness="UNRESOLVED", classifier_version="manual-v1", source_content_hash=email.content_hash,
                ),
                ClassificationResultRecord(
                    email_id=email.id, category="invoice_query", confidence=0.95,
                    candidate_scores={"invoice_query": 0.95}, reason="later automatic", reason_code="AUTO_RERUN",
                    evidence_summary={}, conflict_detected=False, resolved_at_stage="stage1",
                    classifier_version="auto-v2", source_content_hash=email.content_hash,
                ),
            ])
            session.commit()

        with factory() as session:
            email = session.scalar(
                select(EmailMessageRecord)
                .where(EmailMessageRecord.external_message_id == "manual-category-sequence")
                .options(selectinload(EmailMessageRecord.classification_results))
            )
            assert {row.category for row in email.classification_results} == {
                "general_message", "document_comparison", "invoice_query",
            }
            assert _effective_classification(email.classification_results).category == "document_comparison"
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
