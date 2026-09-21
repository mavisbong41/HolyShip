# HolyShip UI design system

HolyShip presents operational shipping-document verification with a calm, auditable visual language. The Dashboard is the full operations workbench; the Outlook Add-in is a compact companion for the currently open email.

## Foundation

- Brand: charcoal `#111111` with logistics orange `#e39439`; orange is an accent, not a generic warning.
- Background/surface: `#f6f6f4` and white, with `#dddddd` borders.
- Text: `#111111` primary, `#626262` secondary, `#9d9d9d` metadata.
- Typography: Inter/system sans; page titles 24px, section titles 13–16px, body 12–13px, metadata 10–11px, badges 10–11px.
- Spacing: 4, 8, 12, 16, 20, 24, and 32px.
- Radius: 6px small controls, 8px cards/inputs, 14px major surfaces.
- Shadow: restrained neutral shadows; state is never communicated by elevation alone.

The authoritative CSS variables are mirrored in `frontend/src/styles/tokens.css` and `outlook-addin/src/styles/tokens.css`. They intentionally use identical semantic values without introducing a cross-package build dependency.

## Semantic states

| Meaning | Label | Treatment |
| --- | --- | --- |
| Successful comparison | Match | green `#217a51` / `#e9f5ee` |
| Definite discrepancy | Mismatch | red `#ae3326` / `#fdeceb` |
| Insufficient evidence | Unresolved | amber `#9b6a00` / `#fff4d8` |
| Pipeline complete | Completed | green |
| Actionable business exception | Needs Review | review orange/brown `#8a4b16` / `#fff1df` |
| Technical failure | Processing Failed | red |
| Waiting for a required document | Awaiting Documents | blue `#216a8a` / `#e8f3f8` |
| Review lifecycle | Open / In Review / Resolved / Dismissed | review / review / green / muted |

Processing state and review state are separate. For example, `Needs Review` and `In Review` may appear together. Awaiting Documents and Processing Failed never masquerade as Human Review.

## Shared patterns

- Primary buttons perform the next safe workflow action; bordered buttons are secondary; dismiss is a separate danger-outline action.
- Badges always include a text label. Color is supporting information only.
- Tables use scoped headers, visible row focus/selection, horizontal overflow, and explicit Match/Mismatch/Unresolved labels.
- Loading uses skeletons or a labelled spinner. Empty and error states always include a title, explanation, and an action when recovery is possible.
- Internal reason/event codes remain available as muted audit metadata while visible copy uses human-readable labels.

## Product responsibilities

- Dashboard: overview, searchable inbox, full email/document detail, seven-field evidence, Human Review editing, resolve/recompare, dismiss, and complete timelines.
- Outlook Add-in: current-email identity, processing/readiness state, compact comparison summary and field cards, active review context, retry, refresh, and deep links to the Dashboard.
- Deep links remain `?email=<id>` and `?review=<id>`.
