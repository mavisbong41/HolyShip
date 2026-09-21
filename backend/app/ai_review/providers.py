from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Protocol

from backend.app.core.config import Settings


class AIReviewProvider(Protocol):
    def generate_review_response(
        self,
        context: dict[str, Any],
        question: str,
    ) -> tuple[str, str, str]:
        """Generate raw JSON response string, provider name, and model name."""
        ...


class DisabledProvider:
    """Deterministic, context-grounded provider used when external AI is disabled or offline."""

    def __init__(self, provider_name: str = "disabled", model_name: str = "deterministic_rule_v1"):
        self.provider_name = provider_name
        self.model_name = model_name

    def generate_review_response(
        self,
        context: dict[str, Any],
        question: str,
    ) -> tuple[str, str, str]:
        q_lower = question.lower().strip()
        reason_title = context.get("presentation_title", "Needs review")
        human_explanation = context.get("human_explanation", "")
        affected = context.get("affected_fields", [])
        comparison = context.get("comparison") or {}
        fields = comparison.get("fields", [])

        def _field_matches(name: str) -> bool:
            if not name:
                return False
            vars_ = [
                name,
                name.replace("_", " "),
                name.replace("_kg", ""),
                name.replace("_kg", "").replace("_", " "),
                "weight" if "weight" in name else "",
                "container" if "container" in name else "",
                "loading" if "loading" in name else "",
                "discharge" if "discharge" in name else "",
                "pol" if "loading" in name else "",
                "pod" if "discharge" in name else "",
            ]
            return any(v and v in q_lower for v in vars_)

        # Check for field specific inquiry or OCR suggestion
        for f in fields:
            fname = f.get("field")
            if fname and _field_matches(fname):
                si_val = str(f.get("si_value") or "")
                bl_val = str(f.get("bl_value") or "")
                status = f.get("status")

                # Check for OCR character confusion like O vs 0 in gross weight or numbers
                if fname == "gross_weight_kg" and status == "MISMATCH" and "suggest" in q_lower:
                    cleaned_bl = bl_val.replace("O", "0").replace("o", "0")
                    if cleaned_bl != bl_val:
                        num_match = re.search(r"[\d,.]+", cleaned_bl)
                        if num_match:
                            suggested_clean = num_match.group(0).replace(",", "")
                            payload = {
                                "message": f"The BL gross weight appears to have an OCR error ('O' instead of '0'). Proposed correction is {suggested_clean} kg.",
                                "mode": "ACTIONABLE_SUGGESTION",
                                "suggestion": {
                                    "action": "FIELD_OVERRIDE",
                                    "document_side": "BL",
                                    "field": "gross_weight_kg",
                                    "current_value": bl_val,
                                    "suggested_value": suggested_clean,
                                    "confidence": 0.95,
                                    "reason": "Corrected likely OCR character confusion (O/0)",
                                    "evidence_refs": [f"Draft BL text: '{bl_val}'"],
                                },
                            }
                            return json.dumps(payload), self.provider_name, self.model_name

                # General field explanation
                return json.dumps({
                    "message": f"For {fname.replace('_', ' ').title()}: SI has '{si_val}' and Draft BL has '{bl_val}'. Status is {status}.",
                    "mode": "EXPLANATION_ONLY",
                    "suggestion": None,
                }), self.provider_name, self.model_name

        # Case-level question matching
        if any(w in q_lower for w in ["why", "blocked", "review", "reason"]):
            aff_text = f" Affected fields: {', '.join(affected)}." if affected else ""
            msg = f"This case needs review because: {reason_title}. {human_explanation}{aff_text}"
            return json.dumps({
                "message": msg,
                "mode": "EXPLANATION_ONLY",
                "suggestion": None,
            }), self.provider_name, self.model_name

        if any(w in q_lower for w in ["summarize", "summary", "overview"]):
            docs_summary = ", ".join(f"{d['role']} ({d['filename']})" for d in context.get("documents", [])) or "No documents"
            state = comparison.get("state", context.get("processing_status", "UNKNOWN"))
            msg = f"Case {context.get('case_id')[:8]}: Subject '{context.get('subject')}'. Status: {state}. Documents: {docs_summary}. {reason_title}."
            return json.dumps({
                "message": msg,
                "mode": "EXPLANATION_ONLY",
                "suggestion": None,
            }), self.provider_name, self.model_name

        if any(w in q_lower for w in ["which", "si", "bl", "document"]):
            si_doc = context.get("si_document")
            bl_doc = context.get("bl_document")
            si_name = si_doc["filename"] if si_doc else "None"
            bl_name = bl_doc["filename"] if bl_doc else "None"
            msg = f"Shipping Instruction (SI): {si_name}. Draft Bill of Lading (BL): {bl_name}."
            return json.dumps({
                "message": msg,
                "mode": "EXPLANATION_ONLY",
                "suggestion": None,
            }), self.provider_name, self.model_name

        # Fallback general explanation
        msg = f"{reason_title}: {human_explanation} You can check the 7 verified fields and documents in the review detail."
        return json.dumps({
            "message": msg,
            "mode": "EXPLANATION_ONLY",
            "suggestion": None,
        }), self.provider_name, self.model_name


class HTTPProvider:
    """Config-driven HTTP provider for external LLM API endpoints using standard urllib."""

    def __init__(
        self,
        endpoint: str,
        api_key: str | None,
        model: str,
        timeout_seconds: float = 10.0,
        provider_name: str = "http",
    ):
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.provider_name = provider_name

    def generate_review_response(
        self,
        context: dict[str, Any],
        question: str,
    ) -> tuple[str, str, str]:
        system_instruction = (
            "You are the HolyShip AI Review Assistant. You explain shipping document verification cases grounded strictly in provided evidence. "
            "You must return ONLY a JSON object with schema: "
            "{"
            "  \"message\": \"string\","
            "  \"mode\": \"EXPLANATION_ONLY\" | \"ACTIONABLE_SUGGESTION\" | \"INSUFFICIENT_EVIDENCE\","
            "  \"suggestion\": null or {"
            "    \"action\": \"FIELD_OVERRIDE\","
            "    \"document_side\": \"SI\" | \"BL\","
            "    \"field\": \"shipper\"|\"consignee\"|\"notify_party\"|\"port_of_loading\"|\"port_of_discharge\"|\"container_count\"|\"gross_weight_kg\","
            "    \"current_value\": \"string\","
            "    \"suggested_value\": \"string\","
            "    \"confidence\": float between 0.0 and 1.0,"
            "    \"reason\": \"string\","
            "    \"evidence_refs\": [\"string\"]"
            "  }"
            "}. "
            "Do not include extra markdown fences or prose outside JSON."
        )
        user_prompt = f"Case Context:\n{json.dumps(context, indent=2)}\n\nQuestion: {question}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
        }
        body_bytes = json.dumps(payload).encode("utf-8")

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        req = urllib.request.Request(self.endpoint, data=body_bytes, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices", [])
                if choices and "message" in choices[0]:
                    content = choices[0]["message"].get("content", "")
                    return content, self.provider_name, self.model
                return json.dumps(data), self.provider_name, self.model
        except Exception:
            # Fall back to safe insufficient evidence on timeout / failure
            pass

        fallback = {
            "message": "AI provider service is currently unavailable or timed out.",
            "mode": "INSUFFICIENT_EVIDENCE",
            "suggestion": None,
        }
        return json.dumps(fallback), self.provider_name, self.model


def get_ai_review_provider(settings: Settings) -> AIReviewProvider:
    if not settings.ai_review_enabled or settings.ai_review_provider == "disabled":
        return DisabledProvider()

    api_key_str = settings.ai_review_api_key.get_secret_value() if settings.ai_review_api_key else None
    endpoint = settings.ai_review_endpoint or "http://localhost:8000/v1/chat/completions"
    return HTTPProvider(
        endpoint=endpoint,
        api_key=api_key_str,
        model=settings.ai_review_model,
        timeout_seconds=settings.ai_review_timeout_seconds,
        provider_name=settings.ai_review_provider,
    )
