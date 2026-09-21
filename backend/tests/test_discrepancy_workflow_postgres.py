from __future__ import annotations

import copy
import hashlib
import os
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from backend.app.api.deps import get_session
from backend.app.extraction.models import (
    CANONICAL_FIELDS,
    CanonicalField,
    DocumentExtractionResult,
    ExtractedField,
    FieldStatus,
    MappingMethod,
    SourceLocation,
)
from backend.app.comparison.persistence import PersistedComparisonService
from backend.app.discrepancy.service import DiscrepancyService, DiscrepancyConflictError
from backend.app.main import app
from backend.app.storage.database import Base
from backend.app.storage.models import (
    ComparisonResultRecord,
    DocumentExtractionRecord,
    DocumentRecord,
    EmailMessageRecord,
    ExtractedFieldRecord,
    FieldComparisonRecord,
    HumanReviewCaseRecord,
    HumanReviewFieldOverrideRecord,
    ProcessingEventRecord,
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


def _field(name: CanonicalField, *, value: Any = None) -> ExtractedField:
    val = value if value is not None else VALUES[name]
    return ExtractedField(
        canonical_field=name,
        raw_label=name.value.upper(),
        raw_value=str(val),
        canonical_value=val,
        status=FieldStatus.RESOLVED,
        confidence=1.0,
        mapping_method=MappingMethod.EXACT_LABEL,
        source_location=SourceLocation(source_type="fixture", line_number=1),
        evidence={"fixture": True},
    )


def _seed_mismatch_case(session, *, email_prefix="em", consignee_bl="Different Consignee Ltd"):
    ext_id = f"{email_prefix}-{uuid.uuid4().hex[:8]}"
    email = EmailMessageRecord(
        external_message_id=ext_id,
        source_type="STATIC_BUNDLE",
        sender="shipper@example.com",
        recipients=["ops@holyship.com"],
        subject=f"Booking Confirmation {ext_id}",
        body="Please find draft BL attached.",
        content_hash=hashlib.sha256(ext_id.encode()).hexdigest(),
        processing_status="EXTRACTING",
    )
    session.add(email)
    session.flush()

    doc_repo = DocumentRepository(session)
    extract_repo = DocumentExtractionRepository(session)
    field_repo = ExtractedFieldRepository(session)

    si_doc = doc_repo.create(
        email_id=email.id,
        attachment_id=None,
        document_type="SI",
        format="PLAIN_TEXT",
        filename="si.txt",
        source_reference=f"memory/{ext_id}/SI",
        routing_outcome="SI_FOUND",
        role_confidence=1.0,
        validation_outcome="VALID",
    )
    bl_doc = doc_repo.create(
        email_id=email.id,
        attachment_id=None,
        document_type="DRAFT_BL",
        format="PLAIN_TEXT",
        filename="bl.txt",
        source_reference=f"memory/{ext_id}/DRAFT_BL",
        routing_outcome="BL_FOUND",
        role_confidence=1.0,
        validation_outcome="VALID",
    )

    si_extract = extract_repo.create(
        document_id=si_doc.id,
        reader_used="PlainTextReader",
        extraction_status="EXTRACTED",
        raw_text="SI content",
        extractor_version="discrepancy-fixture-v1",
    )
    bl_extract = extract_repo.create(
        document_id=bl_doc.id,
        reader_used="PlainTextReader",
        extraction_status="EXTRACTED",
        raw_text="BL content",
        extractor_version="discrepancy-fixture-v1",
    )

    si_result = DocumentExtractionResult(
        document_role="SI",
        fields={name: _field(name) for name in CANONICAL_FIELDS},
        extractor_version="discrepancy-fixture-v1",
    )
    bl_result = DocumentExtractionResult(
        document_role="DRAFT_BL",
        fields={
            name: _field(name, value=consignee_bl if name == CanonicalField.CONSIGNEE else None)
            for name in CANONICAL_FIELDS
        },
        extractor_version="discrepancy-fixture-v1",
    )

    field_repo.create_result(si_extract.id, si_result)
    field_repo.create_result(bl_extract.id, bl_result)

    outcome = PersistedComparisonService(session).compare_and_persist(
        email,
        si_extraction_id=si_extract.id,
        bl_extraction_id=bl_extract.id,
    )
    comp_rec = outcome.record
    email.processing_status = "COMPLETED"
    session.flush()
    return email, comp_rec


def test_mismatch_appears_in_discrepancies_and_sets_open_status(db_factory):
    with db_factory() as session:
        email, comp = _seed_mismatch_case(session)
        assert comp.mismatch_found is True
        assert comp.resolution_status == "OPEN"

        service = DiscrepancyService(session)
        items, total, counts = service.list_discrepancies()
        assert total == 1
        assert counts["total"] == 1
        assert counts["open_count"] == 1
        assert counts["acknowledged_count"] == 0
        assert counts["resolved_count"] == 0
        assert items[0].id == comp.id
        assert items[0].mismatched_fields == ["consignee"]


def test_mismatch_does_not_create_human_review_cases(db_factory):
    with db_factory() as session:
        email, comp = _seed_mismatch_case(session)
        assert comp.mismatch_found is True

        human_reviews = session.scalars(select(HumanReviewCaseRecord)).all()
        assert len(human_reviews) == 0


def test_acknowledge_and_resolve_transitions(db_factory):
    with db_factory() as session:
        email, comp = _seed_mismatch_case(session)
        service = DiscrepancyService(session)

        # 1. Acknowledge
        ack = service.acknowledge(comp.id, operator_name="Alice Operator")
        assert ack.resolution_status == "ACKNOWLEDGED"
        assert ack.acknowledged_by == "Alice Operator"
        assert ack.acknowledged_at is not None
        assert ack.mismatch_found is True

        # Idempotent call
        ack2 = service.acknowledge(comp.id, operator_name="Alice Operator")
        assert ack2.resolution_status == "ACKNOWLEDGED"

        # 2. Resolve
        res = service.resolve(comp.id, operator_name="Bob Operator", notes="Shipper verified the change")
        assert res.resolution_status == "RESOLVED"
        assert res.resolved_by == "Bob Operator"
        assert res.resolved_at is not None
        assert res.resolution_notes == "Shipper verified the change"
        assert res.mismatch_found is True

        # Disallowed backwards transition to ACKNOWLEDGED stays RESOLVED
        ack3 = service.acknowledge(comp.id, operator_name="Alice Operator")
        assert ack3.resolution_status == "RESOLVED"


def test_field_override_and_recomparison_to_match(db_factory):
    with db_factory() as session:
        email, comp = _seed_mismatch_case(session, consignee_bl="Typo Consignee Ltd")
        service = DiscrepancyService(session)

        # 1. Add override correcting BL extraction to match SI ("Beta Imports Ltd")
        override = service.add_override(
            comp.id,
            document_side="BL",
            field_name="consignee",
            corrected_value="Beta Imports Ltd",
            reviewer_name="Correction Reviewer",
            note="OCR misread the consignee name",
        )
        assert override.active is True
        assert override.corrected_canonical_value == "Beta Imports Ltd"
        assert override.comparison_result_id == comp.id
        assert override.review_case_id is None

        # 2. Re-compare
        recompared = service.recompare(comp.id, reviewer_name="Correction Reviewer")
        assert recompared.mismatch_found is False
        assert recompared.resolution_status is None
        assert recompared.supersedes_comparison_id == comp.id

        # 3. Discrepancy list should now be empty (since latest comparison is MATCH)
        items, total, counts = service.list_discrepancies()
        assert total == 0
        assert counts["total"] == 0

        # Old comparison record remains in DB for audit history
        historical = session.get(ComparisonResultRecord, comp.id)
        assert historical is not None
        assert historical.mismatch_found is True


def test_discrepancy_api_endpoints(db_factory):
    with db_factory() as session:
        email, comp = _seed_mismatch_case(session)
        session.commit()
        comp_id = comp.id

    from backend.app.api.deps import get_session
    def _override_session():
        with db_factory() as s:
            yield s
    app.dependency_overrides[get_session] = _override_session

    with TestClient(app) as client:
        # GET /api/v1/discrepancies
        resp = client.get("/api/v1/discrepancies")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["open_count"] == 1
        assert data["items"][0]["id"] == str(comp_id)

        # GET /api/v1/discrepancies/{id}
        resp_detail = client.get(f"/api/v1/discrepancies/{comp.id}")
        assert resp_detail.status_code == 200
        detail = resp_detail.json()
        assert detail["discrepancy"]["id"] == str(comp.id)
        assert len(detail["mismatched_fields_detail"]) == 1
        assert detail["mismatched_fields_detail"][0]["field"] == "consignee"

        # POST /api/v1/discrepancies/{id}/acknowledge
        resp_ack = client.post(
            f"/api/v1/discrepancies/{comp.id}/acknowledge",
            json={"operator_name": "API Operator"},
        )
        assert resp_ack.status_code == 200
        assert resp_ack.json()["discrepancy"]["resolution_status"] == "ACKNOWLEDGED"

        # POST /api/v1/discrepancies/{id}/resolve
        resp_res = client.post(
            f"/api/v1/discrepancies/{comp.id}/resolve",
            json={"operator_name": "API Operator", "notes": "Handled via phone"},
        )
        assert resp_res.status_code == 200
        assert resp_res.json()["discrepancy"]["resolution_status"] == "RESOLVED"

        # POST /api/v1/discrepancies/{id}/override
        resp_over = client.post(
            f"/api/v1/discrepancies/{comp.id}/override",
            json={
                "document_side": "BL",
                "field_name": "consignee",
                "corrected_value": "Beta Imports Ltd",
                "reviewer_name": "API Reviewer",
                "note": "Correction test",
            },
        )
        assert resp_over.status_code == 200
        assert len(resp_over.json()["overrides"]) == 1

        # POST /api/v1/discrepancies/{id}/recompare
        resp_rec = client.post(
            f"/api/v1/discrepancies/{comp.id}/recompare",
            json={"reviewer_name": "API Reviewer"},
        )
        assert resp_rec.status_code == 200
        recompared_data = resp_rec.json()
        assert recompared_data["comparison"]["mismatch_found"] is False

    app.dependency_overrides.clear()
