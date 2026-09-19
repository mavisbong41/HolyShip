from __future__ import annotations

import os
from pathlib import Path
from typing import get_args

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.api.schemas import ClassificationOut, EmailOut
from backend.app.classification.readiness import AWAITING_DOCUMENTS, READY_FOR_COMPARISON, UNRESOLVED
from backend.app.classification.signals import CATEGORY_SIGNALS, EmailCategory
from backend.app.ingestion.models import EmailMessage
from backend.app.main import app
from backend.app.storage.database import Base
from backend.app.storage.models import ClassificationResultRecord, EmailMessageRecord, HumanReviewCaseRecord
from backend.app.storage.transitions import PROCESSING_STATUSES
from backend.app.submission_adapter import to_submission_entry
from backend.app.sync.service import SyncService


CATEGORIES = {"document_comparison", "new_si_request", "invoice_query", "general_message", "spam"}
READINESS = {"READY_FOR_COMPARISON", "AWAITING_DOCUMENTS", "UNRESOLVED"}
STATUSES = {"NEW", "QUEUED", "CLASSIFYING", "CLASSIFIED", "AWAITING_DOCUMENTS", "RETRIEVING_ATTACHMENTS", "EXTRACTING", "COMPARING", "COMPLETED", "BLOCKED", "FAILED"}


def _literal_values(annotation: object) -> set[str]:
    values: set[str] = set()
    for item in get_args(annotation):
        nested = get_args(item)
        values.update(value for value in nested if isinstance(value, str))
        if isinstance(item, str):
            values.add(item)
    return values


def _message(eid: str, subject: str, body: str) -> EmailMessage:
    return EmailMessage(
        external_message_id=eid,
        source_type="INCOMING_API",
        subject=subject,
        body=body,
        content_hash=eid.ljust(64, "x"),
    )


@pytest.fixture()
def db_factory():
    url = os.environ.get("HOLYSHIP_TEST_DATABASE_URL")
    if not url:
        pytest.skip("HOLYSHIP_TEST_DATABASE_URL is required")
    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.mark.req("SCP-01")
def test_current_sync_never_creates_new_human_review_cases(db_factory):
    messages = [
        _message("scp-invoice", "Invoice", "Please clarify this payment amount on the invoice."),
        _message("scp-awaiting", "Draft BL", "Please send the draft BL for booking 42 for checking."),
        _message("scp-unresolved", "Check BL", "Please check draft BL details."),
        _message("scp-ambiguous", "Hello", "Please see the message below. Thank you."),
    ]

    with db_factory() as session:
        before = session.query(HumanReviewCaseRecord).count()
        outcomes = [SyncService(session).sync_one(message) for message in messages]
        session.commit()

    with db_factory() as session:
        records = {row.external_message_id: row for row in session.scalars(select(EmailMessageRecord)).all()}
        classifications = session.scalars(select(ClassificationResultRecord)).all()
        assert session.query(HumanReviewCaseRecord).count() == before == 0
        assert [outcome.status for outcome in outcomes] == ["CLASSIFIED"] * 4
        assert records["scp-invoice"].processing_status == "COMPLETED"
        assert records["scp-awaiting"].processing_status == "AWAITING_DOCUMENTS"
        assert records["scp-unresolved"].processing_status == "BLOCKED"
        assert records["scp-ambiguous"].processing_status == "COMPLETED"
        assert {row.category for row in classifications} <= CATEGORIES
        assert all(row.resolved_at_stage != "HUMAN_REVIEW" for row in classifications)


@pytest.mark.req("SCP-05")
def test_phase1_vocabularies_match_runtime_storage_and_api_contracts():
    assert {category.value for category in EmailCategory} == CATEGORIES
    assert {category.value for category in CATEGORY_SIGNALS} == CATEGORIES
    assert {READY_FOR_COMPARISON, AWAITING_DOCUMENTS, UNRESOLVED} == READINESS
    assert PROCESSING_STATUSES == STATUSES

    assert _literal_values(ClassificationOut.model_fields["category"].annotation) == CATEGORIES
    assert _literal_values(ClassificationOut.model_fields["comparison_readiness"].annotation) == READINESS
    assert _literal_values(EmailOut.model_fields["processing_status"].annotation) == STATUSES
    assert "reason_code" in ClassificationOut.model_fields

    table = ClassificationResultRecord.__table__
    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if constraint.name and hasattr(constraint, "sqltext")
    }
    assert set(constraints) >= {"ck_classification_category", "ck_classification_confidence", "ck_classification_readiness"}
    assert all(category in constraints["ck_classification_category"] for category in CATEGORIES)
    assert all(state in constraints["ck_classification_readiness"] for state in READINESS)
    assert table.c.reason_code.nullable is False

    status_constraint = next(
        str(constraint.sqltext)
        for constraint in EmailMessageRecord.__table__.constraints
        if constraint.name == "ck_email_processing_status"
    )
    assert all(status in status_constraint for status in STATUSES)


@pytest.mark.req("SCP-07")
def test_legacy_categories_are_confined_to_compatibility_boundaries():
    assert "UNCERTAIN" not in EmailCategory.__members__
    assert "GENERAL_MAIL" not in EmailCategory.__members__
    assert to_submission_entry("GENERAL_MAIL")["category"] == "GENERAL"
    assert to_submission_entry("UNCERTAIN", {"SPAM": 0.9})["category"] == "SPAM"

    routes = set(app.openapi()["paths"])
    assert {"/api/health", "/api/sync", "/api/emails", "/api/emails/{email_id}", "/api/emails/{email_id}/classification", "/api/email/incoming"} <= routes

    migration_0003 = Path("backend/alembic/versions/20260920_0003_add_comparison_readiness.py").read_text()
    assert "WHEN 'GENERAL_MAIL' THEN 'general_message'" in migration_0003
    assert "WHEN 'UNCERTAIN' THEN 'general_message'" in migration_0003

    migration_0004 = Path("backend/alembic/versions/20260920_0004_add_processing_state_events.py").read_text()
    assert "category='document_comparison' AND comparison_readiness='AWAITING_DOCUMENTS'" in migration_0004
    assert "category='document_comparison' AND comparison_readiness='UNRESOLVED'" in migration_0004
    assert all(status in migration_0004 for status in STATUSES)
