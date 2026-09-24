from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.app.ai_review.providers import MockAIReviewProvider, OpenAIProvider
from backend.app.ai_review.service import AIReviewService
from backend.app.core.config import Settings
from backend.app.extraction.models import CanonicalField
from backend.app.resolution.models import ExtractionResolutionRequest
from backend.app.resolution.providers import GeminiResolverProvider, HttpJsonResolverProvider
from backend.app.security.ai_gateway import (
    AIGatewayPolicyError,
    AIGatewayResult,
    PURPOSE_FIELD_EXTRACTION,
    PURPOSE_FIELD_SEMANTIC_COMPARISON,
    PURPOSE_HUMAN_REVIEW,
    SecureAIGateway,
)
from backend.app.storage.models import HumanReviewCaseRecord, HumanReviewEventRecord


def _human_review_context() -> dict:
    return {
        "case_id": "case-secret-id",
        "email_id": "email-secret-id",
        "subject": "Private shipment for customer@example.com",
        "sender": "sender@example.com",
        "processing_status": "BLOCKED",
        "category": "document_comparison",
        "comparison_readiness": "READY_FOR_COMPARISON",
        "review_status": "OPEN",
        "reason_code": "COMPARISON_UNRESOLVED",
        "presentation_title": "One or more document fields could not be verified",
        "human_explanation": "Gross Weight needs review.",
        "affected_area": "Document fields",
        "affected_fields": ["gross_weight_kg"],
        "documents": [
            {
                "id": "doc-private-id",
                "filename": "customer-name-BL.pdf",
                "role": "DRAFT_BL",
                "format": "PDF",
                "validation_outcome": "VALID",
                "read_status": "EXTRACTED",
                "routing_outcome": "BL_FOUND",
            }
        ],
        "si_extracted_fields": {
            "gross_weight_kg": {
                "raw_value": "22000 KG",
                "canonical_value": 22000,
                "status": "RESOLVED",
                "confidence": 0.99,
            },
            "shipper": {
                "raw_value": "PRIVATE SHIPPER",
                "canonical_value": "PRIVATE SHIPPER",
                "status": "RESOLVED",
                "confidence": 0.99,
            },
        },
        "bl_extracted_fields": {
            "gross_weight_kg": {
                "raw_value": "22,O00 KG",
                "canonical_value": None,
                "status": "UNRESOLVED",
                "confidence": 0.5,
            },
            "shipper": {
                "raw_value": "PRIVATE SHIPPER",
                "canonical_value": "PRIVATE SHIPPER",
                "status": "RESOLVED",
                "confidence": 0.99,
            },
        },
        "comparison": {
            "state": "BLOCKED",
            "mismatch_found": False,
            "reason_code": "COMPARISON_UNRESOLVED",
            "mismatched_fields": [],
            "unresolved_fields": ["gross_weight_kg"],
            "fields": [
                {
                    "field": "gross_weight_kg",
                    "status": "UNRESOLVED",
                    "reason_code": "MISSING_VALUE",
                    "si_value": "22000 KG",
                    "si_canonical": 22000,
                    "bl_value": "22,O00 KG",
                    "bl_canonical": None,
                },
                {
                    "field": "shipper",
                    "status": "MATCH",
                    "reason_code": "L0_EQUAL",
                    "si_value": "PRIVATE SHIPPER",
                    "si_canonical": "PRIVATE SHIPPER",
                    "bl_value": "PRIVATE SHIPPER",
                    "bl_canonical": "PRIVATE SHIPPER",
                },
            ],
        },
        "active_overrides": [
            {
                "document_side": "BL",
                "field": "gross_weight_kg",
                "corrected_value": "22000",
                "corrected_canonical_value": 22000,
                "reviewer_name": "Private Reviewer",
                "note": "private note",
            }
        ],
        "recent_events": [
            {
                "action": "CASE_CREATED",
                "actor_name": "Private Reviewer",
                "details": {"secret": "do not disclose"},
            }
        ],
    }


def test_enterprise_privacy_mode_defaults_enabled():
    settings = Settings(_env_file=None)
    assert settings.enterprise_privacy_mode is True
    assert settings.ai_gateway_max_payload_bytes == 64 * 1024


def test_human_review_gateway_discloses_only_affected_case_data():
    gateway = SecureAIGateway(enterprise_privacy_mode=True)
    payload, audit = gateway.prepare_payload(
        purpose=PURPOSE_HUMAN_REVIEW,
        feature="human_review_assistant",
        model="gemini-2.5-flash",
        data={
            "question": "Explain this for ops@example.com api_key=topsecret Bearer abc123",
            "context": _human_review_context(),
        },
    )

    serialized = json.dumps(payload, sort_keys=True)
    case = payload["case"]

    assert payload["question"] == (
        "Explain this for [REDACTED_EMAIL] api_key=[REDACTED] Bearer [REDACTED]"
    )
    assert "sender" not in case
    assert "subject" not in case
    assert "case_id" not in case
    assert "email_id" not in case
    assert "recent_events" not in case
    assert case["documents"] == [
        {
            "role": "DRAFT_BL",
            "format": "PDF",
            "validation_outcome": "VALID",
            "read_status": "EXTRACTED",
            "routing_outcome": "BL_FOUND",
        }
    ]
    assert list(case["si_extracted_fields"]) == ["gross_weight_kg"]
    assert list(case["bl_extracted_fields"]) == ["gross_weight_kg"]
    assert [field["field"] for field in case["comparison"]["fields"]] == [
        "gross_weight_kg"
    ]
    assert "PRIVATE SHIPPER" not in serialized
    assert "customer-name-BL.pdf" not in serialized
    assert "Private Reviewer" not in serialized
    assert audit["disclosed_fields"] == ["gross_weight_kg"]
    assert "affected_field_values" in audit["disclosure_categories"]



def test_document_level_review_discloses_no_unrelated_field_values():
    context = _human_review_context()
    context["reason_code"] = "UNREADABLE_ATTACHMENT"
    context["presentation_title"] = "Document could not be read reliably"
    context["affected_area"] = "Documents"
    context["affected_fields"] = []

    payload, audit = SecureAIGateway().prepare_payload(
        purpose=PURPOSE_HUMAN_REVIEW,
        feature="human_review_assistant",
        model="gemini-2.5-flash",
        data={"question": "Why does this need review?", "context": context},
    )

    case = payload["case"]
    serialized = json.dumps(payload, sort_keys=True)
    assert case["si_extracted_fields"] == {}
    assert case["bl_extracted_fields"] == {}
    assert case["comparison"]["fields"] == []
    assert case["comparison"]["mismatched_fields"] == []
    assert case["comparison"]["unresolved_fields"] == []
    assert case["active_overrides"] == []
    assert "22000 KG" not in serialized
    assert "22,O00 KG" not in serialized
    assert "PRIVATE SHIPPER" not in serialized
    assert audit["disclosed_fields"] == []


def test_gemini_extraction_batch_stays_minimized_and_single_call():
    gateway = MagicMock(spec=SecureAIGateway)
    gateway.invoke_gemini_json.return_value = AIGatewayResult(
        structured_response={
            "results": [
                {
                    "field": "port_of_loading",
                    "value": "Port Klang",
                    "normalized_value": "PORT KLANG",
                    "confidence": 0.97,
                    "evidence": "Port of Loading: Port Klang",
                    "reasoning_code": "GEMINI_EXTRACTION",
                },
                {
                    "field": "port_of_discharge",
                    "value": "Singapore",
                    "normalized_value": "SINGAPORE",
                    "confidence": 0.96,
                    "evidence": "Port of Discharge: Singapore",
                    "reasoning_code": "GEMINI_EXTRACTION",
                },
            ]
        },
        audit_metadata={
            "purpose": PURPOSE_FIELD_EXTRACTION,
            "disclosed_fields": ["port_of_loading", "port_of_discharge"],
        },
    )
    provider = GeminiResolverProvider(
        api_key="test-key",
        gateway=gateway,
    )
    requests = (
        ExtractionResolutionRequest(
            case_id="case-1",
            field=CanonicalField.PORT_OF_LOADING,
            document_role="SI",
            document_id="doc-1",
            content_identity="sha:1",
            evidence="Port of Loading: Port Klang",
            deterministic_candidates=(),
            escalation_reason="UNRESOLVED_EXTRACTION",
        ),
        ExtractionResolutionRequest(
            case_id="case-1",
            field=CanonicalField.PORT_OF_DISCHARGE,
            document_role="SI",
            document_id="doc-1",
            content_identity="sha:1",
            evidence="Port of Discharge: Singapore",
            deterministic_candidates=(),
            escalation_reason="UNRESOLVED_EXTRACTION",
        ),
    )

    result = provider.resolve(SimpleNamespace(case_id="case-1", requests=requests))

    assert [item.field for item in result] == [
        CanonicalField.PORT_OF_LOADING,
        CanonicalField.PORT_OF_DISCHARGE,
    ]
    gateway.invoke_gemini_json.assert_called_once()
    call = gateway.invoke_gemini_json.call_args.kwargs
    assert call["purpose"] == PURPOSE_FIELD_EXTRACTION
    assert call["feature"] == "l2_extraction_resolution_batch"
    assert call["data"] == {
        "requests": [
            {
                "field": "port_of_loading",
                "document_role": "SI",
                "evidence": "Port of Loading: Port Klang",
                "escalation_reason": "UNRESOLVED_EXTRACTION",
            },
            {
                "field": "port_of_discharge",
                "document_role": "SI",
                "evidence": "Port of Discharge: Singapore",
                "escalation_reason": "UNRESOLVED_EXTRACTION",
            },
        ]
    }

def test_field_semantic_gateway_rejects_unrelated_context():
    gateway = SecureAIGateway()
    payload, audit = gateway.prepare_payload(
        purpose=PURPOSE_FIELD_SEMANTIC_COMPARISON,
        feature="l2_semantic_comparison",
        model="gemini-2.5-flash",
        data={
            "field": "port_of_loading",
            "si_value": "Port Klang",
            "bl_value": "PORT KLANG, MALAYSIA",
            "si_evidence": "POL: Port Klang",
            "bl_evidence": "Port of Loading: PORT KLANG, MALAYSIA",
            "entire_email": "secret email body",
            "all_customer_data": {"consignee": "Secret Customer"},
        },
    )

    assert set(payload) == {
        "field",
        "si_value",
        "bl_value",
        "si_evidence",
        "bl_evidence",
    }
    assert audit["disclosed_fields"] == ["port_of_loading"]
    assert audit["disclosure_categories"] == [
        "field_name",
        "si_value",
        "bl_value",
        "field_evidence",
    ]


def test_gateway_blocks_oversized_payload_before_network():
    gateway = SecureAIGateway(max_payload_bytes=1024)
    with patch(
        "backend.app.security.ai_gateway.urllib.request.urlopen"
    ) as mocked_urlopen:
        with pytest.raises(AIGatewayPolicyError, match="payload exceeds"):
            gateway.invoke_gemini_json(
                api_key="test-key",
                model="gemini-2.5-flash",
                purpose=PURPOSE_FIELD_SEMANTIC_COMPARISON,
                feature="l2_semantic_comparison",
                data={
                    "field": "shipper",
                    "si_value": "A" * 5000,
                    "bl_value": "B" * 5000,
                    "si_evidence": "A" * 5000,
                    "bl_evidence": "B" * 5000,
                },
                system_instruction="Return JSON.",
                timeout_seconds=1,
            )
        mocked_urlopen.assert_not_called()


def test_gemini_gateway_keeps_secret_out_of_url_and_returns_audit():
    gateway = SecureAIGateway()
    provider_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "field": "port_of_loading",
                                    "equivalent": True,
                                    "confidence": 0.99,
                                    "evidence": "Port Klang | PORT KLANG, MALAYSIA",
                                    "reasoning_code": "PORT_ALIAS",
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(provider_response).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch(
        "backend.app.security.ai_gateway.urllib.request.urlopen",
        return_value=mock_response,
    ) as mocked_urlopen:
        result = gateway.invoke_gemini_json(
            api_key="super-secret-gemini-key",
            model="gemini-2.5-flash",
            purpose=PURPOSE_FIELD_SEMANTIC_COMPARISON,
            feature="l2_semantic_comparison",
            data={
                "field": "port_of_loading",
                "si_value": "Port Klang",
                "bl_value": "PORT KLANG, MALAYSIA",
                "si_evidence": "POL: Port Klang",
                "bl_evidence": "Port of Loading: PORT KLANG, MALAYSIA",
            },
            system_instruction="Return JSON.",
            timeout_seconds=1,
        )

    request = mocked_urlopen.call_args.args[0]
    assert "super-secret-gemini-key" not in request.full_url
    assert request.get_header("X-goog-api-key") == "super-secret-gemini-key"
    assert result.structured_response["equivalent"] is True
    assert result.audit_metadata["purpose"] == PURPOSE_FIELD_SEMANTIC_COMPARISON
    assert result.audit_metadata["request_status"] == "SENT"
    assert result.audit_metadata["response_status"] == "VALIDATED"
    assert result.audit_metadata["payload_sha256"]


def test_human_review_audit_does_not_persist_raw_question():
    session = MagicMock()
    case_id = uuid4()
    case = MagicMock(spec=HumanReviewCaseRecord)
    case.id = case_id
    session.get.return_value = case

    provider = MockAIReviewProvider(
        response_json={
            "message": "Grounded explanation.",
            "mode": "EXPLANATION_ONLY",
            "suggestion": None,
        },
        provider_name="gemini",
        model_name="gemini-2.5-flash",
    )
    provider.last_audit_metadata = {
        "purpose": PURPOSE_HUMAN_REVIEW,
        "feature": "human_review_assistant",
        "payload_sha256": "a" * 64,
        "disclosed_fields": ["gross_weight_kg"],
    }
    question = "Summarize sensitive case customer@example.com"

    with patch(
        "backend.app.ai_review.service.build_case_context",
        return_value=_human_review_context(),
    ):
        AIReviewService(session=session, provider=provider).ask(case_id, question)

    events = [
        call.args[0]
        for call in session.add.call_args_list
        if isinstance(call.args[0], HumanReviewEventRecord)
    ]
    asked = next(event for event in events if event.action == "AI_ASSISTANT_ASKED")
    assert "question" not in asked.details
    assert asked.details["question_sha256"] == hashlib.sha256(
        question.encode("utf-8")
    ).hexdigest()
    assert asked.details["question_length"] == len(question)
    assert asked.details["ai_gateway"]["payload_sha256"] == "a" * 64


def test_gemini_network_calls_are_centralized_in_gateway():
    review_source = Path("backend/app/ai_review/providers.py").read_text(encoding="utf-8")
    resolver_source = Path("backend/app/resolution/providers.py").read_text(encoding="utf-8")
    gateway_source = Path("backend/app/security/ai_gateway.py").read_text(encoding="utf-8")

    gemini_review = review_source.split("class GeminiProvider:", 1)[1].split(
        "class OpenAIProvider:", 1
    )[0]
    gemini_resolver = resolver_source.split("class GeminiResolverProvider:", 1)[1]

    assert "urllib.request.urlopen" not in gemini_review
    assert "urllib.request.urlopen" not in gemini_resolver
    assert gateway_source.count("urllib.request.urlopen") == 1

    gateway_path = Path("backend/app/security/ai_gateway.py")
    config_path = Path("backend/app/core/config.py")
    for path in Path("backend/app").rglob("*.py"):
        if path in {gateway_path, config_path}:
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        assert "generativelanguage.googleapis.com" not in source
        assert '"x-goog-api-key"' not in source

    config_source = config_path.read_text(encoding="utf-8")
    assert "generativelanguage.googleapis.com" in config_source
    assert "urllib.request.urlopen" not in config_source


def test_frontend_sources_do_not_reference_gemini_api_secrets():
    for root in (Path("frontend/src"), Path("outlook-addin/src")):
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
            assert "GEMINI_API_KEY" not in content
            assert "AI_REVIEW_API_KEY" not in content


def test_gateway_enterprise_allowlist_defaults_are_restrictive():
    settings = Settings(_env_file=None)
    gateway = SecureAIGateway.from_settings(settings)

    assert settings.enterprise_privacy_mode is True
    assert gateway.allowed_providers == {"gemini", "google"}
    assert gateway.allowed_models == set()
    assert gateway.allowed_endpoint_hosts == {"generativelanguage.googleapis.com"}


def test_gateway_preserves_explicit_empty_allowlists():
    gateway = SecureAIGateway(
        enterprise_privacy_mode=True,
        allowed_providers=set(),
        allowed_endpoint_hosts=set(),
    )
    with pytest.raises(AIGatewayPolicyError, match="provider"):
        gateway.prepare_payload(
            purpose=PURPOSE_HUMAN_REVIEW,
            feature="human_review_assistant",
            model="gemini-2.5-flash",
            provider="gemini",
            endpoint="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            data={"question": "test", "context": {}},
        )


def test_gateway_requires_https_for_external_ai_in_privacy_mode():
    gateway = SecureAIGateway(
        allowed_providers={"gemini"},
        allowed_endpoint_hosts={"generativelanguage.googleapis.com"},
    )
    with patch("backend.app.security.ai_gateway.urllib.request.urlopen") as mocked:
        with pytest.raises(AIGatewayPolicyError, match="HTTPS"):
            gateway.invoke_gemini_json(
                api_key="test-key",
                model="gemini-2.5-flash",
                purpose=PURPOSE_FIELD_SEMANTIC_COMPARISON,
                feature="l2_semantic_comparison",
                data={
                    "field": "port_of_loading",
                    "si_value": "Port Klang",
                    "bl_value": "Port Klang",
                    "si_evidence": "Port Klang",
                    "bl_evidence": "Port Klang",
                },
                system_instruction="Return JSON.",
                timeout_seconds=1,
                endpoint="http://generativelanguage.googleapis.com/v1beta/models",
            )
        mocked.assert_not_called()


def test_gateway_redacts_common_secret_assignments_in_free_text():
    gateway = SecureAIGateway()
    payload, _audit = gateway.prepare_payload(
        purpose=PURPOSE_HUMAN_REVIEW,
        feature="human_review_assistant",
        model="gemini-2.5-flash",
        data={
            "question": (
                "client_secret=abc access_token=def refresh-token=ghi "
                "secret=jkl password=mno"
            ),
            "context": {},
        },
    )
    serialized = json.dumps(payload)
    for secret in ("abc", "def", "ghi", "jkl", "mno"):
        assert secret not in serialized
    assert serialized.count("[REDACTED]") >= 5


def test_gateway_blocks_unapproved_provider_model_and_endpoint_before_network():
    gateway = SecureAIGateway(
        allowed_providers={"gemini"},
        allowed_models={"gemini-2.5-flash"},
        allowed_endpoint_hosts={"generativelanguage.googleapis.com"},
    )

    with pytest.raises(AIGatewayPolicyError, match="provider"):
        gateway.prepare_payload(
            purpose=PURPOSE_HUMAN_REVIEW,
            feature="human_review_assistant",
            model="gpt-4o-mini",
            provider="openai",
            endpoint="https://api.openai.com/v1/chat/completions",
            data={"question": "test", "context": {}},
        )

    with pytest.raises(AIGatewayPolicyError, match="model"):
        gateway.invoke_gemini_json(
            api_key="test-key",
            model="gemini-unapproved",
            purpose=PURPOSE_FIELD_SEMANTIC_COMPARISON,
            feature="l2_semantic_comparison",
            data={
                "field": "port_of_loading",
                "si_value": "Port Klang",
                "bl_value": "Port Klang",
                "si_evidence": "Port Klang",
                "bl_evidence": "Port Klang",
            },
            system_instruction="Return JSON.",
            timeout_seconds=1,
        )

    with patch("backend.app.security.ai_gateway.urllib.request.urlopen") as mocked:
        with pytest.raises(AIGatewayPolicyError, match="endpoint host"):
            gateway.invoke_gemini_json(
                api_key="test-key",
                model="gemini-2.5-flash",
                purpose=PURPOSE_FIELD_SEMANTIC_COMPARISON,
                feature="l2_semantic_comparison",
                data={
                    "field": "port_of_loading",
                    "si_value": "Port Klang",
                    "bl_value": "Port Klang",
                    "si_evidence": "Port Klang",
                    "bl_evidence": "Port Klang",
                },
                system_instruction="Return JSON.",
                timeout_seconds=1,
                endpoint="https://evil.example/v1/models",
            )
        mocked.assert_not_called()


def test_privacy_mode_off_allows_explicit_development_endpoint_policy_bypass():
    gateway = SecureAIGateway(
        enterprise_privacy_mode=False,
        allowed_providers=set(),
        allowed_models=set(),
        allowed_endpoint_hosts=set(),
    )
    payload, audit = gateway.prepare_payload(
        purpose=PURPOSE_HUMAN_REVIEW,
        feature="human_review_assistant",
        model="dev-model",
        provider="custom",
        endpoint="http://localhost:9999/v1/chat/completions",
        data={"question": "test", "context": {}},
    )
    assert payload["question"] == "test"
    assert audit["provider"] == "custom"
    assert audit["privacy_mode"] is False


def test_openai_review_provider_is_blocked_by_default_privacy_policy_without_network():
    provider = OpenAIProvider(
        api_key="secret",
        model="gpt-4o-mini",
        endpoint="https://api.openai.com/v1/chat/completions",
        gateway=SecureAIGateway(),
    )
    with patch("backend.app.ai_review.providers.urllib.request.urlopen") as mocked:
        raw, provider_name, model = provider.generate_review_response(
            _human_review_context(),
            "Explain this case",
        )

    parsed = json.loads(raw)
    assert provider_name == "openai"
    assert model == "gpt-4o-mini"
    assert parsed["mode"] == "INSUFFICIENT_EVIDENCE"
    assert provider.last_audit_metadata["request_status"] == "BLOCKED_BY_POLICY"
    assert provider.last_audit_metadata["response_status"] == "NOT_SENT"
    mocked.assert_not_called()


def test_allowed_http_json_provider_still_receives_only_minimized_field_data():
    gateway = SecureAIGateway(
        allowed_providers={"http_json"},
        allowed_endpoint_hosts={"resolver.example.com"},
    )
    provider = HttpJsonResolverProvider(
        endpoint="https://resolver.example.com/v1/resolve",
        model_name="approved-resolver",
        timeout_seconds=1,
        api_key="server-secret",
        gateway=gateway,
    )
    request = ExtractionResolutionRequest(
        case_id="private-case-id",
        field=CanonicalField.PORT_OF_LOADING,
        document_role="SI",
        document_id="private-doc-id",
        content_identity="sha256:private-content",
        evidence="Port of Loading: Port Klang",
        deterministic_candidates=("Port Klang",),
        escalation_reason="UNRESOLVED_EXTRACTION",
    )
    response_body = {
        "field": "port_of_loading",
        "value": "Port Klang",
        "normalized_value": "PORT KLANG",
        "equivalent": None,
        "confidence": 0.99,
        "evidence": "Port of Loading: Port Klang",
        "reasoning_code": "APPROVED_RESOLVER",
    }
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(response_body).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch(
        "backend.app.resolution.providers.urllib.request.urlopen",
        return_value=mock_response,
    ) as mocked:
        result = provider.resolve(request)

    sent_request = mocked.call_args.args[0]
    sent_payload = json.loads(sent_request.data.decode("utf-8"))
    serialized = json.dumps(sent_payload)
    assert sent_payload["request"] == {
        "field": "port_of_loading",
        "document_role": "SI",
        "evidence": "Port of Loading: Port Klang",
        "escalation_reason": "UNRESOLVED_EXTRACTION",
    }
    assert "private-case-id" not in serialized
    assert "private-doc-id" not in serialized
    assert "private-content" not in serialized
    assert "deterministic_candidates" not in serialized
    assert result.audit_metadata["provider"] == "http_json"
    assert result.audit_metadata["disclosed_fields"] == ["port_of_loading"]


def test_settings_fail_closed_if_enterprise_allowlists_are_empty():
    with pytest.raises(ValueError, match="ALLOWED_PROVIDERS"):
        Settings(
            _env_file=None,
            enterprise_privacy_mode=True,
            ai_gateway_allowed_providers="",
        )
    with pytest.raises(ValueError, match="ALLOWED_ENDPOINT_HOSTS"):
        Settings(
            _env_file=None,
            enterprise_privacy_mode=True,
            ai_gateway_allowed_endpoint_hosts="",
        )
