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
**Updated by:** Phase R targeted sync reliability repair
**Repository state:** Windows CPython 3.11.9, PostgreSQL 16, Alembic migrations, and the Phase R reliability suite have been independently verified. Phase 0 baseline/harness work remains.

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

### Phase 0 — Audit, traceability, evaluation harness, baseline

- Frozen the original requirement ID set in `docs/requirements_seed_ids.txt` before editing the matrix.
- Static audit found that the persisted classifier exposes `GENERAL_MAIL` and `UNCERTAIN`, and routes unresolved cases into Human Review; this conflicts with the five-category contract and the current milestone scope.
- The prior local-runtime blocker is resolved: CPython 3.11.9 and PostgreSQL 16 are available. Phase 0 still needs a reproducible dependency manifest, bundle-path configuration, test environment setup, harness, and baseline.

### Phase R — Targeted source-stream reliability repair

- Fixed `SyncService.sync` so a generator-level source failure is reported as `SOURCE_ITERATION_FAILED`, does not escape the service boundary, and commits previously completed messages.
- The failure is intentionally source-scoped: there is no materialized `EmailMessage` to persist when `next(iterator)` fails, so no synthetic email/job is created.
- Strengthened the existing broken-source test to assert truthful counts, structured failure data, persisted prior work, and a subsequent clean sync.
- Fixed per-email transaction isolation: each materialized email now commits after processing, so a later materialized-email failure and its existing `Session.rollback()` cannot discard earlier successful work.
- `failed` now means materialized email-processing failures only; `source_failed` and `source_failures` represent iterator failures separately.
- Reproducibility repair: declared `httpx2>=2.13,<3.0` (not `httpx`): installed Starlette 1.6 `TestClient` imports `httpx2`. A disposable CPython 3.11.9 environment installed only `backend/requirements.txt`, imported `fastapi.testclient.TestClient`, and passed `backend/tests/test_api.py` (10 passed, 1 deprecation warning). The default participant-bundle path is now `data/bundle` in settings, examples, Docker compose, and bundle-dependent tests.

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

### Phase 0 execution blockers

- The available `C:\\msys64` Python reports a Windows platform for packages but has no compatible binary wheels for the declared `uvicorn[standard]` and `psycopg[binary]` extras. A standard Windows CPython environment (or a compatible locked dependency set) is required before test/migration/app execution can be evidenced.
- PostgreSQL 16 and the project connection have been independently verified. The organizer server remains an external prerequisite for the one permitted score call.
- The public contract does not define an official `AWAITING_DOCUMENTS` submission mapping. Any baseline-only mapping must remain isolated and explicitly marked `UNVALIDATED`.

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

2026-09-20
- `pytest backend\tests\test_sync_service.py::test_sync_continues_after_broken_email -vv` → NOT RUN: `pytest` is not on this shell's PATH.
- `pytest backend\tests\test_sync_service.py -vv` → NOT RUN: `pytest` is not on this shell's PATH.
- `pytest backend\tests\test_repositories_postgres.py backend\tests\test_sync_service.py -rs` → NOT RUN: `pytest` is not on this shell's PATH.
- `pytest` → NOT RUN: `pytest` is not on this shell's PATH.
- `python -m compileall -q backend\app\sync backend\tests` → PASS.

2026-09-20 — Phase R per-email transaction repair
- `python -m pytest backend\tests\test_sync_service.py -vv` → NOT RUN: the available `C:\\msys64\\ucrt64\\bin\\python.exe` has no pytest module.
- `python -m pytest backend\tests\test_repositories_postgres.py backend\tests\test_sync_service.py -rs` → NOT RUN: same environment limitation.
- `python -m pytest` → NOT RUN: same environment limitation.
- `python -m compileall -q backend\app\sync backend\tests` → PASS.
- `git diff --check` → PASS.

2026-09-20 — Phase 0 reproducibility verification
- `HOLYSHIP_TEST_DATABASE_URL=postgresql+psycopg://holyship:holyship@localhost:5432/holyship .venv\\Scripts\\python.exe -m pytest -q` → PASS: 71 passed, 1 Starlette/AnyIO deprecation warning, 6.12s.
- `.venv\\Scripts\\python.exe -m compileall -q backend\\app\\sync backend\\tests` → PASS.
- `git diff --check` → PASS.

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

### 2026-09-20 — Phase 0 test and bundle reproducibility repair

- **Changed:** Added declared `httpx2` test dependency after clean-install verification and replaced the legacy `sdoc-hackathon-bundle` default/test/Docker path with `data/bundle`; removed the obsolete root junction so only `data/bundle` remains.
- **Why:** A clean checkout must run the existing TestClient suite and public participant bundle without a local junction or manual dependency installation.
- **Files:** `backend/requirements.txt`, `backend/app/core/config.py`, `.env.example`, `docker-compose.yml`, bundle-dependent tests, `implement.md`.
- **Validation:** Full PostgreSQL-enabled suite passed: 71 passed, 1 deprecation warning.
- **Next:** Build the Phase 0 Makefile/harness, finish traceability evidence, run the 520-email baseline, then perform exactly one score call.

### 2026-09-20 — Phase 0 harness and clean dependency verification

- **Changed:** Replaced the incorrect declared `httpx` dependency with `httpx2>=2.13,<3.0`; Starlette 1.6's `TestClient` imports `httpx2`. Added a public-contract boundary adapter, `@pytest.mark.req("SUB-01")` coverage, a Phase 0 Makefile/trace gate, and a public-bundle baseline script. Removed the obsolete `sdoc-hackathon-bundle` junction so `data/bundle` is the only bundle entry point.
- **Clean-install evidence:** Disposable CPython 3.11.9 environment installed only `backend/requirements.txt`; `from fastapi.testclient import TestClient` succeeded and `backend/tests/test_api.py -q` reported **10 passed, 1 deprecation warning**.
- **Validation:** With `HOLYSHIP_TEST_DATABASE_URL=postgresql+psycopg://holyship:holyship@localhost:5432/holyship`, `python -m pytest -q` reported **72 passed, 0 skipped, 1 deprecation warning**. `python -m compileall -q backend/app backend/tests scripts`, `git diff --check`, and `python scripts/trace_phase0.py` passed.
- **Baseline blocker:** The configured ordinary database has `alembic_version=20260919_0002 (head)` but lacks `email_messages`. `alembic upgrade head` correctly performed no work because the stale version row says head. The new baseline script fails before syncing any mail with this explicit precondition error. I did not run destructive downgrade/reset or call `/submit`; therefore no score was requested.
- **Spec/code gap:** The legacy classifier categories are adapted only at the submission boundary. `DOCUMENT_COMPARISON` becomes `BL_COMPARISON` with `NEEDS_REVIEW/missing_value` because actual document comparison is not implemented until later phases; legacy `UNCERTAIN` uses its highest supported candidate (or `GENERAL` fallback) and is never emitted as a sixth public category.

### 2026-09-20 — Phase 0 isolated database baseline

- **Root cause and safeguard:** `DATABASE_URL` and `HOLYSHIP_TEST_DATABASE_URL` previously named the same database. PostgreSQL test fixtures call `Base.metadata.drop_all/create_all/drop_all`, deleting the development tables while leaving `alembic_version` at head. `.env.example` now uses `holyship_dev` and `holyship_test`; `scripts/database_isolation.py` compares resolved host/user/port/database identities and `make test` / `make check` refuse an identical pair before pytest runs.
- **Database evidence:** Read-only verification after the isolated test suite found development tables `email_messages`, `attachments`, `processing_jobs`, `classification_results`, `human_review_cases`, and document tables in `holyship_dev`. The earlier inconsistent `holyship` database was not repaired or reused.
- **Baseline:** `holyship_dev` processed the public 520-email bundle: 499 classified, 21 human-review outcomes, 0 failed, 0 source failures; 3.978 seconds / 130.720 emails per second. Reports are `reports/latest/eval.md`, `reports/latest/submission.json`, `reports/baseline.md`, and `reports/history.csv`.
- **Gates:** `make trace PHASE=0` passed. `make check PHASE=0` passed: 72 passed, 0 skipped, 1 deprecation warning; reliability subset 10 passed. The explicit isolation guard printed distinct dev/test URLs.
- **Score:** The single `make score PHASE=0` call reran the successful gates but POST `/submit` was refused at `localhost:8080`. No organizer response or scoreboard exists; the real failed attempt is recorded in `reports/score_history.jsonl` and was not retried.

### 2026-09-20 — Phase R per-email transaction isolation

- **Changed:** Committed each materialized email before reading the next one; added `source_failed` separate from materialized-email `failed`; added a PostgreSQL integration test for A-success/B-processing-failure/C-success.
- **Why:** The previous single outer transaction allowed B's `Session.rollback()` to invalidate A while the report still described A as successful.
- **Files:** `backend/app/sync/service.py`, `backend/tests/test_sync_service.py`, `implement.md`.
- **Validation:** Compile and diff checks passed. The required pytest commands were attempted but cannot run under the current MSYS Python because pytest is not installed.
- **Next:** Run the required pytest commands in the user-reported PostgreSQL-enabled environment, then continue Phase 0 only.

### 2026-09-20 — Phase R source-stream exception isolation

- **Changed:** Added structured `SOURCE_ITERATION_FAILED` reporting at the `EmailSource.iter_messages()` boundary and strengthened the broken-source integration test.
- **Why:** A source generator exception previously escaped the sync loop, preventing the normal final commit of already completed work.
- **Files:** `backend/app/sync/service.py`, `backend/tests/test_sync_service.py`, `implement.md`.
- **Validation:** Syntax compilation passed. Required pytest commands could not run because no `pytest` executable is available in this shell.
- **Next:** Run the four required pytest commands in the PostgreSQL-enabled test environment; then resume Phase 0 only.

### 2026-09-20 — Phase 0 audit started; executable baseline blocked

- **Changed:** Added the frozen requirement-ID list and recorded static audit findings/blockers.
- **Why:** Phase 0 requires evidence-backed traceability before any product behavior changes.
- **Files:** `docs/requirements_seed_ids.txt`, `implement.md`.
- **Validation:** Read the public participant contract; searched source/tests for private-data references, email-specific logic, hard-coded backlog size, category values, and Human Review usage. Test/migration/app/full-sync/score were not run because dependency installation and external services are blocked.
- **Next:** Provide a compatible CPython environment, `.env` + PostgreSQL, and organizer server, then resume Phase 0 from the audit/test gate.

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
