# HolyShip Enterprise AI Security

This document describes the implemented security controls for the AI paths covered by the HolyShip enhancement requirements.

## Scope

This implementation covers:

- Enterprise Privacy Mode
- Secure AI Gateway for Gemini
- Minimum Necessary Disclosure
- raw AI request/prompt retention minimisation
- server-side secret handling
- disclosure audit metadata

It intentionally does **not** add authentication, RBAC, tenant isolation, Outlook lifecycle sync, Smart Reply, or retention cleanup jobs. Those are separate enhancement areas.

## Enterprise Privacy Mode

`ENTERPRISE_PRIVACY_MODE` is a backend configuration value and defaults to `true`.

It is not an end-user UI toggle.

When enabled, the Secure AI Gateway:

- removes unnecessary email/case identifiers from AI payloads;
- redacts email addresses in free-form question text;
- strips known secret-like assignments from free-form strings;
- enforces purpose-specific data minimisation;
- rejects payloads above `AI_GATEWAY_MAX_PAYLOAD_BYTES`.

## Secure AI Gateway

All Gemini network calls are routed through:

`backend/app/security/ai_gateway.py`

Current Gemini-backed features:

1. L2 extraction resolution
2. L2 semantic comparison
3. Human Review AI Assistant

The feature/provider modules prepare domain requests, but Gemini HTTP transport is owned by the gateway.

The API key is sent in the `x-goog-api-key` request header and is not placed in the request URL.

The gateway performs:

1. purpose validation;
2. minimum-necessary payload construction;
3. sanitisation/redaction;
4. payload-size policy enforcement;
5. Gemini transport;
6. JSON-object response validation;
7. non-sensitive audit metadata generation.

A policy violation fails closed before a provider request is sent.

## Minimum Necessary Disclosure

### Field extraction

Gemini receives only:

- canonical field name;
- document role;
- field-local evidence;
- escalation reason.

It does not receive the full email or full document.

### Field semantic comparison

Gemini receives only:

- canonical field name;
- SI value;
- BL value;
- SI field evidence;
- BL field evidence.

Unrelated fields are dropped.

### Human Review

The gateway removes:

- sender;
- recipients;
- email/case IDs;
- content hashes;
- full raw document text;
- recent audit-event history;
- unrelated extracted fields;
- unrelated comparison fields;
- reviewer identity and free-form override notes.

For field-level review, only affected fields are disclosed.

Document metadata is reduced to operational information such as role, format, validation/read state, and routing outcome.

## AI Data Retention

Raw field-resolution requests are no longer persisted in `ai_resolutions.request_json`.

Instead, persisted request audit metadata contains only information such as:

- purpose;
- field;
- escalation reason;
- payload hash;
- payload size;
- privacy-mode state;
- disclosed field names;
- disclosure categories;
- request/response status;
- latency.

Structured resolver results remain persisted because they are required for deterministic cache/audit behaviour.

Human Review AI events no longer persist the user's raw question. The audit event stores:

- SHA-256 of the question;
- question length;
- provider/model;
- result mode;
- Secure AI Gateway audit metadata.

Structured AI suggestions remain persisted because they are user-reviewable business proposals and are part of the audit trail.

## Secrets

AI credentials remain backend-only and are loaded from environment-backed settings.

Frontend and Outlook source code must not contain:

- `GEMINI_API_KEY`
- `AI_REVIEW_API_KEY`

Provider HTTP error bodies are not returned to users as part of AI error messages.

## Audit Metadata

Gateway audit metadata never contains the complete outbound AI payload.

It contains:

- purpose;
- invoking feature;
- provider/model;
- Enterprise Privacy Mode state;
- payload SHA-256;
- payload byte size;
- disclosed canonical fields;
- disclosure categories;
- request status;
- response status;
- latency when a validated Gemini response is received.

This allows the system to prove what *type* of information was disclosed without retaining the sensitive raw prompt.

## Failure Behaviour

- unsupported AI purpose: blocked before network;
- oversized payload: blocked before network;
- missing Gemini key: blocked;
- Gemini HTTP/transient failure: fail safely through the existing provider/resolver error path;
- malformed Gemini output: rejected by gateway response validation;
- low confidence or unsafe suggestion: existing HolyShip safety gates still apply;
- AI failure never mutates original SI/BL extraction truth.

## Configuration

```env
ENTERPRISE_PRIVACY_MODE=true
AI_GATEWAY_MAX_PAYLOAD_BYTES=65536
```

Production should keep Enterprise Privacy Mode enabled.

## Validation

Security regression coverage lives in:

`backend/tests/test_security_ai_gateway.py`

It verifies:

- privacy mode defaults on;
- Human Review context minimisation;
- field-level minimum disclosure;
- payload-size fail-closed behaviour;
- Gemini key is not embedded in the URL;
- raw Human Review question is not persisted;
- Gemini network calls are centralised in the gateway;
- frontend/Outlook code does not reference Gemini API secret variables.
