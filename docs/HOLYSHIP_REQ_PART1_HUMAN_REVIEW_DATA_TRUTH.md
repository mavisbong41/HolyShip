# HolyShip Requirements — Part 1
## Human Review Product Completion + Data Truth + User-Friendly Mapping

**Owner mission:** Make Human Review understandable, operationally correct, and backed by reconciled persisted data before AI is added.

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

# 1. Scope

This owner is responsible for:

1. Human Review product completion
2. Human Review intelligence/analytics
3. Shared user-facing terminology mapping
4. Dashboard summary/data reconciliation
5. Human-readable problem presentation
6. Regression tests for all of the above

Do **not** implement the AI chat assistant in this part.

---

# 2. Human Review Product Completion

Audit the existing implementation first. Only fill real gaps.

Required capabilities:

- Priority:
  - `HIGH`
  - `MEDIUM`
  - `LOW`
- Human-readable “Why needs review?” explanation
- Affected-field / affected-area summary
- Review age
- Queue sorting:
  - Priority
  - Oldest
  - Newest
- Reviewer name
- Claimed-at timestamp when available
- Original / Reviewed / Effective values
- Recomparison result
- Clear distinction between:
  - Resolve
  - Dismiss
  - Retry
  - Awaiting Documents

Priority must be deterministic and generalizable.

Allowed signals may include:
- unresolved field count;
- mismatch + unresolved combination;
- multiple affected fields;
- `gross_weight_kg`;
- `container_count`;
- wrong/unreadable document conditions.

Forbidden:
- email IDs;
- filenames;
- participant IDs;
- private organizer data;
- scoreboard results.

---

# 3. Human Review Routing Semantics

Preserve these rules.

Human Review can be created for human-resolvable business ambiguity such as:
- unresolved comparison;
- document-role ambiguity;
- wrong document type;
- unreadable attachment when a human can help;
- multiple candidates;
- readiness ambiguity.

Do not route:
- `AWAITING_DOCUMENTS` into Human Review;
- ordinary technical `FAILED` into Human Review.

---

# 4. Human Review Analytics

Using real persisted data only, support:

- Open
- In Review
- Resolved
- Dismissed
- Resolved today
- Average current open age
- Priority distribution
- Review reason distribution
- Most reviewed fields
- Most corrected fields

Correction insights may include only evidence-backed categories such as:
- OCR ambiguity
- Missing extraction
- Value normalization
- Entity ambiguity
- Manual source confirmation

These analytics must never automatically change:
- extraction rules;
- aliases;
- classification;
- L0/L1;
- future cases.

No fabricated counts, percentages, SLA values, or placeholder metrics.

---

# 5. Mandatory User-Friendly Mapping Layer

Internal enums, reason codes, pipeline stages and diagnostic strings must not be the primary text shown to normal users.

Create or reuse one shared presentation mapping layer.

Concept:

```text
Internal truth
→ shared deterministic mapping
→ user-facing title
→ short explanation
→ affected area
→ suggested action
→ semantic style
```

Do not maintain separate wording independently in Dashboard and Outlook. Part 3 must consume the same semantic contract.

Examples:

| Internal / Technical | User-facing meaning |
|---|---|
| `CLASSIFICATION_UNRESOLVED` | **Email type unclear** |
| `Stage 2 unresolved` | **HolyShip could not confidently determine what this email is asking for** |
| `COMPARISON_UNRESOLVED` | **One or more document fields could not be verified** |
| `COMPARISON_MISMATCH` | **The SI and BL contain different values** |
| `DOCUMENT_ROLE_UNRESOLVED` | **HolyShip could not confidently identify which document is the SI or BL** |
| `WRONG_DOCUMENT_TYPE` | **The attached file does not appear to be the required document** |
| `MISSING_REQUIRED_ATTACHMENT` | **A required shipping document is missing** |
| `UNREADABLE_ATTACHMENT` | **The attached document could not be read reliably** |
| `MULTIPLE_CANDIDATES` | **More than one document may match the required role** |
| `READINESS_UNRESOLVED` | **HolyShip is unsure whether the documents are ready for comparison** |
| `AWAITING_DOCUMENTS` | **Waiting for required documents** |
| `FAILED` | **Processing failed — retry required** |
| `BLOCKED` | **Needs attention before processing can continue** |
| `OPEN` | **Needs review** |
| `IN_REVIEW` | **Being reviewed** |
| `RESOLVED` | **Review completed** |
| `DISMISSED` | **Review dismissed** |
| legacy/historical case | **Historical review record** |

Raw technical probabilities, internal reason codes and pipeline diagnostics may remain available behind:
- Technical details
- Why?
- View diagnostics

They must not dominate the normal user experience.

---

# 6. Human-Readable Problem Presentation

Every issue should answer four questions:

```text
1. What is wrong?
2. Why does HolyShip think this?
3. What is affected?
4. What should the user do next?
```

Example:

```text
Email type unclear

Why
The email contains both document-comparison language and invoice-related language,
so HolyShip could not classify it confidently.

Affected area
Email intent

Suggested action
Confirm whether this email is asking for a document comparison.

Technical details
[Expand]
```

For non-field-level issues, do not display misleading text such as:

`0 affected field(s)`

Prefer:
- `Email-level issue`
- `Document-level issue`
- `Affected area: Email intent`

---

# 7. Historical vs Active Human Review

Historical/legacy cases must be visually and semantically distinct from active work.

A historical row with persisted legacy status `OPEN` must not look actionable.

Prefer:

```text
Historical review record
No action required
```

Internal legacy status may remain visible only in technical/audit views.

Actionable summary counts must exclude historical cases unless explicitly labeled otherwise.

---

# 8. Dashboard Data Truth & Reconciliation

The Dashboard must be mathematically explainable.

If summary cards are intended to partition current email processing states:

```text
Total
=
Completed
+ Awaiting Documents
+ Needs Review / Blocked
+ Failed
+ Currently Processing
+ any other explicitly defined bucket
```

If the cards are not exhaustive or overlap, the UI must explicitly say so.

Every metric must document:
- source table(s);
- filter conditions;
- whether ACTIVE or LEGACY review cases are included;
- email-level vs case-level unit;
- overlap/exclusivity;
- timestamp basis.

Do not mix:
- number of emails;
- number of review cases;
- number of fields;
- number of historical cases.

---

# 9. Required Reconciliation Diagnostic

Provide a developer-facing diagnostic/report that can show real persisted counts such as:

```text
Total emails

Emails by processing_status:
NEW
QUEUED
CLASSIFYING
CLASSIFIED
AWAITING_DOCUMENTS
RETRIEVING_ATTACHMENTS
EXTRACTING
COMPARING
COMPLETED
BLOCKED
FAILED

Active Human Review by status:
OPEN
IN_REVIEW
RESOLVED
DISMISSED

Historical Human Review by status

Emails with at least one MISMATCH
Emails with UNRESOLVED comparison fields
```

This can be a script, test helper, internal diagnostic endpoint, or documented SQL/report command.

Do not use private evaluator material.

---

# 10. Mismatch Metric Definition

Do not show “Mismatch = 0” unless the metric is explicitly defined and correct.

Pick and label one clear definition, e.g.:

- `Emails with at least one MISMATCH field`, or
- `Total MISMATCH fields`

Do not silently mix email-level and field-level counts.

---

# 11. Regression Tests

Add tests for:
- Human Review priority;
- explanation mapping;
- affected-area mapping;
- active vs legacy exclusion;
- summary counts;
- status reconciliation;
- email-level vs case-level semantics;
- mismatch metric definition;
- classification-unresolved user-facing mapping;
- historical-case presentation;
- non-field-specific issue display;
- queue sorting and filtering.

---

# 12. Definition of Done

Part 1 is done only when:

- Human Review is understandable without backend terminology;
- Dashboard counts reconcile against persisted data;
- active/historical review semantics are correct;
- user-friendly mapping is centralized and documented for reuse by Outlook;
- all new UI follows HolyShip design system;
- backend tests pass;
- Dashboard typecheck/tests/build pass;
- `make check-fast` passes;
- `make check PHASE=F` passes;
- `git diff --check` passes.

Do not start AI work in this part.
