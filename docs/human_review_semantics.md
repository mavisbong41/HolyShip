# Human Review Semantic Contract

Part 1 establishes one deterministic presentation contract for Dashboard and future Outlook use.

## Contract

`internal truth → title → explanation → affected area → suggested action → semantic style`

The authoritative backend mapping is `backend/app/api/presentation.py`. Product APIs expose the mapped fields so clients do not maintain independent reason-code wording.

## Rules

- `AWAITING_DOCUMENTS` is a processing state, not Human Review.
- Technical `FAILED` means Processing Failed / Retry / Reprocess.
- `OPEN` means Needs Review.
- `IN_REVIEW` means Being Reviewed.
- `RESOLVED` means Review Completed.
- `DISMISSED` means Review Dismissed.
- Legacy cases are Historical review records and are not actionable.
- Email/document-level issues use an affected area; they must not be presented as `0 affected fields`.
- Technical reason codes may remain in audit/diagnostic details, but are not primary user-facing copy.

## Metrics

Dashboard email metrics are email-level unless explicitly labelled otherwise. Human Review analytics are review-case-level. Comparison mismatch and unresolved summary metrics count emails with at least one affected field.

The reconciliation endpoint `/api/v1/human-review-reconciliation` reports persisted processing-status counts, active/legacy review counts, and email-level mismatch/unresolved counts for debugging and audit.

## Cross-surface reuse

Outlook must consume these API presentation fields or the same deterministic mapping. It must not create a second reason-code wording table.
