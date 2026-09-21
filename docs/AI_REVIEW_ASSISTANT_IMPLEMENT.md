# Prompt: Implement HolyShip AI Review Assistant (Part 2)

Paste this whole document to the coding agent as the task prompt. It compresses
`README.md` (system contract) and `HOLYSHIP_REQ_PART2_AI_REVIEW_ASSISTANT.md`
(feature spec) into an actionable build plan. **AGENTS.md is the highest
authority on process/coding standards — read it first and defer to it on any
conflict with this prompt.**

---

## 0. Session Bootstrap (do this before writing any code)

1. Read `AGENTS.md` in full and follow its rules for this entire task (commit
   style, lint/format/test gates, branch policy, prohibited actions, etc.).
2. Run `git status`, confirm current branch/HEAD, `git log -1`, and check the
   Alembic migration head vs `alembic_version` in the DB.
   - Expected lineage: branch `codex/ui-human-review-stabilization`, stable
     baseline commit `144ff56174f46c3a37d2369d6a749dc6254433f8`.
3. Read `README.md` (system contract), `docs/human_review.md`,
   `docs/ui_design_system.md`, `docs/requirements_matrix.md`.
4. Walk the current end-to-end flow once (classify → readiness → extract →
   compare → Human Review) so you understand what Part 1 already provides.
5. Map current backend/DB/API/Dashboard/Outlook responsibilities and classify
   each area needed for this feature as `COMPLETE` / `PARTIAL` / `MISSING`.
6. Only implement `PARTIAL`/`MISSING` areas. **Do not rewrite or "improve"**
   stable classification, extraction, comparison, submission, or Human Review
   logic unless you find and can justify a verified defect — flag it instead
   of silently fixing it if it's out of scope.
7. For any later prompt in this same session, skip steps 2–4 (re-check git
   state only) and inspect just the modules relevant to that follow-up.

---

## 1. Feature Summary (source of truth: Part 2 spec + README §7)

Build the **HolyShip AI Review Assistant**: a context-scoped assistant bound
to a single Human Review case. It explains cases using persisted evidence and
may propose a structured, schema-validated `FIELD_OVERRIDE` suggestion. It
**never** writes to extraction or comparison tables directly. Every
actionable suggestion must pass through: AI Suggestion → Human Preview →
Accept / Edit Before Applying / Dismiss → `HumanReviewFieldOverride` →
existing Resolve & Recompare → new `ComparisonResult`.

Non-negotiable invariants (from README §26 and Part 2 "Common HolyShip
Rules"):
- Original extraction and historical comparison rows are immutable.
- AI suggestions are stored separately from source evidence, never merged in.
- No automatic apply — human approval is mandatory for every action.
- Provider failure must never break manual Human Review.
- No email-ID, filename, participant, ground-truth, `data_v2`, or
  score-specific special-casing anywhere in this feature.
- Do not commit secrets, API keys, or local DB files.
- Reuse Part 1's Human Review override + recompare endpoints; do not
  duplicate that logic inside `ai_review/`.

---

## 2. Backend Implementation

Target package: `backend/app/ai_review/` (new), wired into
`backend/app/api/` and `backend/app/storage/`.

### 2.1 Data model (Alembic migration)

Add tables consistent with README §18 ER diagram:

- `ai_suggestion` (`AISuggestionRecord`)
  - `id`, `human_review_case_id` (FK), `mode`
    (`EXPLANATION_ONLY|ACTIONABLE_SUGGESTION|INSUFFICIENT_EVIDENCE`),
    `message` (text), `document_side` (nullable: `SI|BL`), `field`
    (nullable, one of the 7 allowed fields), `current_value`,
    `suggested_value`, `confidence` (nullable float), `reason`,
    `evidence_refs` (JSON array), `provider_name`, `provider_model`
    (safe metadata only — **never** store API keys/credentials),
    `status` (`PENDING|ACCEPTED|EDITED_APPLIED|DISMISSED`), `created_at`.
- Extend `human_review_event` (`HumanReviewEventRecord`) or add
  `AI_ASSISTANT_ASKED`, `AI_SUGGESTION_CREATED`, `AI_SUGGESTION_ACCEPTED`,
  `AI_SUGGESTION_EDITED`, `AI_SUGGESTION_DISMISSED` as allowed event types,
  carrying: case id, field, document side, suggested value, applied value,
  confidence, evidence refs, provider/model, reviewer label, timestamp.
- `HumanReviewFieldOverrideRecord` (existing, Part 1) gains a nullable
  `source` / provenance marker (e.g. `ai_suggestion_id` FK, nullable) so
  Accept/Edit can be traced back to the originating suggestion without
  touching immutable extraction rows.

Write the migration with `alembic revision --autogenerate`, review the diff
by hand, and confirm it only touches new/extended tables.

### 2.2 Provider abstraction (`ai_review/providers.py`)

```text
AIReviewProvider (interface)
├── DisabledProvider        # default when AI_REVIEW_ENABLED is false/unset
└── HTTPProvider             # generic, config-driven; Claude/OpenAI/Gemini/DeepSeek all implement this shape
```

Requirements:
- Disabled by default; only active when `AI_REVIEW_ENABLED=true` and
  `AI_REVIEW_PROVIDER` + `AI_REVIEW_API_KEY` are configured (read via
  `pydantic-settings`, matching README §23 env vars).
- Enforce `AI_REVIEW_TIMEOUT_SECONDS` on every outbound call; use `httpx`
  with an explicit timeout, not the library default.
- Bound the calls: cap prompt/context size, cap retries (0–1), no unbounded
  loops.
- The provider returns **raw text**; a separate step parses/validates it
  (§2.3). The provider layer must not do UI/formatting/business logic.
- No provider-specific branching outside `ai_review/providers.py` — routes,
  services, and UI code must only depend on the `AIReviewProvider`
  interface.
- Never log or persist the API key; only persist `provider_name` /
  `provider_model` as safe metadata.

### 2.3 Structured response contract + validation (`ai_review/schema.py`)

Define a strict Pydantic schema matching the Part 2 §4 contract:

```json
{
  "message": "string",
  "mode": "EXPLANATION_ONLY | ACTIONABLE_SUGGESTION | INSUFFICIENT_EVIDENCE",
  "suggestion": {
    "action": "FIELD_OVERRIDE",
    "document_side": "SI | BL",
    "field": "<one of the 7 allowed fields>",
    "current_value": "string",
    "suggested_value": "string",
    "confidence": 0.0-1.0,
    "reason": "string",
    "evidence_refs": ["string", ...]
  }
}
```

Validation rules (reject, don't repair):
- `suggestion` is required and non-null only when `mode ==
  ACTIONABLE_SUGGESTION`; must be absent/null otherwise.
- `field` must be one of: `shipper`, `consignee`, `notify_party`,
  `port_of_loading`, `port_of_discharge`, `container_count`,
  `gross_weight_kg`. Anything else → treat as invalid, downgrade response to
  `INSUFFICIENT_EVIDENCE` (never silently coerce to a different field).
- `document_side` must be `SI` or `BL`.
- `evidence_refs` must be non-empty for `ACTIONABLE_SUGGESTION` — an
  evidence-free actionable suggestion is invalid and must be rejected /
  downgraded.
- Unknown top-level or nested keys are rejected (`extra="forbid"`).
- On JSON parse failure, schema validation failure, empty response, or
  provider timeout/unavailability: fail closed into a safe
  `INSUFFICIENT_EVIDENCE`-shaped response to the caller; never raise an
  unhandled exception into the API layer; never fabricate a value.

### 2.4 Context assembly (`ai_review/context.py`)

Build the minimal, current-case context (README §2):
- current email (classification, processing status), comparison readiness,
  SI/BL document metadata, the 7 extracted fields (raw + canonical), evidence
  refs, source location, confidence, latest `ComparisonResult` +
  `FieldComparisonRecord`s, the Human Review reason (via the existing
  user-friendly mapping, not raw codes), existing overrides, and a bounded
  slice of relevant timeline/events.
- Never load or send the whole database, other cases, or unrelated
  emails/participants/filenames.
- Translate internal codes to user-friendly text using the **existing**
  Part 1 mapping utility (README §9) — do not build a second mapping table.

### 2.5 Safety gate (`ai_review/safety.py`)

Before allowing `ACTIONABLE_SUGGESTION` to reach the human:
- Required attachment missing, no BL, wrong document type, unreadable /
  unavailable evidence, severe entity ambiguity, conflicting evidence with no
  safe resolution, or an unsupported field → force
  `EXPLANATION_ONLY`/`INSUFFICIENT_EVIDENCE`.
- This gate runs server-side regardless of what the provider returned —
  never trust the model's self-reported mode alone.

### 2.6 Service layer (`ai_review/service.py`)

- `ask(case_id, question) -> AIResponse`: builds context, calls provider,
  validates via schema, applies safety gate, persists an `AISuggestionRecord`
  when `ACTIONABLE_SUGGESTION`, emits `AI_ASSISTANT_ASKED` (+
  `AI_SUGGESTION_CREATED` when applicable).
- `accept(case_id, suggestion_id, reviewer_label) -> HumanReviewFieldOverride`:
  loads the pending suggestion, calls the **existing** Part 1
  override-creation function with `suggested_value`, tags provenance, emits
  `AI_SUGGESTION_ACCEPTED`, marks suggestion `ACCEPTED`. Does not itself
  trigger recompare — reuse the existing Resolve & Recompare endpoint/flow.
- `apply_edited(case_id, suggestion_id, reviewer_value, reviewer_label, note)`:
  same as accept but persists both `ai_proposed_value` and
  `reviewer_applied_value` on the audit event; marks suggestion
  `EDITED_APPLIED`.
- `dismiss(case_id, suggestion_id, reviewer_label)`: marks suggestion
  `DISMISSED`, emits `AI_SUGGESTION_DISMISSED`. **Must not** touch the
  Human Review case status.
- All mutation paths go through the existing Part 1 override + recompare
  functions — do not reimplement or fork that logic here.

### 2.7 API routes (`backend/app/api/`)

Match README §20 contract (names may vary slightly per note in the README,
but keep the human-approval semantics identical):

| Method | Path | Behavior |
|---|---|---|
| `POST` | `/api/v1/human-review/{id}/ai/ask` | body: `{question}` → `AIResponse` |
| `POST` | `/api/v1/human-review/{id}/ai/suggestions/{suggestion_id}/accept` | body: `{reviewer_label}` → override + new comparison ref |
| `POST` | `/api/v1/human-review/{id}/ai/suggestions/{suggestion_id}/apply-edited` | body: `{value, reviewer_label, note?}` |
| `POST` | `/api/v1/human-review/{id}/ai/suggestions/{suggestion_id}/dismiss` | body: `{reviewer_label}` |

- Validate path/body against the case's current state (404 if case not
  found, 409/422 if suggestion already resolved, 400 on schema violations).
- Wrap provider calls so that provider failure returns a clean
  `503`/degraded payload — the rest of Human Review (claim, manual override,
  resolve, dismiss) must remain fully usable when AI is down or disabled.
- Add Pydantic request/response schemas under `backend/app/api/` alongside
  existing Human Review schemas; do not create a parallel schema style.

### 2.8 Backend tests (`backend/tests/`)

Cover at minimum (Part 2 §13):
- `EXPLANATION_ONLY` response; `ACTIONABLE_SUGGESTION` response;
  `INSUFFICIENT_EVIDENCE` response.
- Invalid structured response (bad JSON, unknown field, unsupported action,
  missing evidence, invalid document side, empty response) → safe fallback,
  no exception leaks.
- Accept → creates `HumanReviewFieldOverride` + triggers recompare correctly.
- Edit Before Applying → both AI-proposed and reviewer-applied values are
  persisted.
- Dismiss → suggestion dismissed, case untouched.
- Audit event persistence for all 5 event types.
- Provider timeout; provider unavailable; `AI_REVIEW_ENABLED=false`
  (Disabled provider path).
- Human Review claim/override/resolve/dismiss still work when AI fails or is
  disabled.
- Original extraction rows unchanged after an accepted AI override.
- A new `ComparisonResult` version is created after an accepted override
  (supersedes the prior one; prior one remains immutable).
- Run against the project's isolated test DB
  (`HOLYSHIP_TEST_DATABASE_URL`), never the dev/eval DB.

---

## 3. Frontend Implementation (Dashboard — `frontend/src/`)

Outlook Add-in gets only the compact AI companion described in §4 below;
full chat/editing stays in the Dashboard (README §15).

### 3.1 Structure

- `src/api/aiReview.ts`: typed client for the 4 endpoints above, mirroring
  the existing `src/api/` conventions (fetch wrapper, error handling, types
  matching backend Pydantic schemas exactly).
- `src/components/ai-review/`:
  - `AIReviewPanel.tsx` — container, mounted inside the existing Human
    Review detail view (not a new page/route).
  - `SuggestedQuestions.tsx` — chips/buttons from the Part 2 §3 example list.
  - `AIChatThread.tsx` — question/answer thread, evidence-grounded text.
  - `AISuggestionCard.tsx` — current value, suggested value, reason,
    confidence, evidence, Accept / Edit Before Applying / Dismiss actions.
  - `AIEditSuggestionDialog.tsx` — inline value edit before applying.

### 3.2 Behavior

- Panel is scoped to the currently open Human Review case only; no global
  chat.
- On suggestion card, before Accept/Edit is confirmed, make explicit
  (Part 2 §8):
  - original value remains preserved;
  - accepting creates a review override;
  - comparison will be re-run;
  - the action is audited.
- Accept → call accept endpoint → optimistically/then-confirmed update the
  case's override + comparison state using the **existing** Part 1
  data-refresh path (e.g. re-fetch case detail / existing polling via
  `/api/v1/events`), do not build a parallel state channel.
- Edit Before Applying → open edit dialog, submit reviewer value, same
  refresh path.
- Dismiss → remove suggestion from UI, case stays exactly as it was.
- States to handle explicitly: loading (asking AI), empty (no suggestion
  yet), error (provider unavailable/timeout — show a friendly message and
  keep manual Human Review controls fully interactive), disabled
  (`AI_REVIEW_ENABLED=false` → hide/disable AI panel gracefully, do not
  break the rest of the page).
- Use the **existing** shared user-friendly text mapping utility for any
  status/reason text; do not hardcode new copy that duplicates Part 1's
  mapping.

### 3.3 Design-system compliance (mandatory — read `docs/ui_design_system.md` first)

Reuse existing charcoal/orange brand identity, typography, spacing scale,
radius/shadows, buttons, badges/status chips, inputs, cards/tables,
loading/error/empty states, focus/keyboard treatment, icon language
(`lucide-react`), and terminology. **Do not** introduce a second "AI product"
style (no purple gradients, neon glow, different fonts/radii, generic chat
bubble UI that breaks the existing card/table language).

Before marking the UI phase complete, explicitly report YES/NO for each of
the 12 checklist items listed in the Part 2 "Mandatory UI design
consistency" section, and fix every `NO`.

### 3.4 Outlook Add-in companion (`outlook-addin/src/`)

Compact only (README §15):
- Ask one concise question about the current email.
- Show the evidence-grounded explanation (or "AI suggestion available" /
  "no suggestion").
- Deep-link (`?review=<id>`) into the Dashboard's full `AIReviewPanel` for
  Accept/Edit/Dismiss — do not implement Accept/Edit/Dismiss inside the
  Add-in itself.
- Reuse the same `src/api/` client pattern and the same user-friendly
  mapping as the Dashboard.

### 3.5 Frontend tests

- Dashboard (Vitest + Testing Library): AI loading, answer rendering,
  structured suggestion card rendering, accept, edit, dismiss, error state,
  empty/no-suggestion state.
- Outlook: question/answer flow, "suggestion available" indicator, deep-link
  behavior, error/disabled state.
- Run `npm run typecheck`, `npm run test`, `npm run build` in both
  `frontend/` and `outlook-addin/` and confirm no regressions against the
  stabilized baselines in README §24.

---

## 4. Definition of Done (must all be true — Part 2 §14)

- [ ] AI explains current cases using persisted evidence only.
- [ ] Unsafe cases never produce actionable suggestions (safety gate
      verified by tests).
- [ ] Suggestions are structured and backend-validated (`extra="forbid"`,
      allowed-field allowlist, evidence-required rule).
- [ ] Human approval is mandatory for every mutation — no auto-apply path
      exists anywhere in the code.
- [ ] Accept/Edit reuse the existing Human Review override + Resolve &
      Recompare flow (no forked/duplicated logic).
- [ ] Audit provenance exists for ask/create/accept/edit/dismiss.
- [ ] Provider failure/timeout/disabled never breaks manual Human Review.
- [ ] Dashboard AI UI passes all 12 design-consistency checks (§3.3).
- [ ] Original extraction and historical comparison rows are unchanged after
      any AI-assisted override.
- [ ] `python -m pytest` passes (no regressions vs. 299-passed baseline).
- [ ] `cd frontend && npm run typecheck && npm run test && npm run build`
      passes (no regressions vs. 12-tests baseline).
- [ ] `cd outlook-addin && npm run typecheck && npm run test && npm run build`
      passes (no regressions vs. 57-tests baseline).
- [ ] `make check-fast` passes.
- [ ] `make check PHASE=F` passes.
- [ ] `git diff --check` passes (no whitespace errors).
- [ ] No email-ID/filename/participant/ground-truth/`data_v2`/score-specific
      logic introduced.
- [ ] No secrets, API keys, or local DB files committed.
- [ ] Self-evaluation work is explicitly out of scope for this part — do not
      touch `submission_adapter.py` or the evaluation pipeline.

---

## 5. Commit / PR hygiene

Follow `AGENTS.md` exactly for branch naming, commit message format, and any
required PR description template. If `AGENTS.md` specifies something that
conflicts with a convenience shortcut in this prompt, `AGENTS.md` wins.
