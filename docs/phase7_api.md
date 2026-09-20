# Phase 7 Product API

The product contract is served under `/api/v1`. Legacy `/api/*` routes remain
available for compatibility.

## Queue and summary

`GET /api/v1/emails` returns `{items,total,skip,limit}`. Each queue item has
email identity, sender/subject/time, attachment count, processing status,
latest category/confidence, comparison readiness/state, mismatch and
unresolved counts, and a deterministic review flag. Supported query filters:

```text
status, category, comparison_readiness, needs_review, review_status,
comparison_state, has_mismatch, search, received_from, received_to, skip, limit
```

`GET /api/v1/summary` returns aggregate totals and counts by persisted
processing status, plus review, comparison-ready, mismatch, and unresolved
case counts.

## Unified detail

`GET /api/v1/emails/{email_id}` is the frontend-ready detail response;
`/detail` is an explicit alias. It contains the original email metadata/body,
attachments and retrieval state, latest classification, validated documents,
reader/extraction state, raw/canonical extracted values, processing timeline,
review context, and Phase 6 resolution provenance. Comparison fields are
returned in canonical order:

```text
shipper, consignee, notify_party, port_of_loading, port_of_discharge,
container_count, gross_weight_kg
```

Each persisted comparison preserves `MATCH`, `MISMATCH`, or `UNRESOLVED`, SI
and BL values separately, normalized values, reason code, and persisted
evidence. `BLOCKED` remains a comparison state and is never rewritten as a
mismatch. Partial processing returns null/empty sections rather than fake
results.

## Review and updates

`GET /api/v1/human-review` and `/api/v1/human-review/{review_id}` provide a
reviewer-ready read-only queue/detail composition. No review decision mutation
is added in this phase. `GET /api/v1/events` is a polling-compatible feed of
persisted processing events shaped as `EMAIL_PROCESSING_UPDATED` records.

AI request payloads, prompts, API keys, authorization headers, and cache
identities are not exposed. Authentication is not implemented; it remains
outside the Phase 7 scope and must be supplied by the deployment boundary.
