from __future__ import annotations

import copy
import hashlib
import os

import pytest
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.app.comparison.models import FieldComparisonStatus
from backend.app.comparison.persistence import PersistedComparisonService
from backend.app.comparison.service import COMPARISON_VERSION, ComparisonService
from backend.app.extraction.models import (
    CANONICAL_FIELDS,
    CanonicalField,
    DocumentExtractionResult,
    ExtractedField,
    FieldStatus,
    MappingMethod,
    SourceLocation,
)
from backend.app.storage.database import Base
from backend.app.storage.models import (
    ComparisonResultRecord,
    EmailMessageRecord,
    FieldComparisonRecord,
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


BASE_VALUES = {
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


def _field(
    name: CanonicalField,
    value=...,
    *,
    raw=...,
    status: FieldStatus = FieldStatus.RESOLVED,
) -> ExtractedField:
    canonical = BASE_VALUES[name] if value is ... else value
    raw_value = canonical if raw is ... else raw
    if status == FieldStatus.MISSING:
        canonical = raw_value = None
        raw_label = None
        method = None
    else:
        raw_label = name.value.upper()
        method = MappingMethod.EXACT_LABEL
    return ExtractedField(
        canonical_field=name,
        raw_label=raw_label,
        raw_value=raw_value,
        canonical_value=canonical,
        status=status,
        confidence=1.0 if status == FieldStatus.RESOLVED else 0.0,
        mapping_method=method,
        source_location=SourceLocation(source_type="p4c-fixture", line_number=1),
        evidence={"fixture": "phase4-comparison-persistence"},
    )


def _result(
    role: str,
    overrides: dict[CanonicalField, ExtractedField] | None = None,
) -> DocumentExtractionResult:
    overrides = overrides or {}
    return DocumentExtractionResult(
        document_role=role,
        fields={name: overrides.get(name, _field(name)) for name in CANONICAL_FIELDS},
        extractor_version="phase3-deterministic-v1",
    )


def _persist_pair(
    session,
    *,
    external_id: str,
    si_overrides: dict[CanonicalField, ExtractedField] | None = None,
    bl_overrides: dict[CanonicalField, ExtractedField] | None = None,
):
    email = EmailMessageRecord(
        external_message_id=external_id,
        source_type="INCOMING_API",
        sender="sender@example.com",
        recipients=["ops@example.com"],
        subject="compare",
        body="compare",
        source_metadata={},
        content_hash=hashlib.sha256(external_id.encode()).hexdigest(),
        processing_status="EXTRACTING",
    )
    session.add(email)
    session.flush()
    extraction_repo = DocumentExtractionRepository(session)
    field_repo = ExtractedFieldRepository(session)
    ids = {}
    for role, extraction_result in (
        ("SI", _result("SI", si_overrides)),
        ("DRAFT_BL", _result("DRAFT_BL", bl_overrides)),
    ):
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
            raw_text="already materialized",
            extractor_version=extraction_result.extractor_version,
        )
        field_repo.create_result(extraction.id, extraction_result)
        ids[role] = extraction.id
    session.flush()
    return email, ids["SI"], ids["DRAFT_BL"]


def _snapshot_extractions(session, extraction_ids):
    # Use ORM rows for a complete value snapshot while keeping the helper
    # independent from comparison persistence internals.
    from backend.app.storage.models import ExtractedFieldRecord

    records = session.scalars(
        select(ExtractedFieldRecord)
        .where(ExtractedFieldRecord.extraction_id.in_(extraction_ids))
        .order_by(ExtractedFieldRecord.extraction_id, ExtractedFieldRecord.field_name)
    ).all()
    return [
        copy.deepcopy(
            {
                "id": row.id,
                "extraction_id": row.extraction_id,
                "field_name": row.field_name,
                "raw_label": row.raw_label,
                "raw_value": row.raw_value,
                "raw_value_json": row.raw_value_json,
                "canonical_value": row.canonical_value,
                "status": row.status,
                "confidence": row.confidence,
                "evidence": row.evidence,
                "source_location": row.source_location,
                "mapping_method": row.mapping_method,
            }
        )
        for row in records
    ]


@pytest.mark.req("CMP-10")
@pytest.mark.req("STA-05")
def test_all_match_persists_clean_result_and_completed_event_chronology(db_factory):
    with db_factory() as session:
        email, si_id, bl_id = _persist_pair(session, external_id="p4c-clean")
        outcome = PersistedComparisonService(session).compare_and_persist(
            email,
            si_extraction_id=si_id,
            bl_extraction_id=bl_id,
        )
        result_id = outcome.record.id
        email_id = email.id
        session.commit()

    with db_factory() as session:
        email = session.get(EmailMessageRecord, email_id)
        result = ComparisonResultRepository(session).get(result_id)
        events = session.scalars(
            select(ProcessingEventRecord)
            .where(ProcessingEventRecord.email_id == email_id)
            .order_by(ProcessingEventRecord.created_at, ProcessingEventRecord.id)
        ).all()

        assert email.processing_status == "COMPLETED"
        assert result.comparison_version == COMPARISON_VERSION
        assert result.comparison_state == "COMPLETED"
        assert result.mismatch_found is False
        assert result.all_fields_definite is True
        assert result.mismatched_fields == []
        assert result.unresolved_fields == []
        assert result.message == "No mismatch detected."
        assert len(result.fields) == 7
        assert [event.new_status for event in events] == ["COMPARING", "COMPLETED"]


@pytest.mark.req("CMP-09")
@pytest.mark.req("CMP-11")
@pytest.mark.parametrize(
    "changed",
    [
        {CanonicalField.CONTAINER_COUNT: _field(CanonicalField.CONTAINER_COUNT, 5, raw="5 x 40'HC")},
        {
            CanonicalField.CONTAINER_COUNT: _field(CanonicalField.CONTAINER_COUNT, 5, raw="5 x 40'HC"),
            CanonicalField.GROSS_WEIGHT_KG: _field(CanonicalField.GROSS_WEIGHT_KG, 23000, raw="23,000 KG"),
        },
    ],
    ids=["single", "multiple"],
)
def test_mismatches_reload_side_by_side_without_mutating_extractions(db_factory, changed):
    with db_factory() as session:
        si_overrides = {
            CanonicalField.CONTAINER_COUNT: _field(
                CanonicalField.CONTAINER_COUNT,
                6,
                raw="6 x 40'HC",
            ),
            CanonicalField.GROSS_WEIGHT_KG: _field(
                CanonicalField.GROSS_WEIGHT_KG,
                22000,
                raw="22,000 KG",
            ),
        }
        email, si_id, bl_id = _persist_pair(
            session,
            external_id=f"p4c-mismatch-{len(changed)}",
            si_overrides=si_overrides,
            bl_overrides=changed,
        )
        before = _snapshot_extractions(session, {si_id, bl_id})
        outcome = PersistedComparisonService(session).compare_and_persist(
            email,
            si_extraction_id=si_id,
            bl_extraction_id=bl_id,
        )
        result_id = outcome.record.id
        session.commit()

    with db_factory() as session:
        result = ComparisonResultRepository(session).get(result_id)
        after = _snapshot_extractions(session, {si_id, bl_id})
        expected = sorted(field.value for field in changed)
        mismatches = sorted(row.field_name for row in result.fields if row.status == "MISMATCH")

        assert result.comparison_state == "COMPLETED"
        assert result.mismatch_found is True
        assert result.all_fields_definite is True
        assert sorted(result.mismatched_fields) == expected
        assert mismatches == expected
        assert result.unresolved_fields == []
        assert before == after

        container = next(
            row for row in result.fields if row.field_name == CanonicalField.CONTAINER_COUNT.value
        )
        assert container.si_raw_value == "6 x 40'HC"
        assert container.bl_raw_value == "5 x 40'HC"
        assert container.si_canonical_value == 6
        assert container.bl_canonical_value == 5
        assert container.si_normalized_value == 6
        assert container.bl_normalized_value == 5
        assert container.status == "MISMATCH"
        assert container.comparison_layer == "L1"
        assert container.reason_code == "L1_CONTAINER_COUNTS_DIFFER"
        assert container.evidence is not None


@pytest.mark.req("CMP-09")
@pytest.mark.req("SUB-03")
def test_mixed_mismatch_and_unresolved_preserves_both_and_blocks(db_factory):
    with db_factory() as session:
        email, si_id, bl_id = _persist_pair(
            session,
            external_id="p4c-mixed",
            bl_overrides={
                CanonicalField.CONTAINER_COUNT: _field(CanonicalField.CONTAINER_COUNT, 5),
                CanonicalField.NOTIFY_PARTY: _field(
                    CanonicalField.NOTIFY_PARTY,
                    None,
                    status=FieldStatus.MISSING,
                ),
            },
        )
        outcome = PersistedComparisonService(session).compare_and_persist(
            email,
            si_extraction_id=si_id,
            bl_extraction_id=bl_id,
        )
        result_id = outcome.record.id
        email_id = email.id
        session.commit()

    with db_factory() as session:
        email = session.get(EmailMessageRecord, email_id)
        result = ComparisonResultRepository(session).get(result_id)
        statuses = {row.field_name: row.status for row in result.fields}
        last_event = session.scalar(
            select(ProcessingEventRecord)
            .where(ProcessingEventRecord.email_id == email_id)
            .order_by(ProcessingEventRecord.created_at.desc(), ProcessingEventRecord.id.desc())
        )

        assert email.processing_status == "BLOCKED"
        assert result.comparison_state == "BLOCKED"
        assert result.mismatch_found is True
        assert result.all_fields_definite is False
        assert result.mismatched_fields == [CanonicalField.CONTAINER_COUNT.value]
        assert result.unresolved_fields == [CanonicalField.NOTIFY_PARTY.value]
        assert statuses[CanonicalField.CONTAINER_COUNT.value] == "MISMATCH"
        assert statuses[CanonicalField.NOTIFY_PARTY.value] == "UNRESOLVED"
        assert last_event.reason_code == "COMPARISON_UNRESOLVED"


@pytest.mark.req("STA-05")
def test_comparison_identity_is_idempotent_and_constraints_reject_invalid_values(db_factory):
    with db_factory() as session:
        schema = inspect(session.bind)
        assert {
            "email_messages",
            "attachments",
            "classification_results",
            "document_extractions",
            "extracted_fields",
            "comparison_results",
            "processing_events",
        } <= set(schema.get_table_names())
        assert "uq_comparison_identity_version" in {
            constraint["name"] for constraint in schema.get_unique_constraints("comparison_results")
        }
        assert {
            "ix_comparison_results_email_id",
            "ix_comparison_results_si_extraction_id",
            "ix_comparison_results_bl_extraction_id",
            "ix_comparison_results_comparison_state",
        } <= {index["name"] for index in schema.get_indexes("comparison_results")}
        assert {
            "ck_field_comparison_name",
            "ck_field_comparison_status",
            "ck_field_comparison_layer",
        } <= {constraint["name"] for constraint in schema.get_check_constraints("field_comparisons")}

        email, si_id, bl_id = _persist_pair(session, external_id="p4c-idempotent")
        service = PersistedComparisonService(session)
        first = service.compare_and_persist(email, si_extraction_id=si_id, bl_extraction_id=bl_id)
        first_id = first.record.id
        second = service.compare_and_persist(email, si_extraction_id=si_id, bl_extraction_id=bl_id)
        session.flush()

        assert second.record.id == first_id
        assert session.scalar(select(func.count(ComparisonResultRecord.id))) == 1
        assert session.scalar(select(func.count(FieldComparisonRecord.id))) == 7

        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(
                FieldComparisonRecord(
                    comparison_result_id=first_id,
                    si_field_id=first.record.fields[0].si_field_id,
                    bl_field_id=first.record.fields[0].bl_field_id,
                    field_name="not_a_canonical_field",
                    comparison_layer="L0",
                    status="LIKELY_MATCH",
                    reason_code="INVALID_FIXTURE",
                    evidence={},
                )
            )
            session.flush()


def test_persisted_comparison_never_invokes_reader_or_extractor(db_factory, monkeypatch):
    from backend.app.documents.readers.composite import CompositeDocumentReader
    from backend.app.extraction.extractor import DeterministicDocumentExtractor

    monkeypatch.setattr(
        CompositeDocumentReader,
        "read",
        lambda *_args, **_kwargs: pytest.fail("comparison invoked a reader"),
    )
    monkeypatch.setattr(
        DeterministicDocumentExtractor,
        "extract",
        lambda *_args, **_kwargs: pytest.fail("comparison invoked the extractor"),
    )
    with db_factory() as session:
        email, si_id, bl_id = _persist_pair(session, external_id="p4c-pure")
        outcome = PersistedComparisonService(session).compare_and_persist(
            email,
            si_extraction_id=si_id,
            bl_extraction_id=bl_id,
        )
        assert outcome.record.comparison_state == "COMPLETED"
