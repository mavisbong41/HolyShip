from __future__ import annotations

import os
import threading

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from backend.app.extraction.models import CanonicalField
from backend.app.resolution.models import ExtractionResolutionRequest, ProviderResolution, ResolutionDecision
from backend.app.resolution.runtime import build_resolution_executor_factory
from backend.app.core.config import Settings
from backend.app.storage.database import Base
from backend.app.storage.models import AIResolutionRecord
from backend.app.storage.repositories import AIResolutionRepository


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


def _request():
    return ExtractionResolutionRequest(
        case_id="case-persist",
        field=CanonicalField.PORT_OF_LOADING,
        document_role="SI",
        document_id="doc-1",
        content_identity="sha256:abc",
        evidence="Port of Loading: Port Klang",
        deterministic_candidates=(),
        escalation_reason="UNRESOLVED_EXTRACTION",
    )


def _decision(request_hash="a" * 64):
    return ResolutionDecision(
        accepted=True,
        validation_reason="AI_RESOLUTION_ACCEPTED",
        field=CanonicalField.PORT_OF_LOADING,
        confidence=0.97,
        value="Port Klang",
        normalized_value="PORT KLANG",
        evidence={"provider_evidence": "Port of Loading: Port Klang"},
        provider_calls=1,
        request_hash=request_hash,
    )


def _store(repo, request_hash="a" * 64, *, version="resolver-v1"):
    return repo.store_decision(
        request_hash=request_hash,
        request=_request(),
        decision=_decision(request_hash),
        provider_name="fake",
        model_name="fixture-v1",
        resolver_version=version,
        prompt_schema_version="schema-v1",
    )


@pytest.mark.req("AI-08")
def test_resolution_audit_round_trips_accepted_metadata(db_factory):
    with db_factory() as session:
        stored = _store(AIResolutionRepository(session))
        session.commit()
        assert stored.accepted is True

    with db_factory() as session:
        record = session.scalar(select(AIResolutionRecord))
        cached = AIResolutionRepository(session).get_decision("a" * 64)
        assert record.purpose == "EXTRACTION"
        assert record.field_name == "port_of_loading"
        assert record.provider_name == "fake"
        assert record.resolver_version == "resolver-v1"
        assert record.request_json["purpose"] == "EXTRACTION"
        assert record.request_json["field"] == "port_of_loading"
        assert record.request_json["escalation_reason"] == "UNRESOLVED_EXTRACTION"
        assert "evidence" not in record.request_json
        assert "Port of Loading: Port Klang" not in str(record.request_json)
        assert record.response_json["normalized_value"] == "PORT KLANG"
        assert cached == _decision()


@pytest.mark.req("AI-09")
def test_concurrent_duplicate_insert_creates_one_cache_row(db_factory):
    barrier = threading.Barrier(2)
    errors: list[Exception] = []

    def insert_once():
        try:
            with db_factory() as session:
                barrier.wait(timeout=5)
                _store(AIResolutionRepository(session))
                session.commit()
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=insert_once) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert errors == []
    with db_factory() as session:
        assert session.scalar(select(func.count(AIResolutionRecord.id))) == 1


@pytest.mark.req("AI-09")
def test_runtime_factory_single_flights_provider_across_database_sessions(db_factory):
    entered = threading.Event()
    release = threading.Event()

    class DelayedProvider:
        def __init__(self):
            self.calls = 0
            self.lock = threading.Lock()

        def resolve(self, _request):
            with self.lock:
                self.calls += 1
            entered.set()
            release.wait(timeout=5)
            return ProviderResolution(
                field=CanonicalField.PORT_OF_LOADING,
                value="Port Klang",
                normalized_value="PORT KLANG",
                confidence=0.97,
                evidence="Port of Loading: Port Klang",
                reasoning_code="LAYOUT_ASSOCIATION",
            )

    provider = DelayedProvider()
    settings = Settings(
        _env_file=None,
        ai_escalation_enabled=True,
        ai_provider="fixture",
        ai_model="fixture-v1",
        ai_max_calls_per_case=2,
        ai_max_concurrent_calls=2,
        ai_timeout_seconds=2,
        retry_max_attempts=1,
    )
    factory = build_resolution_executor_factory(
        settings,
        provider_builders={"fixture": lambda _settings: provider},
    )
    errors: list[Exception] = []
    decisions = []

    def resolve_once():
        try:
            with db_factory() as session:
                decisions.append(factory(session).resolve_extraction(_request()))
                session.commit()
        except Exception as exc:
            errors.append(exc)

    first = threading.Thread(target=resolve_once)
    second = threading.Thread(target=resolve_once)
    first.start()
    assert entered.wait(timeout=5)
    second.start()
    release.set()
    first.join(timeout=10)
    second.join(timeout=10)

    assert errors == []
    assert provider.calls == 1
    assert len(decisions) == 2
    assert sum(decision.cache_hit for decision in decisions) == 1
    with db_factory() as session:
        assert session.scalar(select(func.count(AIResolutionRecord.id))) == 1


def test_request_hash_is_unique_while_versions_can_coexist(db_factory):
    with db_factory() as session:
        repo = AIResolutionRepository(session)
        _store(repo, "a" * 64, version="resolver-v1")
        _store(repo, "b" * 64, version="resolver-v2")
        session.commit()
        rows = session.scalars(select(AIResolutionRecord).order_by(AIResolutionRecord.resolver_version)).all()
        assert [row.resolver_version for row in rows] == ["resolver-v1", "resolver-v2"]
