from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.app.core.reliability import RetryPolicy
from backend.app.extraction.models import CanonicalField
from backend.app.resolution.models import (
    ExtractionResolutionRequest,
    ProviderResolution,
    SemanticResolutionRequest,
)
from backend.app.resolution.providers import TransientResolverError
from backend.app.resolution.service import ResolutionExecutor
from backend.app.resolution.service import ResolutionSharedState


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.lock = threading.Lock()

    def resolve(self, request):
        with self.lock:
            self.calls += 1
            response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if callable(response):
            return response(request)
        return response


def _extraction_request(**overrides):
    values = {
        "case_id": "case-1",
        "field": CanonicalField.PORT_OF_LOADING,
        "document_role": "SI",
        "document_id": "doc-1",
        "content_identity": "sha256:abc",
        "evidence": "Port of Loading: Port Klang",
        "deterministic_candidates": (),
        "escalation_reason": "UNRESOLVED_EXTRACTION",
    }
    values.update(overrides)
    return ExtractionResolutionRequest(**values)


def _semantic_request(**overrides):
    values = {
        "case_id": "case-1",
        "field": CanonicalField.SHIPPER,
        "si_value": "ABC LOGISTICS SDN BHD",
        "bl_value": "ABC LOGISTICS",
        "si_evidence": "Shipper: ABC LOGISTICS SDN BHD",
        "bl_evidence": "Shipper: ABC LOGISTICS",
        "source_identity": "si:1|bl:2",
        "escalation_reason": "SEMANTIC_NORMALIZATION_REQUIRED",
    }
    values.update(overrides)
    return SemanticResolutionRequest(**values)


def _executor(provider, **overrides):
    values = {
        "provider": provider,
        "enabled": True,
        "confidence_threshold": 0.9,
        "timeout_seconds": 0.05,
        "retry_policy": RetryPolicy(max_attempts=2, backoff_seconds=0),
        "max_calls_per_case": 2,
        "max_concurrent_calls": 2,
        "resolver_version": "resolver-v1",
        "provider_name": "fake",
        "model_name": "fixture-v1",
        "prompt_schema_version": "schema-v1",
    }
    values.update(overrides)
    return ResolutionExecutor(**values)


@pytest.mark.req("AI-01")
def test_high_confidence_anchored_extraction_is_accepted():
    provider = FakeProvider([ProviderResolution(
        field=CanonicalField.PORT_OF_LOADING,
        value="Port Klang",
        normalized_value="PORT KLANG",
        confidence=0.97,
        evidence="Port of Loading: Port Klang",
        reasoning_code="LAYOUT_ASSOCIATION",
    )])

    result = _executor(provider).resolve_extraction(_extraction_request())

    assert result.accepted is True
    assert result.normalized_value == "PORT KLANG"
    assert result.validation_reason == "AI_RESOLUTION_ACCEPTED"
    assert provider.calls == 1


@pytest.mark.req("EXT-05b")
def test_multiple_unresolved_fields_are_batched_into_one_provider_call():
    provider = FakeProvider([[
        ProviderResolution(
            field=CanonicalField.PORT_OF_LOADING,
            value="Port Klang",
            normalized_value="PORT KLANG",
            confidence=0.97,
            evidence="Port of Loading: Port Klang",
            reasoning_code="LAYOUT_ASSOCIATION",
        ),
        ProviderResolution(
            field=CanonicalField.PORT_OF_DISCHARGE,
            value="Singapore",
            normalized_value="SINGAPORE",
            confidence=0.96,
            evidence="Port of Discharge: Singapore",
            reasoning_code="LAYOUT_ASSOCIATION",
        ),
    ]])
    executor = _executor(provider)
    results = executor.resolve_extraction_batch((
        _extraction_request(),
        _extraction_request(
            field=CanonicalField.PORT_OF_DISCHARGE,
            evidence="Port of Discharge: Singapore",
        ),
    ))

    assert [result.accepted for result in results] == [True, True]
    assert provider.calls == 1


def test_concurrent_identical_batches_single_flight_across_session_executors():
    entered = threading.Event()
    release = threading.Event()
    responses = [
        ProviderResolution(
            field=CanonicalField.PORT_OF_LOADING,
            value="Port Klang",
            normalized_value="PORT KLANG",
            confidence=0.97,
            evidence="Port of Loading: Port Klang",
            reasoning_code="LAYOUT_ASSOCIATION",
        ),
        ProviderResolution(
            field=CanonicalField.PORT_OF_DISCHARGE,
            value="Singapore",
            normalized_value="SINGAPORE",
            confidence=0.96,
            evidence="Port of Discharge: Singapore",
            reasoning_code="LAYOUT_ASSOCIATION",
        ),
    ]

    def delayed(_request):
        entered.set()
        release.wait(timeout=1)
        return responses

    provider = FakeProvider([delayed])
    shared_state = ResolutionSharedState(max_concurrent_calls=2)
    one = _executor(provider, shared_state=shared_state)
    two = _executor(provider, shared_state=shared_state)
    requests = (
        _extraction_request(),
        _extraction_request(
            field=CanonicalField.PORT_OF_DISCHARGE,
            evidence="Port of Discharge: Singapore",
        ),
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(one.resolve_extraction_batch, requests)
        assert entered.wait(timeout=1)
        second = pool.submit(two.resolve_extraction_batch, requests)
        release.set()
        results = (first.result(timeout=2), second.result(timeout=2))

    assert provider.calls == 1
    assert all(all(decision.accepted for decision in result) for result in results)
    assert sum(decision.cache_hit for decision in results[1]) == 2


@pytest.mark.req("AI-02")
def test_low_confidence_and_contradictory_extractions_are_rejected():
    low = FakeProvider([ProviderResolution(
        field=CanonicalField.PORT_OF_LOADING,
        value="Port Klang",
        normalized_value="PORT KLANG",
        confidence=0.4,
        evidence="Port of Loading: Port Klang",
        reasoning_code="LOW_CONFIDENCE",
    )])
    assert _executor(low).resolve_extraction(_extraction_request()).validation_reason == "AI_CONFIDENCE_BELOW_THRESHOLD"

    conflict = FakeProvider([ProviderResolution(
        field=CanonicalField.PORT_OF_LOADING,
        value="Port Klang",
        normalized_value="PORT KLANG",
        confidence=0.99,
        evidence="Port Klang / Penang",
        reasoning_code="AMBIGUOUS",
    )])
    result = _executor(conflict).resolve_extraction(_extraction_request(
        evidence="POL candidates: Port Klang / Penang",
        deterministic_candidates=("Port Klang", "Penang"),
    ))
    assert result.accepted is False
    assert result.validation_reason == "CONFLICTING_DETERMINISTIC_CANDIDATES"

    invented = FakeProvider([ProviderResolution(
        field=CanonicalField.PORT_OF_LOADING,
        value="Penang",
        normalized_value="PENANG",
        confidence=0.99,
        evidence="Port of Loading: Port Klang",
        reasoning_code="UNSUPPORTED_PROPOSAL",
    )])
    result = _executor(invented).resolve_extraction(_extraction_request())
    assert result.validation_reason == "VALUE_NOT_SUPPORTED_BY_EVIDENCE"


@pytest.mark.req("AI-03")
def test_missing_evidence_never_calls_provider_or_invents_value():
    provider = FakeProvider([])
    result = _executor(provider).resolve_extraction(_extraction_request(evidence=""))
    assert result.accepted is False
    assert result.validation_reason == "SOURCE_EVIDENCE_MISSING"
    assert provider.calls == 0


@pytest.mark.req("EXT-07")
@pytest.mark.req("AI-04")
def test_malformed_timeout_and_retry_exhaustion_are_isolated():
    malformed = FakeProvider([{"field": "shipper", "value": "invented"}])
    assert _executor(malformed).resolve_extraction(_extraction_request()).validation_reason == "PROVIDER_OUTPUT_INVALID"

    slow = FakeProvider([lambda _request: (time.sleep(0.2), None)[1]])
    assert _executor(slow, retry_policy=RetryPolicy(max_attempts=1)).resolve_extraction(
        _extraction_request()
    ).validation_reason == "PROVIDER_TIMEOUT"

    exhausted = FakeProvider([TransientResolverError("temporary"), TransientResolverError("still down")])
    result = _executor(exhausted).resolve_extraction(_extraction_request())
    assert result.validation_reason == "PROVIDER_RETRY_EXHAUSTED"
    assert exhausted.calls == 2


@pytest.mark.req("AI-05")
def test_transient_failure_retries_then_accepts():
    provider = FakeProvider([
        TransientResolverError("temporary"),
        ProviderResolution(
            field=CanonicalField.PORT_OF_LOADING,
            value="Port Klang",
            normalized_value="PORT KLANG",
            confidence=0.98,
            evidence="Port of Loading: Port Klang",
            reasoning_code="LAYOUT_ASSOCIATION",
        ),
    ])
    result = _executor(provider).resolve_extraction(_extraction_request())
    assert result.accepted is True
    assert provider.calls == 2


@pytest.mark.req("AI-06")
def test_numeric_and_unit_validation_rejects_unsafe_output():
    pounds = FakeProvider([ProviderResolution(
        field=CanonicalField.GROSS_WEIGHT_KG,
        value="10,000 LB",
        normalized_value=10000,
        confidence=0.99,
        evidence="Gross Weight: 10,000 LB",
        reasoning_code="QUANTITY_PARSE",
    )])
    result = _executor(pounds).resolve_extraction(_extraction_request(
        field=CanonicalField.GROSS_WEIGHT_KG,
        evidence="Gross Weight: 10,000 LB",
    ))
    assert result.validation_reason == "UNSUPPORTED_GROSS_WEIGHT_UNIT"

    fractional = FakeProvider([ProviderResolution(
        field=CanonicalField.CONTAINER_COUNT,
        value="2.5",
        normalized_value=2.5,
        confidence=0.99,
        evidence="Container Count: 2.5",
        reasoning_code="QUANTITY_PARSE",
    )])
    result = _executor(fractional).resolve_extraction(_extraction_request(
        field=CanonicalField.CONTAINER_COUNT,
        evidence="Container Count: 2.5",
    ))
    assert result.validation_reason == "INVALID_CONTAINER_COUNT"


@pytest.mark.req("AI-07")
def test_semantic_resolution_is_structured_and_evidence_bound():
    provider = FakeProvider([ProviderResolution(
        field=CanonicalField.SHIPPER,
        equivalent=True,
        confidence=0.96,
        evidence="ABC LOGISTICS SDN BHD | ABC LOGISTICS",
        reasoning_code="LEGAL_SUFFIX_EQUIVALENCE",
    )])
    result = _executor(provider).resolve_semantic(_semantic_request())
    assert result.accepted is True
    assert result.equivalent is True


@pytest.mark.req("PRF-03")
def test_budget_is_bounded_per_case():
    provider = FakeProvider([
        ProviderResolution(field=CanonicalField.SHIPPER, equivalent=None, confidence=0.2, evidence="x", reasoning_code="NO_DECISION"),
        ProviderResolution(field=CanonicalField.CONSIGNEE, equivalent=None, confidence=0.2, evidence="x", reasoning_code="NO_DECISION"),
    ])
    executor = _executor(provider, max_calls_per_case=1)
    executor.resolve_semantic(_semantic_request())
    second = executor.resolve_semantic(_semantic_request(field=CanonicalField.CONSIGNEE))
    assert second.validation_reason == "CASE_CALL_BUDGET_EXHAUSTED"
    assert provider.calls == 1


@pytest.mark.req("AI-08")
def test_cached_repeat_and_version_change_have_stable_identity():
    response = ProviderResolution(
        field=CanonicalField.PORT_OF_LOADING,
        value="Port Klang",
        normalized_value="PORT KLANG",
        confidence=0.97,
        evidence="Port of Loading: Port Klang",
        reasoning_code="LAYOUT_ASSOCIATION",
    )
    provider = FakeProvider([response, response])
    executor_v1 = _executor(provider)
    first = executor_v1.resolve_extraction(_extraction_request())
    second = executor_v1.resolve_extraction(_extraction_request())
    executor_v2 = _executor(provider, resolver_version="resolver-v2")
    third = executor_v2.resolve_extraction(_extraction_request())
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert third.cache_hit is False
    assert provider.calls == 2


def test_cache_identity_uses_content_not_case_or_document_database_ids():
    response = ProviderResolution(
        field=CanonicalField.PORT_OF_LOADING,
        value="Port Klang",
        normalized_value="PORT KLANG",
        confidence=0.97,
        evidence="Port of Loading: Port Klang",
        reasoning_code="LAYOUT_ASSOCIATION",
    )
    provider = FakeProvider([response])
    executor = _executor(provider)
    first = executor.resolve_extraction(_extraction_request())
    second = executor.resolve_extraction(_extraction_request(case_id="case-2", document_id="doc-99"))
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert provider.calls == 1


@pytest.mark.req("AI-09")
def test_concurrent_duplicate_escalation_is_single_flight():
    entered = threading.Event()
    release = threading.Event()

    def delayed(_request):
        entered.set()
        release.wait(timeout=2)
        return ProviderResolution(
            field=CanonicalField.PORT_OF_LOADING,
            value="Port Klang",
            normalized_value="PORT KLANG",
            confidence=0.97,
            evidence="Port of Loading: Port Klang",
            reasoning_code="LAYOUT_ASSOCIATION",
        )

    provider = FakeProvider([delayed])
    executor = _executor(provider)
    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(executor.resolve_extraction, _extraction_request())
        assert entered.wait(timeout=1)
        two = pool.submit(executor.resolve_extraction, _extraction_request())
        release.set()
        results = [one.result(timeout=2), two.result(timeout=2)]

    assert provider.calls == 1
    assert sum(result.cache_hit for result in results) == 1


def test_independent_worker_executors_share_in_process_single_flight_and_limit():
    entered = threading.Event()
    release = threading.Event()

    def delayed(_request):
        entered.set()
        release.wait(timeout=2)
        return ProviderResolution(
            field=CanonicalField.PORT_OF_LOADING,
            value="Port Klang",
            normalized_value="PORT KLANG",
            confidence=0.97,
            evidence="Port of Loading: Port Klang",
            reasoning_code="LAYOUT_ASSOCIATION",
        )

    provider = FakeProvider([delayed])
    shared_state = ResolutionSharedState(max_concurrent_calls=1)
    one_executor = _executor(provider, shared_state=shared_state)
    two_executor = _executor(provider, shared_state=shared_state)
    with ThreadPoolExecutor(max_workers=2) as pool:
        one = pool.submit(one_executor.resolve_extraction, _extraction_request())
        assert entered.wait(timeout=1)
        two = pool.submit(two_executor.resolve_extraction, _extraction_request())
        release.set()
        results = [one.result(timeout=2), two.result(timeout=2)]

    assert provider.calls == 1
    assert sum(result.cache_hit for result in results) == 1


def test_provider_model_prompt_and_purpose_changes_invalidate_shared_cache():
    response = ProviderResolution(
        field=CanonicalField.PORT_OF_LOADING,
        value="Port Klang",
        normalized_value="PORT KLANG",
        confidence=0.97,
        evidence="Port of Loading: Port Klang",
        reasoning_code="LAYOUT_ASSOCIATION",
    )
    provider = FakeProvider([response, response, response, response])
    shared_state = ResolutionSharedState(max_concurrent_calls=2)
    common = {"shared_state": shared_state, "max_calls_per_case": 4}
    _executor(provider, **common).resolve_extraction(_extraction_request())
    _executor(provider, provider_name="other", **common).resolve_extraction(_extraction_request())
    _executor(provider, model_name="fixture-v2", **common).resolve_extraction(_extraction_request())
    _executor(provider, prompt_schema_version="schema-v2", **common).resolve_extraction(_extraction_request())
    assert provider.calls == 4


def test_disabled_executor_never_calls_provider():
    provider = FakeProvider([])
    result = _executor(provider, enabled=False).resolve_semantic(_semantic_request())
    assert result.validation_reason == "AI_ESCALATION_DISABLED"
    assert provider.calls == 0


def test_unsupported_field_is_rejected_by_project_owned_request_schema():
    with pytest.raises(ValueError, match="booking_number"):
        _extraction_request(field="booking_number")


def test_resolution_persistence_failure_isolated_as_unresolved():
    class FailingStore:
        def get_decision(self, _request_hash):
            return None

        def store_decision(self, **_kwargs):
            raise RuntimeError("database unavailable")

    provider = FakeProvider([ProviderResolution(
        field=CanonicalField.PORT_OF_LOADING,
        value="Port Klang",
        normalized_value="PORT KLANG",
        confidence=0.97,
        evidence="Port of Loading: Port Klang",
        reasoning_code="LAYOUT_ASSOCIATION",
    )])
    result = _executor(provider, store=FailingStore()).resolve_extraction(_extraction_request())
    assert result.accepted is False
    assert result.validation_reason == "RESOLUTION_PERSISTENCE_FAILED"
