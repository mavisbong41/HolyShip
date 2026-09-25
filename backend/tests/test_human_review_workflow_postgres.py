from __future__ import annotations

from datetime import datetime, timezone
import copy
import hashlib
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.orm import sessionmaker

from backend.app.api.deps import get_session
from backend.app.api.product_queries import get_product_summary, list_human_reviews
from backend.app.extraction.models import (
    CANONICAL_FIELDS,
    CanonicalField,
    DocumentExtractionResult,
    ExtractedField,
    FieldStatus,
    MappingMethod,
    SourceLocation,
)
from backend.app.main import app
from backend.app.comparison.persistence import PersistedComparisonService
from backend.app.review.service import HumanReviewService, ReviewConflictError
from backend.app.review.plan_service import PlanItemInput, ReviewPlanService
from backend.app.storage.database import Base
from backend.app.storage.models import (
    ComparisonResultRecord,
    DocumentExtractionRecord,
    DocumentRecord,
    EmailMessageRecord,
    ExtractedFieldRecord,
    HumanReviewCaseRecord,
    HumanReviewEventRecord,
    HumanReviewFieldOverrideRecord,
    ReviewPlanRecord,
    AuditEventRecord,
)
from backend.app.storage.repositories import (
    ComparisonResultRepository,
    DocumentExtractionRepository,
    DocumentRepository,
    ExtractedFieldRepository,
)


pytestmark = pytest.mark.skipif(
    not os.environ.get("HOLYSHIP_TEST_DATABASE_URL"),
    reason="HOLYSHIP_TEST_DATABASE_URL is required",
)


VALUES = {
    CanonicalField.SHIPPER: "Alpha Trading Sdn Bhd",
    CanonicalField.CONSIGNEE: "Beta Imports Ltd",
    CanonicalField.NOTIFY_PARTY: "Gamma Notify Co",
    CanonicalField.PORT_OF_LOADING: "Port Klang",
    CanonicalField.PORT_OF_DISCHARGE: "Singapore",
    CanonicalField.CONTAINER_COUNT: 6,
    CanonicalField.GROSS_WEIGHT_KG: 22000,
}


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


def _field(name: CanonicalField, *, missing: bool = False) -> ExtractedField:
    if missing:
        return ExtractedField(
            canonical_field=name,
            raw_label=None,
            raw_value=None,
            canonical_value=None,
            status=FieldStatus.MISSING,
            confidence=0.0,
            mapping_method=None,
            source_location=SourceLocation(source_type="fixture"),
            evidence={"reason_code": "FIELD_NOT_PRESENT"},
        )
    value = VALUES[name]
    return ExtractedField(
        canonical_field=name,
        raw_label=name.value.upper(),
        raw_value=value,
        canonical_value=value,
        status=FieldStatus.RESOLVED,
        confidence=1.0,
        mapping_method=MappingMethod.EXACT_LABEL,
        source_location=SourceLocation(source_type="fixture", line_number=1),
        evidence={"fixture": True},
    )


def _result(role: str, *, missing_bl_field: CanonicalField | None = None) -> DocumentExtractionResult:
    return DocumentExtractionResult(
        document_role=role,
        fields={
            name: _field(name, missing=role == "DRAFT_BL" and name == missing_bl_field)
            for name in CANONICAL_FIELDS
        },
        extractor_version="human-review-fixture-v1",
    )


def _blocked_comparison(session, external_id: str = "review-case-1"):
    email = EmailMessageRecord(
        external_message_id=external_id,
        source_type="INCOMING_API",
        sender="review@example.com",
        recipients=["ops@example.com"],
        subject="Compare SI and BL",
        body="Please review the attached shipping documents.",
        source_metadata={},
        content_hash=hashlib.sha256(external_id.encode()).hexdigest(),
        processing_status="EXTRACTING",
    )
    session.add(email)
    session.flush()
    extraction_repo = DocumentExtractionRepository(session)
    field_repo = ExtractedFieldRepository(session)
    extraction_ids = {}
    for role in ("SI", "DRAFT_BL"):
        document = DocumentRepository(session).create(
            email_id=email.id,
            attachment_id=None,
            document_type=role,
            format="PLAIN_TEXT",
            filename=f"{role.lower()}.txt",
            source_reference=f"memory/{external_id}/{role}",
            routing_outcome="SI_FOUND" if role == "SI" else "BL_FOUND",
            role_confidence=1.0,
            validation_outcome="VALID",
        )
        extraction = extraction_repo.create(
            document_id=document.id,
            reader_used="PlainTextReader",
            extraction_status="EXTRACTED",
            raw_text="immutable source",
            extractor_version="human-review-fixture-v1",
        )
        field_repo.create_result(
            extraction.id,
            _result(
                role,
                missing_bl_field=CanonicalField.NOTIFY_PARTY,
            ),
        )
        extraction_ids[role] = extraction.id
    outcome = PersistedComparisonService(session).compare_and_persist(
        email,
        si_extraction_id=extraction_ids["SI"],
        bl_extraction_id=extraction_ids["DRAFT_BL"],
    )
    assert email.processing_status == "BLOCKED"
    case = HumanReviewService(session).ensure_actionable_case(
        email,
        reason_code=outcome.record.reason_code,
        source_comparison_id=outcome.record.id,
    )
    assert case is not None
    session.flush()
    return email, outcome.record, case


def _extraction_snapshot(session, email_id):
    rows = session.scalars(
        select(ExtractedFieldRecord)
        .join(DocumentExtractionRecord, DocumentExtractionRecord.id == ExtractedFieldRecord.extraction_id)
        .join(DocumentRecord, DocumentRecord.id == DocumentExtractionRecord.document_id)
        .where(DocumentRecord.email_id == email_id)
        .order_by(ExtractedFieldRecord.id)
    ).all()
    return copy.deepcopy(
        [
            (
                row.id,
                row.raw_label,
                row.raw_value,
                row.raw_value_json,
                row.canonical_value,
                row.status,
                row.evidence,
            )
            for row in rows
        ]
    )


@pytest.mark.req("HR-01")
@pytest.mark.req("HR-02")
def test_actionable_blocked_is_idempotent_but_waiting_and_failed_are_not_review(db_factory):
    with db_factory() as session:
        blocked = EmailMessageRecord(
            external_message_id="blocked-policy",
            source_type="INCOMING_API",
            subject="blocked",
            body="blocked",
            content_hash="a" * 64,
            processing_status="BLOCKED",
        )
        waiting = EmailMessageRecord(
            external_message_id="waiting-policy",
            source_type="INCOMING_API",
            subject="waiting",
            body="waiting",
            content_hash="b" * 64,
            processing_status="AWAITING_DOCUMENTS",
        )
        failed = EmailMessageRecord(
            external_message_id="failed-policy",
            source_type="INCOMING_API",
            subject="failed",
            body="failed",
            content_hash="c" * 64,
            processing_status="FAILED",
        )
        session.add_all([blocked, waiting, failed])
        session.flush()
        service = HumanReviewService(session)
        first = service.ensure_actionable_case(blocked, reason_code="MISSING_REQUIRED_ATTACHMENT")
        second = service.ensure_actionable_case(blocked, reason_code="MISSING_REQUIRED_ATTACHMENT")
        assert first is not None and second.id == first.id
        assert service.ensure_actionable_case(waiting, reason_code="MISSING_REQUIRED_ATTACHMENT") is None
        assert service.ensure_actionable_case(failed, reason_code="UNREADABLE_ATTACHMENT") is None
        assert session.scalar(select(func.count(HumanReviewCaseRecord.id))) == 1


def test_multi_action_review_plan_applies_two_actions_and_recompares_once(db_factory):
    with db_factory() as session:
        email, original, case = _blocked_comparison(session, "review-plan-multi")
        service = ReviewPlanService(session)
        plan = service.create(case.id, created_by="Reviewer", items=[
            PlanItemInput(
                document_side="BL", field_name="notify_party", current_value=None,
                proposed_value="Gamma Notify Co", reason="AI evidence", status="APPROVED",
            ),
            PlanItemInput(
                document_side="BL", field_name="consignee", current_value="Beta Imports Ltd",
                proposed_value="Wrong proposal", reason="Reviewer corrected", status="APPROVED",
            ),
            PlanItemInput(
                document_side="SI", field_name="shipper", current_value="Alpha Trading Sdn Bhd",
                proposed_value="Rejected value", reason="Not supported", status="PROPOSED",
            ),
        ])
        service.update_item(plan.id, plan.items[1].id, status="EDITED", edited_value="Beta Imports Ltd")
        service.update_item(plan.id, plan.items[2].id, status="REJECTED")
        session.commit()

        applied = ReviewPlanService(session).confirm(plan.id, confirmed_by="Reviewer")
        overrides = session.scalars(
            select(HumanReviewFieldOverrideRecord).where(HumanReviewFieldOverrideRecord.review_case_id == case.id)
        ).all()
        comparisons = session.scalars(
            select(ComparisonResultRecord).where(ComparisonResultRecord.email_id == email.id)
        ).all()
        assert applied.status == "APPLIED"
        assert len(overrides) == 2
        assert len(comparisons) == 2
        assert original.id in {row.id for row in comparisons}
        assert [item.status for item in applied.items].count("APPLIED") == 2
        assert [item.status for item in applied.items].count("REJECTED") == 1


def test_manual_review_plan_item_is_audited_and_applied_on_confirmation(db_factory):
    with db_factory() as session:
        _email, _original, case = _blocked_comparison(session, "review-plan-manual")
        service = ReviewPlanService(session)
        plan = service.create(case.id, created_by="Reviewer", items=[
            PlanItemInput(
                document_side="BL", field_name="notify_party", current_value=None,
                proposed_value="Gamma Notify Co", reason="Manual document verification", status="APPROVED",
            ),
        ])
        assert plan.items[0].ai_suggestion_id is None
        service.confirm(plan.id, confirmed_by="Reviewer")
        override = session.scalar(
            select(HumanReviewFieldOverrideRecord).where(HumanReviewFieldOverrideRecord.review_case_id == case.id)
        )
        events = session.scalars(
            select(AuditEventRecord).where(AuditEventRecord.entity_id == plan.id)
        ).all()
        assert override.corrected_value == "Gamma Notify Co"
        assert any(event.event_type == "REVIEW_PLAN_APPLIED" for event in events)
        assert any(event.event_type == "REVIEW_PLAN_CREATED" and event.metadata_json["manual_item_count"] == 1 for event in events)


@pytest.mark.req("HR-03")
@pytest.mark.req("HR-04")
@pytest.mark.req("HR-05")
def test_override_preserves_extraction_and_resolve_creates_new_comparison(db_factory):
    with db_factory() as session:
        email, original, case = _blocked_comparison(session)
        email_id, original_id, case_id = email.id, original.id, case.id
        before = _extraction_snapshot(session, email_id)
        service = HumanReviewService(session)
        override = service.add_override(
            case_id,
            document_side="BL",
            field_name="notify_party",
            corrected_value="Gamma Notify Co",
            corrected_canonical_value=None,
            reviewer_name="Reviewer One",
            note="Confirmed from the document image.",
        )
        assert override.original_field_id is not None
        resolved, reviewed = service.resolve_and_recompare(
            case_id,
            reviewer_name="Reviewer One",
            notes="All seven fields are now definite.",
        )
        assert resolved.status == "RESOLVED"
        assert reviewed.id != original_id
        assert reviewed.supersedes_comparison_id == original_id
        assert reviewed.review_case_id == case_id
        assert reviewed.comparison_state == "COMPLETED"
        assert email.processing_status == "COMPLETED"
        assert _extraction_snapshot(session, email_id) == before
        session.commit()

    with db_factory() as session:
        email = session.get(EmailMessageRecord, email_id)
        case = session.get(HumanReviewCaseRecord, case_id)
        results = session.scalars(
            select(ComparisonResultRecord)
            .where(ComparisonResultRecord.email_id == email_id)
            .order_by(ComparisonResultRecord.created_at, ComparisonResultRecord.id)
        ).all()
        events = session.scalars(
            select(HumanReviewEventRecord)
            .where(HumanReviewEventRecord.review_case_id == case_id)
            .order_by(HumanReviewEventRecord.created_at, HumanReviewEventRecord.id)
        ).all()
        assert email.processing_status == "COMPLETED"
        assert case.status == "RESOLVED"
        assert len(results) == 2
        assert results[0].id == original_id
        assert results[0].comparison_state == "BLOCKED"
        assert results[1].comparison_state == "COMPLETED"
        assert [event.action for event in events] == [
            "CASE_CREATED",
            "FIELD_OVERRIDE_ADDED",
            "RESOLVE_REQUESTED",
            "RECOMPARISON_COMPLETED",
            "CASE_RESOLVED",
        ]


@pytest.mark.req("HR-05")
@pytest.mark.req("HR-06")
def test_unresolved_review_stays_blocked_and_double_resolution_is_idempotent(db_factory):
    with db_factory() as session:
        email, _original, case = _blocked_comparison(session, "review-unresolved")
        service = HumanReviewService(session)
        still_open, reviewed = service.resolve_and_recompare(case.id, reviewer_name="Reviewer Two")
        assert still_open.status == "IN_REVIEW"
        assert reviewed.comparison_state == "BLOCKED"
        assert email.processing_status == "BLOCKED"

        service.add_override(
            case.id,
            document_side="BL",
            field_name="notify_party",
            corrected_value="Gamma Notify Co",
            corrected_canonical_value=None,
            reviewer_name="Reviewer Two",
            note=None,
        )
        resolved, final = service.resolve_and_recompare(case.id, reviewer_name="Reviewer Two")
        again_case, again_result = service.resolve_and_recompare(case.id, reviewer_name="Reviewer Two")
        assert resolved.status == again_case.status == "RESOLVED"
        assert final.id == again_result.id
        assert session.scalar(
            select(func.count(ComparisonResultRecord.id)).where(
                ComparisonResultRecord.review_case_id == case.id
            )
        ) == 2


@pytest.mark.req("HR-03")
@pytest.mark.req("HR-06")
def test_invalid_override_and_lifecycle_transition_are_rejected(db_factory):
    with db_factory() as session:
        _email, _comparison, case = _blocked_comparison(session, "review-invalid")
        service = HumanReviewService(session)
        with pytest.raises(ValueError, match="seven canonical"):
            service.add_override(
                case.id,
                document_side="BL",
                field_name="booking_number",
                corrected_value="ABC",
                corrected_canonical_value=None,
                reviewer_name="Reviewer",
                note=None,
            )
        with pytest.raises(ValueError, match="non-negative integer"):
            service.add_override(
                case.id,
                document_side="BL",
                field_name="container_count",
                corrected_value="invalid",
                corrected_canonical_value="invalid",
                reviewer_name="Reviewer",
                note=None,
            )
        service.dismiss(case.id, reviewer_name="Reviewer", reason="NOT_ACTIONABLE")
        with pytest.raises(ReviewConflictError, match="Cannot claim"):
            service.claim(case.id, reviewer_name="Other Reviewer")


@pytest.mark.req("HR-07")
def test_review_api_mutations_return_real_persisted_case_detail(db_factory):
    with db_factory() as session:
        _email, _comparison, case = _blocked_comparison(session, "review-api")
        case_id = case.id
        session.commit()

        def override_session():
            yield session

        app.dependency_overrides[get_session] = override_session
        try:
            with TestClient(app) as client:
                claim = client.post(
                    f"/api/v1/human-review/{case_id}/claim",
                    json={"reviewer_name": "API Reviewer"},
                )
                assert claim.status_code == 200
                assert claim.json()["status"] == "IN_REVIEW"
                correction = client.post(
                    f"/api/v1/human-review/{case_id}/overrides",
                    json={
                        "document_side": "BL",
                        "field": "notify_party",
                        "corrected_value": "Gamma Notify Co",
                        "reviewer_name": "API Reviewer",
                        "note": "Verified manually",
                    },
                )
                assert correction.status_code == 200

                assert correction.json()["overrides"][0]["field"] == "notify_party"
                resolution = client.post(
                    f"/api/v1/human-review/{case_id}/resolve",
                    json={"reviewer_name": "API Reviewer"},
                )
                assert resolution.status_code == 200
                payload = resolution.json()
                assert payload["status"] == "RESOLVED"
                assert payload["comparison"]["state"] == "COMPLETED"
                assert len(payload["documents"]) == 2
                assert len(payload["actions"]) >= 5
        finally:
            app.dependency_overrides.pop(get_session, None)


@pytest.mark.req("HR-07")
def test_review_api_queue_supports_filters_and_sorting_without_argument_regression(db_factory):
    with db_factory() as session:
        _email, _comparison, case = _blocked_comparison(session, "review-queue")
        session.commit()

        def override_session():
            yield session

        app.dependency_overrides[get_session] = override_session
        try:
            with TestClient(app) as client:
                response = client.get("/api/v1/human-review")
                assert response.status_code == 200
                assert response.json()["total"] == 1

                claim = client.post(
                    f"/api/v1/human-review/{case.id}/claim",
                    json={"reviewer_name": "Queue Reviewer"},
                )
                assert claim.status_code == 200

                for query in (
                    {"reason": case.reason_code},
                    {"reviewer": "Queue Reviewer"},
                    {"search": "Compare SI and BL"},
                    {"active_only": "true"},
                    {"sort": "priority"},
                    {"sort": "oldest"},
                    {"sort": "age"},
                    {"sort": "newest"},
                ):
                    filtered = client.get("/api/v1/human-review", params=query)
                    assert filtered.status_code == 200, query
                    assert filtered.json()["total"] == 1, query
        finally:
            app.dependency_overrides.pop(get_session, None)


@pytest.mark.req("HR-08")
def test_human_review_schema_has_constraints_indexes_and_separate_audit_tables(db_factory):
    with db_factory() as session:
        schema = inspect(session.bind)
        assert {"human_review_cases", "human_review_field_overrides", "human_review_events"} <= set(
            schema.get_table_names()
        )
        assert "uq_human_review_active_identity" in {
            index["name"] for index in schema.get_indexes("human_review_cases")
        }
        assert "uq_review_override_active_field" in {
            index["name"] for index in schema.get_indexes("human_review_field_overrides")
        }
        assert {"ck_human_review_status", "ck_human_review_case_origin"} <= {
            constraint["name"] for constraint in schema.get_check_constraints("human_review_cases")
        }
        assert session.scalar(select(func.count(HumanReviewFieldOverrideRecord.id))) == 0


@pytest.mark.req("HR-06")
def test_historical_review_records_are_read_only(db_factory):
    with db_factory() as session:
        _email, _comparison, case = _blocked_comparison(session, "review-historical-read-only")
        case.case_origin = "LEGACY"
        session.flush()
        service = HumanReviewService(session)

        with pytest.raises(ReviewConflictError, match="read-only"):
            service.claim(case.id, reviewer_name="Reviewer")
        with pytest.raises(ReviewConflictError, match="read-only"):
            service.add_override(
                case.id,
                document_side="BL",
                field_name="notify_party",
                corrected_value="Gamma Notify Co",
                corrected_canonical_value=None,
                reviewer_name="Reviewer",
                note=None,
            )
        with pytest.raises(ReviewConflictError, match="read-only"):
            service.resolve_and_recompare(case.id, reviewer_name="Reviewer")
        with pytest.raises(ReviewConflictError, match="read-only"):
            service.dismiss(case.id, reviewer_name="Reviewer", reason="NOT_ACTIONABLE")
from backend.app.storage.models import EmailMessageRecord, ClassificationResultRecord, HumanReviewCaseRecord
from backend.app.api.analytics_helper import get_human_review_analytics
from backend.app.api.product_queries import get_product_summary, list_human_reviews
import uuid


@pytest.mark.req("HR-02")
def test_human_review_analytics_is_read_only_and_does_not_sync_blocked_cases(db_factory):
    with db_factory() as session:
        blocked = EmailMessageRecord(
            id=uuid.uuid4(),
            external_message_id="analytics-read-only-blocked",
            source_type="STATIC_BUNDLE",
            sender="a@b.com",
            subject="blocked",
            body="blocked",
            content_hash=hashlib.sha256(b"analytics-read-only-blocked").hexdigest(),
            processing_status="BLOCKED",
        )
        session.add(blocked)
        session.commit()

        analytics = get_human_review_analytics(session)

        assert analytics.open_count == 0
        assert session.scalar(select(func.count(HumanReviewCaseRecord.id))) == 0


def test_legacy_not_counted_in_summary(db_factory):
    with db_factory() as session:
        now = datetime.now(timezone.utc)
        email_legacy = EmailMessageRecord(
            id=uuid.uuid4(),
            external_message_id='legacy_1',
            source_type='STATIC_BUNDLE',
            sender='a@b.com',
            subject='legacy',
            body='legacy',
            content_hash=hashlib.sha256(b"legacy").hexdigest(),
            created_at=now,
            processing_status='COMPLETED',
        )
        session.add(email_legacy)
        session.commit()

        cls_legacy = ClassificationResultRecord(
            id=uuid.uuid4(),
            email_id=email_legacy.id,
            category='general_message',
            confidence=0.5,
            resolved_at_stage='STAGE1_RULES',
            classifier_version='v1',
            created_at=now,
        )
        session.add(cls_legacy)
        session.commit()

        hr_legacy = HumanReviewCaseRecord(
            id=uuid.uuid4(),
            email_id=email_legacy.id,
            status='OPEN',
            case_origin='LEGACY',
            reason_code='STAGE2_UNRESOLVED',
            reason_text='Unresolved',
            created_at=now,
        )
        session.add(hr_legacy)
        session.commit()

        summary1 = get_product_summary(session)
        assert summary1.needs_review_count == 0
        assert summary1.human_review_open_count == 0

        # Check API return
        reviews_legacy = list_human_reviews(session, active_only=False, skip=0, limit=100)
        assert len(reviews_legacy.items) == 1
        assert reviews_legacy.items[0].case_origin == 'LEGACY'

        # Test active open
        email_active = EmailMessageRecord(
            id=uuid.uuid4(),
            external_message_id='active_1',
            source_type='STATIC_BUNDLE',
            sender='a@b.com',
            subject='active',
            body='active',
            content_hash=hashlib.sha256(b"active").hexdigest(),
            created_at=now,
            processing_status='BLOCKED',
        )
        session.add(email_active)
        session.commit()

        hr_active = HumanReviewCaseRecord(
            id=uuid.uuid4(),
            email_id=email_active.id,
            status='OPEN',
            case_origin='ACTIVE',
            reason_code='WRONG_DOCUMENT_TYPE',
            reason_text='Wrong',
            created_at=now,
        )
        session.add(hr_active)
        session.commit()

        summary2 = get_product_summary(session)
        assert summary2.needs_review_count == 1
        assert summary2.human_review_open_count == 1


def test_reprocess_reconciles_stale_reviews_and_summary_counts_distinct_emails(db_factory):
    with db_factory() as session:
        now = datetime.now(timezone.utc)

        def add_email(external_id: str, status: str) -> EmailMessageRecord:
            email = EmailMessageRecord(
                id=uuid.uuid4(),
                external_message_id=external_id,
                source_type="INCOMING_API",
                subject=external_id,
                body=external_id,
                content_hash=hashlib.sha256(external_id.encode()).hexdigest(),
                processing_status=status,
                created_at=now,
            )
            session.add(email)
            session.flush()
            return email

        def add_case(email: EmailMessageRecord, *, workflow: str, comparison_id=None):
            case = HumanReviewCaseRecord(
                id=uuid.uuid4(),
                email_id=email.id,
                source_comparison_id=comparison_id,
                reason_code="COMPARISON_UNRESOLVED",
                reason_text="Comparison unresolved",
                status="OPEN",
                case_origin="ACTIVE",
                workflow_identity=workflow,
                created_at=now,
            )
            session.add(case)
            session.flush()
            return case

        completed = add_email("reprocess-completed", "COMPLETED")
        completed_case = add_case(completed, workflow="old-completed")
        awaiting = add_email("reprocess-awaiting", "AWAITING_DOCUMENTS")
        awaiting_case = add_case(awaiting, workflow="old-awaiting")
        blocked = add_email("reprocess-blocked", "BLOCKED")
        old_comparison = uuid.uuid4()
        blocked_case = add_case(blocked, workflow="old-comparison", comparison_id=old_comparison)
        duplicate_case = add_case(blocked, workflow="new-comparison", comparison_id=uuid.uuid4())
        session.commit()

        service = HumanReviewService(session)
        service.reconcile_email(completed)
        service.reconcile_email(awaiting)
        service.reconcile_email(
            blocked,
            current_reason_code="COMPARISON_UNRESOLVED",
            current_source_comparison_id=old_comparison,
        )
        session.commit()

        session.refresh(completed_case)
        session.refresh(awaiting_case)
        session.refresh(blocked_case)
        session.refresh(duplicate_case)
        assert completed_case.status == "DISMISSED"
        assert awaiting_case.status == "DISMISSED"
        assert blocked_case.status == "OPEN"
        assert duplicate_case.status == "DISMISSED"
        assert session.scalar(
            select(func.count(HumanReviewEventRecord.id)).where(
                HumanReviewEventRecord.review_case_id == completed_case.id,
                HumanReviewEventRecord.action == "CASE_DISMISSED",
            )
        ) == 1

        summary = get_product_summary(session)
        assert summary.human_review_open_count == 1
        assert list_human_reviews(session, active_only=True).total == 1

        # A changed workflow identity supersedes the old active case without
        # deleting its history, then creates exactly one current case.
        replacement = service.ensure_actionable_case(
            blocked,
            reason_code="COMPARISON_UNRESOLVED",
            source_comparison_id=uuid.uuid4(),
        )
        session.commit()
        active_cases = session.scalars(
            select(HumanReviewCaseRecord).where(
                HumanReviewCaseRecord.email_id == blocked.id,
                HumanReviewCaseRecord.status.in_(["OPEN", "IN_REVIEW"]),
            )
        ).all()
        assert replacement is not None
        assert len(active_cases) == 1
        assert session.scalar(select(func.count(HumanReviewCaseRecord.id)).where(HumanReviewCaseRecord.email_id == blocked.id)) == 3
