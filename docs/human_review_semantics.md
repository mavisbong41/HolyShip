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


## Metric truth table

| Metric | Persisted source | Population/filter | Unit | Overlap / timestamp basis |
| --- | --- | --- | --- | --- |
| Total emails | `email_messages` | all persisted emails | email | exhaustive population |
| Processing status counts | `email_messages.processing_status` | grouped by current persisted status | email | mutually exclusive current status |
| Needs Review | active Human Review + current blocked business state | ACTIVE `OPEN` / `IN_REVIEW`; legacy excluded; technical `FAILED` and `AWAITING_DOCUMENTS` excluded | email | operational attention bucket; may overlap a BLOCKED processing state |
| Human Review Open / In Review / Resolved / Dismissed | `human_review_cases` | `case_origin=ACTIVE` only | review case | lifecycle buckets are mutually exclusive |
| Resolved today | `human_review_cases.resolved_at` | ACTIVE + RESOLVED, UTC calendar day | review case | timestamp basis: `resolved_at` |
| Average current open age | `human_review_cases.created_at` | ACTIVE + OPEN only | review case age in minutes | current UTC time minus `created_at` |
| Priority distribution | active Human Review cases | deterministic priority mapping from reason/affected fields | review case | ACTIVE only |
| Reason distribution | `human_review_cases.reason_code` | ACTIVE only | review case | internal code grouped for analytics |
| Most reviewed fields | Human Review + comparison evidence | ACTIVE only | affected-field occurrence | field-level; not an email count |
| Most corrected fields | active field overrides joined to Human Review | ACTIVE case + active override only | corrected-field occurrence | field-level |
| Emails with mismatch | latest persisted comparison per email | at least one persisted MISMATCH | email | email-level, never total mismatch fields |
| Emails with unresolved fields | latest persisted comparison per email | at least one persisted UNRESOLVED field | email | email-level |

Summary processing cards must not be interpreted as an exhaustive partition when the operational Needs Review/Blocked attention bucket overlaps processing status. The reconciliation diagnostic is the source of truth for explaining persisted totals and overlap.


## Part 1 completion checklist

- Human Review priority, explanation, affected area, age, reviewer and claimed-at are persisted/derived from backend truth.
- Original extraction and historical comparison evidence remain immutable; corrections are separate overrides.
- Resolve & Recompare creates a new comparison result; dismiss remains a distinct audited decision.
- Awaiting Documents and technical Failed remain outside actionable Human Review.
- ACTIVE OPEN/IN_REVIEW cases are actionable; LEGACY records are audit-only and read-only.
- Queue filtering/sorting operates over the complete paginated review population.
- Analytics and reconciliation use persisted records only and document their units/populations.
- User-facing presentation fields are centralized in `backend/app/api/presentation.py` for Dashboard/Outlook reuse.
- Technical codes remain secondary audit metadata rather than primary product copy.
- Part 1 does not add AI assistant behavior or evaluator/private-data dependencies.
