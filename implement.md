# implement.md

> Shared implementation handoff for the Shipping Document Verification project.
>
> Codex must update this file after every meaningful coding task.

---

## Project Snapshot

**Goal:** Build the backend workflow from email ingestion through SI/BL comparison.

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
Document Router
    ↓
SI + BL Extraction
    ↓
Canonical Field Mapping
    ↓
Safe Normalization + Compare
    ↓
Persist Result
    ↓
Dashboard / Extension Backend API
```

**Current scope ends at comparison.**

Human Review UI/workflow is intentionally not part of the current milestone.

---

## Last Updated

**Date:** 2026-09-20  
**Updated by:** Requirements revision after direct dataset audit  
**Repository state:** Requirements/architecture refined against the provided dataset; source-code implementation status must still be confirmed against the actual repository before coding.

---

## Current Milestone

### Milestone M1 — Backend: Email Ingestion → Compare

Target behavior:

> When deployed, the system first processes the existing inbox backlog, then continuously monitors for new incoming emails.

Demo concept:

```text
First startup
📥 Initial Sync
N existing emails
       ↓
Process unprocessed emails
       ↓
Dashboard populated progressively

After startup
📧 New email
       ↓
Webhook / polling / simulated ingestion
       ↓
Automatic processing
       ↓
Dashboard updates
```

The provided dataset may currently contain 520 emails for the demo/backlog.

**The implementation must not hard-code 520.**

---

## Current Status

| Area | Status | Notes |
|---|---|---|
| Requirements | DONE | Backend requirements defined through comparison |
| Repository/stack audit | NOT CONFIRMED | Codex must inspect actual repository |
| Email ingestion | NOT CONFIRMED | Implementation must be checked |
| Initial sync | NOT CONFIRMED | Implementation must be checked |
| Continuous ingestion | NOT CONFIRMED | Implementation must be checked |
| Classification Stage 1 | NOT CONFIRMED | Implementation must be checked |
| Classification Stage 2 | NOT CONFIRMED | Implementation must be checked |
| Comparison readiness | NOT CONFIRMED | Must distinguish READY vs AWAITING_DOCUMENTS vs unresolved |
| Attachment retrieval | NOT CONFIRMED | Implementation must be checked |
| Document router | NOT CONFIRMED | Must include XLSX and scan/image routing |
| Document role validation | NOT CONFIRMED | Must detect readable-but-wrong SI/BL documents |
| SI/BL extraction | NOT CONFIRMED | Implementation must be checked |
| Canonical field mapping | NOT CONFIRMED | Implementation must be checked |
| Comparison pipeline | NOT CONFIRMED | Implementation must be checked |
| Persistence | NOT CONFIRMED | Implementation must be checked |
| Dashboard backend API | NOT CONFIRMED | Implementation must be checked |
| Email-extension backend API | NOT CONFIRMED | Implementation must be checked |
| Human Review UI/workflow | OUT OF SCOPE | Next milestone |

`NOT CONFIRMED` means this file was created before inspecting the repository's actual implementation. Codex must replace these statuses with truthful repository state after inspection.

---

## Architecture / Flow

### 1. Ingestion

Supported architecture:

```text
Challenge Dataset / loader.py ─┐
                               │
Microsoft Graph Adapter ───────┼→ Common Email Model
                               │
Simulated Incoming Email API ──┘
```

Provider-specific code should remain outside the core pipeline.

### 2. Classification

```text
Email
 ↓
Stage 1 Fast Classifier
 ↓
Clear/high confidence?
 ├─ Yes → Final Category
 └─ No  → Stage 2 LLM Ambiguity Resolver
              ↓
          Final Category
```

Allowed final categories:

```text
document_comparison
new_si_request
invoice_query
general_message
spam
```

Only `document_comparison` continues to **Comparison Readiness**.

```text
document_comparison
        ↓
READY_FOR_COMPARISON
    → retrieve/extract/compare

AWAITING_DOCUMENTS
    → persist normal waiting state; no extraction

UNRESOLVED
    → stop safely for the next workflow phase
```

A no-attachment email is not automatically an error; the body intent must establish whether documents are expected now.

### 3. Extraction

```text
document_comparison
        ↓
Retrieve SI + BL
        ↓
Document Router / Content Materialization
    ↙           ↘
   SI           BL
   ↓             ↓
Extract 7 fields in parallel where practical
    ↘           ↙
    Structured values
```

### 4. Comparison

```text
Canonical field mapping
        ↓
L0 safe normalization
        ↓
Fast compare
   ├─ MATCH → done
   └─ DIFFERENT
          ↓
     L1 field-specific normalization
          ↓
       compare again
      ├─ MATCH → done
      └─ DIFFERENT
             ↓
        L2 semantic resolution
             ↓
     MATCH / MISMATCH / UNRESOLVED
```

---

## Implemented

### Planning / Requirements

- Defined initial-sync + continuous-ingestion workflow.
- Defined five required final email categories.
- Defined Stage 1 + Stage 2 classification concept.
- Defined lazy attachment retrieval.
- Defined document routing by readable format.
- Defined parallel SI/BL extraction concept.
- Defined one-pass extraction of the seven required fields.
- Defined canonical field mapping.
- Defined layered normalization/comparison strategy.
- Defined `MATCH`, `MISMATCH`, and `UNRESOLVED` comparison outcomes.
- Defined performance principles:
  - avoid unnecessary OCR/LLM use
  - process only document-comparison attachments
  - parallelize SI/BL work
  - cache extraction by file hash where valid
  - controlled backlog concurrency
- Defined shared-backend principle for dashboard + email extension.
- Created repository-level Codex rules in `AGENTS.md`.
- Audited the provided dataset/organizer bundle and incorporated dataset-backed requirements.
- Added XLSX as a required document-routing path.
- Added comparison-readiness design so legitimate no-attachment requests for a future draft BL are not treated as missing-attachment errors.
- Added readable-but-wrong-document validation (`WRONG_DOCUMENT_TYPE`).
- Added contextual `To the Order of` → consignee-equivalent mapping for the relevant negotiable-B/L context.
- Added bilingual/descriptive label-normalization rules.
- Added compound `container_count` parsing and a `NET WEIGHT` guard for gross-weight extraction.
- Added strict isolation of private evaluator/reference answers from runtime inference.

> These are design decisions. Do not interpret this section as proof that corresponding source code already exists.

---

## In Progress

None recorded yet.

Codex should update this section as soon as implementation work begins.

---


## Next

Recommended implementation order after the dataset audit:

1. Inspect repository structure, stack, package manager, tests, and existing services.
2. Confirm/create the common internal email model and processing-state model.
3. Implement idempotent challenge-dataset ingestion and initial sync with bounded concurrency.
4. Implement simulated incoming-email ingestion for the live demo.
5. Implement the deterministic Stage 1 classifier and validate all five categories first.
6. Implement Comparison Readiness:
   - `READY_FOR_COMPARISON`
   - `AWAITING_DOCUMENTS`
   - `UNRESOLVED`
7. Implement attachment retrieval only for `READY_FOR_COMPARISON`.
8. Implement the document router with:
   - TXT
   - PDF
   - DOCX
   - XLSX
   - scan/image-only PDF
9. Implement document-role validation (`WRONG_DOCUMENT_TYPE`) before trusting field extraction.
10. Implement deterministic one-pass field extraction and the canonical label dictionary, prioritizing the observed label variants.
11. Implement bilingual/descriptive label cleanup and contextual `To the Order of` → `consignee` mapping.
12. Implement L0/L1 comparison rules:
   - compound `container_count`
   - `gross_weight_kg`
   - `NET WEIGHT` exclusion
   - conservative entity normalization
   - approved port aliases/codes
13. Implement persistence and exact comparison output.
14. Implement Stage 2 classification/semantic resolvers only for ambiguous cases.
15. Add OCR/Vision for image-only PDFs; unresolved OCR cases may safely remain unresolved until the next milestone.
16. Expose shared case/result APIs for dashboard and email extension.
17. Add end-to-end demo coverage:
   - initial backlog
   - legitimate no-attachment `AWAITING_DOCUMENTS` email
   - ready SI/BL comparison
   - XLSX pair
   - wrong-document-type case
   - scanned/image-only PDF
   - simulated new incoming email
   - automatic dashboard state update

### Hackathon implementation priority

Prioritize the deterministic high-volume path before expensive semantic/OCR refinements:

```text
Stage 1 classification
→ readiness
→ TXT/DOCX/XLSX deterministic extraction
→ label mapping
→ L0/L1 comparison
→ exact mismatch fields
→ reliability edge handling
→ LLM/OCR/Vision refinements
```

Do not optimize by using private reference answers.

This order is a planning recommendation. Codex should adjust it to the actual repository while preserving the architecture and document the adjustment here.

---

## Blocked / Open Questions

These should be resolved from the repository or user direction rather than guessed:

- What backend framework/language is already being used?
- What persistence layer/database already exists?
- Which LLM/Vision provider is selected?
- Which OCR/document-parser libraries are already approved?
- Is Microsoft Graph integration part of the hackathon implementation or only the production integration path?
- Confirm the exact participant-bundle JSON/output schema against the public `sample_submission.json` available to the team.
- What thresholds will be used for:
  - Stage 1 classification confidence
  - Stage 1 top-1/top-2 score gap
  - extraction confidence
  - semantic-resolution confidence?
- Which additional port aliases/codes are safe to approve beyond those observed in public/sample inputs?
- Which unit conversions, if any, should be supported beyond kilograms?

Do not guess these if the answer is available in the repository, dataset guide, or user instructions.

---

## Key Decisions

### KD-001 — No manual upload as the main product workflow

The production-like flow is automatic email ingestion.

Manual/simulated ingestion exists for testing/demo only.

### KD-002 — Backlog + continuous monitoring

The backend supports:

```text
initial backlog processing
+
new incoming email processing
```

### KD-003 — Never hard-code dataset size

Current demo data may have 520 emails, but all logic operates on `N`.

### KD-004 — Classification is cascade-based

Easy cases finish in Stage 1.

Ambiguous/conflicting cases enter Stage 2.

### KD-005 — Only document-comparison emails perform document extraction

Avoid expensive document processing for other categories.

### KD-006 — SI and BL extraction should run in parallel where safe

Avoid unnecessary sequential latency.

### KD-007 — Extract all seven fields per document in one pass where practical

Do not create seven expensive model calls per document.

### KD-008 — Preserve raw values

Normalized values are additional derived data.

Never replace the original source/extracted value.

### KD-009 — Comparison uses progressive normalization

Cheap/safe normalization first.

Deeper/semantic resolution only for fields still different.

### KD-010 — Conservative normalization for entity names

Do not erase meaningful company/person-name differences merely to increase match rate.

### KD-011 — `UNRESOLVED` is a valid backend outcome

Do not force uncertain cases into a false match/mismatch.

### KD-012 — Dashboard and Email Extension share the same backend state

Do not build duplicate processing pipelines for different frontends.

---



### KD-013 — Document-comparison intent is separate from comparison readiness

A `document_comparison` email may legitimately be waiting for another party to provide the draft BL.

Use:

```text
READY_FOR_COMPARISON
AWAITING_DOCUMENTS
UNRESOLVED
```

Do not infer `missing_attachment` from attachment absence alone.

### KD-014 — XLSX is a first-class document format

XLSX SI/BL files must be routed through a structured sheet/key-value reader and use the same canonical label mapping and comparison pipeline.

### KD-015 — Validate document role from content

A filename such as `*_BL.*` is not proof that the content is a Bill of Lading.

Readable-but-wrong documents must become `WRONG_DOCUMENT_TYPE` / `BLOCKED` before comparison.

### KD-016 — Contextual consignee mapping is supported

`To the Order of` may map to canonical `consignee` in the relevant negotiable-B/L context.

Preserve raw label and mapping provenance.

### KD-017 — Compound container values compare by count

For values such as:

```text
6 x 40'HC
```

canonical `container_count = 6`.

Container size/type is preserved as auxiliary parsed data but is not one of the seven required comparison fields.

### KD-018 — Gross weight never falls back to net weight

If a valid gross-weight value is missing, keep `gross_weight_kg` missing/unresolved.

Never substitute `NET WEIGHT`.

### KD-019 — Private evaluator answers are prohibited from runtime inference

`ground_truth.json` and private reference answers may not be read by application code, prompts, caches, rules, or demo prediction logic.


## API / Data Contract Changes

No repository API/schema changes are confirmed yet.

Planned case data now also needs `comparison_readiness` and document-role-validation outcomes.

Planned interfaces from requirements include:

```text
POST /api/v1/sync/initial
POST /api/v1/ingestion/email
GET  /api/v1/emails
GET  /api/v1/emails/{email_id}
POST /api/v1/emails/{email_id}/reprocess   [optional]
```

Codex must replace this section with actual implemented routes/contracts as work proceeds.

---

## Configuration / Environment

No implementation-specific environment variables are confirmed yet.

Likely categories may include:

```text
email provider credentials
database/storage connection
LLM API credentials
OCR/Vision credentials
classification thresholds
extraction thresholds
worker/concurrency limits
polling interval
```

Do not commit secrets.

When adding an environment variable:

1. document its name
2. document whether it is required
3. document a safe example/default when appropriate
4. update `.env.example` or the repository's equivalent

---

## Tests & Validation

### Required future coverage

#### Ingestion

- initial sync
- duplicate email
- already processed email
- simulated new email
- idempotency

#### Classification

- each of the five categories
- misleading subject
- body/subject conflict
- Stage 2 escalation
- legitimate `AWAITING_DOCUMENTS` document-comparison email
- immediate comparison request with genuinely missing attachment

#### Document routing

- text
- text PDF
- DOCX
- XLSX
- scan/image
- missing/corrupt attachment
- wrong document type despite misleading SI/BL filename

#### Extraction

- all seven required fields
- alternate field labels
- bilingual/descriptive labels
- contextual `To the Order of` consignee mapping
- raw value preservation
- missing/ambiguous extraction

#### Comparison

- exact match
- whitespace/case variation
- `22,000 KG` vs `22000 kg`
- compound container count such as `6 x 40'HC`
- gross-weight extraction must not use `NET WEIGHT`
- container count mismatch
- conservative entity-name handling
- semantic ambiguity → `UNRESOLVED`
- all seven match → `No mismatch detected`

### Validation log

No code validation has been recorded yet.

Codex must append real commands/results here after coding.

Example format:

```text
2026-09-20
- `pytest tests/...` → PASS (42 tests)
- `ruff check .` → PASS
- `mypy ...` → NOT RUN: project has no mypy config
```

Never fabricate test results.

---

## Known Limitations

Current document-level limitations:

- Human Review UI/workflow is not specified in this milestone.
- Microsoft Graph integration may be an integration path rather than an implemented hackathon dependency.
- Exact model/OCR/provider choices are intentionally not locked until repository constraints are inspected.
- Exact participant-facing challenge submission schema must be verified against the public `sample_submission.json` used by the team.
- No implementation claim should be made from this document until source code is inspected.

---

## Recent Change Log

### 2026-09-20 — Dataset-audit architecture revision

- **Changed:** Added Comparison Readiness, XLSX routing, content-based document-role validation, bilingual/contextual field mapping, compound container parsing, gross-vs-net guard, and private-ground-truth isolation rules.
- **Why:** Direct inspection of the provided dataset exposed real cases not covered by the original abstract spec, especially legitimate no-attachment BL-comparison workflow emails.
- **Files:** `backend_requirements_ingestion_to_compare.md`, `AGENTS.md`, `implement.md`
- **Validation:** Documentation cross-checked against the provided dataset/organizer bundle; no application source-code tests run.
- **Next:** Inspect the actual repository, then implement the deterministic ingestion/classification/readiness/extraction/compare path first.

### 2026-09-20 — Initial project handoff structure

- **Changed:** Created the initial shared implementation-status document and Codex working rules.
- **Why:** Keep coding sessions consistent and let teammates understand project state quickly.
- **Files:** `AGENTS.md`, `implement.md`
- **Validation:** Documentation only; no source-code tests run.
- **Next:** Inspect the repository and update all `NOT CONFIRMED` implementation statuses before making architecture assumptions.
