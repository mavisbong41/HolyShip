# HolyShip Requirements — Part 3
## Outlook Add-in + Cross-Surface UX Consistency + Final Product Integration

**Owner mission:** Make the Outlook Add-in a clear, compact HolyShip companion and ensure Dashboard + Outlook use the same user-facing language, semantics, and visual system.

**Dependencies:**
- Consume Part 1 user-facing mappings and Human Review contracts.
- Consume Part 2 AI assistant APIs when available.
- Do not duplicate their backend logic.

# Common HolyShip Rules

Baseline:
- Branch lineage: `codex/ui-human-review-stabilization`
- Stable baseline commit: `144ff56174f46c3a37d2369d6a749dc6254433f8`

These requirements are additive. Do not rewrite stable classification, extraction, comparison, submission, or Human Review semantics unless fixing a verified defect.

## Agent workflow
A full-system walkthrough is required only once at the beginning of a new chat / agent session. After that, reuse the established system understanding and inspect only the files relevant to each follow-up change.

At the first task in a new chat/session:
1. Check `git status`, current branch, HEAD, diff and migration head.
2. Read the relevant HolyShip authority/docs.
3. Walk through the current end-to-end flow once.
4. Map backend / DB / API / Dashboard / Outlook responsibilities.
5. Classify requested areas as `COMPLETE`, `PARTIAL`, or `MISSING`.
6. Change only `PARTIAL` / `MISSING` areas.

For later prompts in the same chat/session:
- do not repeat the full walkthrough;
- re-check Git state;
- inspect only relevant modules;
- continue incrementally.

## Core invariants
- Original extraction/evidence is immutable.
- Historical comparison results are immutable.
- Human Review corrections are separate overrides.
- Resolve & Recompare creates a new comparison result.
- `AWAITING_DOCUMENTS` is not Human Review.
- Technical `FAILED` is Retry/Reprocess, not Human Review by default.
- AI must never directly mutate raw extraction or historical comparison data.
- No email-ID, filename, participant, ground-truth, `data_v2`, or score-specific logic.
- Do not commit secrets or local DB files.

## Mandatory UI design consistency
Read `docs/ui_design_system.md` before UI changes.

Reuse the existing HolyShip design language:
- charcoal/orange brand identity;
- existing typography;
- spacing scale;
- radius/shadows;
- buttons;
- badges/status chips;
- inputs;
- cards/tables;
- loading/error/empty states;
- focus/keyboard treatment;
- icon language;
- terminology.

Dashboard and Outlook do not need identical layouts, but they must share the same semantic meaning, labels, colors and button hierarchy.

Do not introduce a second “AI design system” such as purple gradients, neon glow, different typography, arbitrary radii, or unrelated chat styling.

Before completing a UI phase, report:
- Brand palette consistent: YES/NO
- Typography consistent: YES/NO
- Spacing consistent: YES/NO
- Radius/shadows consistent: YES/NO
- Button hierarchy consistent: YES/NO
- Status colors consistent: YES/NO
- Priority treatment consistent: YES/NO
- Human Review terminology consistent: YES/NO
- Comparison terminology consistent: YES/NO
- Dashboard/Outlook semantic mappings consistent: YES/NO
- Loading/error/empty states consistent: YES/NO
- Keyboard/focus behavior consistent: YES/NO

Fix every `NO` before completion.


---

# 1. Outlook Product Role

Product principle:

```text
Dashboard = Full operational workspace
Outlook Add-in = Compact current-email companion
```

Do not shrink the entire Dashboard into Outlook.

Outlook should prioritize:
- current email;
- current HolyShip processing state;
- concise comparison;
- current Human Review status;
- clear problem explanation;
- key next action;
- compact AI explanation;
- deep link into Dashboard.

---

# 2. User-Friendly Mapping Is Mandatory in Outlook

This is a hard requirement.

The Outlook Add-in must not expose raw backend/diagnostic wording as primary UI.

Do not show normal users text such as:

```text
Classification unresolved after Stage 2.
Candidates: {...probabilities...}
Original conflict: Mixed body intent...
COMPARISON_UNRESOLVED
DOCUMENT_ROLE_UNRESOLVED
HISTORICAL LEGACY CASE
0 affected field(s)
```

Use the same semantic mapping established by Part 1.

Examples:

```text
CLASSIFICATION_UNRESOLVED
→ Email type unclear
```

```text
COMPARISON_UNRESOLVED
→ One or more document fields could not be verified
```

```text
MISSING_REQUIRED_ATTACHMENT
→ Required shipping document is missing
```

```text
legacy/historical review
→ Historical review record
```

If a case is not tied to one of the seven fields, show:
- `Email-level issue`
- `Document-level issue`
- or the correct affected area

Do not display `0 affected field(s)` when that wording is misleading.

Technical diagnostic information may be behind an expandable details area, not the primary card content.

---

# 3. Outlook Human Review Card

A review card should answer quickly:

```text
What is wrong?
Why?
What is affected?
What should I do?
```

Suggested structure:

```text
Email type unclear

HolyShip found mixed signals in this email and could not confidently determine
whether it is asking for a document comparison.

Affected area
Email intent

Suggested action
Open Human Review and confirm the email type.

[Open Review]
```

For field-level issues:

```text
Gross weight could not be verified

Affected field
Gross Weight

[Open Review]
```

---

# 4. Historical Cases

Historical/legacy Human Review must not look actionable.

Instead of:

```text
OPEN
COMPLETED
HISTORICAL LEGACY CASE
```

prefer:

```text
Completed
Historical review record
No action required
```

Preserve raw legacy status only in technical/audit details.

---

# 5. Compact Comparison Experience

Outlook should retain a compact seven-field comparison representation.

Required semantics:
- Match
- Mismatch
- Unresolved

Use the same labels/color meaning as Dashboard.

Show real totals, not fabricated summary counts.

Do not make users horizontally scan a desktop-sized comparison table.

---

# 6. Current Email States

Provide clear states for:

- Not in HolyShip
- Processing
- Completed
- Waiting for Documents
- Needs Review
- Processing Failed

Use the Part 1 user-friendly mapping.

Each state should provide the next useful action where appropriate.

Examples:

```text
Waiting for Documents
HolyShip is waiting for the required shipping document before comparison can begin.
```

```text
Processing failed
HolyShip could not finish processing this email.
[Retry / Reprocess]
```

---

# 7. Outlook AI Companion

Outlook gets a compact AI companion, not the full Dashboard assistant.

Permitted:
- Ask a concise question about current email/case;
- show concise grounded explanation;
- indicate when a suggestion is available;
- deep-link to full AI Review in Dashboard.

Recommended action:

**Open AI Review**

Complex multi-field editing / full evidence inspection / full chat history should remain in Dashboard unless explicitly approved later.

If an actionable AI suggestion exists, Outlook can summarize it, e.g.:

```text
AI suggestion available
Gross Weight may contain an OCR error.

[Open AI Review]
```

Do not silently apply it from Outlook.

---

# 8. Deep Links

Preserve and verify:

- `?email=<id>`
- `?review=<id>`

For AI workflow, use the existing review deep link or an explicitly documented extension if necessary.

Refresh/direct URL behavior must remain stable.

Invalid IDs must fail gracefully.

---

# 9. Cross-Surface Semantic Consistency

Dashboard and Outlook must use the same user-facing meaning for:

## Comparison
- Match
- Mismatch
- Unresolved

## Processing
- Completed
- Waiting for Documents
- Needs Review
- Processing Failed

## Human Review
- Needs Review
- Being Reviewed
- Review Completed
- Review Dismissed
- Historical Review Record

## Priority
- High
- Medium
- Low

Do not use different words for the same state unless there is a documented UX reason.

---

# 10. Shared Mapping Contract

Do not duplicate dozens of hard-coded strings separately in Outlook if a shared contract/API mapping already exists.

Prefer consuming:
- shared constants/module;
- shared API presentation fields;
- shared deterministic mapping definitions.

Goal:

```text
One internal condition
→ one user-facing meaning
→ Dashboard and Outlook render it consistently
```

---

# 11. UI Design Consistency

Outlook must use the existing charcoal/orange HolyShip system.

Consistency applies to:
- typography;
- spacing;
- radii;
- buttons;
- status chips;
- icon treatment;
- loading/error/empty states;
- focus;
- semantic colors.

Different density is allowed because Outlook is narrow.

Do not introduce:
- new color language;
- unrelated chat bubble style;
- new badge semantics;
- inconsistent button priority;
- arbitrary one-off spacing/radii.

---

# 12. Runtime / Host States

The task pane must fail gracefully when Office context is unavailable.

Browser/dev preview may show a clear message such as:

```text
Office context is not available.
Run inside an Outlook Add-in environment.
```

Inside Outlook, verify that:
- Office context initializes;
- current email identity can be resolved;
- backend failure does not create a blank pane;
- missing HolyShip email shows a purposeful Not in HolyShip state;
- API errors show a recoverable error state.

Avoid white-screen failure modes.

---

# 13. Data Truth in Outlook

Outlook must display the same persisted truth as Dashboard.

Do not independently derive contradictory counts/statuses.

If the email is:
- completed with historical review history, say so clearly;
- actively blocked, show Needs Review;
- awaiting documents, do not show active Human Review;
- failed technically, show Retry/Reprocess.

Do not let historical `OPEN` override the current email processing state in user-facing presentation.

---

# 14. Final Cross-Surface Audit

Before completion, compare Dashboard and Outlook side by side.

Audit:
- same case shows same current processing meaning;
- same reason shows same user-friendly title;
- same priority uses same semantic treatment;
- same comparison result uses same meaning;
- active vs historical review is consistent;
- no raw backend codes leak into primary UI;
- no `0 affected fields` for email/document-level issues;
- deep links open the correct item/review;
- AI terminology is consistent;
- loading/error/empty states feel like the same product.

---

# 15. Documentation / Demo Integration

Update relevant docs to explain:

```text
Dashboard = full workspace
Outlook = compact companion
```

Document the user-friendly mapping strategy and cross-surface semantic rules.

Prepare Outlook for these demo states:
1. Not in HolyShip
2. Processing
3. Completed
4. Waiting for Documents
5. Needs Review
6. Processing Failed
7. Historical review record
8. AI explanation available
9. Open Review deep link
10. Open AI Review deep link

Do not perform official self-evaluation in this part.

---

# 16. Tests

Cover:
- every key Outlook state;
- user-friendly mapping;
- active vs historical review;
- non-field-specific affected area;
- compact comparison status;
- deep links;
- AI explanation/AI Review link;
- Office context unavailable;
- backend/API error;
- Not in HolyShip;
- retry/reprocess;
- typecheck/build.

---

# 17. Definition of Done

Part 3 is done only when:

- Outlook no longer exposes confusing backend wording as primary UI;
- Outlook consumes the same semantic mapping as Dashboard;
- historical cases are clearly non-actionable;
- current email state is truthful;
- AI companion is compact and grounded;
- complex editing stays in Dashboard;
- deep links work;
- no blank/white-screen failure for expected runtime errors;
- full UI consistency audit is green;
- Outlook tests/typecheck/build pass;
- Dashboard is not visually/semantically regressed;
- `make check-fast` passes;
- `make check PHASE=F` passes;
- `git diff --check` passes.

Do not work on official self-evaluation in this part.
