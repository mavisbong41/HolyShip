from __future__ import annotations

import hashlib
import os

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import Settings
from backend.app.ingestion.models import AttachmentMetadata, EmailMessage
from backend.app.ingestion.sources import EmailSource
from backend.app.resolution.providers import DisabledResolverProvider
from backend.app.resolution.models import ProviderResolution
from backend.app.resolution.runtime import build_resolution_executor_factory
from backend.app.extraction.models import CanonicalField
from backend.app.storage.database import Base
from backend.app.storage.models import AIResolutionRecord, EmailMessageRecord, ExtractedFieldRecord
from backend.app.sync.service import SyncService


class FixtureProvider:
    def resolve(self, _request):
        raise AssertionError("provider call is not needed for construction evidence")


def _settings(**overrides):
    values = {
        "ai_escalation_enabled": True,
        "ai_provider": "fixture",
        "ai_model": "fixture-v1",
        "ai_confidence_threshold": 0.91,
        "ai_timeout_seconds": 0.2,
        "ai_max_calls_per_case": 3,
        "ai_max_concurrent_calls": 1,
        "ai_resolver_version": "resolver-runtime-v1",
        "ai_prompt_schema_version": "schema-runtime-v1",
        "retry_max_attempts": 2,
        "retry_backoff_seconds": 0,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_configured_runtime_factory_builds_enabled_executor_with_all_dimensions():
    provider = FixtureProvider()
    factory = build_resolution_executor_factory(
        _settings(),
        provider_builders={"fixture": lambda _settings: provider},
    )

    executor = factory(None)

    assert executor.enabled is True
    assert executor.provider is provider
    assert executor.provider_name == "fixture"
    assert executor.model_name == "fixture-v1"
    assert executor.confidence_threshold == 0.91
    assert executor.timeout_seconds == 0.2
    assert executor.max_calls_per_case == 3
    assert executor.resolver_version == "resolver-runtime-v1"
    assert executor.prompt_schema_version == "schema-runtime-v1"


def test_disabled_runtime_does_not_construct_provider_or_executor():
    constructed = 0

    def provider_builder(_settings):
        nonlocal constructed
        constructed += 1
        return DisabledResolverProvider()

    factory = build_resolution_executor_factory(
        _settings(ai_escalation_enabled=False),
        provider_builders={"fixture": provider_builder},
    )

    assert factory is None
    assert constructed == 0


def test_unknown_or_disabled_provider_returns_none_gracefully():
    factory_disabled = build_resolution_executor_factory(
        _settings(ai_escalation_enabled=True, ai_provider="disabled")
    )
    assert factory_disabled is None

    factory_unknown = build_resolution_executor_factory(
        _settings(ai_escalation_enabled=True, ai_provider="some_nonexistent_provider")
    )
    assert factory_unknown is None


def test_gemini_provider_without_api_key_returns_none_gracefully():
    factory = build_resolution_executor_factory(
        _settings(ai_escalation_enabled=True, ai_provider="gemini", ai_api_key=None, gemini_api_key=None)
    )
    assert factory is None


class RuntimeSource(EmailSource):
    def __init__(self, external_id: str):
        self.message = EmailMessage(
            external_message_id=external_id,
            source_type="INCOMING_API",
            subject="TO CONFIRM DOCS",
            body="Please compare the attached SI and draft BL. Check the details and confirm.",
            attachments=[
                AttachmentMetadata(filename="SI.txt", source_reference="si"),
                AttachmentMetadata(filename="BL.txt", source_reference="bl"),
            ],
            content_hash=hashlib.sha256(external_id.encode()).hexdigest(),
        )
        common = (
            "Shipper: Alpha Logistics\n"
            "Consignee: Beta Imports\n"
            "Notify Party: Gamma Notify\n"
            "Port of Loading: Port Klang\n"
            "Port of Discharge: Singapore\n"
            "Container Count: 6\n"
        )
        self.contents = {
            "si": ("SHIPPING INSTRUCTION\n" + common + "Gross Weight: twenty two thousand kg").encode(),
            "bl": ("DRAFT BILL OF LADING\n" + common + "Gross Weight: 22,000 KG").encode(),
        }

    def iter_messages(self):
        return iter((self.message,))

    def get_message(self, external_message_id: str) -> EmailMessage:
        if external_message_id != self.message.external_message_id:
            raise KeyError(external_message_id)
        return self.message

    def get_attachment_content(self, attachment: AttachmentMetadata) -> bytes:
        return self.contents[attachment.source_reference]


class RuntimeProvider:
    def __init__(self):
        self.calls = 0

    def resolve(self, _request):
        self.calls += 1
        return ProviderResolution(
            field=CanonicalField.GROSS_WEIGHT_KG,
            value="twenty two thousand kg",
            normalized_value=22000,
            confidence=0.98,
            evidence="Gross Weight: twenty two thousand kg",
            reasoning_code="TEXT_NUMBER_PARSE",
        )


@pytest.fixture()
def runtime_session():
    url = os.environ.get("HOLYSHIP_TEST_DATABASE_URL")
    if not url:
        pytest.skip("HOLYSHIP_TEST_DATABASE_URL is required")
    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with factory() as session:
            yield session
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.mark.req("AI-12")
def test_configured_runtime_reaches_resolver_through_sync_pipeline(runtime_session):
    provider = RuntimeProvider()
    factory = build_resolution_executor_factory(
        _settings(),
        provider_builders={"fixture": lambda _settings: provider},
    )
    source = RuntimeSource("runtime-enabled")
    outcome = SyncService(
        runtime_session,
        resolution_executor_factory=factory,
    ).sync_one(source.message, source)
    runtime_session.commit()

    email = runtime_session.scalar(
        select(EmailMessageRecord).where(
            EmailMessageRecord.external_message_id == "runtime-enabled"
        )
    )
    source_weight = runtime_session.scalars(
        select(ExtractedFieldRecord).where(
            ExtractedFieldRecord.field_name == "gross_weight_kg"
        )
    ).all()
    assert outcome.status == "CLASSIFIED"
    assert provider.calls == 1
    assert outcome.resolver_calls == 1
    assert outcome.resolver_accepted == 1
    assert email.processing_status == "COMPLETED"
    assert runtime_session.query(AIResolutionRecord).count() == 1
    assert any(row.status == "UNRESOLVED" for row in source_weight)


@pytest.mark.req("AI-12")
def test_disabled_configured_runtime_keeps_deterministic_pipeline(runtime_session):
    constructed = 0

    def provider_builder(_settings):
        nonlocal constructed
        constructed += 1
        return RuntimeProvider()

    factory = build_resolution_executor_factory(
        _settings(ai_escalation_enabled=False),
        provider_builders={"fixture": provider_builder},
    )
    source = RuntimeSource("runtime-disabled")
    outcome = SyncService(
        runtime_session,
        resolution_executor_factory=factory,
    ).sync_one(source.message, source)
    email = runtime_session.scalar(
        select(EmailMessageRecord).where(
            EmailMessageRecord.external_message_id == "runtime-disabled"
        )
    )

    assert factory is None
    assert constructed == 0
    assert outcome.status == "CLASSIFIED"
    assert email.processing_status == "BLOCKED"
    assert outcome.resolver_calls == 0
    assert runtime_session.query(AIResolutionRecord).count() == 0
