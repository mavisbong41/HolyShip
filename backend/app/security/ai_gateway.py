from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from backend.app.core.config import Settings


PURPOSE_FIELD_EXTRACTION = "FIELD_EXTRACTION"
PURPOSE_FIELD_SEMANTIC_COMPARISON = "FIELD_SEMANTIC_COMPARISON"
PURPOSE_HUMAN_REVIEW = "HUMAN_REVIEW"

_ALLOWED_PURPOSES = frozenset(
    {
        PURPOSE_FIELD_EXTRACTION,
        PURPOSE_FIELD_SEMANTIC_COMPARISON,
        PURPOSE_HUMAN_REVIEW,
    }
)

_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(api[_-]?key|authorization|bearer|token|password)\s*[:=]\s*[^\s,;]+"
)


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
        max_payload_bytes: int = 65536,
    ) -> None:
        if max_payload_bytes < 1024:
            raise ValueError("max_payload_bytes must be at least 1024")
        self.enterprise_privacy_mode = enterprise_privacy_mode
        self.max_payload_bytes = max_payload_bytes

    @classmethod
    def from_settings(cls, settings: Settings) -> "SecureAIGateway":
        return cls(
            enterprise_privacy_mode=settings.enterprise_privacy_mode,
            max_payload_bytes=settings.ai_gateway_max_payload_bytes,
        )

    def prepare_payload(
        self,
        *,
        purpose: str,
        data: dict[str, Any],
        feature: str,
        model: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if purpose not in _ALLOWED_PURPOSES:
            raise AIGatewayPolicyError(f"Unsupported AI purpose: {purpose}")
        if not isinstance(data, dict):
            raise AIGatewayPolicyError("AI gateway input must be a mapping")

        if purpose == PURPOSE_FIELD_EXTRACTION:
            minimized = self._minimize_field_extraction(data)
        elif purpose == PURPOSE_FIELD_SEMANTIC_COMPARISON:
            minimized = self._minimize_semantic_comparison(data)
        else:
            minimized = self._minimize_human_review(data)

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
            "provider": "gemini",
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

        minimized, audit = self.prepare_payload(
            purpose=purpose,
            data=data,
            feature=feature,
            model=model,
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
            self._gemini_url(endpoint, model),
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
