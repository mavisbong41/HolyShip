# Dashboard API Contract

The Dashboard consumes the verified backend product API under `/api/v1`. It does not call legacy `/api/*` routes.

## `GET /api/v1/summary`

Returns:

- `total_emails`
- `status_counts`
- `needs_review_count`
- `comparison_ready_count`
- `mismatch_count`
- `unresolved_count`

## `GET /api/v1/emails`

Returns `{ items, total, skip, limit }`.

Supported filters:

- `status`
- `category`
- `comparison_readiness`
- `needs_review`
- `review_status`
- `comparison_state`
- `has_mismatch`
- `search`
- `received_from`
- `received_to`
- `skip`
- `limit`

Queue item fields:

- `id`
- `external_message_id`
- `source_type`
- `sender`
- `subject`
- `received_at`
- `created_at`
- `processing_status`
- `attachment_count`
- `category`
- `classification_confidence`
- `comparison_readiness`
- `comparison_state`
- `mismatch_count`
- `unresolved_count`
- `needs_review`
- `review_status`
- `review_reason`

## `GET /api/v1/emails/{email_id}`

Returns unified detail:

- `email`
- `body`
- `recipients`
- `content_hash`
- `attachments`
- `classification`
- `documents`
- `comparison`
- `timeline`
- `review`
- `resolutions`

Comparison fields are rendered in the backend canonical order:

1. `shipper`
2. `consignee`
3. `notify_party`
4. `port_of_loading`
5. `port_of_discharge`
6. `container_count`
7. `gross_weight_kg`

The Dashboard uses backend field status only:

- `MATCH`
- `MISMATCH`
- `UNRESOLVED`

It never performs local SI-vs-BL comparison.

## `GET /api/v1/human-review`

Returns read-only `{ items, total, skip, limit }`.

Review item fields include:

- `id`
- `email_id`
- `email`
- `document_id`
- `field`
- `reason_code`
- `reason_text`
- `status`
- `confidence`
- `evidence`
- `comparison`
- `resolutions`
- `created_at`

## `GET /api/v1/events`

Returns polling-compatible events:

- `event`
- `email_id`
- `status`
- `category`
- `mismatch_found`
- `updated_at`
- `reason_code`

## Enums

Categories:

- `document_comparison`
- `new_si_request`
- `invoice_query`
- `general_message`
- `spam`

Processing statuses:

- `NEW`
- `QUEUED`
- `CLASSIFYING`
- `CLASSIFIED`
- `AWAITING_DOCUMENTS`
- `RETRIEVING_ATTACHMENTS`
- `EXTRACTING`
- `COMPARING`
- `COMPLETED`
- `BLOCKED`
- `FAILED`

Comparison readiness:

- `READY_FOR_COMPARISON`
- `AWAITING_DOCUMENTS`
- `UNRESOLVED`

Comparison states:

- `COMPLETED`
- `BLOCKED`

Field statuses:

- `MATCH`
- `MISMATCH`
- `UNRESOLVED`
