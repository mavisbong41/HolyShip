from __future__ import annotations

import hashlib
import os

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.comparison.persistence import PersistedComparisonService
from backend.app.comparison.service import COMPARISON_VERSION
from backend.app.core.reliability import RetryPolicy
from backend.app.extraction.models import (
    CANONICAL_FIELDS,
    CanonicalField,
    DocumentExtractionResult,
    ExtractedField,
    FieldStatus,
    MappingMethod,
    SourceLocation,
)
from backend.app.resolution.models import ProviderResolution
from backend.app.resolution.service import ResolutionExecutor
from backend.app.storage.database import Base
from backend.app.storage.models import AIResolutionRecord, ExtractedFieldRecord
from backend.app.storage.repositories import (
    AIResolutionRepository,
    DocumentExtractionRepository,
    DocumentRepository,
    ExtractedFieldRepository,
)


pytestmark = pytest.mark.skipif(
    not os.environ.get("HOLYSHIP_TEST_DATABASE_URL"),
    reason="HOLYSHIP_TEST_DATABASE_URL is required",
)

VALUES = {
    CanonicalField.SHIPPER: "ABC LOGISTICS SDN BHD",
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


class QueueProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def resolve(self, _request):
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def _field(name, value=..., *, status=FieldStatus.RESOLVED, evidence=None):
    if value is ...:
        value = VALUES[name]
    if status == FieldStatus.MISSING:
        return ExtractedField(
            canonical_field=name, raw_label=None, raw_value=None, canonical_value=None,
            status=status, confidence=0, mapping_method=None,
            source_location=SourceLocation(source_type="fixture"), evidence={},
        )
    raw_value = value
    canonical = value if status == FieldStatus.RESOLVED else None
    return ExtractedField(
        canonical_field=name,
        raw_label=name.value,
        raw_value=raw_value,
        canonical_value=canonical,
        status=status,
        confidence=1 if status == FieldStatus.RESOLVED else 0.2,
        mapping_method=MappingMethod.EXACT_LABEL if status == FieldStatus.RESOLVED else None,
        source_location=SourceLocation(
            source_type="fixture",
            text_span=evidence or (f"{name.value}: {value}" if value is not None else None),
        ),
        evidence={},
    )


def _persist_pair(session, external_id, *, si_overrides=None, bl_overrides=None):
    from backend.app.storage.models import EmailMessageRecord

    email = EmailMessageRecord(
        external_message_id=external_id, source_type="INCOMING_API",
        sender="sender@example.com", recipients=["ops@example.com"], subject="compare", body="compare",
        source_metadata={}, content_hash=hashlib.sha256(external_id.encode()).hexdigest(),
        processing_status="EXTRACTING",
    )
    session.add(email)
    session.flush()
    ids = {}
    for role, overrides in (("SI", si_overrides or {}), ("DRAFT_BL", bl_overrides or {})):
        result = DocumentExtractionResult(
            document_role=role,
            fields={name: overrides.get(name, _field(name)) for name in CANONICAL_FIELDS},
            extractor_version="phase3-deterministic-v1",
        )
        document = DocumentRepository(session).create(
            email_id=email.id, attachment_id=None, document_type=role, format="PLAIN_TEXT",
            filename=f"{role}.txt", source_reference=f"memory/{external_id}/{role}",
            routing_outcome="SI_FOUND" if role == "SI" else "BL_FOUND",
            role_confidence=1, validation_outcome="VALID", content_sha256=hashlib.sha256(role.encode()).hexdigest(),
        )
        extraction = DocumentExtractionRepository(session).create(
            document_id=document.id, reader_used="PlainTextReader", raw_text="fixture source",
            extractor_version=result.extractor_version,
        )
        ExtractedFieldRepository(session).create_result(extraction.id, result)
        ids[role] = extraction.id
    return email, ids["SI"], ids["DRAFT_BL"]


def _executor(session, provider, *, enabled=True):
    return ResolutionExecutor(
        provider=provider, enabled=enabled, confidence_threshold=0.9,
        timeout_seconds=0.1, retry_policy=RetryPolicy(max_attempts=1),
        max_calls_per_case=4, max_concurrent_calls=2,
        provider_name="fake", model_name="fixture", resolver_version="resolver-v1",
        prompt_schema_version="schema-v1", store=AIResolutionRepository(session),
    )


@pytest.mark.req("EXT-05b")
@pytest.mark.req("AI-10")
def test_explicit_unresolved_extraction_uses_non_destructive_overlay(db_factory):
    response = ProviderResolution(
        field=CanonicalField.PORT_OF_LOADING, value="Port Klang", normalized_value="PORT KLANG",
        confidence=0.98, evidence="Port of Loading: Port Klang", reasoning_code="LAYOUT_ASSOCIATION",
    )
    provider = QueueProvider([response])
    with db_factory() as session:
        unresolved = _field(
            CanonicalField.PORT_OF_LOADING,
            "Port Klang",
            status=FieldStatus.UNRESOLVED,
            evidence="Port of Loading: Port Klang",
        )
        email, si_id, bl_id = _persist_pair(
            session, "overlay", si_overrides={CanonicalField.PORT_OF_LOADING: unresolved},
        )
        source_row = session.scalar(select(ExtractedFieldRecord).where(
            ExtractedFieldRecord.extraction_id == si_id,
            ExtractedFieldRecord.field_name == "port_of_loading",
        ))
        source_snapshot = (source_row.status, source_row.canonical_value, source_row.raw_value_json)
        result = PersistedComparisonService(
            session, resolution_executor=_executor(session, provider),
        ).compare_and_persist(email, si_extraction_id=si_id, bl_extraction_id=bl_id).record
        session.commit()

        assert result.comparison_state == "COMPLETED"
        port = next(field for field in result.fields if field.field_name == "port_of_loading")
        assert port.status == "MATCH"
        assert port.si_canonical_value == "PORT KLANG"
        assert port.evidence["si_extraction"]["ai_resolution"]["validation_reason"] == "AI_RESOLUTION_ACCEPTED"
        assert (source_row.status, source_row.canonical_value, source_row.raw_value_json) == source_snapshot
        assert session.query(AIResolutionRecord).count() == 1


@pytest.mark.req("AI-03")
def test_missing_field_remains_unresolved_without_provider_call(db_factory):
    provider = QueueProvider([])
    with db_factory() as session:
        email, si_id, bl_id = _persist_pair(
            session, "missing", si_overrides={CanonicalField.PORT_OF_LOADING: _field(CanonicalField.PORT_OF_LOADING, status=FieldStatus.MISSING)},
        )
        result = PersistedComparisonService(
            session, resolution_executor=_executor(session, provider),
        ).compare_and_persist(email, si_extraction_id=si_id, bl_extraction_id=bl_id).record
        assert result.comparison_state == "BLOCKED"
        assert provider.calls == 0


@pytest.mark.req("AI-11")
def test_semantic_l2_can_resolve_party_but_definite_mismatch_bypasses_ai(db_factory):
    provider = QueueProvider([ProviderResolution(
        field=CanonicalField.SHIPPER, equivalent=True, confidence=0.96,
        evidence="ABC LOGISTICS SDN BHD | ABC LOGISTICS",
        reasoning_code="LEGAL_SUFFIX_EQUIVALENCE",
    )])
    with db_factory() as session:
        email, si_id, bl_id = _persist_pair(
            session,
            "semantic",
            bl_overrides={
                CanonicalField.SHIPPER: _field(CanonicalField.SHIPPER, "ABC LOGISTICS"),
                CanonicalField.CONTAINER_COUNT: _field(CanonicalField.CONTAINER_COUNT, 5),
            },
        )
        result = PersistedComparisonService(
            session, resolution_executor=_executor(session, provider),
        ).compare_and_persist(email, si_extraction_id=si_id, bl_extraction_id=bl_id).record
        shipper = next(field for field in result.fields if field.field_name == "shipper")
        containers = next(field for field in result.fields if field.field_name == "container_count")
        assert shipper.status == "MATCH" and shipper.comparison_layer == "L2"
        assert containers.status == "MISMATCH" and containers.comparison_layer == "L1"
        assert provider.calls == 1


@pytest.mark.req("AI-12")
def test_ai_disabled_preserves_deterministic_comparison_identity(db_factory):
    provider = QueueProvider([])
    with db_factory() as session:
        email, si_id, bl_id = _persist_pair(session, "disabled")
        result = PersistedComparisonService(
            session, resolution_executor=_executor(session, provider, enabled=False),
        ).compare_and_persist(email, si_extraction_id=si_id, bl_extraction_id=bl_id).record
        assert result.comparison_version == COMPARISON_VERSION
        assert result.message == "No mismatch detected."
        assert provider.calls == 0
