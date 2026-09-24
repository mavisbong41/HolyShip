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
from backend.app.security.ai_gateway import (
    AIGatewayHTTPError,
    AIGatewayPolicyError,
    AIGatewayTransportError,
    PURPOSE_FIELD_EXTRACTION,
    PURPOSE_FIELD_SEMANTIC_COMPARISON,
    SecureAIGateway,
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
    """Gemini resolver routed exclusively through the Secure AI Gateway."""

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str = "gemini-2.5-flash",
        timeout_seconds: float = 15.0,
        endpoint: str | None = None,
        gateway: SecureAIGateway | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("API key is required for the gemini provider")
        self.api_key = api_key
        self.model_name = model_name or "gemini-2.5-flash"
        self.timeout_seconds = timeout_seconds
        self.endpoint = endpoint
        self.gateway = gateway or SecureAIGateway()

    def resolve(
        self,
        request: ExtractionResolutionRequest | SemanticResolutionRequest,
    ) -> ProviderResolution:
        if isinstance(request, ExtractionResolutionRequest):
            purpose = PURPOSE_FIELD_EXTRACTION
            feature = "l2_extraction_resolution"
            data = {
                "field": request.field.value,
                "document_role": request.document_role,
                "evidence": request.evidence,
                "escalation_reason": request.escalation_reason,
            }
            instruction = (
                "Resolve one shipping-document extraction field strictly from the provided "
                "field evidence. Return JSON with field, value, normalized_value, confidence, "
                "evidence, and reasoning_code. Evidence must quote the supplied field evidence."
            )
        elif isinstance(request, SemanticResolutionRequest):
            purpose = PURPOSE_FIELD_SEMANTIC_COMPARISON
            feature = "l2_semantic_comparison"
            data = {
                "field": request.field.value,
                "si_value": request.si_value,
                "bl_value": request.bl_value,
                "si_evidence": request.si_evidence,
                "bl_evidence": request.bl_evidence,
            }
            instruction = (
                "Compare exactly one canonical shipping field. Determine whether the supplied "
                "SI reference value and BL value are semantically equivalent. Return JSON with "
                "field, equivalent, confidence, evidence, and reasoning_code. The evidence text "
                "must mention both supplied values."
            )
        else:
            raise TypeError(
                "Gemini resolver accepts only single extraction or semantic requests"
            )

        try:
            result = self.gateway.invoke_gemini_json(
                api_key=self.api_key,
                model=self.model_name,
                purpose=purpose,
                feature=feature,
                data=data,
                system_instruction=instruction,
                timeout_seconds=self.timeout_seconds,
                endpoint=self.endpoint,
                temperature=0.0,
                max_output_tokens=1024,
            )
        except AIGatewayHTTPError as exc:
            if exc.status_code in {408, 425, 429} or exc.status_code >= 500:
                raise TransientResolverError(
                    f"Gemini HTTP {exc.status_code}"
                ) from exc
            raise RuntimeError(f"Gemini HTTP {exc.status_code}") from exc
        except AIGatewayTransportError as exc:
            raise TransientResolverError("Gemini transport failure") from exc
        except AIGatewayPolicyError as exc:
            raise RuntimeError(
                f"Gemini gateway policy rejected request: {exc}"
            ) from exc

        parsed = result.structured_response
        try:
            return ProviderResolution(
                field=parsed["field"],
                value=parsed.get("value"),
                normalized_value=parsed.get("normalized_value"),
                equivalent=parsed.get("equivalent"),
                confidence=float(parsed["confidence"]),
                evidence=str(parsed.get("evidence", "")),
                reasoning_code=str(parsed.get("reasoning_code", "GEMINI")),
                audit_metadata=result.audit_metadata,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to parse Gemini response: {exc}"
            ) from exc
