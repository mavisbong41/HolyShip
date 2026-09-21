# AGENTS.md

## 1. Purpose

This file defines the repository-level working rules for Codex and any other coding agent working on the **Shipping Document Verification** project.

The current milestone covers the shared backend from ingestion through comparison,
the official React Dashboard and Outlook Add-in clients, and the active Human
Review workflow described in `docs/scope_decisions/2026-09-21-ui-human-review.md`.

Current scope:

```text
Email Source
    ↓
Initial Sync / New Email Ingestion
    ↓
Classification
    ↓
Comparison Readiness
    ↓
Attachment Retrieval
    ↓
Document Routing
    ↓
SI + BL Extraction
    ↓
Canonical Field Mapping
    ↓
Normalization + Comparison
    ↓
Persist Processing Result
    ↓
Dashboard / Extension Backend API
    ↓
Dashboard / Outlook Add-in / Auditable Human Review
```

The project owner expanded this scope on 2026-09-21. Backend deterministic
semantics remain authoritative; clients must consume APIs rather than duplicate
classification, extraction, or comparison rules.

---

## 2. Required Reading Before Coding

Before making changes, read the relevant project documents in this order:

1. The original challenge/use-case specification, if it exists in the repository.
2. `backend_requirements_ingestion_to_compare.md`
3. This `AGENTS.md`
4. `implement.md`
5. Existing code, tests, configuration, and README files relevant to the task.

Do not invent behavior that contradicts the challenge specification.


### Private evaluation/reference data

If the repository or organizer Docker bundle contains `ground_truth.json`, private reference answers, scoring internals, or evaluator-only data:

- application/runtime code MUST NOT read it
- prompts MUST NOT include it
- dictionaries/rules MUST NOT be generated from hidden answers in a way that leaks answers per email
- caches MUST NOT contain prediction lookups derived from it
- tests may use officially supplied public fixtures, but production/demo inference must operate only on permitted email/document inputs

Private reference data may be inspected only for authorized offline dataset/spec auditing or by evaluator tooling, never as a prediction source.


If the requirements and code disagree, do not silently choose one. Preserve existing working behavior where possible and document the conflict in `implement.md`.

---

## 3. Source-of-Truth Rules

The following challenge requirements are non-negotiable unless the user explicitly changes the project scope.

### Email categories

The final category must be exactly one of:

```text
document_comparison
new_si_request
invoice_query
general_message
spam
```

Do not create extra final categories.

Internal candidate labels are allowed during Stage 1 classification, but the persisted final category must be one of the five categories above.

### Document-comparison routing

Only:

```text
document_comparison
```

continues into SI/BL extraction and comparison.


Before extraction, a `document_comparison` email must pass **Comparison Readiness**:

```text
READY_FOR_COMPARISON
AWAITING_DOCUMENTS
UNRESOLVED
```

A no-attachment email that is explicitly asking another party to send/provide a draft BL for later checking is `AWAITING_DOCUMENTS`, not automatically `missing_attachment`.


This rule applies only **after** the email is already classified as `document_comparison`.

Do not convert a `new_si_request` containing a structured SI body plus a future-draft-BL follow-up into `AWAITING_DOCUMENTS`.

Only `READY_FOR_COMPARISON` continues into SI/BL retrieval and extraction.

Other categories stop after classification.

### SI is the reference

For comparison:

```text
SI = reference
BL = document being checked
```

Do not reverse this relationship.

### Required comparison fields

Compare exactly these seven canonical fields:

```text
shipper
consignee
notify_party
port_of_loading
port_of_discharge
container_count
gross_weight_kg
```

Do not silently add or remove required fields.

### Field-label equivalence

Different source labels may map to the same canonical field.

Examples:

```text
Port of Loading
Load Port
Loading Port
POL
    ↓
port_of_loading
```

Field-label mapping is not the same as value normalization.

### Required result behavior

For a document-comparison email:

- determine whether a mismatch exists
- identify the mismatched fields
- preserve/display SI and BL values separately
- if all seven fields match, support the result:

```text
No mismatch detected.
```

---

## 4. Current Product Workflow

### First deployment

The backend must support an initial inbox sync:

```text
📥 Initial Sync
N existing emails
       ↓
Deduplicate / identify unprocessed emails
       ↓
Process unprocessed emails
       ↓
Persist results progressively
       ↓
Dashboard can populate progressively
```

The demo dataset may currently contain 520 emails.

**Never hard-code `520`.**

The system must work with any backlog size `N`.

### After initial sync

```text
📧 New email
       ↓
Webhook / provider push / polling fallback / simulated ingestion
       ↓
Ingest automatically
       ↓
Process automatically
       ↓
Persist result
       ↓
Dashboard / extension can receive updated state
```

Main demo narrative:

> When deployed, the system first processes the existing inbox backlog, then continuously monitors for new incoming emails.

The primary product workflow must not depend on a user manually uploading JSON and clicking "Run".

A manual/simulated ingestion endpoint is allowed for demo/testing.

---

## 5. Architecture Principles

### 5.1 Keep provider integration separate

Provider-specific code must be isolated behind an ingestion adapter.

Possible sources:

```text
Challenge dataset / loader.py
Microsoft Graph / Outlook
Generic simulated incoming email API
```

All sources must normalize into one internal email model before classification.

Do not let Microsoft Graph-specific, dataset-specific, or demo-specific fields leak throughout the core pipeline.

### 5.2 Shared backend, multiple frontends

The Web Dashboard and Email Extension must ultimately read/write the same backend case records.

Do not build separate processing logic for the dashboard and extension.

Conceptually:

```text
                    Shared Backend
                         ↓
                  Shared Case State
                    ↙         ↘
           Web Dashboard    Email Extension
```

The extension is not the primary processing engine.

The backend must be able to process email without the user opening the extension.

---

## 6. Email Ingestion Rules

### Must

- preserve original email subject and body
- preserve provider/external message ID where available
- assign a stable internal email ID
- preserve received timestamp
- preserve attachment metadata
- support idempotent ingestion
- store processing state
- support lazy loading of attachment content
- avoid reprocessing already completed emails unless explicitly requested
- support backlog processing with bounded concurrency

### Must not

- rescan the full inbox on every polling interval
- process the same provider message into duplicate cases
- hard-code a specific mailbox size
- require attachment content to be downloaded before classification if metadata is sufficient
- treat manual upload as the only supported ingestion model

---

## 7. Processing Status Rules

Use explicit machine-readable states.

Current allowed backend states:

```text
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
```

Do not overload one status to mean multiple unrelated things.


`AWAITING_DOCUMENTS` is a legitimate operational state inside the `document_comparison` workflow. It is not a classification category and must not be used as a fallback for ambiguous `new_si_request` emails.

### `FAILED`

Use for technical failures, e.g.:

- parser crash
- OCR/API failure
- timeout
- storage/read failure
- malformed model output that cannot be recovered automatically

### `BLOCKED`

Use when the pipeline cannot safely continue, e.g.:

- required document unavailable
- unresolved extraction
- unresolved comparison

The Human Review behavior for `BLOCKED` cases is outside the current milestone.

---

## 8. Classification Implementation Rules

Classification should use a staged/cascade design.

### Stage 1 — fast candidate classifier

Goal:

> Resolve obvious cases cheaply.

It may use:

- subject
- body
- sender/context metadata if useful
- attachment metadata
- deterministic/rule-based signals
- lightweight classifier
- detected SI-like field labels / field density in the email body

### Critical boundary: `new_si_request` vs `document_comparison / AWAITING_DOCUMENTS`

Never use the following as a sufficient rule:

```text
no attachments + mentions "draft BL"
```

Both intents can have these features.

Use the **primary requested action** and email-body structure.

#### Prefer `new_si_request` when

- the body provides a structured/dense SI field block
- several shipment fields are supplied directly in the body
- the current action is to create/submit a new Shipping Instruction
- any draft-BL wording describes a later follow-up, e.g. `once available`

Example shape:

```text
Please find Shipping Instruction for <ref>.
Shipper: ...
Consignee: ...
POL: ...
POD: ...
...
Please revert with draft BL once available.
```

Result:

```text
final_category = new_si_request
```

#### Prefer `document_comparison` when

- the current action is to obtain/check/verify a draft BL
- the body does not contain a full SI creation block
- the email may contain only an existing booking/reference plus a request for the draft BL to be sent for checking

Example shape:

```text
Please assist to send the draft BL for <ref> for checking asap.
```

Result:

```text
final_category = document_comparison
comparison_readiness = AWAITING_DOCUMENTS
```

Words such as `asap`, `once available`, `for checking`, and `draft BL` are supporting signals only. Do not hard-code category decisions from one phrase.

Stage 1 may emit multiple internal candidate categories with scores.

Example:

```json
{
  "candidates": [
    {"category": "document_comparison", "score": 0.86},
    {"category": "invoice_query", "score": 0.52}
  ],
  "conflict_detected": true
}
```

### Stage 1 may finalize only when

- one category is strongly supported
- there is no major conflicting signal
- the top candidate is sufficiently separated from alternatives
- confidence is above a configurable threshold

Do not hard-code magic confidence values across the codebase. Keep thresholds configurable.

### Stage 2 — ambiguity resolver

Trigger only for ambiguous/conflicting/low-confidence Stage 1 cases.

Stage 2 input should include:

- subject
- body
- attachment metadata
- Stage 1 candidates
- Stage 1 scores
- reason for escalation
- whether a structured SI field block is present
- detected SI-like labels / fields
- inferred primary requested action

For `new_si_request` vs `document_comparison`, Stage 2 must resolve the current business action rather than merely matching the phrase `draft BL`.

Stage 2 must:

- choose only from the five allowed final categories
- return structured output
- return confidence
- return a concise reason/reason code
- not invent new categories

### Important classification principle

Do not blindly trust subject lines.

Misleading subjects are an expected challenge condition.

Body intent and other evidence may outweigh the subject.

---

## 9. Attachment Retrieval Rules

For non-document-comparison emails:

```text
classification complete
→ stop
```

Do not run SI/BL OCR/extraction unnecessarily.

For `document_comparison` with `comparison_readiness = READY_FOR_COMPARISON`:

- retrieve candidate comparison attachments
- determine candidate SI/BL documents
- preserve attachment identity
- generate a content hash when possible
- route each document to the appropriate reader

Possible pre-extraction outcomes include:

```text
SI_FOUND
BL_FOUND
MULTIPLE_CANDIDATES
MISSING_REQUIRED_ATTACHMENT
UNSUPPORTED_ATTACHMENT
CORRUPTED_ATTACHMENT
WRONG_DOCUMENT_TYPE
```

Do not guess which file is authoritative when evidence is insufficient.

Persist `BLOCKED` instead of fabricating a decision.

---

## 10. Document Router Rules

Before extraction, identify how the document should be read.

Examples:

```text
plain text
→ direct text reader

XLSX
→ XLSX key-value / table reader

text-based PDF
→ PDF text extractor

DOCX
→ DOCX parser

scanned/image-only PDF
→ OCR / Vision

image
→ OCR / Vision
```

### Do

- detect machine-readable text when practical
- choose the cheapest suitable route first
- route obvious scanned/image-only documents directly to OCR/Vision
- preserve source/page information where available

### Do not

- intentionally run several unsuitable extractors in sequence before using the obvious one
- OCR every PDF by default
- use Vision/LLM for documents that can be parsed deterministically without loss

---


## 10.1 Document Role Validation Rules

A readable file is not automatically a valid SI or BL.

After readable content is materialized and before extracted fields are trusted:

- validate that the claimed SI/BL role is consistent with document content
- use cheap deterministic signals first:
  - document title/header
  - density of expected SI/BL labels
  - conflicting document-type titles such as `COMMERCIAL INVOICE`, `PACKING LIST`, or `CERTIFICATE OF ORIGIN`
  - explicit source declarations
- clearly wrong document roles must produce `WRONG_DOCUMENT_TYPE` and stop comparison
- inconclusive validation must not be force-labeled as wrong; allow extraction confidence / unresolved logic to handle ambiguity

The validator must support text, tables/cells, and OCR/Vision output — not only raw text.

---

## 11. Extraction Rules

Extraction means:

> Convert SI and BL source documents into structured values for the seven required canonical fields.

Extraction is not comparison.

### Required extraction schema

Preserve at least:

```text
canonical field
raw label
raw value
confidence
source evidence/location
```

Example:

```json
{
  "field": "gross_weight_kg",
  "raw_label": "GROSS WEIGHT",
  "raw_value": "22,000 KG",
  "confidence": 0.99,
  "source": {
    "page": 1,
    "text_span": "GROSS WEIGHT: 22,000 KG"
  }
}
```

### Preserve raw data

Never overwrite or discard raw extracted values after normalization.

### One-pass extraction

Prefer:

```text
1 document
→ 1 extraction pass
→ 7 required fields
```

Avoid:

```text
7 fields
→ 7 separate expensive LLM calls
```

### Parallel extraction

When possible:

```text
SI extraction ─┐
               ├→ continue when both are ready
BL extraction ─┘
```

Do not unnecessarily wait for SI to finish before starting BL.

### Extraction Stage 2 / fallback

Use expensive LLM/Vision reasoning only when needed, such as:

- unusual layout
- scan/image
- unknown field label
- multiple candidate values
- low confidence
- unresolved deterministic extraction

Where practical, send only unresolved fields/relevant source regions rather than rerunning the whole document.

If several fields are unresolved in the same context, batch them into one resolver request rather than separate calls.

---

## 12. Canonical Field Mapping Rules

Map source labels to the seven canonical names before comparison.

The mapping dictionary must be:

- configurable
- extendable
- covered by tests


### Dataset-validated label behavior

Support bilingual/descriptive labels while preserving `raw_label`.

Examples:

```text
Shipper (Principal or Seller) (发货人)
→ shipper

Port of Loading (POL) (装货港)
→ port_of_loading

Gross Wt (kgs) (毛重 KGS)
→ gross_weight_kg
```

Do not blindly delete all parenthesized text; recognized shipping abbreviations such as `POL`/`POD` may be meaningful.

### Contextual consignee mapping

In the relevant negotiable-B/L context:

```text
To the Order of
→ consignee
```

Record this as a contextual business mapping, not as an arbitrary fuzzy text match.

Where practical, preserve mapping provenance such as:

```text
exact_label
alias_dictionary
bilingual_label_normalization
contextual_business_rule
table_structure
llm_resolved
```

Examples:

```text
Port of Loading
Load Port
POL
→ port_of_loading
```

```text
Port of Discharge
Discharge Port
POD
→ port_of_discharge
```

Do not use broad fuzzy matching that can silently map one source field to the wrong canonical field.

Ambiguous mappings should remain unresolved.

---

## 13. Comparison Rules

### Required field result states

Each of the seven fields should resolve to:

```text
MATCH
MISMATCH
UNRESOLVED
```

Do not force uncertain cases into `MATCH` or `MISMATCH`.

### Layered comparison strategy

Use:

```text
Canonical Mapping
      ↓
L0 Safe Normalization
      ↓
Fast Compare
  ┌───┴───┐
MATCH   DIFFERENT
          ↓
 L1 Field-Specific Normalization
          ↓
      Compare again
     ┌────┴────┐
   MATCH    STILL DIFFERENT
                ↓
      L2 Semantic Resolution
                ↓
     MATCH / MISMATCH / UNRESOLVED
```

---

## 14. Normalization Safety Rules

Accuracy is more important than forcing equivalence.

### L0 — universally safe normalization

Allowed examples:

- trim leading/trailing whitespace
- collapse repeated whitespace
- standardize case for comparison
- Unicode normalization
- normalize obvious line-break artifacts

L0 must not remove meaningful words.

### L1 — field-specific normalization

#### `container_count`

Safe examples:

```text
"03" → 3
"3 containers" → 3
"6 x 40'HC" → count = 6, type = "40'HC"
"15 x 20'GP" → count = 15, type = "20'GP"
```

Only the count participates in the canonical `container_count` comparison. Preserve the raw compound value and any parsed type/size separately.

Do not infer complex container expressions unless the logic is deterministic and tested.

#### `gross_weight_kg`

Safe examples:

```text
"22,000 KG" → 22000
"22000 kg" → 22000
```

If supporting unit conversion, conversion must be explicit, deterministic, and tested.

`NET WEIGHT` must never be silently substituted for `gross_weight_kg`. If no valid gross-weight label/value is available, keep gross weight missing/unresolved.

#### Port fields

Allowed:

- case normalization
- whitespace normalization
- approved alias dictionary
- approved port-code mapping

Do not equate unverified locations merely because names look similar.

#### Entity fields

Fields:

```text
shipper
consignee
notify_party
```

Use conservative normalization.

Safe examples may include:

- case
- whitespace
- harmless punctuation differences

Do not aggressively remove meaningful legal/entity words.

Example of behavior to avoid:

```text
ABC Logistics Malaysia
→ ABC Logistics
```

unless there is verified project logic proving equivalence.

### L2 — semantic resolution

Only invoke for values that remain different after safe deterministic normalization and plausibly represent equivalent information.

L2 must return structured output including:

```text
equivalent
confidence
reason
```

If uncertain:

```text
UNRESOLVED
```

---

## 15. Performance Rules

Performance must be achieved by avoiding unnecessary work, not by reducing correctness.

### Required optimizations

1. Classify all emails, but extract documents only for `document_comparison`.
2. Lazy-load full attachment content.
3. Process SI and BL in parallel where safe.
4. Extract all seven fields in one document pass where practical.
5. Use Stage 2 only for ambiguous cases.
6. Apply deeper normalization only after cheaper comparison fails.
7. Cache document extraction by content hash where valid.
8. Use controlled concurrency for backlog processing.
9. Do not repeatedly process unchanged documents/results.
10. Keep external API/model concurrency configurable.

### Never optimize by

- skipping required fields
- using only subject for classification
- accepting low-confidence extraction as fact
- treating semantic similarity as equality without evidence
- removing source evidence
- forcing unresolved cases to appear completed

---

## 16. Caching Rules

Where supported, calculate a stable file hash, e.g.:

```text
SHA-256(file bytes)
```

Cache:

```text
file hash
→ extraction result
```

Reusing cached extraction is allowed only when:

- the exact file content is unchanged
- extractor/schema version is compatible
- relevant normalization/extraction logic has not invalidated the cached result

If extractor logic changes materially, support cache invalidation/versioning.

---

## 17. API / Model Output Rules

### Structured model output

LLM/Vision calls used in the pipeline must return validated structured data.

Do not parse important backend decisions from free-form prose if structured output can be used.

Validate:

- category enums
- field names
- numeric types
- confidence ranges
- required keys

Malformed model output should be retried/repaired within a bounded policy or persisted as `FAILED`/`BLOCKED`.

### Stable internal contracts

Frontend-facing APIs should not depend directly on a third-party model response shape.

Model/provider output must be normalized into project-owned schemas.

---

## 18. Data Integrity Rules

Always preserve:

- original email content
- attachment identity
- original extracted value
- normalized comparison value
- classification result
- comparison result
- source evidence where available
- timestamps/status transitions

Do not silently mutate historical source data.

Do not delete evidence just because a normalized value was produced.

---

## 19. Reliability Rules

### Idempotency

Re-ingesting the same source email must not create a duplicate case.

### Bounded retries

Technical retries must be bounded.

Do not create infinite retry loops.

### Timeouts

External services must use sensible timeouts.

### Partial failure

If SI succeeds but BL extraction fails:

- preserve SI result
- do not discard successful work
- mark the overall case appropriately

### Unresolved is valid

`UNRESOLVED` is preferable to an incorrect confident answer.

---

## 20. Security Rules

- Never commit secrets, tokens, OAuth credentials, API keys, or passwords.
- Use environment variables or the repository's existing secret-management approach.
- Do not log full secrets or bearer tokens.
- Avoid logging full sensitive document content unless required for local development; prefer IDs and structured diagnostics.
- Do not add production credentials to demo fixtures.
- Keep provider permissions as narrow as practical.

---


## 21. Coding Behavior — Codex MUST Do

For every coding task:

1. Read `AGENTS.md`, `backend_requirements_ingestion_to_compare.md`, and `implement.md`.
2. Inspect existing code before deciding architecture.
3. Reuse existing stack, patterns, package manager, and configuration where reasonable.
4. Treat the provided public/sample dataset formats as real acceptance inputs, including XLSX, DOCX, PDF, scanned/image-only PDFs, and corrupted files.
5. Implement comparison-readiness logic before declaring no-attachment document-comparison emails missing.
6. Keep private evaluator/reference answers such as `ground_truth.json` isolated from runtime code, prompts, caches, rules, and demo inference.
7. Make the smallest coherent change that satisfies the task.
8. Keep provider-specific code separated from core domain logic.
9. Keep thresholds/configuration centralized.
10. Add or update tests for changed behavior.
11. Run the relevant tests/lint/type checks available in the repository.
12. Report real validation results; never claim tests passed if they were not run.
13. Update `implement.md` before finishing every implementation task.
14. Keep `implement.md` understandable to a teammate who did not participate in the coding session.
15. Document newly added dependencies and why they were needed.
16. Preserve backward compatibility unless the user explicitly approves a breaking change.
17. Prefer readable deterministic code over clever abstractions.


18. When adding or renaming a status/outcome/category enum, search the whole repository for every authoritative enum list, schema, validator, test fixture, API contract, and documentation reference. Update them together so narrative text and machine-readable lists cannot drift.

---

## 22. Coding Behavior — Codex MUST NOT Do

Unless explicitly requested:

- Do not implement Human Review UI/workflow yet.
- Do not implement final visual report screens.
- Do not build Outlook Add-in UI as part of backend tasks.
- Do not make Microsoft Graph a hard dependency of the core pipeline.
- Do not replace the challenge dataset/loader interface with a proprietary-only input path.
- Do not hard-code `520`.
- Do not read `ground_truth.json` or private evaluator/reference answers from runtime application code, prompts, caches, rules, or demo inference.
- Do not guess an official submission mapping for internal states such as `AWAITING_DOCUMENTS`; validate mappings only against permitted public schema/self-evaluation interfaces.
- Do not assume every `document_comparison` email should immediately retrieve attachments; evaluate comparison readiness first.
- Do not classify `new_si_request` as `document_comparison` merely because the body mentions a future draft BL.
- Do not use `attachments = 0` + `draft BL` as a standalone classification rule.
- Do not let Comparison Readiness reclassify an email that should have remained `new_si_request`.
- Do not classify an explicit request to send/provide a future draft BL as `missing_attachment` solely because no file is attached.
- Do not treat filename suffixes such as `_BL` / `_SI` as sufficient proof of document role.
- Do not ignore XLSX attachments.
- Do not create extra final email categories.
- Do not compare fields outside the required seven as if they were challenge-required.
- Do not reverse SI and BL.
- Do not treat missing data as a mismatch automatically.
- Do not treat missing data as a match.
- Do not convert uncertain comparisons into confident mismatches.
- Do not run OCR/LLM on every email by default.
- Do not run seven expensive model calls just to extract seven fields from one document.
- Do not aggressively normalize entity names.
- Do not destroy raw values after normalization.
- Do not silently alter requirements to make implementation easier.
- Do not fabricate hidden/reference answers for the challenge dataset.
- Do not optimize solely for the self-evaluation score by hard-coding dataset-specific answers.
- Do not introduce large unrelated refactors.
- Do not delete teammate code without confirming it is obsolete and documenting the change.
- Do not add unnecessary production dependencies.
- Do not commit secrets.
- Do not leave `implement.md` stale after changing the code.

---

## 23. Testing Expectations

At minimum, cover the behavior changed by each task.

Important test categories for this project:

### Ingestion

- first sync
- duplicate email ingestion
- new email ingestion
- already processed email
- failed/retried ingestion

### Classification

- obvious document comparison
- obvious new SI request
- invoice query
- general message
- spam
- misleading subject
- conflicting subject/body
- multiple candidates routed to Stage 2

### Attachment routing

- text
- text PDF
- DOCX
- XLSX
- scan/image
- missing attachment
- unsupported/corrupt attachment

### Extraction

- all seven fields
- alternate labels
- bilingual/descriptive labels
- `To the Order of` contextual consignee mapping
- missing field
- multiple candidate values
- raw value preservation

### Comparison

- exact match
- case/whitespace-only difference
- `22,000 KG` vs `22000 kg`
- compound container count parsing (`6 x 40'HC` → count 6)
- gross-weight extraction that does not substitute `NET WEIGHT`
- true container-count mismatch
- conservative entity-name comparison
- unresolved semantic ambiguity
- all seven match → no mismatch result

Use challenge samples as test fixtures where licensing/data handling permits, but do not hard-code expected hidden answers that are not supplied by the challenge.

---

## 24. Definition of Done

A coding task is not complete until:

- requested code is implemented
- relevant tests are added/updated
- available tests/checks have been run, or inability to run them is documented
- new configuration/environment variables are documented
- important design decisions are recorded
- known limitations are recorded
- `implement.md` is updated
- the final summary clearly states what changed and what remains

---

# 25. Mandatory `implement.md` Update Protocol

`implement.md` is the shared teammate handoff document.

**Codex must update it after every meaningful coding task and before declaring the task complete.**

Do not use it as a raw scratchpad.

It must remain concise, truthful, and easy to scan.

## Required sections to maintain

```text
Project Snapshot
Current Milestone
Current Status
Architecture / Flow
Implemented
In Progress
Next
Blocked / Open Questions
Key Decisions
API / Data Contract Changes
Configuration / Environment
Tests & Validation
Known Limitations
Recent Change Log
```

## Update rules

After each task:

1. Update `Last updated`.
2. Update the current milestone/status if it changed.
3. Move completed items from `In Progress` to `Implemented`.
4. Add newly discovered work to `Next`.
5. Record blockers/open questions.
6. Record architectural decisions that teammates need to know.
7. Record any endpoint/schema/config changes.
8. Record tests actually run and their result.
9. Record known limitations honestly.
10. Add one concise entry to `Recent Change Log`.

### Do not

- mark work as done when only planned
- say tests passed if they were not run
- erase important prior decisions without explaining why they changed
- paste long code into `implement.md`
- turn `implement.md` into a duplicate of the requirements document

### Recommended change-log entry

```markdown
### YYYY-MM-DD — Short task name
- Changed:
- Why:
- Files:
- Validation:
- Next:
```

The goal is that a teammate can open `implement.md` and understand the project state in under two minutes.

---

# 26. Autonomous Phase Protocol

Applies whenever the user sends a `PHASE N` prompt.

1. Work only on the requested phase. Do not start the next phase and do not perform unrelated refactors.
2. Read `backend_requirements_ingestion_to_compare.md` and the latest `implement.md` before changing code.
3. Use the loop:
   `inspect → implement → make check-fast → analyze → fix → rerun`.
   At the phase gate run `make check`.
4. Maximum 6 fix iterations for one failing gate. If still failing, STOP, record the blocker in
   `implement.md`, and report it. Never weaken a gate, delete a valid test, or special-case data just to pass.
5. Never change an existing test's expected result merely to make it pass unless the requirement truly changed.
   If a requirement changed, document why in `implement.md`.
6. Accuracy evidence may come only from:
   - unit/integration tests,
   - metamorphic tests,
   - synthetic defect tests,
   - direct inspection of permitted input emails/documents,
   - the permitted public self-evaluation interface.
   Never read or derive predictions from `ground_truth.json`, `data_v2/`, private evaluator answers, or secrets.
7. Never add per-email-id, per-filename, or known-answer lookup rules. Every production rule must be generalizable
   and justified by business/document evidence.
8. Public self-evaluation is a validation signal, not a training oracle. Use only through the repository's
   logged `make score PHASE=N` target, maximum 2 calls per phase by default. Do not repeatedly tune rules to
   aggregate score fluctuations.
9. Reliability: new paths must handle missing/empty/corrupt input, duplicate ingestion, timeouts, and partial
   failure without crashing the whole run. Retries must be bounded.
10. Performance: measure before optimizing. Record wall time, throughput, p50/p95 where available, expensive
    LLM/OCR/Vision call counts, cache hit rate, and memory where practical. Do not trade correctness for speed.
11. When adding/renaming any category, processing state, readiness value, document outcome, or review reason,
    search and update every authoritative enum/schema/validator/migration/test/API/doc reference together.
12. Existing Human Review code may remain, but do not extend Human Review UI/workflow in the current backend
    milestone unless the user explicitly expands scope.
13. Before finishing every phase:
    - update `implement.md` with real implementation state and real metrics,
    - write/update the phase reports under `reports/`,
    - list exact commands run and their real outcomes,
    - state what could not be verified,
    - print the standard PHASE REPORT,
    - STOP.
