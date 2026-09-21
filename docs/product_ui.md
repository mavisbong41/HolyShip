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

The Outlook Add-in remains a presentation client and opens the selected backend
email in the Dashboard with `?email=<id>`. The Dashboard resolves that exact ID
through the product API and supports `?review=<id>` for review navigation.

## Deferred

- Replacement SI/BL upload
- Production authentication
- Production Graph identity linkage
