# HolyShip Requirements — Part 2
## HolyShip AI Review Assistant + Dashboard AI Workflow

**Owner mission:** Add a grounded AI assistant on top of the completed Human Review workflow. AI explains and suggests; humans decide.

**Dependency:** Build against the completed Part 1 Human Review contracts. Do not reimplement Part 1.

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

# 1. Product Definition

Feature name:

# **HolyShip AI Review Assistant**

It is not a generic chatbot.

Core behavior:

```text
Explain
→ Ground in current persisted evidence
→ Suggest only when safe
→ Human decides
→ Existing Human Review override flow
→ Resolve & Recompare
```

---

# 2. Context Boundary

The assistant should receive only necessary current-case context.

Possible context:
- current email;
- classification;
- processing status;
- readiness;
- SI/BL document metadata;
- seven extracted fields;
- raw/canonical values;
- evidence;
- source location;
- confidence;
- comparison result;
- Human Review reason;
- existing overrides;
- relevant timeline.

Do not send the whole database by default.

---

# 3. Supported Questions

Examples:
- Why is this case blocked?
- Why does this need Human Review?
- Which fields should I check first?
- Where did this value come from?
- Why are these two ports different?
- What does UNRESOLVED mean?
- Which document is the SI?
- Summarize this case.
- Explain the gross weight mismatch.
- Can you suggest the correct BL gross weight?

Answers must use the Part 1 user-friendly terminology, not raw backend codes.

---

# 4. Structured AI Response

Never parse free-form prose and directly execute it.

Supported modes:
- `EXPLANATION_ONLY`
- `ACTIONABLE_SUGGESTION`
- `INSUFFICIENT_EVIDENCE`

Conceptual contract:

```json
{
  "message": "The BL value likely contains an OCR error.",
  "mode": "ACTIONABLE_SUGGESTION",
  "suggestion": {
    "action": "FIELD_OVERRIDE",
    "document_side": "BL",
    "field": "gross_weight_kg",
    "current_value": "22,O00 KG",
    "suggested_value": "22000",
    "confidence": 0.94,
    "reason": "Possible O/0 OCR confusion",
    "evidence_refs": []
  }
}
```

Backend validation must reject unknown fields, document sides, actions, invalid payloads, or evidence-free actionable suggestions.

---

# 5. Allowed Actionable Fields

AI may suggest an override only for:

- `shipper`
- `consignee`
- `notify_party`
- `port_of_loading`
- `port_of_discharge`
- `container_count`
- `gross_weight_kg`

Anything else must be explanation-only or rejected.

---

# 6. Accept / Edit / Dismiss

## Accept

Required flow:

```text
AI Suggestion
→ Human Preview
→ Accept
→ HumanReviewFieldOverride
→ Resolve & Recompare
→ New ComparisonResult
```

Never update original extraction.

Record AI-assisted provenance.

## Edit Before Applying

Reviewer can modify the proposed value.

Audit must preserve:
- AI-proposed value;
- reviewer-applied value;
- reviewer label;
- timestamp;
- note when supplied.

## Dismiss Suggestion

This dismisses only the AI suggestion.

It must not dismiss the Human Review case.

---

# 7. Safety Gate

Actionable suggestions require sufficient evidence.

Use `EXPLANATION_ONLY` / `INSUFFICIENT_EVIDENCE` for cases such as:
- missing required attachment;
- no BL;
- wrong document type;
- unavailable source evidence;
- severe entity ambiguity;
- conflicting evidence without safe resolution;
- unsupported field.

Do not fabricate a shipment value simply to finish the workflow.

Explicit uncertainty is preferred.

---

# 8. Dashboard AI Assistant UI

Dashboard remains the full AI workspace.

Human Review detail may contain:

```text
HolyShip AI Review Assistant
├── Suggested questions
├── Chat
├── Evidence-grounded explanation
└── Structured suggestion card
    ├── Current value
    ├── Suggested value
    ├── Reason
    ├── Confidence
    ├── Evidence
    ├── Accept
    ├── Edit Before Applying
    └── Dismiss Suggestion
```

The suggestion preview must make clear:
- original value remains preserved;
- accepting creates a review override;
- comparison will be re-run;
- action is audited.

Do not use a visually separate “AI product” style. It must look native to HolyShip.

---

# 9. AI Audit Events

Add auditable events such as:

- `AI_ASSISTANT_ASKED`
- `AI_SUGGESTION_CREATED`
- `AI_SUGGESTION_ACCEPTED`
- `AI_SUGGESTION_EDITED`
- `AI_SUGGESTION_DISMISSED`

Store where appropriate:
- case;
- field;
- document side;
- suggested value;
- applied value;
- confidence;
- evidence refs;
- safe provider/model metadata;
- reviewer label;
- timestamp.

Never store provider credentials.

---

# 10. Provider Architecture

Use a provider abstraction.

Concept:

```text
AIReviewProvider
├── DisabledProvider
└── ConfiguredProvider / HTTPProvider
```

Requirements:
- disabled by default unless configured;
- timeout;
- bounded calls;
- structured output validation;
- no automatic apply;
- provider failure must not break Human Review;
- avoid provider-specific logic scattered throughout UI.

Potential providers can include Gemini, Claude, OpenAI, DeepSeek, or a generic HTTP provider.

---

# 11. Failure Handling

Safely handle:
- provider unavailable;
- timeout;
- invalid JSON;
- invalid schema;
- unknown field;
- unsupported action;
- evidence-free suggestion;
- invalid document side;
- empty response.

Required principle:

```text
AI unavailable
≠
Human Review unavailable
```

Users must still be able to manually review and resolve cases.

---

# 12. AI + User-Friendly Mapping

The assistant must use the same user-facing terms established in Part 1.

Bad:

```text
COMPARISON_UNRESOLVED due to Stage 2 candidate conflict
```

Good:

```text
Gross weight could not be verified.

The BL value may contain an OCR character error.
```

Technical codes may appear only in an optional diagnostic view.

---

# 13. Tests

Cover at least:
- explanation-only response;
- actionable suggestion;
- insufficient evidence;
- invalid structured response;
- unsupported field;
- missing evidence;
- Accept;
- Edit Before Applying;
- Dismiss Suggestion;
- audit event persistence;
- provider timeout;
- provider unavailable;
- AI disabled;
- Human Review still works when AI fails;
- original extraction remains unchanged;
- new comparison version is created after accepted override.

Dashboard:
- AI loading;
- answer;
- structured card;
- accept;
- edit;
- dismiss;
- error;
- empty/no-suggestion states.

---

# 14. Definition of Done

Part 2 is done only when:

- AI explains current cases using persisted evidence;
- unsafe cases do not produce actionable suggestions;
- suggestions are structured and backend-validated;
- human approval is mandatory;
- Accept/Edit uses existing Human Review override + recompare flow;
- audit provenance exists;
- provider failure does not break Human Review;
- Dashboard AI UI is consistent with HolyShip design;
- all relevant tests/typechecks/builds pass;
- `make check-fast` passes;
- `make check PHASE=F` passes;
- `git diff --check` passes.

Do not work on self-evaluation in this part.
