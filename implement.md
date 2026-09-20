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

**Current scope includes the persisted-result product API; frontend UI remains out of scope.**

Human Review UI/workflow is intentionally not part of the current milestone.

---

## Last Updated

**Date:** 2026-09-20  
**Updated by:** Phase F final adversarial audit
**Repository state:** `phaseF` is the active audit branch from `feature/email-classification` at `f4081af`. Phase F changes remain isolated; no merge or rebase has been performed.

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

Phase F final adversarial audit is in progress on the isolated `phaseF` branch. The audit has closed SEC-04, SCP-02, and SCP-06 with executable evidence and repaired the reproduced incoming-base64 size-bound defect. Final trace/check and fresh-clone parity remain the last gates before human review.

| Area | Status | Notes |
|---|---|---|
| Requirements | DONE | Backend requirements defined through comparison |
| Repository/stack audit | DONE | Python/FastAPI/SQLAlchemy/PostgreSQL stack and public participant bundle verified |
| Email ingestion | IMPLEMENTED | Source adapters normalize provider messages; duplicate identity is database-backed |
| Initial sync | IMPLEMENTED | Repeated sync skips completed unchanged messages and processes progressively |
| Continuous ingestion | VERIFIED — PHASE 7 | Generic worker, startup lifespan, configurable 60-second polling, bounded backoff, durable source checkpoint, restart persistence, and completed-email/attachment dedupe passed live PostgreSQL verification |
| Classification Stage 1 | IMPLEMENTED | Centralized deterministic signals and thresholds; exact five-category output contract |
| Classification Stage 2 | IMPLEMENTED | Validated five-category output, explicit zero-signal policy, evidence-aware deterministic tie handling |
| Comparison readiness | IMPLEMENTED | READY_FOR_COMPARISON / AWAITING_DOCUMENTS / UNRESOLVED after document_comparison only |
| Attachment retrieval | IMPLEMENTED | Lazy source-owned retrieval only for READY_FOR_COMPARISON; SHA-256 and storage identity persisted |
| Document router | IMPLEMENTED | TXT/PDF/DOCX/XLSX native paths; scanned/image inputs enter OCR/Vision directly; failures are structured |
| Document role validation | IMPLEMENTED | Content/title/table evidence assigns SI/BL; filename is never proof; clear wrong business documents block |
| SI/BL extraction | IMPLEMENTED | Deterministic independent seven-field extraction, bounded SI/BL parallel work, persistence, and versioned content-hash reuse |
| Canonical field mapping | IMPLEMENTED | Strict dictionary, bilingual/contextual/table provenance, ambiguity handling, and NET-weight exclusion have executable evidence |
| Comparison pipeline | IMPLEMENTED — PHASE 4 | Persisted SI-reference comparison with exact MATCH/MISMATCH/UNRESOLVED evidence and COMPLETED/BLOCKED transitions |
| Targeted hard-case AI | IMPLEMENTED — LIVE PROVIDER NOT VERIFIED | Disabled by default; unresolved extraction fields batch per document; semantic AI runs only after L0/L1 uncertainty; structured results are evidence/type/unit/confidence validated |
| OCR | IMPLEMENTED / MOCK VERIFIED | Native-first routing, injectable engine, content cache, timeout, call budget, concurrency limit, and clean failure outcomes |
| Persistence | IMPLEMENTED THROUGH PHASE 6 | Non-destructive AI proposal/audit persistence and versioned request-cache identity added |
| Reliability/performance | VERIFIED — PHASE 6 | 257 tests, PostgreSQL cache/concurrency tests, trace 89/0/0, byte-identical disabled evaluation, and measured sub-20% slowdown |
| Dashboard backend API | IMPLEMENTED — PHASE 7 | `/api/v1/emails`, `/api/v1/summary`, unified detail, filters, pagination, and persisted event polling |
| Email-extension backend API | IMPLEMENTED — PHASE 7 | Shared v1 email/detail/ingestion contracts; no extension UI was added |
| Human Review product API | IMPLEMENTED — READ-ONLY | Reviewer queue/detail composition exposes persisted reason, evidence, comparison, and AI provenance; no review mutation |
| Human Review UI/workflow | OUT OF SCOPE | No frontend or reviewer action workflow was added |

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

### Phase R — close Phase 7 implementation and verification gaps

- Added generic `ContinuousIngestionWorker` with source-independent polling, restart-safe DB-backed checkpoint persistence, bounded exponential backoff, reset-after-success behavior, and no-refetch/no-reprocess guards for unchanged completed messages.
- Added optional FastAPI lifespan startup integration for initial sync and continuous polling. Disabled settings create no worker; startup initial sync runs in a daemon thread and does not block HTTP startup.
- Added migration `20260920_0012_ingestion_checkpoints` and centralized polling settings with safe `.env.example` defaults.
- Added request-only base64 attachment content to the generic incoming API so simulated/demo messages use the shared lazy source and real document pipeline.
- Added a completed `progress` snapshot to `/api/v1/sync/initial`; the endpoint remains explicitly synchronous.
- Added `scripts/demo.sh` and expanded the HTTP-only demo to text, XLSX, wrong-document, scanned-PDF, `AWAITING_DOCUMENTS`, and spam scenarios with event checks.
- Added requirement-marked polling/runtime/API tests and a PostgreSQL checkpoint-restart test (skipped when `HOLYSHIP_TEST_DATABASE_URL` is absent).

### Phase 7 — product-facing API and live-demo boundary

- Added explicit Pydantic product contracts for queue rows, summary counts, unified email detail, documents, extracted fields, seven-field comparison, evidence, timeline, reviewer context, AI resolution provenance, and polling events.
- Added `/api/v1/emails` with stable pagination and server-side status/category/readiness/review/comparison/mismatch/search/time filters. Queue rows include attachment, mismatch, unresolved, and needs-review summaries.
- Added `/api/v1/summary` with persisted status/review/readiness/mismatch/unresolved aggregates.
- Added `/api/v1/emails/{id}` and `/detail` unified detail routes; GET composition uses eager/bulk loading and never runs document readers, OCR, extraction, AI resolution, or comparison.
- Added read-only `/api/v1/human-review` queue/detail composition and `/api/v1/events` as a deterministic polling-compatible `EMAIL_PROCESSING_UPDATED` feed.
- Added `/api/v1/sync/initial`, `/api/v1/ingestion/email`, and technical-failure-only `/api/v1/emails/{id}/reprocess` aliases over the existing `SyncService`; legacy `/api/*` routes remain unchanged.
- Added a provider-isolated `MicrosoftGraphSource` payload adapter with no credentials/network dependency.
- Added `scripts/demo_phase7.py`, `scripts/demo.sh`, `docs/phase7_api.md`, `reports/phase7_api_audit.md`, `reports/phase7_api_verification.md`, `reports/phase7_demo.md`, and the Phase 7 PostgreSQL/API/provider tests.
- Product responses reuse persisted processing tables and do not expose request payloads, prompts, secrets, or AI cache identities. Phase R adds only the additive checkpoint migration `20260920_0012`.

### Phase 6 — targeted hard-case AI layer

- The Phase 0–5 deterministic path remains primary. `AI_ESCALATION_ENABLED=false` produces no resolver calls.
- `backend.app.resolution` supplies provider-independent extraction/semantic contracts, structured validation, finite retry/timeout, per-case budget, concurrency limits, stable versioned cache keys, and single-flight behavior.
- Environment-backed settings now construct the configured resolver for both API and batch entry points. The factory shares provider limits and duplicate suppression across in-process SQLAlchemy worker sessions; disabled mode constructs no provider.
- Only `UNRESOLVED`/`AMBIGUOUS` fields with source evidence escalate; hard fields are batched per document. Accepted values are comparison-only overlays. Phase 3 `extracted_fields` rows are never overwritten.
- Semantic escalation occurs only after L0/L1 make no decision. Definite matches/mismatches bypass AI. Missing/unanchored/conflicting evidence, low confidence, malformed output, unsafe units, timeout, retry exhaustion, or persistence failure remains unresolved.
- Migration `20260920_0011` adds `ai_resolutions` with versioned request identity, request/response JSON, acceptance, confidence, validation reason, call count, and timestamps.
- `OcrReader` now supports injected engines and Tesseract detection with SHA-256 cache, timeout, call budget, concurrency limit, and structured unavailable/timeout/exhaustion outcomes. OCR output uses the existing role validator and deterministic extractor.
- No provider SDK or production dependency was added. Live AI-provider and live Tesseract accuracy are not claimed.

### Self-evaluation harness — dedicated clean evaluation database

- `make eval`, `make perf`, and the eval stage of `make check` now require `HOLYSHIP_EVAL_DATABASE_URL` and use it exclusively for evaluation persistence. The normal development and test URLs retain their original roles.
- Evaluation fails before destructive work if eval resolves to dev, test, an empty database name, or PostgreSQL maintenance databases (`postgres`, `template0`, `template1`). Unit tests cover each refusal path.
- Every evaluation drops only the dedicated eval database's `public` schema, recreates it, applies the complete Alembic chain through `20260920_0010`, processes every public bundle ID with current code, validates the generated public contract against `sample_submission.json`, and writes the normal reports.
- Two independent clean runs produced byte-identical `reports/latest/submission.json` files with SHA-256 `37b33169797c6aef6b781fbcbf1ba99cb92d3a8d96ac184235eeda167d2a4eab`.
- Observed regression distribution remains category `BL_COMPARISON=203`, `SI_REQUEST=141`, `INVOICE_QUERY=84`, `GENERAL=66`, `SPAM=26`; status `OK=317`, `MISMATCH=0`, `NEEDS_REVIEW=203`. These values are observed evidence only and are not runtime assertions or prediction rules.
- Read-only dev fingerprints before and after all eval/check work matched exactly (`6346f45875e8581f51e85833dd56f9f58037af7938f7ad61f2cff1478307dd3b`), with Alembic still at `20260920_0008` and all row counts unchanged. Eval runs also left the test fingerprint unchanged; the later full test target performed its existing intentional test-fixture cleanup independently.
- No classifier, readiness, routing, extraction, comparison, or submission mapping behavior changed. No dependency was added and no scoreboard call was made.

### Phase 5 — reliability and performance hardening

- `SyncService` now supports a bounded in-flight email window with one SQLAlchemy session per worker when a session factory is provided. The default remains single-worker when no factory is supplied, preserving existing callers and deterministic semantics.
- Repeated unchanged syncs skip completed and business-blocked cases. Interrupted technical states (`NEW`, `QUEUED`, `CLASSIFYING`, `RETRIEVING_ATTACHMENTS`, `EXTRACTING`, and `COMPARING`) are eligible for restart/resume. Source message, job, classification, attachment, document, and extraction identities are persisted with database uniqueness/conflict recovery.
- Additive migrations `20260920_0009` and `20260920_0010` add job/classification content identities, attachment/document identities, attempt counts, and a durable `(content_sha256, extractor_version)` extraction-cache pointer.
- Retry/timeout controls are finite and configurable. Organizer HTTP retries only transient network/408/425/429/5xx failures and records structured retry events; deterministic failures are not retried. Injected semantic resolvers receive bounded timeout/malformed-output handling and become structured `UNRESOLVED` results.
- Sync reports now expose wall time, throughput, per-email p50/p95, retries, reader/extractor/OCR/Vision counts, cache hits/misses, worker count, and unhandled worker exceptions. `run_baseline.py` consumes these values instead of hard-coding external-call counts.
- No Phase 0–4 category/readiness/field/comparison behavior, Human Review UI, Phase 6 AI provider, or Phase 7 frontend was added.

### Phase 5 final verification and closure

- Clean PostgreSQL verification used isolated `holyship_dev`, `holyship_test`, and `holyship_eval` databases on a temporary local PostgreSQL 18.6 cluster. Alembic clean upgrade, Phase 5 downgrade/upgrade, and live schema constraints/indexes all passed through `20260920_0010`.
- The first live reliability run exposed one real defect: `EmailRepository.upsert_message()` flushed a new row before assigning its required `content_hash`. The insert now initializes that field before the savepoint flush. This is the only implementation change made during final verification.
- PostgreSQL reliability target passed 14/14; the full suite passed 222/222 with no skips and one existing Starlette/HTTP-client deprecation warning. Cache/retry/failure-isolation coverage passed.
- Clean evaluation processed all 520 public emails with 0 failures and 0 unhandled exceptions. Category distribution remained `BL_COMPARISON=203`, `SI_REQUEST=141`, `INVOICE_QUERY=84`, `GENERAL=66`, `SPAM=26`; status distribution remained `OK=317`, `NEEDS_REVIEW=203`, `MISMATCH=0`.
- Repeated clean runs and workers=1 versus workers=4 produced byte-identical submission SHA-256 `37b33169797c6aef6b781fbcbf1ba99cb92d3a8d96ac184235eeda167d2a4eab`. Final measured run: 13.351 seconds, 38.949 emails/second, p50 0.024455 seconds, p95 0.106313 seconds.
- Full `mingw32-make check` passed, including test, clean eval, reliability, performance, and trace stages. Peak RSS was not measured; no score call was made.

### Phase 4 — P4C comparison persistence, pipeline, and submission boundary

- `comparison_results` preserves email, SI extraction, BL extraction, comparison version, state, exact mismatch/unresolved lists, definite-mismatch and all-fields-definite flags, reason code, and message. `field_comparisons` preserves all seven side-by-side raw, canonical, and normalized values plus layer, final status, reason, evidence, and source field identities.
- Central `COMPARISON_VERSION = "phase4-deterministic-v1"` and the unique email/SI/BL/version identity make reruns idempotent. PostgreSQL checks constrain comparison state, exact canonical fields, field statuses, and layers.
- Pipeline integration consumes persisted Phase 3 extraction rows without reopening attachments or invoking readers/extractors. It records `EXTRACTING -> COMPARING -> COMPLETED` when all fields are definite and `EXTRACTING -> COMPARING -> BLOCKED` with `COMPARISON_UNRESOLVED` when any field is unresolved.
- A definite mismatch is a completed business result, not a technical failure. Mixed mismatch plus unresolved preserves both fact sets internally and remains BLOCKED. Unexpected comparison exceptions become structured `COMPARISON_FAILED / FAILED` outcomes inside the existing per-email transaction boundary; prior results survive and later emails continue.
- Comparison normalization is additive. PostgreSQL reload evidence proves Phase 3 raw/native/canonical/provenance rows are byte-for-byte logically unchanged while comparison-normalized values live only on field-comparison rows.
- The isolated submission adapter maps completed clean to `OK`, completed definite mismatch to `MISMATCH`, and supported blocked reasons to `NEEDS_REVIEW` with only the public reason strings. The provisional `AWAITING_DOCUMENTS -> NEEDS_REVIEW/missing_value` policy remains explicitly `UNVALIDATED`. Mixed internal mismatch/unresolved state is compressed at this boundary without mutating or discarding its internal facts.
- Additive migration `20260920_0008_add_phase4_comparison.py` creates both comparison tables, foreign keys, uniqueness, checks, and lookup indexes. Read-only development introspection confirmed head `20260920_0008` and all expected tables/constraints/indexes after the test suite.
- `reports/comparison_sanity.md` uses only public participant data and claims no accuracy: 112 comparison-ready emails, 98 valid SI/BL pairs attempted, 0 clean, 0 fully definite mismatch, 98 blocked unresolved, 0 failed; L0=267, L1=7, L2=29. Comparison itself caused 0 reader/extractor calls and all LLM/OCR/Vision provider calls were 0.
- Closed `CMP-09`, `CMP-10`, `CMP-11`, `STA-05`, `SUB-02`, and `SUB-03`. Phase 4 trace is 76 PASS / 0 TODO / 0 FAIL.

### Phase 3 — P3A-2 one-pass deterministic extraction and persistence

- `DeterministicDocumentExtractor.extract()` performs one coordinated scan of an already-materialized `UnifiedDocument` and always returns exactly seven field slots. Missing fields remain explicit `MISSING` rows; malformed values become `UNRESOLVED`; conflicting candidates become `AMBIGUOUS` with candidate evidence.
- Each field result preserves canonical field, original raw label/value, typed canonical value, status, confidence, mapping method, structured source location, and evidence. Raw data is additive and is never replaced by canonicalization.
- Text provenance records page, source line, and text span. Table provenance records table/sheet name, original row number, label cell, and value cell.
- `XlsxReader` now retains native cell values and A1 coordinates while continuing to expose the existing row values. `DocxReader` adds table cell positions. Phase 2 materialization now persists page/table/cell structure instead of discarding titles and coordinates.
- Deterministic inputs cover `Label: Value`, conservative multiline entity blocks, TXT, text PDF, DOCX tables, and XLSX key/value or header/value tables. No attachment is reopened after `UnifiedDocument` materialization.
- Table-position mappings emit `table_structure`; their underlying label-dictionary method remains in evidence. The full six-value provenance vocabulary is preserved, while deterministic Phase 3 never emits `llm_resolved`.
- `To the Order of ...` produces a contextual consignee only for an explicit negotiable draft-BL role and consignee context. It never populates notify party or crosses documents.
- Numeric extraction preserves raw values while producing typed values: `22,000 KG` and `22000 kg` become `22000`; native XLSX `22000` remains an integer; `6 x 40'HC` becomes count `6` with `40'HC` retained only as auxiliary evidence.
- `NET WEIGHT` and other explicitly non-gross labels cannot populate `gross_weight_kg`. Gross and net labels coexist independently; absent gross remains missing.
- Alembic `20260920_0007` additively extends existing extraction tables with extractor version, raw label/native raw JSON, canonical JSON value, source location, mapping method, exact field/status/method/confidence constraints, and one-row-per-field uniqueness. It adds no cache lookup or cache uniqueness.
- Valid Phase 2 SI/BL materializations now persist all seven downstream field rows and remain at `EXTRACTING`; no comparison state or outcome is created.
- Closed `EXT-01`, `EXT-02`, `EXT-04`, `EXT-05a`, and `MAP-04`. `EXT-03` and `EXT-06` intentionally remain TODO for P3B.

### Phase 3 — P3A-1 canonical field contract and strict label mapping

- The authoritative in-memory vocabulary contains exactly `shipper`, `consignee`, `notify_party`, `port_of_loading`, `port_of_discharge`, `container_count`, and `gross_weight_kg`; auxiliary data cannot become an eighth canonical field.
- `backend/app/extraction/field_labels.json` is the single configurable mapping dictionary. It contains general shipping-label aliases only and no email IDs, filenames, corpus answers, or private reference data.
- Lookup normalization is deliberately conservative: Unicode NFKC, surrounding/repeated whitespace, case-folding, and a trailing label colon. It does not use fuzzy matching, edit distance, embeddings, substring guessing, or broad parenthesis removal.
- Supported bilingual/descriptive labels are explicit dictionary entries, so their complete original `raw_label` is preserved. Meaningful unsupported parenthesized qualifiers remain unresolved.
- `To the Order of ...` maps to `consignee` only when the caller supplies explicit negotiable Bill-of-Lading, consignee-section context. Ordinary order language and SI/unrelated contexts remain unresolved.
- Explicit net/tare-weight labels, including `NET WEIGHT`, `Net Wt`, `Net Weight (KG)`, and `净重`, are blocked from `gross_weight_kg`. A gross label remains independently eligible when gross and net labels coexist.
- Mapping provenance is a closed six-value enum: `exact_label`, `alias_dictionary`, `bilingual_label_normalization`, `contextual_business_rule`, `table_structure`, and `llm_resolved`. P3A-1 emits only the first four deterministic methods; `table_structure` and `llm_resolved` are reserved and never fabricated.
- Matrix rows `MAP-01`, `MAP-02`, `MAP-03`, `MAP-05`, and `MAP-06` are closed with substantive tests. `MAP-04` intentionally remains TODO until P3A-2 exercises and persists table-structure provenance.
- No extraction orchestration, document parsing changes, database migration, field persistence, cache, SI/BL parallelism, comparison, LLM, or Vision behavior was added.

### Phase 2 — document materialization and role validation

- Only `document_comparison / READY_FOR_COMPARISON` enters attachment retrieval. Non-comparison mail, `AWAITING_DOCUMENTS`, and unresolved readiness never load attachment bytes.
- Immediate comparison requests that explicitly expect SI and draft BL now remain ready even when one or both attachments are absent; retrieval then persists `MISSING_REQUIRED_ATTACHMENT / BLOCKED`, distinct from a true request to send a future draft BL.
- `EmailSource.get_attachment_content()` is the lazy content boundary. Static bundle and organizer HTTP adapters implement it; incoming API sources accept explicitly supplied content and otherwise fail with a structured attachment-read outcome.
- `DocumentMaterializationService` preserves attachment identity and source reference, computes SHA-256, persists raw materialized text/table cells separately, and stops valid pairs at `EXTRACTING`. It does not perform seven-field extraction or enter `COMPARING`.
- Native routing supports TXT/CSV, text PDF, DOCX paragraphs/tables, and XLSX rows/cells. XLSX native numeric cell types remain intact in `UnifiedDocument.tables`.
- Image inputs enter OCR/Vision without visiting native text/Office readers. Image-only PDFs require one PDF readability probe, then enter OCR/Vision directly. An unavailable OCR backend becomes `UNREADABLE_ATTACHMENT / BLOCKED`, not a crash.
- Empty, corrupt/truncated, unsupported, source-read, and unexpected reader failures have structured outcomes. Technical failures persist `FAILED`; safe business stops persist `BLOCKED`; later emails continue.
- `DocumentRoleValidator` uses materialized text and table/cell content. Explicit SI/BL headers assign roles; `COMMERCIAL INVOICE`, `PACKING LIST`, and `CERTIFICATE OF ORIGIN` produce `WRONG_DOCUMENT_TYPE`; inconclusive evidence remains unknown and blocks without guessing. Filename suffixes are supporting metadata only and never determine a role.
- Alembic `20260920_0006` adds attachment hash/retrieval fields, document routing/role/validation evidence, parse duration, database checks, and the hash index. Existing rows receive explicit non-fabricated legacy/default states.
- The public audit in `reports/attachment_inventory.md` covers all 520 emails and all 250 attachments: `SI_FOUND=123`, `BL_FOUND=114`, `WRONG_DOCUMENT_TYPE=5`, `CORRUPTED_ATTACHMENT=2`, `UNREADABLE_ATTACHMENT=6`; no attachment lacks a defined outcome.
- Public Phase 2 email audit: 317 non-comparisons do not enter, 91 remain `AWAITING_DOCUMENTS`, 98 valid pairs reach `EXTRACTING`, and 14 ready cases block (`5` missing, `4` wrong type, `3` unreadable scan cases, `2` corrupt attachments). The audit is offline coverage; executable PostgreSQL evidence proves runtime lazy loading.

### Phase 1 — R3B scope/process closure

- Human Review is frozen: current classifier/sync processing creates no new review cases; unresolved readiness persists `BLOCKED` with `READINESS_UNRESOLVED`. Historical storage and read-only routes remain compatible.
- Alembic `20260920_0005` adds non-null persisted classification `reason_code` and database checks for the five categories, confidence `[0, 1]`, and the three readiness values.
- API schemas now expose exact category, readiness, and 11-state processing-status contracts; email responses include processing status and classification responses include reason code.
- `reports/phase1_consistency_audit.md` records runtime, persistence, live-database, API, migration, test, and documentation consistency.
- Legacy `GENERAL_MAIL` / `UNCERTAIN` handling is confined to migration/export compatibility boundaries and is absent from the authoritative runtime enum.
- `SCP-01`, `SCP-05`, and `SCP-07` have substantive executable and audit evidence. All 22 Phase-1-owned requirements are PASS.

### Phase 1 — R3A-2 classification closure

- Exact runtime category set is `document_comparison`, `new_si_request`, `invoice_query`, `general_message`, and `spam`.
- True all-zero evidence uses an explicit neutral `general_message` result with confidence `0.20`, `low_confidence=True`, and reason code `ZERO_SIGNAL_GENERAL`; this is not a blanket fallback for evidence-bearing ambiguity.
- Stage 2 zero-signal output is independent of enum/dictionary order. Evidence-bearing ties use body score, subject score, then an explicit lexical tie-break.
- A bare `draft BL` mention is no longer specialized classification evidence. Action-specific send/provide/issue/check/compare signals preserve the legitimate Pattern A workflow.
- Pattern A remains `document_comparison` / `AWAITING_DOCUMENTS`; Pattern B remains `new_si_request` with no readiness evaluation.
- The fixed-seed public audit preserves all 91 legitimate awaiting cases and all three immediate-comparison/missing-document cases.
- `CLS-01`, `CLS-05`, `CLS-06`, `CLS-07`, `CLS-08`, `CLS-10`, and `CLS-12` now have passing executable evidence.

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

- Phase R implementation and service-backed verification are complete for the current scope. The live API, PostgreSQL migration/checkpoint path, demo, exporter, AI-disabled evaluation, reliability, performance, and full test gate have evidence below.
- `ING-08` is now PASS in the requirements matrix after live A/B, restart, and A/B/C polling evidence; no Phase F work has started.
- The older Phase 0 and Phase R notes below are historical implementation context, not current blockers.

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

- Human review of the Phase 7 evidence and commit is next. Do not merge or start Phase F from this task.
- Keep the three database identities isolated for any future destructive test/evaluation operation.
- Do not merge. Human Review UI/actions remain out of scope.

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

- Live AI provider choice, credentials, latency, and accuracy are NOT VERIFIED.
- Live Tesseract accuracy on the six public scanned documents is NOT VERIFIED; injected behavior and failures are covered.
- The public self-evaluation service was not called in Phase 6; no hidden labels were used.
- Cross-process provider-call single-flight is not implemented. PostgreSQL uniqueness keeps persisted resolution rows idempotent, but separate application processes may duplicate provider work before a result commits.

### Phase 0 execution blockers

- The final verification used a temporary PostgreSQL 18.6 cluster because Docker and a persistent local PostgreSQL service were unavailable. The repository's own database paths and isolation guards were used; no permanent infrastructure was added.
- The organizer server remains an external prerequisite for a public score call. No Phase 5 score call was made.
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

### KD-021 — AI is an auditable fallback, never the primary path

Only unresolved/ambiguous extraction evidence or L2 comparison uncertainty may invoke it. Accepted proposals are non-destructive overlays persisted separately.

### KD-022 — Missing or contradictory evidence stays unresolved

No provider call is made when evidence is absent. Conflicts, unsafe units, unanchored evidence, and insufficient confidence cannot become definite results.

### KD-023 — Resolver cost and concurrency are bounded

Hard extraction fields batch per document. Calls have finite timeout/retry, per-case and concurrency limits, and versioned cache identities.

### KD-024 — Single-flight scope is explicit

The configured runtime shares resolver/OCR coordination across the process-local multi-session worker pool. Database uniqueness provides cross-process persistence idempotency, not cross-process provider-call suppression.

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

### KD-020 — Zero evidence is explicit and neutral

An all-zero category score vector is not evidence for the first enum member. It resolves to low-confidence `general_message` with `ZERO_SIGNAL_GENERAL`. This policy applies only when every specialized score is zero; evidence-bearing ambiguity continues through normal Stage 2 resolution.


## API / Data Contract Changes

`ClassificationOutput` now exposes a machine-readable `reason_code` and a derived `low_confidence` property. Stage 1 emits `STAGE1_CONFIDENT`; Stage 2 reason codes are propagated; true zero-signal output emits `ZERO_SIGNAL_GENERAL`. R3A added no database migration or external dependency.

R3B aligns the external and persisted contract:

- `ClassificationOut.category` is restricted to the five internal categories.
- `ClassificationOut.comparison_readiness` is restricted to READY/AWAITING/UNRESOLVED or null.
- `ClassificationOut.confidence` is constrained to `[0, 1]` and exposes `reason_code`.
- `EmailOut` and `EmailListItem` expose the exact processing-status vocabulary.
- `classification_results.reason_code` is non-null after migration `20260920_0005`; category, confidence, and readiness checks are enforced in PostgreSQL.

Phase 2 persistence is additive in migration `20260920_0006`:

- `attachments.content_sha256`, `retrieval_status`, and `retrieval_reason_code` preserve lazy materialization identity and outcome.
- `documents.routing_outcome`, `role_confidence`, `role_evidence`, `validation_outcome`, and `parse_duration_ms` preserve pre-extraction decisions and diagnostics.
- Database checks constrain retrieval status, routing outcomes, and validation outcomes. No category, readiness, or processing-status vocabulary changed.
- No new external dependency or environment variable was added.

Phase 3 persistence is additive in migration `20260920_0007`:

- `document_extractions.extractor_version` identifies the producing extraction schema without implementing cache lookup.
- `extracted_fields` adds `raw_label`, native `raw_value_json`, typed `canonical_value`, `source_location`, and `mapping_method`.
- PostgreSQL constrains the exact seven canonical names, four field statuses, confidence range, six mapping methods, and uniqueness of one canonical field per extraction.
- No comparison-result schema or Phase 4 state was added.

Phase 4 persistence is additive in migration `20260920_0008`:

- `comparison_results` owns the versioned email/SI-extraction/BL-extraction result identity and aggregate state.
- `field_comparisons` owns seven per-field side-by-side values, additive normalized values, layer, final status, and structured evidence linked to both extraction-field rows.
- Internal comparison states remain project-owned (`COMPLETED`/`BLOCKED`, field `MATCH`/`MISMATCH`/`UNRESOLVED`). Public `OK`/`MISMATCH`/`NEEDS_REVIEW` strings remain isolated in `submission_adapter.py`.
- No external dependency or environment variable was added.

Phase 5 persistence/runtime changes are additive:

- Migration `20260920_0009` adds nullable source-content identities for jobs/classifications, bounded job attempt counts, attachment source-reference uniqueness, and document attachment/content uniqueness. Nullable legacy columns preserve older rows while new processing writes content identities.
- Migration `20260920_0010` adds `extraction_cache`, uniquely keyed by content SHA-256 plus extractor version and pointing to one complete source extraction. Cache reuse copies fields into the current document-owned extraction and keeps raw/provenance values intact.
- New configuration in `.env.example`: `SYNC_MAX_WORKERS=4`, `ORGANIZER_HTTP_TIMEOUT_SECONDS=10`, `RETRY_MAX_ATTEMPTS=3`, `RETRY_BACKOFF_SECONDS=0.25`, and `SEMANTIC_RESOLVER_TIMEOUT_SECONDS=5`. No secrets or new production dependency were added; Alembic was already declared and was installed in the verification environment only.
- `SyncReport` adds operational metrics; these fields are additive and existing API response shapes remain backward-compatible.

No new public route was added in Phase 5. Existing `/api/sync` and `/api/email/incoming` now pass bounded worker/retry settings into the shared service; persistence changes are additive Alembic migrations `0009` and `0010`.

Phase 6 adds no public route and does not change the submission schema. Migration `20260920_0011` adds internal `ai_resolutions`. `field_comparisons` retains the original extraction foreign keys while canonical/evidence values may describe an accepted overlay. AI-enabled comparison identity includes resolver/provider/model/schema versions; disabled identity remains `phase4-deterministic-v1`. Existing API and batch constructors now activate the configured factory when enabled.

Phase 7 reuses `email_messages`, `attachments`, `classification_results`, `documents`, `document_extractions`, `extracted_fields`, `comparison_results`, `field_comparisons`, `processing_events`, `human_review_cases`, and `ai_resolutions` through explicit product schemas. Phase R adds migration `20260920_0012_ingestion_checkpoints` for source polling state. GET routes never invoke the processing pipeline. A forced `SyncService.sync_one(..., force=True)` path is used only by the technical-failure reprocess control.

`POST /api/v1/sync/initial` remains a blocking request and now includes a final `progress` object. `POST /api/v1/ingestion/email` accepts optional request-only `content_base64` attachment bytes; the decoded bytes are passed through `IncomingApiSource` and are not copied into email metadata.

Implemented product interfaces:

```text
POST /api/v1/sync/initial
POST /api/v1/ingestion/email
GET  /api/v1/emails
GET  /api/v1/emails/{email_id}
GET  /api/v1/emails/{email_id}/detail
GET  /api/v1/summary
GET  /api/v1/human-review
GET  /api/v1/human-review/{review_id}
GET  /api/v1/events
POST /api/v1/emails/{email_id}/reprocess
```

`/api/v1/emails` supports status, category, comparison readiness, needs-review,
review status, comparison state, mismatch, subject/sender/external-id search,
received time, and bounded skip/limit filters. Detail preserves raw/canonical/
normalized values, SI-vs-BL direction, comparison states, evidence, review
context, and safe AI provenance. The legacy `/api/*` contract remains intact.

---

## Configuration / Environment

The three PostgreSQL roles are intentionally separate:

```text
DATABASE_URL                 -> holyship_dev
HOLYSHIP_TEST_DATABASE_URL   -> holyship_test
HOLYSHIP_EVAL_DATABASE_URL   -> holyship_eval
```

`HOLYSHIP_EVAL_DATABASE_URL` is required for `make eval` and scoring preflight. It must identify a dedicated non-maintenance database distinct from dev and test. The database itself must exist and be owned by or writable by the configured application user; the harness owns only its eval schema lifecycle. `.env.example` documents the safe local names, while the local `.env` remains ignored and uncommitted.

Phase 5 worker/retry defaults are safe bounded values documented in `.env.example`. Production `/api/sync` passes `SessionLocal`, the configured worker limit, retry attempts, HTTP timeout policy, and semantic resolver timeout into the shared service. Phase R adds `INITIAL_SYNC_ON_STARTUP`, `CONTINUOUS_POLLING_ENABLED`, `POLLING_INTERVAL_SECONDS` (default 60), `POLLING_BACKOFF_INITIAL_SECONDS`, `POLLING_BACKOFF_MAX_SECONDS`, `POLLING_SOURCE_TYPE`, and optional `POLLING_ORGANIZER_HTTP_URL`. The generic runtime supports static-bundle and Organizer HTTP sources; Microsoft Graph remains an isolated adapter skeleton.

Phase 6 adds `EXTRACTION_MAX_WORKERS`, `AI_ESCALATION_ENABLED`, `AI_PROVIDER`, `AI_MODEL`, `AI_ENDPOINT`, optional secret `AI_API_KEY`, `AI_CONFIDENCE_THRESHOLD`, `AI_TIMEOUT_SECONDS`, `AI_MAX_CALLS_PER_CASE`, `AI_MAX_CONCURRENT_CALLS`, `AI_RESOLVER_VERSION`, `AI_PROMPT_SCHEMA_VERSION`, `OCR_TIMEOUT_SECONDS`, `OCR_MAX_CALLS`, and `OCR_MAX_CONCURRENT_CALLS`. No key/token or secret is committed. The built-in configured provider is the vendor-neutral `http_json` boundary; deterministic fake providers are injected at the same runtime factory boundary in tests.

Phase F adds `MAX_ATTACHMENT_BYTES` (default 25 MiB, bounded to 1–100 MiB) for incoming base64 attachment protection. `CLASSIFICATION_THRESHOLD` and `CLASSIFICATION_MARGIN_THRESHOLD` are now listed in `.env.example` alongside their existing safe defaults.

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

### Phase F final adversarial audit (2026-09-20)

- Recovered `phaseF` from clean integration SHA `f4081af`; verified no deliberate mutation remained after five RED→revert→GREEN checks (CLS-01, CMP-01, CMP-02, MAP-06, ING-08).
- Strengthened trace gate validates frozen seed IDs, exact cited `req` markers, executable JUnit evidence, and rejects skipped/xfail evidence. Matrix is 106 PASS / 0 TODO / 0 FAIL / 0 WAIVED.
- Reproduced and repaired incoming API arbitrary-base64 allocation risk with configurable `MAX_ATTACHMENT_BYTES`; focused invalid/normal/oversized attachment tests pass.
- `python -m pytest backend/tests -q` → 292 passed, 0 failed, 0 skipped, 1 existing Starlette/httpx warning.
- `mingw32-make check-fast` → 34 passed plus compileall/diff check. `mingw32-make reliability` → 14 passed. `mingw32-make perf` → 520 emails, 37.043s, 14.038 emails/s.
- Clean temporary PostgreSQL database upgraded from empty to Alembic head `20260920_0012`; actual Git Bash `scripts/demo.sh` passed normal/XLSX/wrong/scanned/awaiting/spam/events/summary scenarios.
- AI-disabled `reports/latest/submission.json` SHA-256 matched `37b33169797c6aef6b781fbcbf1ba99cb92d3a8d96ac184235eeda167d2a4eab`.
- Remaining final work: final documentation-parity commit/push, exact-candidate fresh-clone gates, and parity report.

### Phase R / Phase 7 executed evidence

- Service-backed verification on 2026-09-20: Docker Desktop PostgreSQL 16.15 was healthy; `holyship_dev`, `holyship_test`, and `holyship_eval` were distinct; clean Alembic upgrade reached `20260920_0012`; live schema contained `ingestion_checkpoints`.
- Focused Phase 7 PostgreSQL/API/polling suite with explicit isolated URLs → 23 passed, 0 skipped, 1 existing Starlette/httpx deprecation warning. Full repository collection after a clean test-schema reset → 284 passed, 0 failed, 0 skipped, 1 warning.
- Live ING-08 A/B, A/B, restart, and A/B/C sequence → only new messages processed; checkpoint survived restart; attachment reads were 2, 0, 0, 1; backoff was bounded and reset after success.
- Actual `scripts/demo.sh` through Git Bash → PASS for normal SI/BL, XLSX, wrong document, scanned/image, legitimate `AWAITING_DOCUMENTS`, spam, events, and summary. Live API queue/detail/events/summary/filter/reprocess checks passed; persisted GET query counts were queue 3, detail 12, summary 2.
- AI-disabled clean evaluation → 520 emails, 0 failed, 0 unhandled; submission SHA-256 `37b33169797c6aef6b781fbcbf1ba99cb92d3a8d96ac184235eeda167d2a4eab`. `mingw32-make reliability` → 14 passed; final Phase 7 check evaluation → 16.351s / 31.803 emails/s, p50 `0.034048s`, p95 `0.141978s`; `mingw32-make check-fast` → PASS.
- `mingw32-make trace PHASE=7` → PASS: 103 PASS, 0 TODO, 0 FAIL, with no evidence-reference errors. The prior trace correctly reported only `ING-08` TODO before the live evidence and matrix update. Scoreboard was not called because no authoritative organizer endpoint was available.

- `python -m pytest backend/tests/test_phase7_polling.py backend/tests/test_phase7_product_api.py backend/tests/test_phase7_polling_postgres.py -q` → historical pre-service run: 20 passed, 1 PostgreSQL test skipped, 1 existing Starlette/TestClient deprecation warning.
- `python -m compileall -q backend/app backend/tests scripts` → PASS.
- `python -m alembic heads` → PASS: `20260920_0012`.
- `python -m pytest backend/tests -q` → historical pre-service run: 221 passed, 60 skipped (database-dependent), 1 existing Starlette/TestClient deprecation warning.
- PostgreSQL dialect compilation of queue/count statements → PASS; live SQL execution remains unverified.
- `mingw32-make check-fast` → PASS: inherited 34-test gate, compileall, and diff check.
- `mingw32-make check PHASE=7` → PASS: 284 tests passed/0 failed/0 skipped with 1 existing Starlette/httpx warning; clean AI-disabled evaluation 520/520 with 0 failed/0 unhandled; reliability 14 passed; perf/eval passed; trace 103 PASS/0 TODO/0 FAIL.
- Production-code safety scan → PASS by focused source scan: no private-reference access or per-email production lookup was added.
- `git diff --check` → PASS with expected Windows LF/CRLF conversion warnings.
- Live `scripts/demo.sh`, full PostgreSQL check, and public evaluation → verified in the service-backed re-verification entries above; scoreboard intentionally not run.

### Phase 6 executed evidence

- Focused resolver/OCR/runtime/PostgreSQL suite: 35 passed.
- Full PostgreSQL suite: 257 passed, 0 failed, 0 skipped, 1 existing deprecation warning. Reliability: 14 passed. Trace: 89 PASS / 0 TODO / 0 FAIL.
- `mingw32-make check-fast`: 34 passed plus compileall/diff check. `mingw32-make check PHASE=6B`: PASS.
- Alembic `0011 -> 0010 -> 0011` downgrade/upgrade passed.
- AI-disabled evaluation: 520 emails, 0 failed, 0 unhandled, SHA-256 `37b33169797c6aef6b781fbcbf1ba99cb92d3a8d96ac184235eeda167d2a4eab`. Measured 15.081s / 34.480 emails/s, p50 0.028657s, p95 0.115928s; 12.39% slower than this machine's 13.419s pre-change baseline, below 20%.
- Fixture evaluation: 5 attempted, 4 calls, 2 accepted, 3 unresolved, 1 cache hit, 0 provider failures/malformed responses. This is behavior evidence, not live-model accuracy.

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

2026-09-20 — Phase 5 reliability and performance hardening
- Branch policy → PASS: `phase5` created from `feature/email-classification` (`67f00f2`), published with upstream, and left separate from the base branch.
- Pre-Phase-5 baseline → `mingw32-make check-fast` PASS: 19 tests, 0 failures, 1 existing Starlette warning, wall time 6.322s. Existing clean-evaluation artifact fingerprint: `37b33169797c6aef6b781fbcbf1ba99cb92d3a8d96ac184235eeda167d2a4eab`; observed legacy full-run metrics were 520 emails, 15.284s, 34.023 emails/s, 0 unhandled exceptions. Per-email p50/p95 and peak RSS were not measured by the legacy artifact.
- TDD/fast reliability evidence → focused Phase 5 suite 11 passed; refreshed expanded fast gate 34 passed; refreshed complete available test collection 175 passed, 47 skipped, 1 warning. The skipped tests are PostgreSQL-gated and were not silently counted as verified. The final repository-boundary regression assertion is included in both refreshed counts.
- PostgreSQL reliability tests were added for repeated sync idempotency, concurrent duplicate ingestion, restart/resume, and single-worker/parallel semantic snapshots. This was the pre-verification checkpoint; the live results are recorded in the closure entry immediately below.
- The first `mingw32-make check` attempt was blocked by the missing database environment. That historical precondition was resolved for final verification with isolated temporary databases; the final full gate passed.
- Private coupling scan → no runtime reads of `ground_truth.json`, `data_v2`, answer lookup, email-specific production rules, or hard-coded 520 processing logic found in Phase 5 changes.

2026-09-20 — Phase 5 final verification and closure
- Isolated PostgreSQL 18.6 cluster → PASS: separate `holyship_dev`, `holyship_test`, and `holyship_eval` databases on port 55432; clean Alembic upgrade reached `20260920_0010`; downgrade to `20260920_0008` and upgrade back to head also passed.
- First live Phase 5 PostgreSQL run exposed a real insert-order defect: the new email row was flushed before its required `content_hash`. `EmailRepository.upsert_message()` now initializes the hash in the insert object. Focused regression rerun → 4 passed; `mingw32-make reliability` → 14 passed.
- Full PostgreSQL-enabled test collection → 222 passed, 0 skipped, 1 existing Starlette/HTTP-client deprecation warning. Cache suite → 6 passed; retry/timeout and non-PostgreSQL reliability suite → 11 passed.
- Clean evaluation repeat → 520 emails, 0 failed, 0 unhandled exceptions. Final normal-worker run: 13.351 seconds, 38.949 emails/s, p50 0.024455s, p95 0.106313s, reader 216, extractor 196, OCR 6, Vision 0, LLM 0, retries 0.
- Determinism/worker equivalence → clean run 1 and run 2, plus workers=1 versus workers=4, all produced byte-identical submission SHA-256 `37b33169797c6aef6b781fbcbf1ba99cb92d3a8d96ac184235eeda167d2a4eab`.
- `mingw32-make check-fast` and `mingw32-make check` → PASS. `git diff --check` → PASS. Scoreboard not called because no Phase 5 call was needed for closure; scale test not run.
- Runtime audit → no private evaluator/reference-data reads, per-email answer rules, hard-coded runtime 520 assumption, secrets, infinite retry, or unbounded concurrency path found.

2026-09-20 — Self-evaluation harness isolation repair
- Isolation guard unit suite → 6 passed. `make check-fast` → PASS: compileall, 19 tests, and diff check.
- Clean eval run 1 → 520/520 processed in 15.530 seconds; submission SHA-256 `37b33169797c6aef6b781fbcbf1ba99cb92d3a8d96ac184235eeda167d2a4eab`.
- Clean eval run 2 after another eval-only schema reset/migration → 520/520 processed in 14.755 seconds; identical SHA-256 and byte-for-byte comparison PASS.
- Required standalone `make eval` → PASS: 520 emails in 17.250 seconds / 30.145 emails/s.
- Final `make check PHASE=4` → PASS: 205 tests, 0 failed, 0 skipped, 1 warning; clean eval 520 emails in 15.284 seconds / 34.023 emails/s; reliability 10 passed; trace 76 PASS / 0 TODO / 0 FAIL.
- Final submission after the check retained the same SHA-256 as both determinism runs and the exact observed category/status distribution.
- Dev remained at `20260920_0008`; pre/post data fingerprint and every table row count matched. Dev modified/reset by evaluation: NO.
- Dev, test, and eval URL identities were confirmed pairwise distinct. Test was unchanged across all standalone eval runs; the full test target then used its pre-existing fixtures to clean test tables as designed. Eval never connected to or reset test.
- `make score PHASE=4` and `POST /submit` → NOT RUN by instruction.

2026-09-20 — Phase P4C comparison persistence and Phase 4 closure
- Test-first focused collection failed because comparison persistence and new submission workflow types did not yet exist. The first PostgreSQL run exposed a same-session idempotency defect; linking child rows through the ORM relationship fixed it without changing comparison semantics.
- Focused P4C suite (`test_phase4_comparison_postgres.py`, Phase 2 pipeline integration, submission adapter, metamorphic suite) → 47 passed, 0 skipped.
- PostgreSQL-enabled full regression → 199 passed, 0 failed, 0 skipped, 1 existing Starlette/AnyIO deprecation warning.
- `make reliability` → 10 passed.
- Standalone `make eval` → 520 emails, 1.727 seconds, 301.125 emails/s.
- Standalone `make perf` → 520 emails, 1.676 seconds, 310.207 emails/s.
- `make check-fast` → PASS: compileall, 19 tests passed with 1 warning, and `git diff --check` passed with line-ending warnings only.
- `make trace PHASE=4` → PASS: 76 PASS, 0 TODO, 0 FAIL.
- `make check PHASE=4` → PASS: 199 tests; eval 520 emails in 1.700 seconds (305.857 emails/s); reliability 10 passed; trace 76/0/0.
- Development Alembic upgrade `20260920_0007 -> 20260920_0008` → PASS. Read-only introspection confirmed `comparison_results`, `field_comparisons`, `email_messages`, and `processing_events`; comparison identity uniqueness, four aggregate indexes, and all three field check constraints survived the test suite.
- Public comparison sanity audit → 98 pairs attempted, 0 clean, 0 fully definite mismatch, 98 blocked unresolved, 0 failed; field mismatch counts are shipper=0, consignee=0, notify_party=0, port_of_loading=0, port_of_discharge=0, container_count=3, gross_weight_kg=4; unresolved counts are 76, 66, 51, 47, 47, 75, and 50 respectively. L0=267, L1=7, L2=29; no accuracy claim.
- Metamorphic formatting-only false alarms → 0. Single-material-defect case → PASS with exactly one mismatch and exact `mismatched_fields`.
- `make score PHASE=4` → NOT RUN by explicit instruction.

2026-09-20 — Phase P3B parallel extraction, versioned cache, and Phase 3 closure
- Focused EXT-03/EXT-06 PostgreSQL evidence (`backend/tests/test_phase3_parallel_cache_postgres.py`) → 6 passed. The barrier test proved two distinct worker threads reached extraction concurrently; SQL event evidence showed all database work remained on the caller thread.
- Combined Phase 2/Phase 3 focused regression → 36 passed.
- Public extraction coverage audit → SI=106, BL=98, attempts=204, computations=204, cache hits=0, cache misses=204, failures=0, bounded parallel pairs=98, wall time=2.305 seconds, provider calls=0.
- PostgreSQL-enabled `python -m pytest` → 144 passed, 0 failed, 0 skipped, 1 existing Starlette/AnyIO deprecation warning.
- `make reliability` → 10 passed.
- Standalone `make eval` → 520 emails, 1.678 seconds, 309.926 emails/s.
- Standalone `make perf` → 520 emails, 1.611 seconds, 322.797 emails/s.
- `make check-fast` → PASS: compileall, 11 tests passed, and `git diff --check` passed with line-ending warnings only.
- `make trace PHASE=3` → PASS: 58 PASS, 0 TODO, 0 FAIL, no evidence-reference errors.
- Final `make check PHASE=3` after cache fresh-session reload evidence → PASS: 144 tests; eval 520 emails in 1.666 seconds (312.108 emails/s); reliability 10 passed; trace 58/0/0.
- Read-only development verification after all tests: Alembic head `20260920_0007`; `email_messages`, `attachments`, `documents`, `document_extractions`, `extracted_fields`, and `processing_events` all survived.
- `make score PHASE=3` → NOT RUN by explicit instruction.

2026-09-20 — Phase P3A-2 one-pass deterministic extraction and persistence
- Test-first focused collection failed as expected because `backend.app.extraction.extractor` did not yet exist.
- First implementation run → 6 passed, 1 failed; the defect was empty `Shipper:` multiline handling. After repair, the only remaining failure was a fixture line-number expectation (`10`, not `9`).
- Final focused Phase 3 suite (`test_phase3_label_mapping.py`, `test_phase3_extractor.py`, `test_phase3_extraction_postgres.py`) → 18 passed.
- Phase 2/document/storage regression subset → 22 passed.
- Development migration `20260920_0006 -> 20260920_0007` → PASS; `alembic current` reports `20260920_0007 (head)`.
- PostgreSQL-enabled full regression → 138 passed, 0 failed, 0 skipped, 1 existing Starlette/AnyIO deprecation warning.
- `make reliability` → 10 passed.
- `make check-fast` → PASS: compileall, 11 focused tests, and `git diff --check` passed; only line-ending warnings were emitted.
- Read-only development-schema introspection confirmed head `20260920_0007`, surviving email/document/extraction/event tables, the five new extracted-field columns, all four Phase 3 check constraints, and `uq_extracted_field_extraction_name`.
- `make trace PHASE=3` → expected FAIL: 56 PASS, 2 TODO (`EXT-03`, `EXT-06`), 0 FAIL, and no evidence-reference errors.

2026-09-20 — Phase P3A-1 canonical field contract and strict label mapping
- Focused mapper/model suite: `python -m pytest backend/tests/test_phase3_label_mapping.py -vv` → 11 passed.
- First full run without a test-database environment → 102 passed, 29 skipped, 1 warning; not accepted as the regression gate.
- PostgreSQL-enabled full regression against `holyship_test`: `python -m pytest` → 131 passed, 0 failed, 0 skipped, 1 Starlette/AnyIO deprecation warning.
- Safety scan of `backend/app/extraction` found no participant email IDs, answer filenames, `ground_truth`, `data_v2`, fuzzy libraries, embeddings, LLM calls, or Vision calls.
- `make check-fast` through the installed MSYS make executable → PASS: compileall passed, 11 focused API/submission tests passed with 1 existing deprecation warning, and `git diff --check` passed with line-ending warnings only.

2026-09-20 — Phase 2 document materialization and role validation
- Required pre-change `make check-fast` first exposed a broken local `.venv` launcher whose base Python no longer existed. A workspace-local native Windows Python 3.13 environment was created and populated only from `backend/requirements.txt`; the repository dependency declaration itself was unchanged.
- Test-first red evidence: `python -m pytest backend/tests/test_phase2_document_contract.py -vv` failed collection because the Phase 2 materialization module did not yet exist.
- First PostgreSQL Phase 2 run → 6 passed, 4 failed: one test-result construction defect plus the real `CLS-09` gap where immediate comparison requests with missing attachments became `READINESS_UNRESOLVED` instead of entering retrieval and persisting `MISSING_REQUIRED_ATTACHMENT`.
- Focused reader/role unit suite after repair → 5 passed. Focused PostgreSQL Phase 2 suite after adding source-read and reader-exception isolation → 12 passed.
- Combined document/readiness/Phase 2 focused suite before the final failure-isolation additions → 36 passed; the added focused tests also passed in the 12-test PostgreSQL suite and full regression.
- Public attachment audit → PASS: 520 emails, 250/250 attachments, 100% defined outcomes, 0 unhandled exceptions. Formats: TXT 192, text PDF 22, scanned PDF 6, DOCX 8, XLSX 22. Outcomes: SI 123, BL 114, wrong type 5, corrupt 2, unreadable 6.
- Public Phase 2 gate audit → 317 non-comparison/not-entered, 91 awaiting, 98 materialized to EXTRACTING, 5 missing blocked, 4 wrong-type blocked, 3 scanned-email cases blocked unreadable, and 2 corrupt blocked. No seven-field extraction or comparison was run.
- Development migration `20260920_0005 -> 20260920_0006` → PASS. Read-only introspection confirmed the new attachment/document columns, three check constraints, SHA-256 index, and surviving `email_messages`, `attachments`, `documents`, and `processing_events` tables at head.
- Final `make check-fast` → PASS: compileall, 11 tests passed, `git diff --check` passed (line-ending warnings only).
- Final full PostgreSQL-enabled test suite → 120 passed, 0 failed, 0 skipped, 1 Starlette/AnyIO deprecation warning.
- `make reliability` → 10 passed.
- Standalone `make eval` → 520 emails, 1.686 seconds, 308.489 emails/s.
- Standalone `make perf` → 520 emails, 1.777 seconds, 292.670 emails/s.
- `make trace PHASE=2` → PASS: 46 PASS, 0 TODO, 0 FAIL for all requirements owned by phases 0–2.
- Final `make check PHASE=2` → PASS: 120 tests; eval 520 emails in 1.675 seconds (310.422 emails/s); reliability 10 passed; trace 46/0/0.
- `make score PHASE=2` → NOT RUN by explicit instruction.

2026-09-20 — Phase R3A-2
- Pre-fix synthetic regression: `python -m pytest backend/tests/test_phase1_zero_signal.py -vv` → expected RED, 4 failed; reproduced enum-order zero-signal fallback, missing reason code, and bare-draft-BL standalone evidence.
- Focused zero-signal suite after repair → 4 passed.
- Focused CLS suite (`test_phase1_classification_readiness.py`, `test_classification_pipeline.py`, `test_phase1_classifier_contract.py`, `test_phase1_zero_signal.py`) → 37 passed.
- R3A-1 audit baseline: distribution `234/136/83/41/26` (document comparison / new SI / invoice / general / spam), low confidence 200, no-attachment comparison `108` with `A=91, B=3, C=0, D=14`, conflicts 49.
- R3A-2 audit: distribution `203/141/84/66/26`, low confidence 102, no-attachment comparison `94` with `A=91, B=3, C=0, D=0`, conflicts 45; all 25 zero-signal cases resolve to low-confidence `general_message` and none to `document_comparison`.
- Initial full suite without the test database environment → 82 passed, 16 skipped, 1 warning; not accepted as the gate.
- PostgreSQL-enabled `python -m pytest` → 98 passed, 0 failed, 0 skipped, 1 deprecation warning.
- `make reliability` target via `C:\msys64\usr\bin\make.exe` and project virtualenv → 10 passed.
- `make check-fast` target via `C:\msys64\usr\bin\make.exe` and project virtualenv → PASS: compileall, 11 tests passed, `git diff --check` passed (line-ending warnings only).
- `make trace PHASE=1` target → expected FAIL with only `SCP-01`, `SCP-05`, and `SCP-07` TODO; Phase 1 matrix totals are 19 PASS, 3 TODO, 0 FAIL.

2026-09-20 — Phase R3B final closure
- Focused SCP/API/compatibility suite → 23 passed, 0 failed, 0 skipped, 1 warning.
- Development Alembic upgrade `20260920_0004 -> 20260920_0005` → PASS; live introspection confirmed all classification/status constraints and non-null reason codes.
- Live development compatibility aggregates: five valid categories; statuses `CLASSIFIED=214`, `COMPLETED=306`; reason codes `CLASSIFICATION_RESOLVED=21`, `STAGE1_CONFIDENT=274`, `STAGE2_RESOLVED=225`; 21 historical Human Review rows retained and not extended.
- PostgreSQL-enabled `python -m pytest` → 101 passed, 0 failed, 0 skipped, 1 warning.
- `make reliability` → 10 passed.
- Standalone `make eval` → 520 emails, 1.411 seconds, 368.574 emails/s; all rows skipped as unchanged in the historical dev baseline.
- Standalone `make perf` → 520 emails, 1.477 seconds, 351.984 emails/s.
- `make check-fast` → PASS: compileall, 11 tests passed, `git diff --check` passed with line-ending warnings only.
- `make trace PHASE=1` → PASS; Phase 1 matrix 22 PASS, 0 TODO, 0 FAIL.
- `make check PHASE=1` → PASS: 101 tests, eval 520 emails in 1.569 seconds (331.462 emails/s), reliability 10 passed, trace passed.
- `make score PHASE=1` → NOT RUN by instruction; public score remains NOT VERIFIED.

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

- No live AI credentials were available and no live model call ran. Provider quality/latency/cancellation/accuracy are NOT VERIFIED.
- Resolver/OCR single-flight, call budgets, and concurrency limits are process-local. Independent processes share durable cache identity only after commit and can duplicate external work during a race.
- Live Tesseract was not verified on the six public scanned documents. Injected success, unavailable, garbage, timeout, cache, budget, and concurrency paths are tested.
- Missing values, corrupt/wrong documents, and missing attachments intentionally remain blocked/Human Review outcomes.

- Live PostgreSQL migrations, database concurrency, idempotency, cache versioning, failure isolation, clean evaluation, and database-backed worker equivalence are verified on isolated temporary databases. Restart/resume is verified at the persisted-state/service level; a true OS process kill/restart was not exercised.
- Organizer HTTP has no true `since` cursor, so the worker may list the source again; persisted email identity/content state prevents completed reprocessing and attachment refetch. Live Microsoft Graph polling is not required by Phase 7 and remains NOT VERIFIED.
- Peak RSS remains NOT MEASURED because no cross-platform process-metrics dependency is declared. The new report records this honestly rather than emitting zero.
- The semantic timeout helper bounds caller wait but cannot forcibly cancel an arbitrary provider thread; production clients should also enforce their own timeout.
- Public clean evaluation is verified twice and remains byte-identical to the Phase 4 baseline. The public scoreboard was not called because the organizer endpoint is external and unavailable in this environment.

- P4B L1 remains deliberately conservative: unapproved port spellings and entity aliases without an exact safe rule pass to the default-unresolved L2 boundary rather than being guessed.
- The default L2 resolver still performs zero calls; Phase 6 uses the validated resolver only when explicitly injected/enabled.
- The public `AWAITING_DOCUMENTS` mapping remains a configurable provisional `NEEDS_REVIEW/missing_value` policy and is explicitly UNVALIDATED because the public contract does not define this internal waiting state.
- The public comparison sanity audit found all 98 attempted public pairs contained at least one unresolved field under the conservative deterministic/default-L2 policy. This is coverage evidence, not a private-label accuracy measurement and was not used to tune rules.

- The public classification audit provides semantic/input evidence, not hidden-label correctness. No private ground truth or evaluator data was used.
- Live OCR/Tesseract is unverified; the injected OCR contract closes `DOC-07b`, while unavailable native OCR remains a clean blocking outcome.
- Zero-signal messages intentionally remain low-confidence neutral results. A future model-backed resolver may improve their semantics, but Phase 1 does not invent unsupported specialized intent.
- The development database retains 21 historical Human Review rows and the legacy read-only Human Review API for compatibility. Current Phase 1 processing creates none.
- `holyship_dev` intentionally retains historical Phase 0 rows, but the evaluation harness no longer reads them; `reports/latest/eval.md` is generated from a clean dedicated evaluation database.
- Peak RSS remains unavailable because no cross-platform process-metrics dependency is declared. Per-email p50/p95 are now measured by the Phase 5 harness.
- Public Phase 5 scoreboard results are not verified; no Phase 5 score call was made.

Current document-level limitations:

- Phase 7 exposes read-only Human Review queue/detail context; reviewer UI/actions and authentication remain out of scope.
- Microsoft Graph is a provider-isolated payload adapter only; OAuth and live Graph polling are not implemented. Generic static/Organizer HTTP polling and startup lifecycle wiring are implemented.
- `/api/v1/sync/initial` is a synchronous initial-sync boundary that returns a product job ID for the completed request; background job progress persistence is not implemented.
- PostgreSQL joins/checkpoint migration, live demo, full evaluation, latency measurements, and bounded product-query counts are verified in the 2026-09-20 service-backed report above. Peak RSS remains unavailable by declared dependency design.
- `scripts/demo.sh` calls the HTTP-only `scripts/demo_phase7.py`, which uses public bundle bytes and incoming API messages; it does not fabricate database rows or read private answers.
- Exact participant-facing challenge submission schema must be verified against the public `sample_submission.json` used by the team.

---

## Recent Change Log

### 2026-09-20 — Phase F final adversarial audit

- **Changed:** Strengthened requirement trace/evidence validation; added SEC-04 input-bound/log audit, SCP-02 scope, SCP-06 category coverage, and mutation evidence; repaired configurable incoming base64 attachment size enforcement; corrected `.env.example` and Phase F matrix evidence.
- **Why:** Final adversarial audit independently reproduced an unbounded base64 allocation risk and found trace evidence-integrity gaps. Both were repaired at the smallest general boundary with regression coverage.
- **Files:** `backend/app/api/router.py`, `backend/app/core/config.py`, `.env.example`, Phase F audit/trace tests, `scripts/trace_phase0.py`, `docs/requirements_matrix.md`, `reports/final_audit.md`, and this handoff.
- **Validation:** Full PostgreSQL suite 292 passed/0 failed/0 skipped; check-fast 34 passed; reliability 14 passed; perf 520 emails in 37.043s; demo PASS; AI-disabled SHA matched required reference; clean migration reached `20260920_0012`.
- **Next:** Push exact candidate to `origin/phaseF`, verify clean clone, then stop for human review; do not merge.

### 2026-09-20 — Phase 7 service-backed final verification

- **Changed:** Fixed persisted event polling projection unpacking, made the demo script import-safe through its shell execution context, and added a general `win a prize` spam signal; added regression tests and updated Phase 7 evidence/matrix status.
- **Why:** Live PostgreSQL/API verification reproduced two API/demo defects and one required spam classification gap. Each was fixed at the smallest general boundary and rechecked.
- **Files:** `backend/app/api/product_queries.py`, `backend/app/classification/signals.py`, the Phase 1/7 regression tests, `scripts/demo_phase7.py`, `docs/requirements_matrix.md`, `reports/phase7_api_verification.md`, `reports/phase7_demo.md`, and this handoff.
- **Validation:** PostgreSQL 16.15 service healthy; focused Phase 7 suite 23 passed; full repository collection 284 passed/0 failed/0 skipped; live demo PASS; AI-disabled submission SHA matched the required reference; reliability, perf, check-fast, live API/query checks, trace PHASE=7 (103 PASS/0 TODO/0 FAIL), and `mingw32-make check PHASE=7` passed.
- **Next:** Human review of this report, then decide whether to merge `phase7`; do not start Phase F automatically.

### 2026-09-20 — Phase R continuous ingestion and Phase 7 closure repair

- **Changed:** Added generic polling worker/runtime lifecycle, durable checkpoint migration `20260920_0012`, configurable startup/poll/backoff settings, incoming base64 attachment transport, initial-sync progress snapshot, `scripts/demo.sh`, expanded public-fixture demo scenarios, and requirement-marked tests. Repaired Phase 7 matrix evidence paths and audited the fetched integration base.
- **Why:** Phase 7 left ING-08 incomplete and the live demo/DB verification contract too narrow; the product boundary needed a generic restart-safe source coordinator without changing Phase 0–6 semantics.
- **Files:** `backend/app/ingestion/polling.py`, `backend/app/ingestion/runtime.py`, `backend/app/main.py`, `backend/app/api/router.py`, `backend/app/api/schemas.py`, `backend/app/core/config.py`, `backend/app/storage/models.py`, migration `20260920_0012`, Phase R tests, demo/docs/matrix, `.env.example`, and this handoff.
- **Validation:** Focused Phase R suite 20 passed/1 PostgreSQL skipped; full repository suite 221 passed/60 skipped; migration head `20260920_0012`; live PostgreSQL, demo, full check, compatibility fingerprint, and performance/N+1 measurements remain NOT VERIFIED because no service/database is available.
- **Next:** Run the service-backed DB/migration/demo/full-gate workflow; the pushed branch remains blocked until those checks execute.

### 2026-09-20 — Phase 7 product-facing API and live-demo boundary

- **Changed:** Added explicit `/api/v1` queue, summary, unified detail, read-only Human Review, polling-event, initial-sync, ingestion, and technical-reprocess contracts; added persisted-only query composition, Graph adapter skeleton, demo script, API docs/audit, and product/PostgreSQL/provider tests.
- **Why:** Phase 0–6 processing and persistence existed, but dashboard/extension/reviewer clients had no stable product contract and would otherwise need to join internal tables or rerun processing.
- **Files:** `backend/app/api/product_schemas.py`, `backend/app/api/product_queries.py`, `backend/app/api/router.py`, `backend/app/api/schemas.py`, `backend/app/ingestion/graph_source.py`, `backend/app/ingestion/models.py`, `backend/app/sync/service.py`, Phase 7 tests, `scripts/demo_phase7.py`, `docs/phase7_api.md`, Phase 7 reports, this handoff, and the Phase 7 design/plan docs.
- **Validation:** New product/provider suite 12 passed; inherited focused suite with Phase 7 46 passed; full repository unit collection 212 passed/59 skipped; `mingw32-make check-fast`, compileall, Alembic head, SQL compilation, and diff check passed. PostgreSQL integration (2 tests), live demo, and full check/evaluation remain unverified; push to `origin/phase7` passed.
- **Next:** Run PostgreSQL/live-demo/full-gate verification in a service-enabled environment; do not merge.

### 2026-09-20 — Phase 6 targeted hard-case AI layer and focused closure

- **Changed:** Added bounded structured resolution, non-destructive overlays, per-document batching, durable cache/audit migration `0011`, bounded injectable OCR, configured API/batch runtime wiring, process-shared worker coordination, Phase 6 trace support, and hard-case evaluation/reports.
- **Why:** Phase 5 left 29 semantic uncertainties, one explicit unresolved extraction, and six OCR-routed documents; only evidence-backed cases should escalate.
- **Files:** resolution/comparison/materialization/OCR/sync/storage/config modules, migration `0011`, Phase 6 tests/scripts/reports, matrix, `.env.example`, and this handoff.
- **Validation:** focused 35; full 257; reliability 14; trace 89/0/0; full check PASS; disabled fingerprint identical; fixture 5 attempted / 2 accepted / 3 unresolved; migration through `0011` PASS.
- **Next:** Review/merge `phase6`; optionally perform live provider/Tesseract verification. Do not begin Phase 7 or Human Review UI here.

### 2026-09-20 — Phase 5 reliability and performance hardening

- **Changed:** Added bounded email-level concurrency, per-worker sessions, finite retry/timeout primitives, transient HTTP retry diagnostics, resolver timeout/malformed-output handling, resumable technical states, database-backed duplicate identities, additive cache identity persistence, and structured sync metrics.
- **Why:** Phase 5 requires reliable restart/resume, duplicate protection under concurrency, bounded resource use, observable failures, and measured performance while preserving Phase 0–4 semantics.
- **Files:** `backend/app/core/reliability.py`, sync/source/comparison/materialization/extraction/storage modules, Alembic `0009`/`0010`, `.env.example`, `Makefile`, `scripts/run_baseline.py`, Phase 5 tests, reports, and this handoff.
- **Dependencies:** No new production dependency. Existing declared Alembic was installed in the verification environment to collect the full suite.
- **Validation:** initial implementation evidence was collected before PostgreSQL was available; final verification is recorded in the closure entry below.
- **Next:** Final verification and closure.

### 2026-09-20 — Phase 5 final verification and closure

- **Changed:** Fixed the PostgreSQL insert-order defect in `EmailRepository.upsert_message()` and replaced Phase 5 reliability/performance “NOT VERIFIED” statements with executed evidence. No new dependency or infrastructure was committed.
- **Why:** Live PostgreSQL correctly enforced the existing non-null `content_hash` contract; the repository had to initialize that field before its duplicate-protection savepoint flush.
- **Files:** `backend/app/storage/repositories.py`, `reports/phase5_reliability.md`, `reports/phase5_performance.md`, `reports/latest/eval.md`, `reports/latest/eval.json`, `reports/history.csv`, and this handoff.
- **Validation:** clean Alembic upgrade/downgrade/upgrade through `20260920_0010`; focused PostgreSQL reliability 4 passed; `mingw32-make reliability` 14 passed; full suite 222 passed/0 skipped; clean evaluations repeated with byte-identical SHA-256; workers=1 and workers=4 submissions byte-identical; `mingw32-make check-fast`, `git diff --check`, and `mingw32-make check` passed. Final run 13.351s / 38.949 emails/s; 0 failed and 0 unhandled exceptions.
- **Next:** Stop. Keep `phase5` separate from its base and do not begin Phase 6/7 or Human Review UI work.

### 2026-09-20 — Dedicated self-evaluation database repair

- **Changed:** Added `HOLYSHIP_EVAL_DATABASE_URL`, fail-closed three-database identity checks, eval-only schema reset plus Alembic rebuild, and public submission contract validation inside the evaluation harness.
- **Why:** Idempotent processing against historical dev rows could export stale classifications, and `make score` depends on the evaluation path. A fresh, dedicated database makes evaluation current, repeatable, and non-destructive to development data.
- **Files:** `.env.example`, local ignored `.env`, `scripts/database_isolation.py`, `scripts/evaluation_database.py`, `scripts/run_baseline.py`, `backend/tests/test_evaluation_harness.py`, generated evaluation reports, and this handoff.
- **Validation:** Six guard tests; two clean 520-email evaluations with identical SHA-256; standalone eval passed; final Phase 4 check passed with 205 tests, reliability 10, and trace 76/0/0. Dev fingerprint/head remained unchanged; eval did not touch test.
- **Next:** Stop. Start the organizer server and explicitly authorize the Phase 4 score call separately; do not begin Phase 5 or tune from score movement.

### 2026-09-20 — Phase P4C comparison persistence, pipeline, and Phase 4 closure

- **Changed:** Added additive comparison-result and per-field persistence, centralized comparison versioning/idempotency, real EXTRACTING/COMPARING/COMPLETED-or-BLOCKED orchestration, structured comparison failure isolation, rich internal mixed-state semantics, and an isolated explicit public submission mapping.
- **Why:** Phase 4 required durable side-by-side mismatch evidence and exact overall semantics without mutating Phase 3 extraction data or forcing project-owned states into the five-key participant schema.
- **Files:** Comparison domain/persistence, storage models/repositories, sync/materialization orchestration, migration `20260920_0008`, submission adapter/baseline mapping, PostgreSQL/pipeline/submission/metamorphic tests, comparison sanity script/report, matrix, and this handoff.
- **Dependencies/config:** None. Reused SQLAlchemy/PostgreSQL and the existing reader/extractor stack; added no environment variables.
- **Validation:** Focused P4C 47 passed; full PostgreSQL suite 199 passed with 0 failures/skips and 1 warning; reliability 10 passed; eval/perf/check-fast passed; Phase 4 trace 76/0/0; final `make check PHASE=4` passed. Dev remains at Alembic `20260920_0008` with expected tables/constraints/indexes.
- **Audit:** Public-only sanity report attempted 98 pairs: 0 clean, 0 fully definite mismatch, 98 blocked unresolved, 0 failed; L0=267, L1=7, L2=29. Comparison-time reader/extractor and provider calls were zero. No private ground truth was used and no score was called.
- **Next:** Stop after Phase 4. Do not begin Phase 5, Phase 7 API work, real providers, or scoreboard evaluation until explicitly requested.

### 2026-09-20 — Phase P4B field-specific L1 and metamorphic accuracy

- **Architecture:** Added `FieldSpecificL1Comparator` with separate dispatch paths for container count, gross kilograms, port values, and entity values. P4A still runs L0 first, L1 only after an L0 difference, and L2 only after L1 returns no decision; real-L1 counters prove 0/0, 1/0, and 1/1 call patterns.
- **Container policy:** Prefer Phase 3 numeric canonical counts. Deterministic compatibility parsing accepts simple counts and compound `count x type` forms; only count participates in comparison, type remains auxiliary evidence, count differences are mismatches, and unparseable input remains unresolved.
- **Gross-weight policy:** Prefer Phase 3 native numeric kilograms. Deterministic L1 accepts numeric values or kilograms with validated comma/decimal formatting, performs no invented unit conversion, and produces definite numeric differences. A real NET-only extraction remains missing for gross weight and comparison stays unresolved.
- **Entity policy:** Only abbreviation periods immediately following a letter and preceding whitespace/end are removed after L0. No legal, company, business, or geographic token is stripped—including `SDN BHD`, `BERHAD`, `LTD`, `LIMITED`, `LLC`, `INC`, `PTE LTD`, `MALAYSIA`, `SINGAPORE`, `LOGISTICS`, or `TRADING`. Unproved aliases proceed to L2/default unresolved.
- **Port policy:** Added exact configurable aliases in `port_aliases.json`, backed only by published UN/LOCODE entries: `PORT KLANG` ↔ `MYPKG` / `MY PKG`, and `SINGAPORE` ↔ `SGSIN` / `SG SIN`. The registry rejects conflicting aliases and uses no fuzzy, edit-distance, substring, or similarity matching. `reports/port_aliases_review.md` records every runtime alias and rationale.
- **Anti-overfitting:** No email IDs, filenames, participant rows, corpus counts, or known-answer overrides are used. Every rule is a field-level business rule or explicit externally sourced configuration entry; provider/model calls remain zero.
- **Metamorphic evidence:** Thirteen deterministic equivalence-preserving transformations produced 13 MATCH results and zero false alarms. Five semantic negative controls—company word, geography, port, container count, and gross weight—had zero failures and were never normalized to MATCH.
- **Files:** Comparison L1 module/config/default wiring; P4B unit and metamorphic tests; port review report; matrix; this handoff. No dependency, schema, migration, persistence, API, or submission change.
- **Validation:** Initial P4B red run: 8 passed / 12 failed before L1 existed. Final focused Phase 4 suite: 39 passed. PostgreSQL-enabled full regression: 183 passed, 0 failed, 0 skipped, 1 warning. `make reliability`: 10 passed. `make check-fast`: compileall and diff check passed; 11 tests passed with 1 warning.
- **Closed rows:** `MAP-07`, `CMP-05`, `CMP-06`, `CMP-07`, `CMP-12`.
- **Next:** Stop after P4B. P4C owns `CMP-09`, `CMP-10`, `CMP-11`, `STA-05`, `SUB-02`, and `SUB-03`.

### 2026-09-20 — Phase P4A core comparison contract and layered dispatch

- **Contract:** Added an in-memory result model whose only final per-field states are `MATCH`, `MISMATCH`, and `UNRESOLVED`. Every batch contains exactly the seven canonical extraction fields and enforces SI as the reference and `DRAFT_BL` as the candidate.
- **Conservative uncertainty:** Missing, ambiguous, unresolved, or otherwise non-materialized canonical values stop at a structured precondition result and never become a fabricated match or mismatch. The default L1 comparator makes no decision; the default L2 resolver returns `{equivalent: None, confidence: 0.0, reason: SEMANTIC_RESOLUTION_NOT_CONFIGURED}` and makes zero provider calls.
- **Layering:** Safe L0 applies NFKC Unicode normalization, trimming/whitespace and line-break collapse, and case folding without deleting punctuation or meaningful words. Strict dispatch short-circuits after L0 or L1 decisions and invokes L2 only after cheaper comparison remains undecided; call-counter tests prove the boundaries.
- **Purity:** Comparison consumes the immutable Phase 3 `DocumentExtractionResult` values directly. It neither reopens documents nor reruns extraction, and tests prove both input objects remain unchanged.
- **Files:** `backend/app/comparison/__init__.py`, `models.py`, `normalization.py`, `service.py`; `backend/tests/test_phase4_comparison_core.py`; requirements matrix; this handoff.
- **Dependencies/schema:** No dependency, database model, migration, persistence, API, or submission change.
- **Validation:** Test-first collection failed because the package did not yet exist; after implementation the focused suite passed 16 tests. PostgreSQL-enabled full regression passed 160 tests with 0 failures, 0 skips, and 1 Starlette/AnyIO deprecation warning. `make reliability` passed 10 tests. `make check-fast` passed compileall, 11 tests with 1 warning, and `git diff --check`.
- **Closed rows:** `CMP-01`, `CMP-02`, `CMP-03`, `CMP-04`, `CMP-08`, `CMP-13`, `REL-04`.
- **Next:** Stop after P4A. Do not begin field-specific P4B rules or P4C persistence/output until explicitly authorized.

### 2026-09-20 — Phase P3B parallel extraction, versioned cache, and closure

- **EXT-03 architecture:** Valid SI and BL documents are submitted together to a bounded `ThreadPoolExecutor(max_workers=2)`. Worker threads receive only already-materialized `UnifiedDocument` values and perform pure deterministic computation; every SQLAlchemy cache query, savepoint, field write, status update, and commit remains on the owning caller thread. A barrier-based test proves both work units start before either finishes, and a SQLAlchemy event spy proves worker threads execute no SQL.
- **Failure isolation and retry:** Each side persists behind its own nested transaction. Extractor failure records `DOCUMENT_FIELD_EXTRACTION_FAILED` on only that document extraction, preserves the other side's seven durable fields, transitions the case to technical `FAILED`, and never fabricates fields from the other role. Both SI-fails and BL-fails directions are executable evidence. A later extraction retry recognizes the already-complete side, leaves its field row IDs intact, reruns only the failed side, and finishes with exactly seven unique rows per extraction.
- **Version/cache contract:** The single runtime version is `EXTRACTOR_VERSION = "phase3-deterministic-v1"`. Cache identity is exactly attachment `content_sha256` plus extractor version. Repository lookup joins the current document to its attachment hash; a hit copies only content-derived raw/native/canonical/provenance payload into the current document's own extraction and field rows. Same bytes across distinct attachment/document identities compute once; different bytes or a version change recompute. Same-pair duplicate keys are deduplicated before worker submission, and the existing per-extraction seven-field uniqueness constraint prevents duplicate rows.
- **Schema:** No migration `0008` was added. Migration `20260920_0007` already provides `attachments.content_sha256`, `document_extractions.extractor_version`, current-document ownership, and the unique `(extraction_id, field_name)` contract needed for safe lookup and reuse.
- **Public extraction audit:** `scripts/run_extraction_coverage.py` reads only `data/bundle`, writes `reports/extraction_coverage.md` and `reports/unmapped_labels.md`, and does not use private reference labels. It observed SI=106, BL=98, attempts=204, computations=204, cache hits=0, cache misses=204, failures=0, and 98 bounded parallel pairs in 2.305 seconds. Format distribution: PLAIN_TEXT=160, PDF_TEXT=14, DOCX=8, XLSX=22. Field status counts are recorded in the report; no accuracy percentage is claimed. LLM/OCR/Vision provider calls were all 0.
- **Files:** Extraction version/orchestration service; materialization integration; cache repositories; PostgreSQL concurrency/cache evidence; public audit script and reports; matrix; this handoff.
- **Dependencies:** None.
- **Validation:** Focused EXT-03/EXT-06 6 passed; combined Phase 2/3 focused 36 passed; full PostgreSQL suite 144 passed, 0 failed, 0 skipped, 1 warning; reliability 10 passed; eval 520 emails at 1.678 seconds / 309.926 emails/s; perf 520 emails at 1.611 seconds / 322.797 emails/s; check-fast 11 passed plus diff check; trace 58 PASS / 0 TODO / 0 FAIL; final Phase 3 check passed with 144 tests and a 1.666-second eval.
- **Next:** Stop. Do not begin comparison or call the scoreboard; Phase 4 requires explicit authorization.

### 2026-09-20 — Phase P3A-2 one-pass deterministic extraction and persistence

- **Changed:** Added the one-pass seven-field extractor, typed/raw field contract, structured page/table/cell provenance, XLSX native cell coordinates, DOCX table positions, additive field persistence, runtime materialization integration, migration `20260920_0007`, and substantive extraction/PostgreSQL tests.
- **Why:** Phase 3 requires independent deterministic SI/BL field results with durable raw evidence before parallelism, caching, or comparison can be built.
- **Files:** Extraction models/extractor; document models/readers/materialization; storage models/repositories; Alembic `0007`; Phase 3 tests; matrix; this handoff.
- **Dependencies:** None.
- **Validation:** Focused Phase 3 18 passed; Phase 2 regression subset 22 passed; full PostgreSQL suite 138 passed with zero skips; reliability 10 passed; check-fast passed; development DB migrated to `20260920_0007`.
- **Next:** Stop after P3A-2. P3B owns only `EXT-03` parallel isolation and `EXT-06` cache/version invalidation; do not begin either here.

### 2026-09-20 — Phase P3A-1 canonical field contract and strict label mapping

- **Changed:** Added the exact seven-field contract, closed provenance vocabulary, JSON-backed strict label mapper, conservative lookup normalization, explicit bilingual mappings, context-gated `To the Order of` handling, gross-vs-net protection, and substantive mapper tests.
- **Why:** Phase 3 needs an auditable mapping boundary before field extraction and persistence are designed.
- **Files:** `backend/app/extraction/*`, `backend/tests/test_phase3_label_mapping.py`, `docs/requirements_matrix.md`, and this handoff.
- **Dependencies:** None.
- **Validation:** Focused suite 11 passed; PostgreSQL-enabled full suite 131 passed with zero skips; safety scan clean; `make check-fast` passed.
- **Next:** Stop after P3A-1. P3A-2 may later add deterministic extraction/table-structure evidence; do not begin it in this task.

### 2026-09-20 — Phase 2 document materialization and role-validation closure

- **Changed:** Added lazy source attachment retrieval, SHA-256 and retrieval persistence, format-directed materialization, content/table-based SI/BL validation, structured blocking/failure outcomes, migration `20260920_0006`, public attachment inventory, Phase 2 corpus gate audit, and executable evidence for all Phase 2-owned rows.
- **Why:** The repository had standalone readers and a filename-weighted router but no READY-only orchestration, durable pre-extraction outcomes, or content-authoritative role validation. Immediate comparison requests with genuinely missing files also stopped one stage too early as unresolved readiness.
- **Files:** Ingestion source contract/adapters; readiness; document models/readers/router/validator/materialization; storage models/repositories; sync; Alembic `0006`; Phase 2 tests; trace tooling; matrix; audit/report artifacts; this handoff.
- **Dependencies:** No production dependency added. The existing declared reader stack was reused.
- **Validation:** Public inventory 250/250 with defined outcomes; focused Phase 2 unit and PostgreSQL evidence green; full PostgreSQL suite 120 passed with zero skips; reliability/check-fast/eval/perf/trace/check passed; dev schema survived at `20260920_0006`.
- **Next:** Stop. Begin Phase 3 only when explicitly authorized; do not implement canonical seven-field extraction or comparison in this phase.

### 2026-09-20 — Phase R3B final Phase 1 closure

- **Changed:** Froze current Human Review creation with PostgreSQL evidence; aligned category/readiness/status/reason-code contracts across runtime, database, API, migration, tests, and docs; added migration `20260920_0005`; retained compatibility boundaries.
- **Why:** `SCP-01`, `SCP-05`, and `SCP-07` required executable proof that Phase 1 did not extend Human Review, vocabularies cannot drift, and prior supported interfaces/data migrate safely.
- **Files:** API schemas/router, storage model/repository, sync persistence, Alembic `0005`, SCP/API/adapter/repository tests, `reports/phase1_consistency_audit.md`, matrix, and this handoff.
- **Validation:** Focused 23 passed; full PostgreSQL suite 101 passed; reliability 10 passed; eval/perf/check-fast/trace passed; final `make check PHASE=1` passed.
- **Next:** Stop Phase 1. Begin Phase 2 only when explicitly requested in a new phase session.

### 2026-09-20 — Phase R3A-2 zero-signal classification closure

- **Changed:** Added an explicit order-independent all-zero policy, propagated classification reason codes, replaced bare draft-BL evidence with action-specific signals, expanded CLS executable evidence, and regenerated the fixed-seed public audit.
- **Why:** A five-way zero-score tie accidentally selected `document_comparison` by insertion order, and a bare draft-BL token could independently create comparison intent.
- **Files:** `backend/app/classification/models.py`, `pipeline.py`, `signals.py`, `stage2.py`, Phase 1 classification tests, `scripts/run_classification_audit.py`, `reports/classification_audit.md`, `docs/requirements_matrix.md`, `implement.md`.
- **Validation:** Focused CLS 37 passed; full PostgreSQL suite 98 passed with zero skips; reliability 10 passed; check-fast passed.
- **Next:** Close only the remaining `SCP-01`, `SCP-05`, and `SCP-07` rows in R3B; do not begin Phase 2.

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

### 2026-09-20 — Phase 1 classification and readiness (partial)

- **Changed:** Final classifier output now uses five lowercase domain categories; `GENERAL_MAIL` is a compatibility alias with value `general_message`, and the pipeline no longer returns `UNCERTAIN` or creates Human Review cases for unresolved classification. Added the post-classification `comparison_readiness` field and additive Alembic revision `20260920_0003`; migrated legacy stored category values. Added deterministic readiness evaluation only for `document_comparison` and public synthetic tests for Pattern A, Pattern B, READY, AWAITING, UNRESOLVED, and non-comparison routing.
- **Validation:** `python scripts/run_tests.py -q` → 76 passed, 1 warning. Public bundle eval completed (520 emails, 2.000 seconds, 260.058 emails/s); reliability subset → 10 passed.
- **Blocked:** Phase 1 trace gate correctly fails because several Phase-1-owned matrix rows remain TODO and lack executable requirement-marked evidence. The prior Phase-0-only trace script was corrected not to falsely report a Phase 1 pass. Do not declare Phase 1 complete until every owner-phase-1 row is either implemented and marked PASS with evidence, or honestly marked FAIL with its blocker.

### 2026-09-20 — R1 processing-state evidence closed

- **Migration:** `20260920_0004_add_processing_state_events` adds `email_messages.processing_status` (NOT NULL) constrained to `NEW, QUEUED, CLASSIFYING, CLASSIFIED, AWAITING_DOCUMENTS, RETRIEVING_ATTACHMENTS, EXTRACTING, COMPARING, COMPLETED, BLOCKED, FAILED`, plus immutable `processing_events` with email FK and email/timestamp indexes.
- **Runtime:** `backend/app/storage/transitions.py` centralizes validated, transactional transitions and suppresses no-op events. Phase-1 flows persist completed non-comparisons, awaiting comparisons, and unresolved readiness as BLOCKED with `READINESS_UNRESOLVED`.
- **Backfill verification:** development database at `20260920_0004`: `CLASSIFIED=214`, `COMPLETED=306`, no null processing statuses. Inspector confirmed the check constraint, table, FK, and both indexes.
- **Validation:** focused PostgreSQL state suite 4 passed; sync regression 8 passed; full suite 80 passed, 0 skipped, 1 warning; reliability 10 passed; check-fast passed.

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
