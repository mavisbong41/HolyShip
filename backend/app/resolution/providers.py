from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict
from typing import Protocol

from backend.app.resolution.models import (
    ExtractionResolutionRequest,
    ProviderResolution,
    SemanticResolutionRequest,
)


class ResolverProvider(Protocol):
    def resolve(
        self,
        request: ExtractionResolutionRequest | SemanticResolutionRequest,
    ) -> ProviderResolution: ...


class TransientResolverError(RuntimeError):
    """Provider failure that may recover within the configured retry budget."""


class DisabledResolverProvider:
    """Safe provider used when no external resolver is configured."""

    def resolve(self, request):  # pragma: no cover - executor bypasses disabled providers
        raise RuntimeError("AI resolver provider is not configured")


class HttpJsonResolverProvider:
    """Minimal vendor-neutral HTTP boundary for structured resolver services."""

    def __init__(
        self,
        *,
        endpoint: str,
        model_name: str,
        timeout_seconds: float,
        api_key: str | None = None,
    ) -> None:
        if not endpoint.strip():
            raise ValueError("AI_ENDPOINT is required for the http_json provider")
        self.endpoint = endpoint
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key

    def resolve(self, request):
        requests = getattr(request, "requests", None)
        if requests is None:
            payload = self._request_payload(request)
        else:
            payload = {
                "purpose": "EXTRACTION_BATCH",
                "model": self.model_name,
                "requests": [self._request_payload(item) for item in requests],
            }
        body = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        http_request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in {408, 425, 429} or exc.code >= 500:
                raise TransientResolverError(f"resolver HTTP {exc.code}") from exc
            raise RuntimeError(f"resolver HTTP {exc.code}") from exc
        except (TimeoutError, ConnectionError, urllib.error.URLError) as exc:
            raise TransientResolverError("resolver transport failure") from exc

        if requests is not None:
            items = decoded.get("results") if isinstance(decoded, dict) else decoded
            if not isinstance(items, list):
                return decoded
            return [self._parse_resolution(item) for item in items]
        return self._parse_resolution(decoded)

    def _request_payload(self, request) -> dict:
        purpose = (
            "EXTRACTION"
            if isinstance(request, ExtractionResolutionRequest)
            else "SEMANTIC"
        )
        return {
            "purpose": purpose,
            "model": self.model_name,
            "request": json.loads(json.dumps(asdict(request), default=str)),
        }

    @staticmethod
    def _parse_resolution(payload):
        if not isinstance(payload, dict):
            return payload
        try:
            return ProviderResolution(
                field=payload["field"],
                value=payload.get("value"),
                normalized_value=payload.get("normalized_value"),
                equivalent=payload.get("equivalent"),
                confidence=payload["confidence"],
                evidence=payload["evidence"],
                reasoning_code=payload["reasoning_code"],
            )
        except (KeyError, TypeError, ValueError):
            return payload
