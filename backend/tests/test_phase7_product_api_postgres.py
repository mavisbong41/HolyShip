from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.api.product_queries import get_email_detail, get_product_summary, list_email_queue
from backend.app.storage.database import Base
from backend.app.storage.models import (
    AIResolutionRecord,
    AttachmentRecord,
    ClassificationResultRecord,
    ComparisonResultRecord,
    DocumentExtractionRecord,
    DocumentRecord,
    EmailMessageRecord,
    ExtractedFieldRecord,
    FieldComparisonRecord,
    HumanReviewCaseRecord,
    ProcessingEventRecord,
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
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


FIELDS = (
    "shipper",
    "consignee",
    "notify_party",
    "port_of_loading",
    "port_of_discharge",
    "container_count",
    "gross_weight_kg",
)


def _persist_product_case(session):
    email = EmailMessageRecord(
        external_message_id="phase7-product-1",
        source_type="STATIC_BUNDLE",
        sender="ops@example.com",
        recipients=["docs@example.com"],
        subject="Compare SI and draft BL",
        body="Please compare the attached documents.",
        received_at=datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc),
        source_metadata={"fixture": "phase7"},
        content_hash=hashlib.sha256(b"phase7-product-1").hexdigest(),
        processing_status="COMPLETED",
    )
    session.add(email)
    session.flush()
    attachment_si = AttachmentRecord(
        email_id=email.id,
        filename="si.txt",
        content_type="text/plain",
        source_reference="attachments/si.txt",
        retrieval_status="MATERIALIZED",
        content_sha256="a" * 64,
    )
    attachment_bl = AttachmentRecord(
        email_id=email.id,
        filename="bl.txt",
        content_type="text/plain",
        source_reference="attachments/bl.txt",
        retrieval_status="MATERIALIZED",
        content_sha256="b" * 64,
    )
    session.add_all([attachment_si, attachment_bl])
    session.flush()
    classification = ClassificationResultRecord(
        email_id=email.id,
        category="document_comparison",
        confidence=0.98,
        candidate_scores={"document_comparison": 0.98},
        reason="The body asks for a document comparison.",
        reason_code="COMPARISON_INTENT",
        evidence_summary={"text_span": "compare the attached documents"},
        conflict_detected=False,
        resolved_at_stage="STAGE1",
        comparison_readiness="READY_FOR_COMPARISON",
        classifier_version="phase7-fixture",
        source_content_hash=email.content_hash,
    )
    session.add(classification)
    si_document = DocumentRecord(
        email_id=email.id,
        attachment_id=attachment_si.id,
        document_type="SI",
        format="PLAIN_TEXT",
        filename="si.txt",
        source_reference=attachment_si.source_reference,
        routing_outcome="SI_FOUND",
        role_confidence=0.99,
        role_evidence={"markers": ["SHIPPING INSTRUCTION"]},
        validation_outcome="VALID",
        content_sha256=attachment_si.content_sha256,
    )
    bl_document = DocumentRecord(
        email_id=email.id,
        attachment_id=attachment_bl.id,
        document_type="DRAFT_BL",
        format="PLAIN_TEXT",
        filename="bl.txt",
        source_reference=attachment_bl.source_reference,
        routing_outcome="BL_FOUND",
        role_confidence=0.99,
        role_evidence={"markers": ["BILL OF LADING"]},
        validation_outcome="VALID",
        content_sha256=attachment_bl.content_sha256,
    )
    session.add_all([si_document, bl_document])
    session.flush()
    si_extraction = DocumentExtractionRecord(
        document_id=si_document.id,
        reader_used="PlainTextReader",
        extraction_status="EXTRACTED",
        extraction_quality=1.0,
        raw_text="SI source",
        extractor_version="phase7-fixture",
    )
    bl_extraction = DocumentExtractionRecord(
        document_id=bl_document.id,
        reader_used="PlainTextReader",
        extraction_status="EXTRACTED",
        extraction_quality=1.0,
        raw_text="BL source",
        extractor_version="phase7-fixture",
    )
    session.add_all([si_extraction, bl_extraction])
    session.flush()
    for extraction, document_role in ((si_extraction, "SI"), (bl_extraction, "DRAFT_BL")):
        for field in FIELDS:
            value = "Port Klang" if field == "port_of_loading" else (22000 if field == "gross_weight_kg" else 6 if field == "container_count" else f"{document_role}-{field}")
            session.add(
                ExtractedFieldRecord(
                    extraction_id=extraction.id,
                    field_name=field,
                    raw_label=field.upper(),
                    raw_value=str(value),
                    raw_value_json=value,
                    canonical_value=value,
                    status="RESOLVED",
                    confidence=0.99,
                    evidence={"text_span": f"{field.upper()}: {value}"},
                    source_location={"page_number": 1},
                    mapping_method="exact_label",
                    extraction_method="DETERMINISTIC_ONE_PASS",
                )
            )
    session.flush()
    comparison = ComparisonResultRecord(
        email_id=email.id,
        si_extraction_id=si_extraction.id,
        bl_extraction_id=bl_extraction.id,
        comparison_version="phase7-fixture",
        comparison_state="COMPLETED",
        mismatch_found=True,
        all_fields_definite=True,
        mismatched_fields=["shipper"],
        unresolved_fields=[],
        reason_code="COMPARISON_COMPLETE",
        message="Mismatch detected.",
    )
    session.add(comparison)
    session.flush()
    si_fields = {row.field_name: row for row in si_extraction.fields}
    bl_fields = {row.field_name: row for row in bl_extraction.fields}
    for field in FIELDS:
        session.add(
            FieldComparisonRecord(
                comparison_result_id=comparison.id,
                si_field_id=si_fields[field].id,
                bl_field_id=bl_fields[field].id,
                field_name=field,
                si_raw_value=si_fields[field].raw_value_json,
                bl_raw_value=bl_fields[field].raw_value_json,
                si_canonical_value=si_fields[field].canonical_value,
                bl_canonical_value=bl_fields[field].canonical_value,
                si_normalized_value=si_fields[field].canonical_value,
                bl_normalized_value=bl_fields[field].canonical_value,
                comparison_layer="L0",
                status="MISMATCH" if field == "shipper" else "MATCH",
                reason_code="L0_DIFFERENT" if field == "shipper" else "L0_EQUAL",
                evidence={"comparison": {"text_span": f"{field} comparison"}},
            )
        )
    session.add(
        ProcessingEventRecord(
            email_id=email.id,
            old_status="COMPARING",
            new_status="COMPLETED",
            reason_code="COMPARISON_COMPLETE",
        )
    )
    session.add(
        HumanReviewCaseRecord(
            email_id=email.id,
            document_id=bl_document.id,
            field_name="shipper",
            reason_code="MISMATCH_REVIEW",
            reason_text="Review the shipper discrepancy.",
            evidence={"text_span": "shipper differs"},
            confidence=0.99,
            status="OPEN",
        )
    )
    session.add(
        AIResolutionRecord(
            request_hash="c" * 64,
            purpose="SEMANTIC",
            case_id=str(email.id),
            field_name="shipper",
            source_identity="phase7-fixture",
            provider_name="fixture",
            model_name="fixture-v1",
            resolver_version="phase6-fixture",
            prompt_schema_version="phase6-schema-v1",
            request_json={"api_key": "do-not-expose"},
            response_json={"evidence": {"reason": "fixture evidence"}},
            accepted=False,
            confidence=0.4,
            validation_reason="AI_CONFIDENCE_BELOW_THRESHOLD",
            provider_calls=1,
        )
    )
    session.commit()
    return email.id


@pytest.mark.req("API-01")
@pytest.mark.req("API-02")
@pytest.mark.req("API-07")
def test_product_queue_detail_and_summary_join_persisted_phase6_rows(db_factory):
    with db_factory() as session:
        email_id = _persist_product_case(session)
        page = list_email_queue(
            session,
            skip=0,
            limit=25,
            category="document_comparison",
            needs_review=True,
            comparison_state="COMPLETED",
        )
        assert page.total == 1
        assert page.items[0].id == email_id
        assert page.items[0].mismatch_count == 1
        assert page.items[0].needs_review is True

        detail = get_email_detail(session, email_id)
        assert detail is not None
        assert detail.classification.category == "document_comparison"
        assert [field.field for field in detail.comparison.fields] == list(FIELDS)
        assert detail.comparison.mismatched_fields == ["shipper"]
        assert detail.review[0].field == "shipper"
        assert detail.resolutions[0].accepted is False
        assert "api_key" not in detail.model_dump_json()

        summary = get_product_summary(session)
        assert summary.total_emails == 1
        assert summary.mismatch_count == 1
        assert summary.needs_review_count == 1


@pytest.mark.req("API-02")
def test_product_detail_missing_email_is_safe(db_factory):
    with db_factory() as session:
        assert get_email_detail(session, "00000000-0000-0000-0000-000000000000") is None
