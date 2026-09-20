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
**Updated by:** Phase P3A-2 one-pass deterministic extraction and persistence
**Repository state:** Phase 2 remains complete. P3A-2 closes deterministic one-pass extraction, structured provenance, and seven-row persistence. Phase 3 still has only `EXT-03` parallel orchestration and `EXT-06` SHA/version cache behavior outstanding; comparison remains untouched.

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
| Repository/stack audit | DONE | Python/FastAPI/SQLAlchemy/PostgreSQL stack and public participant bundle verified |
| Email ingestion | NOT CONFIRMED | Implementation must be checked |
| Initial sync | NOT CONFIRMED | Implementation must be checked |
| Continuous ingestion | NOT CONFIRMED | Implementation must be checked |
| Classification Stage 1 | IMPLEMENTED | Centralized deterministic signals and thresholds; exact five-category output contract |
| Classification Stage 2 | IMPLEMENTED | Validated five-category output, explicit zero-signal policy, evidence-aware deterministic tie handling |
| Comparison readiness | IMPLEMENTED | READY_FOR_COMPARISON / AWAITING_DOCUMENTS / UNRESOLVED after document_comparison only |
| Attachment retrieval | IMPLEMENTED | Lazy source-owned retrieval only for READY_FOR_COMPARISON; SHA-256 and storage identity persisted |
| Document router | IMPLEMENTED | TXT/PDF/DOCX/XLSX native paths; scanned/image inputs enter OCR/Vision directly; failures are structured |
| Document role validation | IMPLEMENTED | Content/title/table evidence assigns SI/BL; filename is never proof; clear wrong business documents block |
| SI/BL extraction | PARTIAL — P3A-2 | Deterministic per-document one-pass extraction and persistence implemented; cross-document parallel orchestration/cache remain pending |
| Canonical field mapping | IMPLEMENTED | Strict dictionary, bilingual/contextual/table provenance, ambiguity handling, and NET-weight exclusion have executable evidence |
| Comparison pipeline | NOT CONFIRMED | Implementation must be checked |
| Persistence | IMPLEMENTED THROUGH P3A-2 | Processing events, attachment/document materialization, and complete seven-field raw/canonical extraction rows with provenance |
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

- Stop after Phase 3. Begin SI-vs-BL comparison only when Phase 4 is explicitly authorized in a new phase session.

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

- Phase 3 stops after deterministic extraction in `EXTRACTING`; actual SI-vs-BL comparison remains Phase 4 work.
- Extraction remains deterministic and native. OCR and model-backed hard-case resolution remain later-phase work; `llm_resolved` is an allowed persisted provenance value but is never emitted here.
- The pipeline intentionally remains at `EXTRACTING`; it does not compare SI against BL, create MATCH/MISMATCH states, discrepancies, or an overall result.

- The public classification audit provides semantic/input evidence, not hidden-label correctness. No private ground truth or evaluator data was used.
- OCR/Tesseract is unavailable in the verified environment. Phase 2 therefore routes six public image-only PDFs correctly and persists a clean unreadable/blocking outcome; a working OCR implementation remains owned by `DOC-07b` in Phase 6A.
- Phase 2 materializes readable document content and validates SI/BL roles but intentionally does not extract the seven canonical shipment fields or compare documents. Those are Phase 3/4 responsibilities.
- Zero-signal messages intentionally remain low-confidence neutral results. A future model-backed resolver may improve their semantics, but Phase 1 does not invent unsupported specialized intent.
- The development database retains 21 historical Human Review rows and the legacy read-only Human Review API for compatibility. Current Phase 1 processing creates none.
- The Phase 0 baseline in `reports/latest/eval.md` contains historical classifications and skips unchanged emails; current Phase 1 classifier behavior is represented by `reports/classification_audit.md`, not by reinterpreting the historical baseline.
- Per-email p50/p95 and peak RSS remain unavailable because the existing sync/eval harness has no per-email timing or cross-platform process-metrics instrumentation.
- Public scoreboard results are not verified; no score call was made in Phase 1.

Current document-level limitations:

- Human Review UI/workflow is not specified in this milestone.
- Microsoft Graph integration may be an integration path rather than an implemented hackathon dependency.
- Exact model/OCR/provider choices are intentionally not locked until repository constraints are inspected.
- Exact participant-facing challenge submission schema must be verified against the public `sample_submission.json` used by the team.
- No implementation claim should be made from this document until source code is inspected.

---

## Recent Change Log

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
