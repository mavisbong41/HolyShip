# Product UI

The official product clients are the React Dashboard and Outlook Add-in. The
2026-09-21 owner scope decision also activates the Dashboard Human Review
workflow; see `scope_decisions/2026-09-21-ui-human-review.md`.

## Design Direction

The visual system uses:

- Averis-inspired orange accent
- white surfaces
- grey background and borders
- black/charcoal text and navigation

The style is operational and dashboard-first: dense enough for repeated work, but with soft white panels and restrained orange accents inspired by the provided reference images.

## Dashboard Structure

- Overview
- Email Queue
- Email Detail panel
- Human Review actionable queue, detail, corrections, lifecycle actions, and audit timeline

The Dashboard consumes only persisted backend product API data. It does not classify emails, compare SI/BL values, normalize values, infer review reason, or call OCR/LLM.

The Outlook Add-in remains a compact current-email companion, not a second
Dashboard. It shows the selected email's HolyShip state, compact SI vs Draft BL
comparison, active or historical Human Review context, concise AI explanation
when available, Retry/Reprocess for technical failures, and deep links back to
the Dashboard.

Outlook opens the selected backend email in the Dashboard with `?email=<id>`.
The Dashboard resolves that exact ID through the product API and supports
`?review=<id>` for Human Review and AI Review navigation.

Dashboard and Outlook use the same user-facing semantic mapping:

- `CLASSIFICATION_UNRESOLVED` -> `Email type unclear`
- `COMPARISON_UNRESOLVED` -> `One or more document fields could not be verified`
- `DOCUMENT_ROLE_UNRESOLVED` -> `Document role unclear`
- `MISSING_REQUIRED_ATTACHMENT` -> `Required shipping document is missing`
- `AWAITING_DOCUMENTS` -> `Waiting for Documents`
- `BLOCKED` -> `Needs Review`
- `FAILED` -> `Processing Failed`
- legacy Human Review records -> `Historical review record`

Cases not tied to one of the seven comparison fields are shown as
`Email-level issue` or `Document-level issue`, never as `0 affected field(s)`.

## Deferred

- Replacement SI/BL upload
- Production authentication
- Production Graph identity linkage
