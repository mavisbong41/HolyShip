from __future__ import annotations

import hashlib
import json
import math
import re
import threading
from dataclasses import dataclass, replace
from typing import Any, Protocol

from backend.app.core.reliability import RetryPolicy, retry_call, run_with_timeout
from backend.app.extraction.models import CanonicalField
from backend.app.resolution.models import (
    ExtractionResolutionRequest,
    ProviderResolution,
    ResolutionDecision,
    ResolutionMetrics,
    SemanticResolutionRequest,
)
from backend.app.resolution.providers import ResolverProvider, TransientResolverError


class ResolutionStore(Protocol):
    def get_decision(self, request_hash: str) -> ResolutionDecision | None: ...

    def store_decision(
        self,
        *,
        request_hash: str,
        request: ExtractionResolutionRequest | SemanticResolutionRequest,
        decision: ResolutionDecision,
        provider_name: str,
        model_name: str,
        resolver_version: str,
        prompt_schema_version: str,
    ) -> ResolutionDecision: ...


class ResolutionSharedState:
    """Process-local coordination shared by all database-session executors."""

    def __init__(self, *, max_concurrent_calls: int) -> None:
        if max_concurrent_calls < 1:
            raise ValueError("max_concurrent_calls must be positive")
        self.max_concurrent_calls = max_concurrent_calls
        self.cache: dict[str, ResolutionDecision] = {}
        self.case_calls: dict[str, int] = {}
        self.key_locks: dict[str, threading.Lock] = {}
        self.lock = threading.RLock()
        self.provider_slots = threading.BoundedSemaphore(max_concurrent_calls)


class ResolutionExecutor:
    """Validate, budget, cache, and isolate targeted resolver calls."""

    def __init__(
        self,
        *,
        provider: ResolverProvider,
        enabled: bool = False,
        confidence_threshold: float = 0.9,
        timeout_seconds: float = 5.0,
        retry_policy: RetryPolicy | None = None,
        max_calls_per_case: int = 2,
        max_concurrent_calls: int = 2,
        resolver_version: str = "phase6-resolver-v1",
        provider_name: str = "disabled",
        model_name: str = "none",
        prompt_schema_version: str = "phase6-schema-v1",
        store: ResolutionStore | None = None,
        shared_state: ResolutionSharedState | None = None,
    ) -> None:
        if not 0 <= confidence_threshold <= 1:
            raise ValueError("confidence_threshold must be between zero and one")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_calls_per_case < 1 or max_concurrent_calls < 1:
            raise ValueError("resolver budgets must be positive")
        self.provider = provider
        self.enabled = enabled
        self.confidence_threshold = confidence_threshold
        self.timeout_seconds = timeout_seconds
        self.retry_policy = retry_policy or RetryPolicy()
        self.max_calls_per_case = max_calls_per_case
        self.resolver_version = resolver_version
        self.provider_name = provider_name
        self.model_name = model_name
        self.prompt_schema_version = prompt_schema_version
        self.store = store
        self.metrics = ResolutionMetrics()
        self.shared_state = shared_state or ResolutionSharedState(
            max_concurrent_calls=max_concurrent_calls
        )
        self._cache = self.shared_state.cache
        self._case_calls = self.shared_state.case_calls
        self._lock = self.shared_state.lock
        self._key_locks = self.shared_state.key_locks
        self._provider_slots = self.shared_state.provider_slots

    @property
    def comparison_version(self) -> str:
        if not self.enabled:
            return "phase4-deterministic-v1"
        identity = f"{self.resolver_version}|{self.provider_name}|{self.model_name}|{self.prompt_schema_version}"
        return f"phase6-ai-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:16]}"

    def resolve_extraction(self, request: ExtractionResolutionRequest) -> ResolutionDecision:
        early = self._early_rejection(request.field, request.case_id, request.evidence)
        if early is not None:
            return early
        return self._resolve(request, purpose="EXTRACTION")

    def resolve_extraction_batch(
        self,
        requests: tuple[ExtractionResolutionRequest, ...],
    ) -> tuple[ResolutionDecision, ...]:
        """Resolve all hard fields from one document in one provider operation."""

        if not requests:
            return ()
        if len(requests) == 1:
            return (self.resolve_extraction(requests[0]),)
        if len({request.case_id for request in requests}) != 1 or len(
            {(request.document_id, request.content_identity) for request in requests}
        ) != 1:
            raise ValueError("extraction batches must belong to one case and document")

        decisions: list[ResolutionDecision | None] = [None] * len(requests)
        pending: list[tuple[int, ExtractionResolutionRequest, str]] = []
        for index, request in enumerate(requests):
            early = self._early_rejection(request.field, request.case_id, request.evidence)
            if early is not None:
                decisions[index] = early
                continue
            request_hash = self._request_hash(request, "EXTRACTION")
            cached = self._get_cached(request_hash)
            if cached is not None:
                decisions[index] = cached
                continue
            distinct = {
                str(value).strip().casefold()
                for value in request.deterministic_candidates
                if str(value).strip()
            }
            if len(distinct) > 1:
                decision = self._rejection(
                    request.field,
                    "CONFLICTING_DETERMINISTIC_CANDIDATES",
                    request_hash=request_hash,
                )
                decisions[index] = self._remember(request_hash, request, decision)
                continue
            pending.append((index, request, request_hash))

        if pending:
            batch_identity = hashlib.sha256(
                "|".join(sorted(request_hash for _index, _request, request_hash in pending)).encode("utf-8")
            ).hexdigest()
            with self._lock:
                batch_lock = self._key_locks.setdefault(
                    f"batch:{batch_identity}", threading.Lock()
                )
            with batch_lock:
                still_pending = []
                for index, request, request_hash in pending:
                    cached = self._get_cached(request_hash)
                    if cached is not None:
                        decisions[index] = cached
                    else:
                        still_pending.append((index, request, request_hash))
                if still_pending:
                    self._resolve_extraction_pending(still_pending, decisions)
        return tuple(decision for decision in decisions if decision is not None)

    def _resolve_extraction_pending(
        self,
        pending: list[tuple[int, ExtractionResolutionRequest, str]],
        decisions: list[ResolutionDecision | None],
    ) -> None:
        batch = _ExtractionBatchRequest(
            case_id=pending[0][1].case_id,
            requests=tuple(request for _index, request, _hash in pending),
        )
        try:
            response, calls = self._call_provider(batch)
            response_items = response if isinstance(response, (list, tuple)) else (response,)
            by_field = {
                item.field: item
                for item in response_items
                if isinstance(item, ProviderResolution)
            }
            for offset, (index, request, request_hash) in enumerate(pending):
                item = by_field.get(request.field)
                decision = self._validate(
                    request,
                    item,
                    request_hash,
                    calls if offset == 0 else 0,
                )
                decisions[index] = self._remember(request_hash, request, decision)
        except _BudgetExhausted:
            self._reject_batch(pending, decisions, "CASE_CALL_BUDGET_EXHAUSTED")
        except TimeoutError:
            self._record_failure()
            self._reject_batch(pending, decisions, "PROVIDER_TIMEOUT")
        except TransientResolverError:
            self._record_failure()
            self._reject_batch(pending, decisions, "PROVIDER_RETRY_EXHAUSTED")
        except Exception:
            self._record_failure()
            self._reject_batch(pending, decisions, "PROVIDER_FAILURE")

    def _reject_batch(
        self,
        pending: list[tuple[int, ExtractionResolutionRequest, str]],
        decisions: list[ResolutionDecision | None],
        reason: str,
    ) -> None:
        for index, request, request_hash in pending:
            decision = self._rejection(request.field, reason, request_hash=request_hash)
            decisions[index] = self._remember(request_hash, request, decision)

    def resolve_semantic(self, request: SemanticResolutionRequest) -> ResolutionDecision:
        evidence = f"{request.si_evidence}\n{request.bl_evidence}".strip()
        if request.si_value in (None, "") or request.bl_value in (None, ""):
            evidence = ""
        early = self._early_rejection(request.field, request.case_id, evidence)
        if early is not None:
            return early
        return self._resolve(request, purpose="SEMANTIC")

    def _early_rejection(
        self,
        field: CanonicalField,
        case_id: str,
        evidence: str,
    ) -> ResolutionDecision | None:
        if not self.enabled:
            return self._rejection(field, "AI_ESCALATION_DISABLED")
        if field not in set(CanonicalField):
            return self._rejection(field, "UNSUPPORTED_FIELD")
        if not evidence.strip():
            return self._rejection(field, "SOURCE_EVIDENCE_MISSING")
        with self._lock:
            self.metrics.escalated_cases.add(case_id)
        return None

    def _resolve(
        self,
        request: ExtractionResolutionRequest | SemanticResolutionRequest,
        *,
        purpose: str,
    ) -> ResolutionDecision:
        request_hash = self._request_hash(request, purpose)
        cached = self._get_cached(request_hash)
        if cached is not None:
            return cached

        with self._lock:
            key_lock = self._key_locks.setdefault(request_hash, threading.Lock())
        with key_lock:
            cached = self._get_cached(request_hash)
            if cached is not None:
                return cached
            if isinstance(request, ExtractionResolutionRequest):
                distinct = {str(value).strip().casefold() for value in request.deterministic_candidates if str(value).strip()}
                if len(distinct) > 1:
                    decision = self._rejection(
                        request.field,
                        "CONFLICTING_DETERMINISTIC_CANDIDATES",
                        request_hash=request_hash,
                    )
                    return self._remember(request_hash, request, decision)

            try:
                response, calls = self._call_provider(request)
            except _BudgetExhausted:
                return self._rejection(request.field, "CASE_CALL_BUDGET_EXHAUSTED", request_hash=request_hash)
            except TimeoutError:
                self._record_failure()
                decision = self._rejection(request.field, "PROVIDER_TIMEOUT", request_hash=request_hash)
                return self._remember(request_hash, request, decision)
            except TransientResolverError:
                self._record_failure()
                decision = self._rejection(request.field, "PROVIDER_RETRY_EXHAUSTED", request_hash=request_hash)
                return self._remember(request_hash, request, decision)
            except Exception:
                self._record_failure()
                decision = self._rejection(request.field, "PROVIDER_FAILURE", request_hash=request_hash)
                return self._remember(request_hash, request, decision)

            decision = self._validate(request, response, request_hash, calls)
            return self._remember(request_hash, request, decision)

    def _call_provider(
        self,
        request: ExtractionResolutionRequest | SemanticResolutionRequest | _ExtractionBatchRequest,
    ) -> tuple[object, int]:
        calls_before = self.metrics.provider_calls

        def one_attempt():
            with self._lock:
                used = self._case_calls.get(request.case_id, 0)
                if used >= self.max_calls_per_case:
                    raise _BudgetExhausted()
                self._case_calls[request.case_id] = used + 1
                self.metrics.provider_calls += 1
            with self._provider_slots:
                return self.provider.resolve(request)

        def operation():
            return retry_call(
                one_attempt,
                policy=self.retry_policy,
                is_retryable=lambda exc: isinstance(exc, TransientResolverError),
            )

        response = run_with_timeout(operation, timeout_seconds=self.timeout_seconds)
        return response, self.metrics.provider_calls - calls_before

    def _validate(
        self,
        request: ExtractionResolutionRequest | SemanticResolutionRequest,
        response: object,
        request_hash: str,
        calls: int,
    ) -> ResolutionDecision:
        if not isinstance(response, ProviderResolution) or response.field != request.field:
            with self._lock:
                self.metrics.malformed_responses += 1
            return self._rejection(
                request.field,
                "PROVIDER_OUTPUT_INVALID",
                request_hash=request_hash,
                provider_calls=calls,
            )
        if response.confidence < self.confidence_threshold:
            return self._rejection(
                request.field,
                "AI_CONFIDENCE_BELOW_THRESHOLD",
                confidence=response.confidence,
                request_hash=request_hash,
                provider_calls=calls,
                response=response,
            )
        if isinstance(request, SemanticResolutionRequest):
            return self._validate_semantic(request, response, request_hash, calls)
        return self._validate_extraction(request, response, request_hash, calls)

    def _validate_extraction(
        self,
        request: ExtractionResolutionRequest,
        response: ProviderResolution,
        request_hash: str,
        calls: int,
    ) -> ResolutionDecision:
        if not response.evidence.strip() or response.evidence.casefold() not in request.evidence.casefold():
            return self._rejection(
                request.field, "EVIDENCE_NOT_ANCHORED", confidence=response.confidence,
                request_hash=request_hash, provider_calls=calls, response=response,
            )
        if response.value in (None, "") or response.normalized_value in (None, ""):
            return self._rejection(
                request.field, "PROVIDER_VALUE_MISSING", confidence=response.confidence,
                request_hash=request_hash, provider_calls=calls, response=response,
            )
        if not self._value_is_anchored(response.value, response.evidence):
            return self._rejection(
                request.field, "VALUE_NOT_SUPPORTED_BY_EVIDENCE", confidence=response.confidence,
                request_hash=request_hash, provider_calls=calls, response=response,
            )
        if request.deterministic_candidates:
            candidate = next((value for value in request.deterministic_candidates if str(value).strip()), None)
            if candidate is not None and str(response.value).strip().casefold() != str(candidate).strip().casefold():
                return self._rejection(
                    request.field, "CONTRADICTS_DETERMINISTIC_EVIDENCE", confidence=response.confidence,
                    request_hash=request_hash, provider_calls=calls, response=response,
                )
        invalid = self._validate_field_value(request.field, response, request.evidence)
        if invalid is not None:
            return self._rejection(
                request.field, invalid, confidence=response.confidence,
                request_hash=request_hash, provider_calls=calls, response=response,
            )
        return ResolutionDecision(
            accepted=True,
            validation_reason="AI_RESOLUTION_ACCEPTED",
            field=request.field,
            confidence=response.confidence,
            value=response.value,
            normalized_value=response.normalized_value,
            evidence=self._response_evidence(response),
            provider_calls=calls,
            request_hash=request_hash,
        )

    def _validate_semantic(
        self,
        request: SemanticResolutionRequest,
        response: ProviderResolution,
        request_hash: str,
        calls: int,
    ) -> ResolutionDecision:
        evidence = response.evidence.casefold()
        if response.equivalent is None:
            return self._rejection(
                request.field, "AI_NO_DECISION", confidence=response.confidence,
                request_hash=request_hash, provider_calls=calls, response=response,
            )
        if not evidence or str(request.si_value).casefold() not in evidence or str(request.bl_value).casefold() not in evidence:
            return self._rejection(
                request.field, "EVIDENCE_NOT_ANCHORED", confidence=response.confidence,
                request_hash=request_hash, provider_calls=calls, response=response,
            )
        return ResolutionDecision(
            accepted=True,
            validation_reason="AI_RESOLUTION_ACCEPTED",
            field=request.field,
            confidence=response.confidence,
            equivalent=response.equivalent,
            evidence=self._response_evidence(response),
            provider_calls=calls,
            request_hash=request_hash,
        )

    @staticmethod
    def _value_is_anchored(value: Any, evidence: str) -> bool:
        if isinstance(value, bool):
            return False
        if isinstance(value, (int, float)):
            normalized_evidence = evidence.casefold().replace(",", "")
            return str(value).casefold() in normalized_evidence
        return str(value).strip().casefold() in evidence.casefold()

    @staticmethod
    def _validate_field_value(
        field: CanonicalField,
        response: ProviderResolution,
        source_evidence: str,
    ) -> str | None:
        if field == CanonicalField.CONTAINER_COUNT:
            value = response.normalized_value
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                return "INVALID_CONTAINER_COUNT"
        elif field == CanonicalField.GROSS_WEIGHT_KG:
            combined = f"{response.value} {response.evidence} {source_evidence}".casefold()
            if re.search(r"\b(lb|lbs|pound|pounds)\b", combined):
                return "UNSUPPORTED_GROSS_WEIGHT_UNIT"
            value = response.normalized_value
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value < 0:
                return "INVALID_GROSS_WEIGHT_KG"
        elif not isinstance(response.normalized_value, str) or not response.normalized_value.strip():
            return "INVALID_TEXT_VALUE"
        return None

    def _get_cached(self, request_hash: str) -> ResolutionDecision | None:
        with self._lock:
            cached = self._cache.get(request_hash)
        if cached is None and self.store is not None:
            cached = self.store.get_decision(request_hash)
        if cached is None:
            return None
        with self._lock:
            self.metrics.cache_hits += 1
        return replace(cached, cache_hit=True, provider_calls=0)

    def _remember(
        self,
        request_hash: str,
        request: ExtractionResolutionRequest | SemanticResolutionRequest,
        decision: ResolutionDecision,
    ) -> ResolutionDecision:
        stored = decision
        if self.store is not None:
            try:
                stored = self.store.store_decision(
                    request_hash=request_hash,
                    request=request,
                    decision=decision,
                    provider_name=self.provider_name,
                    model_name=self.model_name,
                    resolver_version=self.resolver_version,
                    prompt_schema_version=self.prompt_schema_version,
                )
            except Exception:
                with self._lock:
                    self.metrics.provider_failures += 1
                    self.metrics.rejected += 1
                return replace(
                    decision,
                    accepted=False,
                    validation_reason="RESOLUTION_PERSISTENCE_FAILED",
                    value=None,
                    normalized_value=None,
                    equivalent=None,
                )
        with self._lock:
            self._cache[request_hash] = stored
            if stored.accepted:
                self.metrics.accepted += 1
            else:
                self.metrics.rejected += 1
        return stored

    def _request_hash(
        self,
        request: ExtractionResolutionRequest | SemanticResolutionRequest,
        purpose: str,
    ) -> str:
        if isinstance(request, ExtractionResolutionRequest):
            request_identity = {
                "field": request.field.value,
                "document_role": request.document_role,
                "content_identity": request.content_identity,
                "evidence": request.evidence,
                "deterministic_candidates": request.deterministic_candidates,
                "escalation_reason": request.escalation_reason,
            }
        else:
            request_identity = {
                "field": request.field.value,
                "si_value": request.si_value,
                "bl_value": request.bl_value,
                "si_evidence": request.si_evidence,
                "bl_evidence": request.bl_evidence,
                "source_identity": request.source_identity,
                "escalation_reason": request.escalation_reason,
            }
        payload = {
            "purpose": purpose,
            "request": request_identity,
            "resolver_version": self.resolver_version,
            "provider": self.provider_name,
            "model": self.model_name,
            "prompt_schema_version": self.prompt_schema_version,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _record_failure(self) -> None:
        with self._lock:
            self.metrics.provider_failures += 1

    @staticmethod
    def _response_evidence(response: ProviderResolution) -> dict[str, Any]:
        evidence = {
            "provider_evidence": response.evidence,
            "reasoning_code": response.reasoning_code,
        }
        if response.audit_metadata:
            evidence["ai_gateway"] = response.audit_metadata
        return evidence

    @staticmethod
    def _rejection(
        field: CanonicalField,
        reason: str,
        *,
        confidence: float = 0.0,
        request_hash: str = "",
        provider_calls: int = 0,
        response: ProviderResolution | None = None,
    ) -> ResolutionDecision:
        return ResolutionDecision(
            accepted=False,
            validation_reason=reason,
            field=field,
            confidence=confidence,
            value=response.value if response is not None else None,
            normalized_value=response.normalized_value if response is not None else None,
            equivalent=response.equivalent if response is not None else None,
            evidence=(ResolutionExecutor._response_evidence(response) if response is not None else {}),
            provider_calls=provider_calls,
            request_hash=request_hash,
        )


class _BudgetExhausted(RuntimeError):
    pass


@dataclass(frozen=True)
class _ExtractionBatchRequest:
    case_id: str
    requests: tuple[ExtractionResolutionRequest, ...]
