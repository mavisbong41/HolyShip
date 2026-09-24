from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.resolution.providers import (
    DisabledResolverProvider,
    GeminiResolverProvider,
    HttpJsonResolverProvider,
    ResolverProvider,
)
from backend.app.resolution.service import ResolutionExecutor, ResolutionSharedState
from backend.app.storage.repositories import AIResolutionRepository
from backend.app.security.ai_gateway import SecureAIGateway


ProviderBuilder = Callable[[Settings], ResolverProvider]
ExecutorFactory = Callable[[Session | None], ResolutionExecutor]


def build_resolution_executor_factory(
    settings: Settings,
    *,
    provider_builders: dict[str, ProviderBuilder] | None = None,
) -> ExecutorFactory | None:
    """Build one process-shared provider boundary and session-local stores."""

    if not settings.ai_escalation_enabled or settings.ai_provider.lower() in ("disabled", "none", "off", ""):
        return None
    builders = provider_builders or {
        "http_json": _build_http_json_provider,
        "gemini": _build_gemini_provider,
        "google": _build_gemini_provider,
        "custom": _build_http_json_provider,
    }
    builder = builders.get(settings.ai_provider.lower())
    if builder is None:
        return None
    provider = builder(settings)
    if isinstance(provider, DisabledResolverProvider):
        return None
    shared_state = ResolutionSharedState(
        max_concurrent_calls=settings.ai_max_concurrent_calls
    )

    def factory(session: Session | None) -> ResolutionExecutor:
        return ResolutionExecutor(
            provider=provider,
            enabled=True,
            confidence_threshold=settings.ai_confidence_threshold,
            timeout_seconds=settings.ai_timeout_seconds,
            retry_policy=settings.retry_policy,
            max_calls_per_case=settings.ai_max_calls_per_case,
            max_concurrent_calls=settings.ai_max_concurrent_calls,
            resolver_version=settings.ai_resolver_version,
            provider_name=settings.ai_provider,
            model_name=settings.ai_model,
            prompt_schema_version=settings.ai_prompt_schema_version,
            store=AIResolutionRepository(session) if session is not None else None,
            shared_state=shared_state,
        )

    return factory


def _build_gemini_provider(settings: Settings) -> ResolverProvider:
    api_key = (
        (settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None)
        or (settings.ai_api_key.get_secret_value() if settings.ai_api_key else None)
        or (settings.ai_review_api_key.get_secret_value() if settings.ai_review_api_key else None)
    )
    if not api_key:
        return DisabledResolverProvider()
    return GeminiResolverProvider(
        api_key=api_key,
        model_name=settings.ai_model if settings.ai_model not in ("none", "", "disabled") else "gemini-2.5-flash",
        timeout_seconds=settings.ai_timeout_seconds,
        endpoint=settings.ai_endpoint,
        gateway=SecureAIGateway.from_settings(settings),
    )


def _build_http_json_provider(settings: Settings) -> ResolverProvider:
    api_key = (
        settings.ai_api_key.get_secret_value()
        if settings.ai_api_key is not None
        else None
    )
    return HttpJsonResolverProvider(
        endpoint=settings.ai_endpoint or "",
        model_name=settings.ai_model,
        timeout_seconds=settings.ai_timeout_seconds,
        api_key=api_key,
        gateway=SecureAIGateway.from_settings(settings),
    )


_FACTORY_LOCK = threading.Lock()
_FACTORIES: dict[tuple[Any, ...], ExecutorFactory | None] = {}


def get_configured_resolution_executor_factory(
    settings: Settings,
) -> ExecutorFactory | None:
    """Return the process-shared runtime factory used by API and batch paths."""

    key = (
        settings.ai_escalation_enabled,
        settings.ai_provider,
        settings.ai_model,
        settings.ai_endpoint,
        (
            settings.ai_api_key.get_secret_value()
            if settings.ai_api_key is not None
            else None
        ),
        settings.ai_confidence_threshold,
        settings.ai_timeout_seconds,
        settings.ai_max_calls_per_case,
        settings.ai_max_concurrent_calls,
        settings.ai_resolver_version,
        settings.ai_prompt_schema_version,
        settings.enterprise_privacy_mode,
        settings.ai_gateway_allowed_providers,
        settings.ai_gateway_allowed_models,
        settings.ai_gateway_allowed_endpoint_hosts,
        settings.ai_gateway_max_payload_bytes,
        settings.retry_max_attempts,
        settings.retry_backoff_seconds,
    )
    with _FACTORY_LOCK:
        if key not in _FACTORIES:
            _FACTORIES[key] = build_resolution_executor_factory(settings)
        return _FACTORIES[key]
