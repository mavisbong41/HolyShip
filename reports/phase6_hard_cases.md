# Phase 6 hard-case audit

## Permitted-data baseline

The clean public-bundle Phase 5-compatible run processed 520 emails and produced 98 persisted comparison results. All 98 comparison results remained `BLOCKED / COMPARISON_UNRESOLVED`; the public submission therefore contained 203 `NEEDS_REVIEW` items. Runtime provider calls were zero.

Persisted field evidence showed 29 L2 semantic uncertainties: shipper 3, consignee 3, notify party 5, port of loading 6, and port of discharge 12. Extraction contained one explicit unresolved gross-weight format. Six image-only documents reached the OCR boundary. These 36 field/document events are the narrow Phase 6 target surface; they are not assumed to be correctable without supported evidence.

## Cause taxonomy

| Cause | Observed evidence | Phase 6 policy |
| --- | ---: | --- |
| Cross-document semantic ambiguity | 29 L2 field decisions | Targeted semantic resolver after L0/L1 `NO_DECISION` only |
| Explicit unresolved extraction | 1 gross-weight format | Targeted extraction request only when source evidence exists |
| Scanned/image-only input | 6 OCR-routed documents | Bounded OCR; same role validation and deterministic extraction pipeline |
| Missing extracted field | 386 missing field slots across the 98 pairs | Human Review; never ask AI to invent source data |
| Corrupt/unreadable input | 8 documents | Document/reliability outcome; no semantic answer |
| Wrong document type | 4 documents | `WRONG_DOCUMENT_TYPE`; no override |
| Missing attachment/role evidence | Remaining blocked comparison emails | Human Review; no provider call |

## Resolver architecture

The deterministic reader, role validator, extractor, L0 normalization, and L1 comparator remain authoritative. Only unresolved/ambiguous extraction fields are batched by document into a provider-independent structured request. Semantic resolution runs only after L0/L1 decline to decide. AI is disabled by default.

Every provider operation has a timeout, finite retry policy, per-case call budget, concurrency semaphore, stable versioned request hash, in-process single-flight protection, and PostgreSQL cache/audit persistence. Cache identity includes purpose, evidence/content identity, field/role, provider, model, resolver version, and prompt schema version.

The final focused review traced the production path from environment-backed `Settings`, through the configured provider/executor factory, both API and batch `SyncService` construction, and an eligible unresolved field to a validated persisted result. The disabled path constructs no provider and preserves the Phase 5 deterministic comparison identity. The deterministic fake used the same runtime factory boundary; this is integration evidence, not a live-provider claim.

Resolver single-flight and provider concurrency are process-local and shared across the real multi-session worker pool. OCR cache, call budget, and concurrency state are likewise shared across that worker pool. PostgreSQL uniqueness makes resolution persistence idempotent across processes, but independent application processes can still perform duplicate provider work before either commits; no cross-process provider-call single-flight is claimed.

## Acceptance and rejection

Acceptance requires a valid project-owned result object, one of the seven fields, confidence at or above the configured threshold, evidence anchored in the supplied source, a valid field type, safe numeric/unit semantics, and no contradiction with deterministic candidates. Gross-weight pounds are rejected rather than treated as kilograms; container count must be a non-negative integer.

Low confidence, malformed output, timeout, retry exhaustion, missing evidence, unanchored evidence, conflicting candidates, unsafe units, and unsupported values remain unresolved with machine-readable reasons. A definite L0/L1 match or mismatch never calls the resolver.

Accepted extraction proposals are comparison-only overlays. The original `extracted_fields` rows stay unchanged. The proposal, validation result, evidence, confidence, resolver identity, and cache metadata are persisted in `ai_resolutions` and copied into comparison evidence for later backend/UI consumption.

## Provider status

Automated validation uses deterministic fakes. Tesseract availability and live AI provider behavior are environment-dependent. No live AI credentials were available or used; live-provider accuracy is **NOT VERIFIED**.
