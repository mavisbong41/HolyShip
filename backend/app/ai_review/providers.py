from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Protocol

from backend.app.core.config import Settings
from backend.app.security.ai_gateway import (
    AIGatewayHTTPError,
    AIGatewayPolicyError,
    AIGatewayTransportError,
    PURPOSE_HUMAN_REVIEW,
    SecureAIGateway,
)

SYSTEM_INSTRUCTION = """You are the HolyShip AI Review Assistant for Shipping Document Verification.
Your mission is to explain shipping document verification discrepancies and suggest field corrections ONLY when firmly grounded in provided document evidence.

CORE INVARIANTS:
1. Grounding: You must base all explanations and suggestions strictly on the provided case context (email, Shipping Instruction (SI), Draft Bill of Lading (BL), and extracted fields). Do not invent or hallucinate data.
2. Terminology: Use user-friendly, professional shipping terminology (Shipper, Consignee, Notify Party, Port of Loading, Port of Discharge, Container Count, Gross Weight KG).
3. Modes:
   - "ACTIONABLE_SUGGESTION": Use ONLY when there is clear evidence of an OCR error, character confusion (e.g. 'O' vs '0'), or direct evidence in the source document text that supports a concrete field override.
   - "EXPLANATION_ONLY": Use when answering questions about why a case is blocked, explaining mismatches, summarizing the case, or when human judgment is needed.
   - "INSUFFICIENT_EVIDENCE": Use when documents are missing, unreadable, or context is insufficient to answer.
4. Allowed Actionable Fields (must be one of these 7 if suggestion is provided):
   - "shipper", "consignee", "notify_party", "port_of_loading", "port_of_discharge", "container_count", "gross_weight_kg"
5. Allowed Document Sides: "SI" or "BL"
6. Output Format: You MUST output strictly valid JSON matching this schema:
{
  "message": "Clear explanation grounded in evidence.",
  "mode": "EXPLANATION_ONLY" | "ACTIONABLE_SUGGESTION" | "INSUFFICIENT_EVIDENCE",
  "suggestion": null | {
    "action": "FIELD_OVERRIDE",
    "document_side": "SI" | "BL",
    "field": "shipper" | "consignee" | "notify_party" | "port_of_loading" | "port_of_discharge" | "container_count" | "gross_weight_kg",
    "current_value": "string",
    "suggested_value": "string",
    "confidence": float between 0.0 and 1.0,
    "reason": "Clear explanation of why this override is suggested",
    "evidence_refs": ["Quote or reference from document"]
  }
}
Do not include any prose or markdown fences outside the JSON object."""


class AIReviewProvider(Protocol):
    def generate_review_response(
        self,
        context: dict[str, Any],
        question: str,
    ) -> tuple[str, str, str]:
        """Generate raw JSON response string, provider name, and model name."""
        ...


class DisabledProvider:
    """Safe provider used when external AI is disabled or not configured."""

    def __init__(self, provider_name: str = "disabled", model_name: str = "none"):
        self.provider_name = provider_name
        self.model_name = model_name
        self.last_audit_metadata: dict[str, Any] = {}

    def generate_review_response(
        self,
        context: dict[str, Any],
        question: str,
    ) -> tuple[str, str, str]:
        payload = {
            "message": "AI Review Assistant is currently disabled in backend configuration. To enable live AI explanations and grounded suggestions, configure AI_REVIEW_ENABLED=true and a provider API key (e.g. Gemini, OpenAI, or HTTP endpoint) in your environment.",
            "mode": "INSUFFICIENT_EVIDENCE",
            "suggestion": None,
        }
        return json.dumps(payload), self.provider_name, self.model_name


class MockAIReviewProvider:
    """Configurable mock provider used for testing without live API network calls."""

    def __init__(
        self,
        response_json: str | dict[str, Any] | None = None,
        provider_name: str = "mock",
        model_name: str = "mock-model",
    ):
        self.response_json = response_json
        self.provider_name = provider_name
        self.model_name = model_name
        self.last_audit_metadata: dict[str, Any] = {}

    def generate_review_response(
        self,
        context: dict[str, Any],
        question: str,
    ) -> tuple[str, str, str]:
        if self.response_json is None:
            default_payload = {
                "message": f"Mock response for question: {question}",
                "mode": "EXPLANATION_ONLY",
                "suggestion": None,
            }
            return json.dumps(default_payload), self.provider_name, self.model_name
        if isinstance(self.response_json, dict):
            return json.dumps(self.response_json), self.provider_name, self.model_name
        return str(self.response_json), self.provider_name, self.model_name


class GeminiProvider:
    """Real API provider connecting to Google Gemini REST API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        endpoint: str | None = None,
        timeout_seconds: float = 15.0,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        gateway: SecureAIGateway | None = None,
    ):
        self.api_key = api_key
        self.model = model or "gemini-2.5-flash"
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.provider_name = "gemini"
        self.gateway = gateway or SecureAIGateway()
        self.last_audit_metadata: dict[str, Any] = {}

    def generate_review_response(
        self,
        context: dict[str, Any],
        question: str,
    ) -> tuple[str, str, str]:
        try:
            result = self.gateway.invoke_gemini_json(
                api_key=self.api_key,
                model=self.model,
                purpose=PURPOSE_HUMAN_REVIEW,
                feature="human_review_assistant",
                data={"context": context, "question": question},
                system_instruction=SYSTEM_INSTRUCTION,
                timeout_seconds=self.timeout_seconds,
                endpoint=self.endpoint,
                temperature=self.temperature,
                max_output_tokens=self.max_tokens,
            )
            self.last_audit_metadata = result.audit_metadata
            return (
                json.dumps(result.structured_response),
                self.provider_name,
                self.model,
            )
        except AIGatewayHTTPError as exc:
            self.last_audit_metadata = {
                "purpose": PURPOSE_HUMAN_REVIEW,
                "feature": "human_review_assistant",
                "provider": "gemini",
                "model": self.model,
                "privacy_mode": self.gateway.enterprise_privacy_mode,
                "request_status": "REJECTED_BY_PROVIDER",
                "response_status": f"HTTP_{exc.status_code}",
            }
            error_payload = {
                "message": f"Gemini API error (HTTP {exc.status_code}).",
                "mode": "INSUFFICIENT_EVIDENCE",
                "suggestion": None,
            }
            return json.dumps(error_payload), self.provider_name, self.model
        except (AIGatewayPolicyError, AIGatewayTransportError) as exc:
            self.last_audit_metadata = {
                "purpose": PURPOSE_HUMAN_REVIEW,
                "feature": "human_review_assistant",
                "provider": "gemini",
                "model": self.model,
                "privacy_mode": self.gateway.enterprise_privacy_mode,
                "request_status": "BLOCKED" if isinstance(exc, AIGatewayPolicyError) else "FAILED",
                "response_status": type(exc).__name__,
            }
            error_payload = {
                "message": f"Gemini API request failed: {str(exc)}",
                "mode": "INSUFFICIENT_EVIDENCE",
                "suggestion": None,
            }
            return json.dumps(error_payload), self.provider_name, self.model


class OpenAIProvider:
    """Real API provider connecting to OpenAI or OpenAI-compatible Chat Completions API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        endpoint: str | None = None,
        timeout_seconds: float = 15.0,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        provider_name: str = "openai",
        gateway: SecureAIGateway | None = None,
    ):
        self.api_key = api_key
        self.model = model or "gpt-4o-mini"
        self.endpoint = endpoint or "https://api.openai.com/v1/chat/completions"
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.provider_name = provider_name
        self.gateway = gateway or SecureAIGateway()
        self.last_audit_metadata: dict[str, Any] = {}

    def generate_review_response(
        self,
        context: dict[str, Any],
        question: str,
    ) -> tuple[str, str, str]:
        try:
            minimized, audit = self.gateway.prepare_payload(
                purpose=PURPOSE_HUMAN_REVIEW,
                data={"context": context, "question": question},
                feature="human_review_assistant",
                model=self.model,
                provider=self.provider_name,
                endpoint=self.endpoint,
            )
        except AIGatewayPolicyError:
            self.last_audit_metadata = {
                "purpose": PURPOSE_HUMAN_REVIEW,
                "feature": "human_review_assistant",
                "provider": self.provider_name,
                "model": self.model,
                "privacy_mode": self.gateway.enterprise_privacy_mode,
                "request_status": "BLOCKED_BY_POLICY",
                "response_status": "NOT_SENT",
            }
            return (
                json.dumps(
                    {
                        "message": "AI request was blocked by Enterprise Privacy Mode.",
                        "mode": "INSUFFICIENT_EVIDENCE",
                        "suggestion": None,
                    }
                ),
                self.provider_name,
                self.model,
            )
        self.last_audit_metadata = {
            **audit,
            "request_status": "SENT",
        }
        user_prompt = (
            "MINIMIZED CASE INPUT:\n"
            + json.dumps(minimized, indent=2, default=str)
        )

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        body_bytes = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = urllib.request.Request(self.endpoint, data=body_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                choices = resp_data.get("choices", [])
                self.last_audit_metadata = {
                    **self.last_audit_metadata,
                    "response_status": "RECEIVED",
                }
                if choices and "message" in choices[0]:
                    content = choices[0]["message"].get("content", "")
                    return content, self.provider_name, self.model
                return json.dumps(resp_data), self.provider_name, self.model
        except urllib.error.HTTPError as exc:
            self.last_audit_metadata = {
                **self.last_audit_metadata,
                "response_status": f"HTTP_{exc.code}",
            }
            err_msg = f"OpenAI API error (HTTP {exc.code})."
            error_payload = {
                "message": err_msg,
                "mode": "INSUFFICIENT_EVIDENCE",
                "suggestion": None,
            }
            return json.dumps(error_payload), self.provider_name, self.model
        except Exception as exc:
            self.last_audit_metadata = {
                **self.last_audit_metadata,
                "response_status": type(exc).__name__,
            }
            error_payload = {
                "message": "OpenAI API request failed.",
                "mode": "INSUFFICIENT_EVIDENCE",
                "suggestion": None,
            }
            return json.dumps(error_payload), self.provider_name, self.model


class HTTPProvider(OpenAIProvider):
    """Generic config-driven HTTP provider for external OpenAI-compatible endpoints."""

    def __init__(
        self,
        endpoint: str,
        api_key: str | None,
        model: str,
        timeout_seconds: float = 15.0,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        provider_name: str = "http",
        gateway: SecureAIGateway | None = None,
    ):
        super().__init__(
            api_key=api_key,
            model=model,
            endpoint=endpoint,
            timeout_seconds=timeout_seconds,
            temperature=temperature,
            max_tokens=max_tokens,
            provider_name=provider_name,
            gateway=gateway,
        )


def get_ai_review_provider(settings: Settings) -> AIReviewProvider:
    """Factory resolving configured real API provider from settings and environment."""
    provider_name = (settings.ai_review_provider or "").lower().strip()

    # Check explicit disabled flag
    if provider_name == "disabled" and not settings.ai_review_enabled:
        return DisabledProvider()

    # Extract available API keys
    api_key_str: str | None = None
    if settings.ai_review_api_key:
        api_key_str = settings.ai_review_api_key.get_secret_value()
    elif settings.gemini_api_key:
        api_key_str = settings.gemini_api_key.get_secret_value()
    elif settings.openai_api_key:
        api_key_str = settings.openai_api_key.get_secret_value()
    elif settings.ai_api_key:
        api_key_str = settings.ai_api_key.get_secret_value()
    else:
        api_key_str = (
            os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("AI_API_KEY")
            or os.environ.get("AI_REVIEW_API_KEY")
        )

    model_name = settings.ai_review_model if settings.ai_review_model and settings.ai_review_model != "none" else (settings.ai_model if settings.ai_model != "none" else "")
    endpoint = settings.ai_review_endpoint or settings.ai_endpoint
    gateway = SecureAIGateway.from_settings(settings)

    # Auto-resolve provider type if not explicitly set
    if not provider_name or provider_name in ("auto", "none", "disabled"):
        if endpoint and ("openai" in endpoint or "chat/completions" in endpoint):
            provider_name = "openai"
        elif "gemini" in model_name.lower() or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            provider_name = "gemini"
        elif "gpt" in model_name.lower() or os.environ.get("OPENAI_API_KEY"):
            provider_name = "openai"
        elif api_key_str:
            # Default to Gemini if API key available and no other provider specified
            provider_name = "gemini"
        else:
            return DisabledProvider()

    if provider_name == "gemini":
        model = model_name or "gemini-2.5-flash"
        return GeminiProvider(
            api_key=api_key_str or "",
            model=model,
            endpoint=endpoint,
            timeout_seconds=settings.ai_review_timeout_seconds,
            temperature=settings.ai_review_temperature,
            max_tokens=settings.ai_review_max_tokens,
            gateway=gateway,
        )

    if provider_name in ("openai", "azure_openai"):
        model = model_name or "gpt-4o-mini"
        return OpenAIProvider(
            api_key=api_key_str,
            model=model,
            endpoint=endpoint or "https://api.openai.com/v1/chat/completions",
            timeout_seconds=settings.ai_review_timeout_seconds,
            temperature=settings.ai_review_temperature,
            max_tokens=settings.ai_review_max_tokens,
            provider_name=provider_name,
            gateway=gateway,
        )

    if provider_name in ("http", "http_json", "custom"):
        return HTTPProvider(
            endpoint=endpoint or "http://localhost:8000/v1/chat/completions",
            api_key=api_key_str,
            model=model_name or "default",
            timeout_seconds=settings.ai_review_timeout_seconds,
            temperature=settings.ai_review_temperature,
            max_tokens=settings.ai_review_max_tokens,
            provider_name=provider_name,
            gateway=gateway,
        )

    return DisabledProvider(provider_name=provider_name, model_name=model_name or "none")
