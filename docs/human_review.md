# Human Review workflow

Human Review handles business-resolvable blocked conditions. It is not a catch-all for every non-completed email.

```text
BLOCKED reviewable condition
        |
        v
HumanReviewCase OPEN
        |
        v
Reviewer inspects email, SI/BL documents, and seven fields
        |
        +--> separate field override (original extraction stays immutable)
        |
        v
Resolve & Recompare
        |
        +--> all fields definite -> COMPLETED / case RESOLVED
        |
        `--> still unresolved -> BLOCKED / case remains IN_REVIEW
```

`AWAITING_DOCUMENTS` means the workflow is legitimately waiting for a future document and does not create a review case. Ordinary technical `FAILED` states use the retry/reprocess endpoint and also do not create cases by default.

## Persistence and audit

- `human_review_cases` stores lifecycle state (`OPEN`, `IN_REVIEW`, `RESOLVED`, `DISMISSED`), a stable workflow identity, reviewer-supplied name, notes, resolution, and source comparison identity.
- `human_review_field_overrides` stores SI/BL corrections separately from immutable `extracted_fields`; replacing a correction supersedes rather than overwrites the earlier row.
- `human_review_events` stores immutable case actions in chronological order.
- a review recomparison creates a new `comparison_results` row linked to both the case and the comparison it supersedes.
- reviewer names are explicit labels supplied by the caller; the current project has no authentication system and does not present them as verified identities.

## API

```text
GET  /api/v1/human-review
GET  /api/v1/human-review/{review_id}
POST /api/v1/human-review/{review_id}/claim
POST /api/v1/human-review/{review_id}/overrides
POST /api/v1/human-review/{review_id}/resolve
POST /api/v1/human-review/{review_id}/dismiss
```

All mutation endpoints return the freshly persisted review detail. Conflicting lifecycle actions return HTTP 409 and invalid corrections return HTTP 422.
