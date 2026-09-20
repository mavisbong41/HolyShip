# Phase 7 Product-Facing API Design

## Goal

Expose the persisted Phase 0–6 shipping-verification state through a stable backend contract that a dashboard, extension, reviewer workspace, and live demo can consume without knowing ORM relationships or rerunning processing.

## Architecture

The legacy router remains the compatibility boundary. A new product composition module owns explicit Pydantic contracts and read-only query/serialization helpers. It loads the latest persisted classification/comparison/review data with SQL aggregation and `selectinload`; it does not call the processing pipeline. v1 aliases reuse the existing `SyncService` only for POST ingestion/sync operations.

## Product contracts

- Queue: paginated `items`, `total`, `skip`, and `limit`; each row includes email identity, sender/subject/time, attachment count, status, classification category/confidence, readiness, comparison state, mismatch/unresolved counts, and review state.
- Summary: total, status counts, needs-review count, comparison-ready count, mismatch count, and unresolved count.
- Detail: email/attachments, latest classification, readiness/status/timeline, validated documents and extraction fields, exactly seven canonical SI-vs-BL comparisons, bounded evidence, review context, and safe Phase 6 resolution provenance.
- Review: queue/detail responses include email summary, reason, optional document/field, evidence, comparison context, and resolution records.
- Events: polling-compatible persisted processing-event feed with product event name, email id, status, category, mismatch flag, and timestamp.

## Semantics and safety

The API preserves `MATCH`, `MISMATCH`, and `UNRESOLVED`; `BLOCKED` is never rewritten as mismatch. Missing/partial rows remain null or empty rather than fabricated. SI is always the reference and BL is always the checked document. Evidence is copied from persisted JSONB only. Provider/model names may be shown for explainability, but request payloads, prompts, secrets, and cache identities are not exposed.

## Error behavior

UUID path/query validation produces 422, unknown emails/reviews produce 404, invalid pagination/filter values produce 422, and no new mutation is introduced for review decisions. Technical reprocess rejects non-FAILED states with 409 and is idempotent at the source identity boundary.

## Verification

Contract tests cover queue filters/pagination, summary, detail composition, seven-field ordering and state preservation, evidence/provenance redaction, partial state, 404/422 responses, and the fact that GET composition never invokes expensive processing. PostgreSQL tests cover representative persisted joins. The demo script exercises initial sync, queue/detail, persisted comparison scenarios, and simulated incoming messages.
