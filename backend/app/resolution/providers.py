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


class GeminiResolverProvider:
    """Direct provider connecting to Google Gemini REST API for targeted resolution."""

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str = "gemini-2.5-flash",
        timeout_seconds: float = 15.0,
        endpoint: str | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("API key is required for the gemini provider")
        self.api_key = api_key
        self.model_name = model_name or "gemini-2.5-flash"
        self.timeout_seconds = timeout_seconds
        self.endpoint = endpoint

    def resolve(
        self,
        request: ExtractionResolutionRequest | SemanticResolutionRequest,
    ) -> ProviderResolution:
        if isinstance(request, ExtractionResolutionRequest):
            prompt = (
                f"You are a shipping document extraction resolver.\n"
                f"Document role: {request.document_role}\n"
                f"Target canonical field: {request.field.value}\n"
                f"Escalation reason: {request.escalation_reason}\n"
                f"Evidence text:\n{request.evidence}\n\n"
                f"Extract the exact value for field '{request.field.value}' from the evidence text.\n"
                f"Output strictly a JSON object with keys:\n"
                f'{{"field": "{request.field.value}", "value": "<extracted string>", "normalized_value": <normalized value or null>, "confidence": <float 0.0-1.0>, "evidence": "<quote>", "reasoning_code": "GEMINI_EXTRACTION"}}'
            )
        else:
            prompt = (
                f"You are a shipping document semantic comparison resolver.\n"
                f"Target canonical field: {request.field.value}\n"
                f"SI reference value: {request.si_value}\n"
                f"BL document value: {request.bl_value}\n"
                f"SI evidence:\n{request.si_evidence}\n"
                f"BL evidence:\n{request.bl_evidence}\n\n"
                f"Determine if the SI value and BL value are semantically equivalent.\n"
                f"Output strictly a JSON object with keys:\n"
                f'{{"field": "{request.field.value}", "equivalent": <true or false>, "confidence": <float 0.0-1.0>, "evidence": "<explanation>", "reasoning_code": "GEMINI_SEMANTIC"}}'
            )

        base_url = self.endpoint or "https://generativelanguage.googleapis.com/v1beta/models"
        import urllib.parse
        url = f"{base_url}/{self.model_name}:generateContent?key={urllib.parse.quote(self.api_key)}"

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.0,
                "maxOutputTokens": 1024,
            },
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}
        http_request = urllib.request.Request(url, data=body, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(http_request, timeout=self.timeout_seconds) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in {408, 425, 429} or exc.code >= 500:
                raise TransientResolverError(f"Gemini HTTP {exc.code}") from exc
            raise RuntimeError(f"Gemini HTTP {exc.code}") from exc
        except (TimeoutError, ConnectionError, urllib.error.URLError) as exc:
            raise TransientResolverError("Gemini transport failure") from exc

        try:
            raw_text = decoded["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(raw_text)
            return ProviderResolution(
                field=parsed["field"],
                value=parsed.get("value"),
                normalized_value=parsed.get("normalized_value"),
                equivalent=parsed.get("equivalent"),
                confidence=float(parsed["confidence"]),
                evidence=str(parsed.get("evidence", "")),
                reasoning_code=str(parsed.get("reasoning_code", "GEMINI")),
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to parse Gemini response: {exc}") from exc
