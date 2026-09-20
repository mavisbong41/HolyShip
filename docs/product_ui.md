# Product UI

The current product UI work adds the web Dashboard only.

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
- Human Review read-only queue

The Dashboard consumes only persisted backend product API data. It does not classify emails, compare SI/BL values, normalize values, infer review reason, or call OCR/LLM.

## Deferred

- Outlook Add-in
- Human Review write/actions workflow
- Correct-field workflow
- Replacement SI/BL upload
- Production authentication
- Production Graph identity linkage
