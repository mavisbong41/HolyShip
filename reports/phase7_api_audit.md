# Phase 7 Product API Audit

**Date:** 2026-09-20
**Inherited state:** local Phase 7 history was audited against fetched `origin/feature/email-classification` at `47a184accb47491f718e3c3ac2d209b244e95aa1`. Its production tree matches the Phase 7 base; the difference is merge topology only, so no merge/rebase was performed.

## Existing endpoints

| Product data | Persisted data | Current endpoint/schema | Product need | Phase 7 action |
|---|---|---|---|---|
| Email metadata/body | `email_messages` | `GET /api/emails/{id}` → `EmailOut` | Yes | Reuse in a v1 composed detail contract |
| Attachments | `attachments` | Nested in legacy email response | Yes | Add retrieval/status metadata to v1 detail |
| Classification | `classification_results` | `GET /api/emails/{id}/classification` → `ClassificationOut` | Yes | Add latest classification to queue/detail |
| Comparison readiness | `classification_results.comparison_readiness` | Only classification endpoint | Yes | Expose in queue/detail |
| Processing status/history | `email_messages.processing_status`, `processing_events` | Status only; no timeline | Yes | Add deterministic product timeline |
| Document materialization | `documents` | Not exposed | Yes | Add role/format/read/validation state |
| Document role | `documents.document_type`, validation/routing fields | Not exposed | Yes | Add validated role and evidence |
| Document read status | `document_extractions` | Not exposed | Yes | Add latest extraction/read status |
| Extracted fields | `extracted_fields` | Not exposed | Yes | Add exactly seven canonical field entries per document |
| Raw/normalized values | extracted fields and `field_comparisons` | Not exposed | Yes | Preserve raw, canonical, normalized values |
| Comparison result | `comparison_results` | Not exposed | Yes | Add summary and per-field result |
| Per-field comparison | `field_comparisons` | Not exposed | Yes | Add stable canonical order, SI vs BL values, reason/evidence |
| Evidence | field/document/review JSONB | Not exposed | Yes | Normalize to bounded evidence items |
| Human Review | `human_review_cases` | Thin list/detail ORM serialization | Yes | Add reviewer-ready queue/detail composition without actions |
| Phase 6 provenance | `ai_resolutions` and field evidence overlays | Not exposed | Yes | Add safe attempted/accepted/confidence/reason/evidence |

## Identified gaps

- No dashboard queue contract with server-side status/category/readiness/review/comparison filters.
- No total-count/aggregate summary contract.
- No unified email detail response joining documents, seven fields, comparison, evidence, timeline, review, and resolution provenance.
- Existing Human Review routes return only database rows and require frontend joins.
- No documented polling-compatible event endpoint.
- Existing `/api/sync` and `/api/email/incoming` are the working processing entry points but have no v1 aliases.
- No Phase 7 demo script exercises the product contract.

## Implemented Phase 7 shape

- `GET /api/v1/emails`: paginated dashboard queue with validated status/category/readiness/review/comparison/mismatch/search/time filters and aggregate row fields.
- `GET /api/v1/summary`: database aggregate counts.
- `GET /api/v1/emails/{id}` and `/detail`: unified persisted detail contract.
- `GET /api/v1/human-review` and `GET /api/v1/human-review/{id}`: reviewer-ready composition.
- `GET /api/v1/events`: deterministic polling-compatible processing-event feed.
- `POST /api/v1/sync/initial` and `POST /api/v1/ingestion/email`: additive aliases for existing pipeline entry points.
- `POST /api/v1/sync/initial` returns a final progress snapshot because the current request is synchronous; it does not claim background job polling semantics.
- `POST /api/v1/ingestion/email` accepts request-only base64 attachment bytes and passes decoded content through `IncomingApiSource` to the existing lazy document pipeline.
- `scripts/demo.sh`: canonical shell entrypoint for the HTTP-only six-scenario live demo.
- `backend/app/ingestion/polling.py` and `backend/app/ingestion/runtime.py`: generic startup/continuous polling with a durable checkpoint, completed-message/content-hash dedupe, bounded backoff, and clean shutdown-aware sleeping. Organizer HTTP may list again because it has no true `since` cursor.
- Migration `20260920_0012_ingestion_checkpoints`: additive source checkpoint persistence.
- `POST /api/v1/emails/{id}/reprocess`: bounded technical-failure reprocess control where the source adapter can be reconstructed.
- `scripts/demo_phase7.py`: live API walkthrough using the static bundle for persisted comparison scenarios and incoming API for new-message scenarios.
- Microsoft Graph adapter skeleton remains isolated behind `EmailSource` and has no credentials.

## Query strategy and compatibility

- Queue rows use aggregate/window subqueries for latest classification/comparison/review and attachment counts; no per-row relationship queries.
- Detail uses one email graph with `selectinload` for attachments, documents, extractions/fields, events, reviews, plus bounded bulk queries for comparisons and AI audit rows.
- GET endpoints serialize persisted rows only; they never call readers, OCR, extractors, resolvers, or comparison services.
- Legacy `/api/*` endpoints remain unchanged; v1 is the product contract.
- Product GET routes still compose persisted rows only; they never call readers, OCR, extractors, resolvers, or comparison services. The checkpoint migration is the only Phase R persistence addition.

## Intentionally omitted

- No React/dashboard or Outlook UI.
- No reviewer mutation/action endpoint; the current requirements define read-only product exposure and reprocess only for technical failures.
- No provider credentials or live Microsoft Graph polling implementation; the Graph adapter remains isolated, while the generic worker operates with static-bundle and Organizer HTTP sources.
