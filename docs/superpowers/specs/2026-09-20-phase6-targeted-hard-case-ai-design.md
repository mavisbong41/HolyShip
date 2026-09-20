# Phase 6 Targeted Hard-Case AI Design

## Scope and evidence

Phase 6 extends the merged Phase 5 backend with fallback-only OCR and structured AI resolution. The deterministic classifier, readers, role validator, extractor, L0/L1 comparison, persistence, and submission adapter remain authoritative. AI is disabled by default and is never invoked for definite deterministic matches or mismatches.

The clean inherited public-bundle baseline is 520 emails, 203 comparison emails, 98 valid SI/BL pairs, 98 blocked comparisons, and zero provider calls. The comparison audit contains 29 L2 semantic uncertainties. Extraction contains one explicit unparseable gross-weight value and many `FIELD_NOT_PRESENT` rows. Six image-only documents reach the OCR boundary. Phase 6 targets only the 29 semantic cases, explicit unresolved/ambiguous extraction evidence, and scanned inputs. Truly missing fields, missing attachments, corrupt files, wrong document types, and unsupported evidence remain unresolved.

## Architecture

The existing deterministic path stays unchanged when `AI_ESCALATION_ENABLED=false`.

When enabled, a provider-independent hard-case resolver accepts one of two project-owned request types:

- extraction resolution for an `UNRESOLVED` or `AMBIGUOUS` field with source text/candidates;
- semantic comparison resolution after L0 and L1 return no decision.

Requests carry only the target field, document role/identity, relevant evidence, deterministic candidates or normalized SI/BL values, escalation reason, and resolver/cache version dimensions. Provider responses are structured dataclasses and are validated before acceptance.

An orchestration layer applies bounded timeout, bounded retry, a per-case call budget, schema validation, confidence policy, evidence anchoring, field-type validation, and contradiction checks. A PostgreSQL cache uses a stable request hash that includes content identity, purpose, role, field, resolver version, provider, model, and prompt schema version. An in-process single-flight lock prevents duplicate concurrent provider calls; the database unique key resolves insertion races.

Accepted extraction proposals are overlays used to build comparison rows. Existing deterministic extraction rows are never overwritten. The AI proposal, validation decision, provenance, resolver/model version, evidence, and cache metadata are persisted separately and copied into comparison evidence. Semantic results may resolve only an L2 `NO_DECISION`; they cannot override a definite L0/L1 result.

## Acceptance and rejection policy

An extraction proposal is accepted only when all conditions hold: the field is one of the seven canonical fields; source evidence exists; the returned evidence is anchored in that source; confidence meets the configured threshold; the value is valid for the field; numeric/unit semantics are safe; and the proposal does not contradict stronger deterministic evidence.

Container counts must be deterministic non-negative integers. Gross weight accepts kilograms only; pounds are rejected rather than silently treated as kilograms. Entity and port values must be supported by source evidence. Missing source evidence bypasses the provider entirely.

A semantic result is accepted only after deterministic L0/L1 uncertainty, with valid structured output, sufficient confidence, and non-empty SI/BL evidence. Low confidence, malformed output, timeout, retry exhaustion, unsupported fields, contradictions, missing evidence, and invalid numeric/unit output remain `UNRESOLVED` with a machine-readable validation reason.

## OCR and Vision

The existing native-first router remains authoritative. OCR is invoked only for images or image-only PDFs; Vision remains a later fallback when OCR cannot produce usable text. The OCR reader gains injectable deterministic test support plus configurable concurrency and call budget. OCR text remains a `UnifiedDocument`, passes through the same role validator and deterministic extractor, and carries page/provenance metadata. Real Tesseract/provider execution is reported honestly according to environment availability.

## Reliability and metrics

Provider timeout, malformed output, transient errors, and exhaustion are isolated to the current field/case. The batch continues. Metrics include escalated cases, provider calls, accepted/rejected results, cache hits, failures, malformed responses, and average calls per escalated case. AI-disabled evaluation must retain the Phase 5 submission SHA-256. Fixture-backed enabled evaluation demonstrates behavior without claiming live-provider accuracy.

## Persistence and compatibility

An additive Alembic migration creates the AI resolution cache/audit table. No existing extraction or comparison evidence is destructively changed. AI-disabled comparison identity remains the Phase 4 deterministic version; AI-enabled identity includes the output-affecting resolver configuration. Existing API and submission schemas remain compatible.

## Testing

Tests cover accepted and rejected structured results, low confidence, missing evidence, contradictions, malformed output, timeout, transient retry, retry exhaustion, unsupported fields, invalid units, concurrent duplicate escalation, cache reuse, version invalidation, OCR success/unavailable/garbage behavior, PostgreSQL persistence/concurrency, and full-pipeline outcomes. The phase closes with focused tests, `git diff --check`, `make check-fast`, `make check PHASE=6B`, clean AI-disabled fingerprint comparison, targeted fixture evaluation, leakage audit, reports, commit, and push.
