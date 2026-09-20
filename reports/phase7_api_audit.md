# Phase 7 Product API Audit

**Date:** 2026-09-20
**Inherited state:** local `phase6` tip `f38b42d27ecc8e63a1dc5e972c24043d2ee058ac` (the configured remote feature branch is stale at `a415000`; fetch was unavailable in this environment)

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
- `POST /api/v1/emails/{id}/reprocess`: bounded technical-failure reprocess control where the source adapter can be reconstructed.
- `scripts/demo_phase7.py`: live API walkthrough using the static bundle for persisted comparison scenarios and incoming API for new-message scenarios.
- Microsoft Graph adapter skeleton remains isolated behind `EmailSource` and has no credentials.

## Query strategy and compatibility

- Queue rows use aggregate/window subqueries for latest classification/comparison/review and attachment counts; no per-row relationship queries.
- Detail uses one email graph with `selectinload` for attachments, documents, extractions/fields, events, reviews, plus bounded bulk queries for comparisons and AI audit rows.
- GET endpoints serialize persisted rows only; they never call readers, OCR, extractors, resolvers, or comparison services.
- Legacy `/api/*` endpoints remain unchanged; v1 is the product contract.
- No migration is required because Phase 0–6 persistence already contains the needed product data.

## Intentionally omitted

- No React/dashboard or Outlook UI.
- No reviewer mutation/action endpoint; the current requirements define read-only product exposure and reprocess only for technical failures.
- No provider credentials or live Graph polling implementation; only a provider-isolated adapter contract skeleton.
