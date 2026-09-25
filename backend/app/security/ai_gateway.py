from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from dataclasses import dataclass
from typing import Any

from backend.app.core.config import Settings


PURPOSE_FIELD_EXTRACTION = "FIELD_EXTRACTION"
PURPOSE_FIELD_SEMANTIC_COMPARISON = "FIELD_SEMANTIC_COMPARISON"
PURPOSE_HUMAN_REVIEW = "HUMAN_REVIEW"
PURPOSE_REPLY_SUMMARY = "REPLY_SUMMARY"
PURPOSE_REPLY_DRAFT = "REPLY_DRAFT"
PURPOSE_REPLY_REFINE = "REPLY_REFINE"

_ALLOWED_PURPOSES = frozenset(
    {
        PURPOSE_FIELD_EXTRACTION,
        PURPOSE_FIELD_SEMANTIC_COMPARISON,
        PURPOSE_HUMAN_REVIEW,
        PURPOSE_REPLY_SUMMARY,
        PURPOSE_REPLY_DRAFT,
        PURPOSE_REPLY_REFINE,
    }
)

_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_ -]?key|authorization|access[_ -]?token|refresh[_ -]?token|"
    r"client[_ -]?secret|token|password|secret)\s*[:=]\s*(?:bearer\s+)?[^\s,;]+"
)
_BEARER_TOKEN_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")


class AIGatewayPolicyError(RuntimeError):
    """The requested AI operation violates HolyShip disclosure policy."""


class AIGatewayTransportError(RuntimeError):
    """The approved AI provider could not be reached safely."""


class AIGatewayHTTPError(RuntimeError):
    """The approved AI provider rejected the request."""

    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"AI provider HTTP {status_code}")


@dataclass(frozen=True)
class AIGatewayResult:
    structured_response: dict[str, Any]
    audit_metadata: dict[str, Any]


class SecureAIGateway:
    """Single policy boundary for Gemini disclosure and transport.

    The gateway accepts purpose-specific structured inputs, minimizes them,
    strips unnecessary identifiers, enforces payload limits, performs the
    Gemini call, validates JSON output, and returns audit metadata that never
    contains the raw prompt/payload.
    """

    def __init__(
        self,
        *,
        enterprise_privacy_mode: bool = True,
        allowed_providers: set[str] | frozenset[str] | None = None,
        allowed_models: set[str] | frozenset[str] | None = None,
        allowed_endpoint_hosts: set[str] | frozenset[str] | None = None,
        max_payload_bytes: int = 65536,
    ) -> None:
        if max_payload_bytes < 1024:
            raise ValueError("max_payload_bytes must be at least 1024")
        self.enterprise_privacy_mode = enterprise_privacy_mode
        provider_source = {"gemini", "google"} if allowed_providers is None else allowed_providers
        model_source = set() if allowed_models is None else allowed_models
        endpoint_source = (
            {"generativelanguage.googleapis.com"}
            if allowed_endpoint_hosts is None
            else allowed_endpoint_hosts
        )
        self.allowed_providers = {
            value.strip().lower()
            for value in provider_source
            if value and value.strip()
        }
        self.allowed_models = {
            value.strip()
            for value in model_source
            if value and value.strip()
        }
        self.allowed_endpoint_hosts = {
            value.strip().lower()
            for value in endpoint_source
            if value and value.strip()
        }
        self.max_payload_bytes = max_payload_bytes

    @classmethod
    def from_settings(cls, settings: Settings) -> "SecureAIGateway":
        return cls(
            enterprise_privacy_mode=settings.enterprise_privacy_mode,
            allowed_providers={
                value.strip()
                for value in settings.ai_gateway_allowed_providers.split(",")
                if value.strip()
            },
            allowed_models={
                value.strip()
                for value in settings.ai_gateway_allowed_models.split(",")
                if value.strip()
            },
            allowed_endpoint_hosts={
                value.strip()
                for value in settings.ai_gateway_allowed_endpoint_hosts.split(",")
                if value.strip()
            },
            max_payload_bytes=settings.ai_gateway_max_payload_bytes,
        )

    def prepare_payload(
        self,
        *,
        purpose: str,
        data: dict[str, Any],
        feature: str,
        model: str,
        provider: str = "gemini",
        endpoint: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if purpose not in _ALLOWED_PURPOSES:
            raise AIGatewayPolicyError(f"Unsupported AI purpose: {purpose}")
        if not isinstance(data, dict):
            raise AIGatewayPolicyError("AI gateway input must be a mapping")
        self.enforce_provider_policy(
            provider=provider,
            model=model,
            endpoint=endpoint,
        )

        if purpose == PURPOSE_FIELD_EXTRACTION:
            minimized = self._minimize_field_extraction(data)
        elif purpose == PURPOSE_FIELD_SEMANTIC_COMPARISON:
            minimized = self._minimize_semantic_comparison(data)
        elif purpose == PURPOSE_HUMAN_REVIEW:
            minimized = self._minimize_human_review(data)
        else:
            minimized = self._minimize_reply(purpose, data)

        minimized = self._sanitize(minimized)
        encoded = json.dumps(
            minimized,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        if len(encoded) > self.max_payload_bytes:
            raise AIGatewayPolicyError(
                f"AI gateway payload exceeds {self.max_payload_bytes} bytes"
            )

        audit = {
            "purpose": purpose,
            "feature": feature,
            "provider": provider,
            "model": model,
            "privacy_mode": self.enterprise_privacy_mode,
            "payload_sha256": hashlib.sha256(encoded).hexdigest(),
            "payload_bytes": len(encoded),
            "disclosed_fields": self._disclosed_fields(purpose, minimized),
            "disclosure_categories": self._disclosure_categories(purpose, minimized),
        }
        return minimized, audit

    def invoke_gemini_json(
        self,
        *,
        api_key: str,
        model: str,
        purpose: str,
        feature: str,
        data: dict[str, Any],
        system_instruction: str,
        timeout_seconds: float,
        endpoint: str | None = None,
        temperature: float = 0.0,
        max_output_tokens: int = 1024,
    ) -> AIGatewayResult:
        if not api_key or not api_key.strip():
            raise AIGatewayPolicyError("Gemini API key is required")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        resolved_endpoint = self._gemini_url(endpoint, model)
        minimized, audit = self.prepare_payload(
            purpose=purpose,
            data=data,
            feature=feature,
            model=model,
            provider="gemini",
            endpoint=resolved_endpoint,
        )

        request_payload: dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                "TASK INPUT (already minimized by HolyShip Secure AI Gateway):\n"
                                + json.dumps(minimized, ensure_ascii=False, default=str)
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens,
            },
        }
        if system_instruction.strip():
            request_payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        body = json.dumps(request_payload, default=str).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }
        request = urllib.request.Request(
            resolved_endpoint,
            data=body,
            headers=headers,
            method="POST",
        )

        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                response_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise AIGatewayHTTPError(exc.code) from exc
        except (TimeoutError, ConnectionError, urllib.error.URLError) as exc:
            raise AIGatewayTransportError("Gemini transport failure") from exc

        latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
        try:
            provider_payload = json.loads(response_body)
            raw_text = provider_payload["candidates"][0]["content"]["parts"][0]["text"]
            structured = json.loads(raw_text)
            if not isinstance(structured, dict):
                raise TypeError("Gemini structured response must be a JSON object")
        except Exception as exc:
            raise AIGatewayTransportError("Gemini response validation failed") from exc

        return AIGatewayResult(
            structured_response=structured,
            audit_metadata={
                **audit,
                "request_status": "SENT",
                "response_status": "VALIDATED",
                "latency_ms": latency_ms,
            },
        )

    def enforce_provider_policy(
        self,
        *,
        provider: str,
        model: str,
        endpoint: str | None = None,
    ) -> None:
        """Fail closed on unapproved external AI destinations in privacy mode."""
        if not self.enterprise_privacy_mode:
            return
        normalized_provider = (provider or "").strip().lower()
        if normalized_provider not in self.allowed_providers:
            raise AIGatewayPolicyError(
                f"AI provider {provider!r} is not approved by Enterprise Privacy Mode"
            )
        if self.allowed_models and model not in self.allowed_models:
            raise AIGatewayPolicyError(
                f"AI model {model!r} is not approved by Enterprise Privacy Mode"
            )
        if endpoint:
            parsed = urlparse(endpoint)
            scheme = (parsed.scheme or "").strip().lower()
            host = (parsed.hostname or "").strip().lower()
            if scheme != "https":
                raise AIGatewayPolicyError(
                    "AI endpoint must use HTTPS while Enterprise Privacy Mode is active"
                )
            if not host or host not in self.allowed_endpoint_hosts:
                raise AIGatewayPolicyError(
                    f"AI endpoint host {host or '<missing>'!r} is not approved by Enterprise Privacy Mode"
                )
            if (
                host == "generativelanguage.googleapis.com"
                and normalized_provider not in {"gemini", "google"}
            ):
                raise AIGatewayPolicyError(
                    "Google Gemini endpoint may only be used by the Gemini gateway provider"
                )

    def _minimize_field_extraction(self, data: dict[str, Any]) -> dict[str, Any]:
        batch = data.get("requests")
        if isinstance(batch, list):
            minimized_batch = []
            for item in batch:
                if not isinstance(item, dict):
                    raise AIGatewayPolicyError(
                        "Field-extraction batch entries must be mappings"
                    )
                minimized_batch.append(
                    {
                        "field": item.get("field"),
                        "document_role": item.get("document_role"),
                        "evidence": item.get("evidence"),
                        "escalation_reason": item.get("escalation_reason"),
                    }
                )
            if not minimized_batch:
                raise AIGatewayPolicyError(
                    "Field-extraction batch must contain at least one request"
                )
            return {"requests": minimized_batch}
        return {
            "field": data.get("field"),
            "document_role": data.get("document_role"),
            "evidence": data.get("evidence"),
            "escalation_reason": data.get("escalation_reason"),
        }

    def _minimize_semantic_comparison(self, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "field": data.get("field"),
            "si_value": data.get("si_value"),
            "bl_value": data.get("bl_value"),
            "si_evidence": data.get("si_evidence"),
            "bl_evidence": data.get("bl_evidence"),
        }

    def _minimize_human_review(self, data: dict[str, Any]) -> dict[str, Any]:
        context = data.get("context")
        if not isinstance(context, dict):
            context = {}
        question = data.get("question")
        if not isinstance(question, str):
            question = ""

        affected_fields = [
            str(field)
            for field in (context.get("affected_fields") or [])
            if isinstance(field, str) and field
        ]
        affected_set = set(affected_fields)

        documents = []
        for item in context.get("documents") or []:
            if not isinstance(item, dict):
                continue
            documents.append(
                {
                    "role": item.get("role"),
                    "format": item.get("format"),
                    "validation_outcome": item.get("validation_outcome"),
                    "read_status": item.get("read_status"),
                    "routing_outcome": item.get("routing_outcome"),
                }
            )

        comparison_source = context.get("comparison")
        comparison = None
        if isinstance(comparison_source, dict):
            fields = []
            for item in comparison_source.get("fields") or []:
                if not isinstance(item, dict):
                    continue
                field_name = item.get("field")
                if not affected_set or field_name not in affected_set:
                    continue
                fields.append(
                    {
                        "field": field_name,
                        "status": item.get("status"),
                        "reason_code": item.get("reason_code"),
                        "si_value": item.get("si_value"),
                        "si_canonical": item.get("si_canonical"),
                        "bl_value": item.get("bl_value"),
                        "bl_canonical": item.get("bl_canonical"),
                    }
                )
            comparison = {
                "state": comparison_source.get("state"),
                "mismatch_found": comparison_source.get("mismatch_found"),
                "reason_code": comparison_source.get("reason_code"),
                "mismatched_fields": [
                    field
                    for field in (comparison_source.get("mismatched_fields") or [])
                    if affected_set and field in affected_set
                ],
                "unresolved_fields": [
                    field
                    for field in (comparison_source.get("unresolved_fields") or [])
                    if affected_set and field in affected_set
                ],
                "fields": fields,
            }

        def selected_field_map(key: str) -> dict[str, Any]:
            source = context.get(key)
            if not isinstance(source, dict):
                return {}
            result: dict[str, Any] = {}
            for field_name, value in source.items():
                if affected_set and field_name not in affected_set:
                    continue
                if not affected_set:
                    continue
                if not isinstance(value, dict):
                    continue
                result[str(field_name)] = {
                    "raw_value": value.get("raw_value"),
                    "canonical_value": value.get("canonical_value"),
                    "status": value.get("status"),
                    "confidence": value.get("confidence"),
                }
            return result

        active_overrides = []
        for item in context.get("active_overrides") or []:
            if not isinstance(item, dict):
                continue
            field_name = item.get("field")
            if not affected_set or field_name not in affected_set:
                continue
            active_overrides.append(
                {
                    "document_side": item.get("document_side"),
                    "field": field_name,
                    "corrected_value": item.get("corrected_value"),
                    "corrected_canonical_value": item.get("corrected_canonical_value"),
                }
            )

        return {
            "question": question[:2000],
            "case": {
                "processing_status": context.get("processing_status"),
                "category": context.get("category"),
                "comparison_readiness": context.get("comparison_readiness"),
                "review_status": context.get("review_status"),
                "reason_code": context.get("reason_code"),
                "presentation_title": context.get("presentation_title"),
                "human_explanation": context.get("human_explanation"),
                "affected_area": context.get("affected_area"),
                "affected_fields": affected_fields,
                "documents": documents,
                "comparison": comparison,
                "si_extracted_fields": selected_field_map("si_extracted_fields"),
                "bl_extracted_fields": selected_field_map("bl_extracted_fields"),
                "active_overrides": active_overrides,
            },
        }

    def _minimize_reply(self, purpose: str, data: dict[str, Any]) -> dict[str, Any]:
        key_points = [str(item)[:500] for item in (data.get("key_points") or []) if str(item).strip()][:12]
        if purpose == PURPOSE_REPLY_DRAFT:
            return {"approved_key_points": key_points}
        if purpose == PURPOSE_REPLY_REFINE:
            return {
                "approved_key_points": key_points,
                "draft": str(data.get("draft") or "")[:8000],
                "instruction": str(data.get("instruction") or "")[:1000],
            }
        return {
            "subject": str(data.get("subject") or "")[:500],
            "relevant_message_excerpt": str(data.get("body") or "")[:4000],
            "comparison_state": data.get("comparison_state"),
            "mismatched_fields": list(data.get("mismatched_fields") or [])[:7],
            "unresolved_fields": list(data.get("unresolved_fields") or [])[:7],
        }

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key): self._sanitize(item)
                for key, item in value.items()
                if str(key).lower()
                not in {
                    "sender",
                    "recipients",
                    "email_id",
                    "case_id",
                    "content_hash",
                    "raw_text",
                    "full_document",
                    "attachment_bytes",
                    "recent_events",
                }
            }
        if isinstance(value, list):
            return [self._sanitize(item) for item in value]
        if isinstance(value, tuple):
            return [self._sanitize(item) for item in value]
        if isinstance(value, str):
            sanitized = _SECRET_ASSIGNMENT_RE.sub(r"\1=[REDACTED]", value)
            sanitized = _BEARER_TOKEN_RE.sub("Bearer [REDACTED]", sanitized)
            if self.enterprise_privacy_mode:
                sanitized = _EMAIL_RE.sub("[REDACTED_EMAIL]", sanitized)
            return sanitized
        return value

    @staticmethod
    def _disclosed_fields(purpose: str, payload: dict[str, Any]) -> list[str]:
        if purpose == PURPOSE_FIELD_EXTRACTION:
            batch = payload.get("requests")
            if isinstance(batch, list):
                fields: list[str] = []
                for item in batch:
                    if not isinstance(item, dict):
                        continue
                    field = item.get("field")
                    if field and str(field) not in fields:
                        fields.append(str(field))
                return fields
            field = payload.get("field")
            return [str(field)] if field else []
        if purpose == PURPOSE_FIELD_SEMANTIC_COMPARISON:
            field = payload.get("field")
            return [str(field)] if field else []
        if purpose in {PURPOSE_REPLY_SUMMARY, PURPOSE_REPLY_DRAFT, PURPOSE_REPLY_REFINE}:
            return []
        case = payload.get("case")
        if not isinstance(case, dict):
            return []
        return [
            str(field)
            for field in (case.get("affected_fields") or [])
            if field
        ]

    @staticmethod
    def _disclosure_categories(purpose: str, payload: dict[str, Any]) -> list[str]:
        if purpose == PURPOSE_FIELD_EXTRACTION:
            return ["field_name", "document_role", "field_evidence"]
        if purpose == PURPOSE_FIELD_SEMANTIC_COMPARISON:
            return ["field_name", "si_value", "bl_value", "field_evidence"]
        if purpose == PURPOSE_REPLY_SUMMARY:
            return ["relevant_email_excerpt", "comparison_status"]
        if purpose == PURPOSE_REPLY_DRAFT:
            return ["human_approved_reply_points"]
        if purpose == PURPOSE_REPLY_REFINE:
            return ["human_approved_reply_points", "draft", "refinement_instruction"]

        categories = ["review_reason", "document_metadata", "user_question"]
        case = payload.get("case")
        if isinstance(case, dict) and case.get("affected_fields"):
            categories.extend(["affected_field_values", "comparison_context"])
        if isinstance(case, dict) and case.get("active_overrides"):
            categories.append("active_human_overrides")
        return categories

    @staticmethod
    def _gemini_url(endpoint: str | None, model: str) -> str:
        if endpoint:
            endpoint = endpoint.strip()
            if "{model}" in endpoint:
                return endpoint.format(model=model)
            if ":generateContent" in endpoint:
                return endpoint
            if endpoint.rstrip("/").endswith("/models"):
                return f"{endpoint.rstrip('/')}/{model}:generateContent"
            return endpoint
        return (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
