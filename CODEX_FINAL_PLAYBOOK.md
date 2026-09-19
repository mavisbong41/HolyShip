# HolyShip Backend - Codex Final Playbook

Goal: Codex builds the backend in controlled phases, tests itself, measures accuracy / reliability / performance, and
**every spec requirement is tracked by ID and machine-checked** (`docs/requirements_matrix.md` + `make trace`).

Three files travel together:

| File Where it goes in the repo        |                                     |
| ------------------------------------- | ----------------------------------- |
| `CODEX_FINAL_PLAYBOOK.md` (this file) | anywhere (you copy prompts from it) |
| `PHASE_PROTOCOL.md`                   | `docs/PHASE_PROTOCOL.md`            |
| `requirements_matrix.md`              | `docs/requirements_matrix.md`       |

---

## 0. One-time setup

1. **Repo**: clone your friend's full code as a git repo (`git checkout -b codex/phase-0`).
2. **Root of the repo**: `AGENTS.md`, `backend_requirements_ingestion_to_compare.md`, `implement.md`, `README_batch1.md`. **`docs/`**: `PHASE_PROTOCOL.md`, `requirements_matrix.md`.
3. **Data**: only the participant bundle (`inbox/`, `attachments/`, `sample_submission.json`, `loader.py`, `README.md`) in `data/bundle/`. 
   - NEVER put `data_v2/ground_truth.json` (from the organizer docker zip) anywhere Codex can read.
   - Run the organizer server OUTSIDE the repo: `docker compose up --build` -> `http://localhost:8080`. Codex only calls `POST /submit`.
4. **Postgres / Docker**: start them yourself outside Codex (its sandbox usually cannot run docker). Connection string in `.env`.
5. **Codex config** (`~/.codex/config.toml`): 
   ```toml
   project_doc_max_bytes = 65536   # AGENTS.md is ~30 KB; the default 32 KiB cap silently truncates anything beyond it

   ```
   Also allow the sandbox network (for `localhost:8080` and `pip install`), or approve those commands when asked. The setting name depends on the Codex version; check `codex --help` / the official docs.
6. **Run**: `codex --full-auto` in the repo root. **One new session per phase.**
7. **After each phase**: review (section 4), then `git add -A && git commit -m "phase N" && git tag phase-N-pass`.

Do not paste several phases at once. You are the outer loop; Codex runs the inner loop
(implement -> test -> measure -> fix -> rerun) and stops at a gate or a blocker.

## 1. Commands Codex creates in Phase 0

```text
make test                 full unit + integration tests
make check-fast           focused tests + schema validation + lint/type checks (use while iterating)
make eval                 full participant-bundle run -> reports/latest/{submission.json,eval.md}, appends reports/history.csv
make reliability          idempotency, determinism, failure isolation, restart/resume, fault injection
make perf                 throughput, p50/p95 per stage, memory, expensive-call counts
make trace PHASE=<N>      requirements-matrix gate (fails on any TODO/FAIL row owned by a phase <= N)
make check PHASE=<N>      test + eval + reliability + perf + trace   (never calls the scoreboard)
make score PHASE=<N>      POST submission to the public /submit; max 2 per phase; logged; aggregate only

```

## 2. How "follow the requirements" is enforced

- **Traceability**: \~105 requirement rows (ID, spec/AGENTS section, owner phase, how to verify). A row is `PASS` only with a passing test carrying `@pytest.mark.req("ID")` (or an existing audit report). Codex cannot delete/reword rows or self-`WAIVE`. `make trace` fails the phase gate otherwise.
- **Authority order**: public challenge files > spec > AGENTS.md > phase prompt. If a prompt disagrees with the spec, Codex follows the spec and reports it.
- **Prompts reference spec sections instead of re-paraphrasing them**, so the prompt cannot drift from the spec.
- **Phase F** re-verifies everything independently, including a mutation check that the tests are not vacuous.

What this cannot do: decide things the spec leaves open. Those are listed in section 5 and need YOU (or the organizers).

---

## 3. Prompts

### PHASE 0 - Audit, traceability, evaluation harness, baseline

```text
PHASE 0 - AUDIT, TRACEABILITY, EVALUATION HARNESS, BASELINE

READ FIRST, in this order:
1. docs/PHASE_PROTOCOL.md
2. AGENTS.md
3. backend_requirements_ingestion_to_compare.md (entire file)
4. implement.md
5. docs/requirements_matrix.md
6. README_batch1.md  (a teammate's CLAIM about existing work - verify it, do not trust it)
7. data/bundle/README.md and data/bundle/sample_submission.json (public challenge contract)
8. the actual source code, migrations, tests, configs, Docker files

Authority order and conflict handling: docs/PHASE_PROTOCOL.md section 1.

SCOPE: audit + harness + baseline only.
Do NOT rewrite the classifier. Do NOT start extraction/comparison. Do NOT change product behaviour except the minimal
adapter in TASK E.
OWNS: ING-09, SUB-01, SEC-01, SEC-02, SEC-03, SCP-03, SCP-04, SCP-08, and the audit status of every other row.

TASK A - Audit the real repository
Install, run existing tests, run migrations, start the app, run one full participant-bundle sync through the existing
source. Record exact commands and exact results. Replace every "NOT CONFIRMED" in implement.md with evidence.
Verify README_batch1.md claims one by one (including its test-status claims; the test-status section of that README is empty).

TASK B - Fill the requirements matrix
1. BEFORE editing the matrix, write its ID list to docs/requirements_seed_ids.txt (one ID per line). This file is frozen.
2. For EVERY row set Status from evidence:
   - PASS only with a passing test carrying @pytest.mark.req("<ID>") (write a minimal test for already-existing behaviour
     if needed) or, for audit rows, an existing report path.
   - FAIL with a Notes entry (what is wrong, which file) if current code violates the row.
   - TODO if the behaviour is not built yet.
3. In implement.md add a "Spec gap analysis" summary table: requirement | current behaviour | required behaviour |
   severity | evidence | files | fix phase. It must at least cover the checks in TASK C.

TASK C - Specific conflicts to check (report each explicitly)
1. Final categories: required exactly document_comparison / new_si_request / invoice_query / general_message / spam.
   Does code expose UNCERTAIN, GENERAL_MAIL or other values?
2. State model vs spec section 7 (every enum, schema, migration, test, API, doc).
3. Comparison Readiness (READY_FOR_COMPARISON / AWAITING_DOCUMENTS / UNRESOLVED) - exists?
4. The critical collision. Can the classifier distinguish:
   A: "Please assist to send the draft BL for <ref> for checking asap."  -> document_comparison + AWAITING_DOCUMENTS
   B: "Please find Shipping Instruction for <ref>. Shipper: ... Consignee: ... POL: ... POD: ... Please revert with draft
       BL once available." -> new_si_request
   "0 attachments + contains draft BL" must never be a sufficient rule.
5. WRONG_DOCUMENT_TYPE validation and misleading _SI/_BL filename handling.
6. Human Review tables/code exist: FREEZE them (do not extend, do not delete).
7. API paths (/api/*) vs spec (/api/v1/*).
8. Common internal email model vs spec section 6 (fields, idempotency key source + external_email_id).
9. Leakage audit: search the whole repo for ground_truth.json, data_v2, private answers, email_id-specific conditions,
   filename-specific expected answers, hard-coded 520, lookup tables of answers. Write reports/leakage_audit.md.
10. The README's claim of 214 document-comparison emails vs the number of emails that actually have attachments - what is
    the gap composed of? (Report only; fixing is Phase 1.)

TASK D - Build the harness (scripts/eval/, scripts/trace_check.py, Makefile)
Implement every target in section 1 of the playbook. Requirements:
- make eval writes reports/latest/submission.json (official shape, validated against data/bundle/sample_submission.json)
  and reports/latest/eval.md containing: total emails; category distribution; stage1/stage2 counts; low-confidence count;
  attachment stats for comparison emails; readiness distribution if implemented; internal unresolved counts;
  FAILED/BLOCKED by reason; unhandled exceptions; wall time; p50/p95 per stage; LLM/OCR/Vision call counts; cache-hit rate;
  peak RSS if practical. Append one row to reports/history.csv.
- make reliability (pytest marker): idempotent resync, duplicate ingest, deterministic repeated run, per-email failure
  isolation, corrupt/empty input handling.
- make trace PHASE=<N>: implemented in scripts/trace_check.py exactly as docs/PHASE_PROTOCOL.md section 2 specifies
  (parse the matrix; owner-phase ordering 0,1,2,3,4,5,6A,6B,7,F; verify cited tests exist, carry the req marker and passed
  in the latest run; verify no seed ID from docs/requirements_seed_ids.txt is missing).
- make check PHASE=<N> = test + eval + reliability + perf + trace. It must NOT call the scoreboard.
- make score PHASE=<N>: POST only the generated official-shape submission to the public self-evaluation endpoint
  (http://localhost:8080/submit via loader.py or plain HTTP); refuse a 3rd call for the same phase unless --force (logged);
  append every call to reports/score_history.jsonl; save the aggregate response to reports/latest/scoreboard.json.
- make check must not depend on manual setup beyond the documented .env / docker compose.

TASK E - Minimal submission adapter (baseline only)
Categories: document_comparison->BL_COMPARISON, new_si_request->SI_REQUEST, invoice_query->INVOICE_QUERY,
general_message->GENERAL, spam->SPAM. Verify the enums (status OK|MISMATCH|NEEDS_REVIEW; review_reason
wrong_doc_type|missing_attachment|unreadable|missing_value) against the bundle README and sample_submission.json.
Non-comparison emails: status OK, review_reason null, has_defect false, defect_fields [].
Legacy UNCERTAIN: for BASELINE EXPORT ONLY use the top-scoring of the five categories; mark TEMPORARY LEGACY COMPATIBILITY.
Comparison emails that cannot be compared yet: NEEDS_REVIEW + missing_value, marked PLACEHOLDER in code and implement.md.
AWAITING_DOCUMENTS: its official mapping is NOT validated. Isolate one config value, mark it UNVALIDATED, record it in
implement.md, and do not tune it from scoreboard movement.

TASK F - Baseline
Run make check PHASE=0, then make score PHASE=0 once. Save reports/baseline.md and say which metrics are meaningful now
(only classification-related ones) and which are not.

GATES
- make check PHASE=0 runs end-to-end with 0 unhandled process-wide exceptions (trace may show FAIL/TODO rows owned by later
  phases; rows owned by phase 0 must be PASS).
- reports/baseline.md, reports/leakage_audit.md, docs/requirements_seed_ids.txt exist.
- implement.md has the gap table and no NOT CONFIRMED without an explicit reason.
- No broad product-behaviour rewrite.

FINISH per docs/PHASE_PROTOCOL.md sections 7 and 8. Print the PHASE REPORT. STOP. Do not begin Phase 1.

```

**你检查**：`git diff --stat` 范围；`docs/requirements_seed_ids.txt` 行数 = 矩阵行数；gap table 是否列出上面 10 项；`reports/leakage_audit.md` 里有没有找到问题；自己在干净 checkout 跑一次 `make check PHASE=0`。

---

### PHASE 1 - Classification alignment, states, Comparison Readiness

```text
PHASE 1 - CLASSIFICATION ALIGNMENT, PROCESSING STATES, COMPARISON READINESS

READ FIRST: docs/PHASE_PROTOCOL.md; AGENTS.md; spec sections 6, 7, 8, 17.7, 20, 21, 22; implement.md;
docs/requirements_matrix.md; reports/baseline.md.
Authority order: PHASE_PROTOCOL section 1 (spec wins over this prompt).

SCOPE ONLY: five-category alignment, state model, ProcessingEvent, common email model alignment, deterministic
Stage 1/Stage 2 cleanup, Comparison Readiness, adapter compatibility for these concepts.
Do NOT touch document readers, extraction or comparison.
OWNS: ING-06, ING-07, CLS-01..08, CLS-10..13, STA-01, STA-02, STA-04, STA-06, STA-07, SCP-01, SCP-05, SCP-07.

TASK 1 - Final categories (CLS-01)
Persist and expose exactly: document_comparison, new_si_request, invoice_query, general_message, spam.
UNCERTAIN / GENERAL_MAIL must not survive as final values. Represent uncertainty as confidence + a low_confidence flag and
still choose the best of the five. Write an Alembic migration that converts existing rows safely. Stop creating NEW Human
Review cases from the classifier (leave existing Human Review tables/APIs untouched and frozen).

TASK 2 - States and events (STA-01, STA-02, STA-04, STA-06, STA-07, CLS-02)
Authoritative states per spec section 7. Non-document_comparison emails go to COMPLETED right after classification.
Add ProcessingEvent: every status transition persisted with timestamp and reason code. Readiness UNRESOLVED -> persisted as
UNRESOLVED with status BLOCKED (reason code), never guessed. Original email content is never mutated.
Search the whole repository for every enum list, schema, validator, migration, fixture, API contract, test and doc and
update them together (SCP-05). Keep old routes/behaviour working where the spec does not require a break (SCP-07).

TASK 3 - Common email model (ING-06, ING-07)
One internal model per spec section 6. Provider/dataset-specific fields must not leak into classification.
Dataset records contain only email_id/from/subject/body/attachments: do NOT fabricate received_at or recipients; store null
plus a separate ingested_at. Enforce uniqueness on (source, external_email_id) at DB level.

TASK 4 - Inputs and thresholds (CLS-11, CLS-13)
Classification reads subject, body, sender/context, attachment METADATA only; never attachment content.
All thresholds and weights live in one config module.

TASK 5 - The critical collision (CLS-06, CLS-07, CLS-08, CLS-10)
Implement a general structured-SI-body detector (density of canonical SI labels in the body) plus primary-requested-action
detection. Evidence: detected SI labels, field density, immediate compare/check wording, future draft-BL follow-up wording,
attachment count as SUPPORTING evidence only.
Pattern A (short request to send the draft BL for checking, no SI block) -> document_comparison + AWAITING_DOCUMENTS.
Pattern B (inline SI block + future draft-BL follow-up) -> new_si_request.
Never use "attachments == 0 AND contains draft BL" as a rule. asap / once available / for checking / revert with draft BL
are supporting evidence only. Subject lines are not blindly trusted.

TASK 6 - Comparison Readiness (CLS-05, CLS-12)
Runs ONLY after final category == document_comparison and can never reclassify a new_si_request.
States READY_FOR_COMPARISON / AWAITING_DOCUMENTS / UNRESOLVED with the evidence object from spec section 8.6.
AWAITING_DOCUMENTS is a legitimate operational state (status AWAITING_DOCUMENTS, no extraction). Whether an expected-but-
missing attachment becomes MISSING_REQUIRED_ATTACHMENT is decided at retrieval in Phase 2.

TASK 7 - Stage 2 interface (CLS-04)
Keep Stage 2 deterministic but behind a pluggable Stage2Resolver interface with the input/output of spec section 8.4
(exactly one of five categories, confidence, reason_code). No LLM dependency yet.

TASK 8 - Adapter
Update the adapter for the new categories/states. AWAITING_DOCUMENTS keeps its single UNVALIDATED config mapping.

TASK 9 - Tests (mark each with @pytest.mark.req)
Each of the five categories; misleading subject; subject/body conflict; Pattern A; Pattern B; zero attachments + draft BL;
immediate comparison request with attachments genuinely expected; Stage 1 clear case; Stage 2 ambiguous case; readiness only
after document_comparison; readiness cannot reclassify new_si_request; invalid enum rejected at DB level; non-comparison
emails end COMPLETED with no document-layer calls (spy); ProcessingEvent transitions; duplicate (source, external id) rejected.

TASK 10 - reports/classification_audit.md (input-based, no private data)
A. Fixed-seed sample of 15 emails per category: id, evidence summary, system decision, YOUR correctness judgement, ambiguity notes.
B. ALL no-attachment emails currently classified document_comparison, grouped: legitimate AWAITING_DOCUMENTS / true expected-
   but-missing attachment / likely new_si_request / unresolved. Explain the gap noted in Phase 0.
C. All subject/body conflict cases.
Fix systematic errors with general rules only.

GATES
- every email has exactly one of the five categories; DB constraint enforces it
- Pattern A and Pattern B tests pass; no per-email hacks
- make check PHASE=1 passes (trace: all rows owned by phases 0-1 PASS)
- make score PHASE=1 (max 2): Stage-1 macro-F1 must not regress vs baseline without a documented, accepted reason
Investigate generalizable causes; never change logic just because one aggregate moved.

FINISH per docs/PHASE_PROTOCOL.md sections 7 and 8. Print the PHASE REPORT. STOP.

```

**你检查**：`classification_audit.md` (b) 那批无附件 comparison 是不是被逐类看过；DB 里真的有 enum/CHECK 约束；`grep -rn "UNCERTAIN\|GENERAL_MAIL" src` 为空（迁移脚本除外）。

---

### PHASE 2 - Document layer: retrieval, router, role assignment, validation

```text
PHASE 2 - DOCUMENT READER / ROUTER / ROLE VALIDATION

READ FIRST: docs/PHASE_PROTOCOL.md; AGENTS.md; spec sections 9, 10, 11.5, 17.1, 17.2, 21; implement.md;
docs/requirements_matrix.md.

SCOPE: attachment retrieval for READY_FOR_COMPARISON, content materialization, routing, SI/BL role assignment,
WRONG_DOCUMENT_TYPE validation, attachment inventory. NO seven-field extraction yet.
OWNS: ING-11, CLS-09, DOC-01..06, DOC-07a, DOC-08, DOC-09, DOC-10, DOC-11, DOC-13, STA-03, PRF-01.

FIRST inspect and reuse the existing UnifiedDocument, PlainTextReader, PdfTextReader, DocxReader, XlsxReader, OcrReader,
VisionReader, CompositeDocumentReader and Document Router. Do not rewrite working components unnecessarily.

TASK 1 - Lazy retrieval (DOC-01, DOC-02, ING-11, PRF-01)
Only READY_FOR_COMPARISON emails enter this layer. Retrieve content lazily via the source adapter (the organizer HTTP source
serves /attachments/{path}); compute SHA-256; persist a storage reference; keep attachment identity.
If the email is READY and the SI or BL that the body says is attached is genuinely absent -> MISSING_REQUIRED_ATTACHMENT +
status BLOCKED (CLS-09). This is different from AWAITING_DOCUMENTS (decided in Phase 1).

TASK 2 - Routing by content, not extension alone (DOC-03..08)
Support: plain text; text PDF; DOCX paragraphs + tables; XLSX (iterate rows/cells, no fixed header assumption, native numeric
cells preserved and exposed as tables/cells in UnifiedDocument); image-only PDF; images; corrupted/truncated; empty/zero-byte;
unsupported types.
Native first: never OCR a normal text PDF. Image-only PDFs and images go DIRECTLY to the OCR/Vision route (do not try
unsuitable extractors first). If OCR is unavailable: clean "unreadable" outcome, never a crash.
Outcomes persisted: SI_FOUND, BL_FOUND, MULTIPLE_CANDIDATES, MISSING_REQUIRED_ATTACHMENT, UNSUPPORTED_ATTACHMENT,
CORRUPTED_ATTACHMENT, WRONG_DOCUMENT_TYPE.

TASK 3 - Role assignment (DOC-10, DOC-13)
Filename + content evidence together. A *_SI / *_BL filename is NOT proof. If evidence is insufficient do not guess which
file is authoritative: persist BLOCKED with a reason code.

TASK 4 - WRONG_DOCUMENT_TYPE (DOC-11)
After readable content exists, before fields are trusted, validate the claimed role with cheap deterministic evidence only:
title/header; density of expected SI/BL labels vs conflicting labels; conflicting titles (COMMERCIAL INVOICE, PACKING LIST,
CERTIFICATE OF ORIGIN, ...); explicit self-declaring lines. Clearly wrong -> WRONG_DOCUMENT_TYPE + BLOCKED.
Inconclusive -> do NOT force it; continue and let extraction confidence/UNRESOLVED handle it.
The validator consumes UnifiedDocument (text AND tables/cells), so it will also work on OCR output later.

TASK 5 - reports/attachment_inventory.md
For EVERY attachment in the bundle: email ref, filename, format, reader chosen, readable?, text/table size, detected role,
validation outcome, parse time, anomalies. Explicitly list all PDF / DOCX / XLSX / scanned / corrupt / empty / wrong-type /
ambiguous-role cases. For each WRONG_DOCUMENT_TYPE record the marker/evidence that triggered it.

TESTS (req-marked): normal TXT SI+BL; DOCX; XLSX; text PDF; image-only PDF; corrupted PDF; 0-byte; misleading filename;
wrong business document type; missing SI; missing BL; multiple SI; multiple BL; unsupported type; READY email with genuinely
missing attachment vs AWAITING_DOCUMENTS email (no retrieval at all); non-comparison email never reaches this layer.
PERFORMANCE ASSERTION: an image-only PDF must not traverse multiple unsuitable readers before the OCR route (call counters/spies).

GATES
- 100% of attachments in the bundle end in a defined outcome; 0 unhandled exceptions
- each WRONG_DOCUMENT_TYPE decision cites its marker and you inspected all of them
- make check PHASE=2 passes (trace: rows owned by phases 0-2 PASS)
- make score PHASE=2: classification must not regress

FINISH per docs/PHASE_PROTOCOL.md sections 7 and 8. Print the PHASE REPORT. STOP.

```

**你检查**：inventory 里 pdf/docx/xlsx/扫描/坏文件各有例子；WRONG_DOCUMENT_TYPE 的引用理由；没有靠文件名判角色。

---

### PHASE 3 - Deterministic seven-field extraction + canonical mapping

```text
PHASE 3 - DETERMINISTIC SEVEN-FIELD EXTRACTION + CANONICAL LABEL MAPPING

READ FIRST: docs/PHASE_PROTOCOL.md; AGENTS.md; spec sections 11, 12, 17.3, 17.4, 17.6; implement.md;
docs/requirements_matrix.md.

SCOPE: extraction and label mapping only. NO real LLM/Vision. Deterministic/native extraction.
OWNS: EXT-01..04, EXT-05a, EXT-06, MAP-01..06.

TASK 1 - One-pass extraction (EXT-01, EXT-02, EXT-04)
One document -> one pass -> the seven canonical fields (shipper, consignee, notify_party, port_of_loading,
port_of_discharge, container_count, gross_weight_kg). No field added or removed. Per field keep raw_label, canonical_field,
raw_value, confidence, mapping_method, source (page/table/cell/text_span). Raw values are never overwritten.
Support key:value lines, multi-line values, plain text blocks, DOCX tables, XLSX rows/cells, PDF text, tables from UnifiedDocument.
Extraction confidence thresholds are configurable; below threshold -> unresolved, not fact.
Decide from corpus evidence how multi-line entity values (name + address) are represented; preserve the full raw block;
record the decision in implement.md.

TASK 2 - Label dictionary (MAP-01, MAP-05)
One configurable dictionary file (yaml/json), extendable, covered by tests. Cover observed and general variants (Port of
Loading / Load Port / Loading Port / POL, Port of Discharge / Discharge Port / POD, Gross Wt (kgs), ...). No broad fuzzy
matching; ambiguous stays unresolved.

TASK 3 - Bilingual / descriptive labels (MAP-02)
"Shipper (Principal or Seller) (发货人)" -> shipper; "Port of Loading (POL) (装货港)" -> port_of_loading;
"Gross Wt (kgs) (毛重 KGS)" -> gross_weight_kg. Keep raw_label. Do NOT blindly delete parenthesized text.

TASK 4 - Contextual consignee rule (MAP-03)
In the negotiable-B/L consignee/order context, "To the Order of" -> consignee with mapping_method contextual_business_rule.
Never map arbitrary occurrences of "order".

TASK 5 - Provenance (MAP-04)
mapping_method is one of: exact_label, alias_dictionary, bilingual_label_normalization, contextual_business_rule,
table_structure, llm_resolved.

TASK 6 - Gross-weight guard (MAP-06)
NET WEIGHT (or any non-gross weight) never populates gross_weight_kg. If gross weight is absent, missing/unresolved is correct.

TASK 7 - Container raw value
Keep raw_value "6 x 40'HC"; store auxiliary parsed count=6 and type "40'HC". (Comparison semantics are Phase 4.)

TASK 8 - Parallelism and cache (EXT-03, EXT-06)
SI and BL extraction run in parallel where safe; if one fails, the other's result is preserved and the case marked properly.
Cache by content SHA-256 + extractor version; invalidate when the extractor/schema version changes.

TASK 9 - Reports
reports/unmapped_labels.md: every unmapped candidate label - normalized text, count, document examples, why not mapped.
Extend the dictionary ONLY when input evidence unambiguously supports the canonical meaning.
reports/extraction_coverage.md: format x field -> extracted %, low-confidence %, missing %, unresolved %, reason distribution.
Every missing field needs a stated reason (label absent / unmapped label / layout unsupported / unreadable).

TESTS (req-marked): all seven fields; alternate labels; bilingual labels; To the Order of (positive AND a negative "order"
case); DOCX tables; XLSX numeric cells; multi-line values; missing field; duplicate candidate values; raw-value preservation;
NET WEIGHT-only document; compound container format; malformed numeric data; parallel extraction with one side failing;
cache hit and cache invalidation on version change.

GATES
- coverage report numbers are real; every missing field explained
- grep shows no per-email/per-filename logic; no fuzzy matching
- make check PHASE=3 passes (trace: rows owned by phases 0-3 PASS); make score PHASE=3 if useful; no classification regression

FINISH per docs/PHASE_PROTOCOL.md sections 7 and 8. Print the PHASE REPORT. STOP.

```

**你检查**：`unmapped_labels.md` 剩下的确实是模糊标签；没有偷偷加 fuzzy；覆盖率表里没有 "unknown reason"。

---

### PHASE 4 - Normalization, comparison, persistence, submission output

```text
PHASE 4 - LAYERED NORMALIZATION + COMPARISON + PERSISTENCE + SUBMISSION OUTPUT

READ FIRST: docs/PHASE_PROTOCOL.md; AGENTS.md; spec sections 13, 14, 15, 16, 20, 22; implement.md;
docs/requirements_matrix.md; data/bundle/README.md (submission contract).

SI is ALWAYS the reference; the draft BL is the document being checked. NO Human Review UI.
OWNS: MAP-07, CMP-01..13, STA-05, REL-04, SUB-02, SUB-03.

TASK 1 - L0 (CMP-04): trim, collapse whitespace, case, Unicode normalization, line-break artifacts. Never remove meaningful
words. Fast compare after L0.

TASK 2 - L1 field-specific (CMP-05, CMP-06, CMP-07, MAP-07)
- container_count: "03"->3, "3 containers"->3, "6 x 40'HC"->6 (type kept aside); a type-only difference is NOT a count
  mismatch; unparseable -> UNRESOLVED.
- gross_weight_kg: "22,000 KG" == "22000 kg"; XLSX native numbers use the same canonical path; unit conversion only if
  explicit, deterministic and tested; NET WEIGHT never substitutes.
- ports: case/whitespace + APPROVED alias/code dictionary only. Alias entries live in a config file and each entry needs
  evidence (a standard code<->name pair, or a clear SI/BL pair in the corpus). Write reports/port_aliases_review.md listing
  EVERY entry with its evidence for human sign-off. No similarity-based equivalence.
- shipper/consignee/notify_party: conservative (case, whitespace, harmless punctuation). Never strip legal/company words
  ("ABC Logistics Malaysia" must not become "ABC Logistics").

TASK 3 - Layering proof (CMP-03, CMP-13)
canonical mapping -> L0 -> fast compare -> L1 -> compare -> L2. Prove with call counters that L1/L2 do not run for values
that already matched at the cheaper layer.

TASK 4 - L2 interface only (CMP-08)
Interface returning {equivalent, confidence, reason}; default implementation returns UNRESOLVED. Real LLM is optional Phase 6B.

TASK 5 - Field results (CMP-01, CMP-02, REL-04)
Each field MATCH / MISMATCH / UNRESOLVED. Missing data is neither MATCH nor MISMATCH. Never convert an uncertain comparison
into a confident mismatch.

TASK 6 - Persistence and output model (CMP-09, CMP-10, CMP-11, STA-05)
Persist per spec section 16: si_raw, bl_raw, normalized values, per-field status, mismatched_fields, evidence references.
All seven MATCH -> mismatch_found=false + message "No mismatch detected.". Case status: COMPLETED when every field is
definite (MATCH/MISMATCH); BLOCKED (reason code) when any field is UNRESOLVED; partial results are preserved either way.
Ensure all entities from spec section 20 exist and are populated.

TASK 7 - Submission adapter (SUB-02, SUB-03) - explicit, isolated, separately tested mapping table
  internal outcome                                        -> status        review_reason      has_defect / defect_fields
  all seven MATCH                                         -> OK            null               false / []
  >=1 field MISMATCH                                      -> MISMATCH      null               true / [those fields]   (PROVISIONAL)
  WRONG_DOCUMENT_TYPE                                     -> NEEDS_REVIEW  wrong_doc_type     false / []
  READY + MISSING_REQUIRED_ATTACHMENT                     -> NEEDS_REVIEW  missing_attachment false / []
  CORRUPTED / UNSUPPORTED / unreadable (no OCR)           -> NEEDS_REVIEW  unreadable         false / []
  field UNRESOLVED/missing, no confident MISMATCH         -> NEEDS_REVIEW  missing_value      false / []
  AWAITING_DOCUMENTS                                      -> UNVALIDATED config value (default NEEDS_REVIEW + missing_attachment)
  MULTIPLE_CANDIDATES / readiness UNRESOLVED / other BLOCKED -> UNVALIDATED config value (default NEEDS_REVIEW + missing_value)
  non-comparison email                                    -> OK            null               false / []
Rows marked PROVISIONAL/UNVALIDATED are single config values, listed under "Blocked / Open Questions" in implement.md.
Do not tune them from scoreboard movement. The internal model stays semantically correct regardless of this mapping.
Remove the Phase-0 placeholder.

TASK 8 - Metamorphic accuracy tests in tests/metamorphic/ (CMP-12, REL-04; built from REAL pairs where possible)
M1 format-only changes to BL values (case, whitespace, thousands separators, kg/KG, "03" vs "3", "3 containers", harmless
   punctuation) -> must stay MATCH. False alarms must be 0.
M2 single-field defect injection: change exactly ONE canonical field materially -> exactly that field is MISMATCH.
   Synthetic recall must be 100%.
M3 missing value / NET WEIGHT-only / unreadable -> never a fabricated MATCH or MISMATCH.
M4 normalization never destroys stored raw values.
M5 swapping SI/BL changes which side is the reference and nothing else.

TASK 9 - reports/comparison_sanity.md
Mismatch rate per field over the real pairs. Investigate suspicious spikes (likely extraction/normalization bugs) before
accepting them. Do not "fix" a spike by suppressing mismatches without evidence.

GATES
- M1 false alarms = 0; M2 recall = 100%; every READY comparison case ends in a defined state; 0 unhandled exceptions
- reports/port_aliases_review.md exists
- make check PHASE=4 passes (trace: rows owned by phases 0-4 PASS)
- make score PHASE=4 (max 2). Use it as supporting evidence only; fix only generalizable root causes and record them.

FINISH per docs/PHASE_PROTOCOL.md sections 7 and 8. Print the PHASE REPORT. STOP.

```

**你检查**：M1/M2 样本量和是否用了真实 pair；各字段 mismatch 率有没有尖峰；`port_aliases_review.md` 的每一条你能认同（这是需要你签字的地方）；adapter 映射表里哪些行还是 UNVALIDATED。

---

### PHASE 5 - Reliability and performance hardening

```text
PHASE 5 - RELIABILITY + PERFORMANCE HARDENING

READ FIRST: docs/PHASE_PROTOCOL.md; AGENTS.md; spec sections 17, 21; implement.md; docs/requirements_matrix.md;
the last three rows of reports/history.csv.

NO new business features. Correctness must stay stable: the semantic submission output must not change unless you explain
and justify each difference.
OWNS: ING-02, PRF-02, PRF-04, REL-01, REL-02, REL-03, REL-05, REL-06.

TASK 1 - Controlled concurrency (PRF-02): config-driven limits for classification / extraction / OCR / LLM workers; bounded
backlog batches; progressive persistence (results visible while the sync is still running). Never hard-code dataset size.
TASK 2 - Idempotency (ING-02, REL-01): repeated initial sync; repeated same provider message; duplicate CONCURRENT incoming
request; content-hash reuse; no duplicate cases/results (DB-level uniqueness).
TASK 3 - Restart/resume: interrupt a sync mid-way (process-level simulation), resume with no duplicate and no lost work.
TASK 4 - Retries/timeouts (REL-02): bounded retries, exponential backoff where appropriate, explicit timeouts, no infinite
loops, preserved partial work (REL-03).
TASK 5 - Failure semantics (REL-05, REL-06): technical failure -> FAILED with reason code and diagnostics (ids, not document
contents); cannot-safely-continue -> BLOCKED; the batch always continues. Enumerate every reason code in implement.md.
TASK 6 - Fault-injection suite (pytest -m reliability): corrupt PDF; zero-byte; very large file; odd encoding; Unicode filename;
duplicate concurrent ingestion; parser exception; mocked DB transient failure; mocked resolver timeout; malformed model output
(mock); SI success + BL failure. Expected: isolated failure, reason code, the rest continues, no process-wide crash.
TASK 7 - Cache (PRF-04): identical documents reuse cached extraction; unchanged emails are not reclassified; version bump invalidates.
TASK 8 - Measure first, then optimize: total wall, emails/sec, p50/p95 per stage, time per document format, DB hotspots,
cache-hit rate, peak RSS, expensive-call counts. Profile (e.g. cProfile), name the top 5 bottlenecks, fix ONLY measured ones,
show before/after. Allowed: bounded parallelism, SI/BL parallel, hash cache, batching, avoiding repeated parsing, DB query
improvements, lazy retrieval. Never speed up by weakening correctness.
TASK 9 - Scale check (optional if infrastructure is constrained; else say NOT VERIFIED): synthetic larger backlog from allowed
sample inputs under NEW ids; bounded memory, roughly linear time.

GATES
- workers=1 vs configured parallel run -> identical semantic submission output; two identical runs -> identical output
- idempotency, restart/resume and fault-injection tests pass; 0 unhandled process-wide exceptions
- second run cache-hit rate >= 90% for documents
- any >20% performance regression vs previous history row is explained
- make check PHASE=5 passes (trace: rows owned by phases 0-5 PASS); make score PHASE=5 equals Phase 4's semantics

FINISH per docs/PHASE_PROTOCOL.md sections 7 and 8. Print the PHASE REPORT. STOP.

```

---

### PHASE 6A - OCR path (required by the acceptance criteria)

```text
PHASE 6A - OCR / SCANNED-DOCUMENT PATH (DETERMINISTIC, NO LLM)

READ FIRST: docs/PHASE_PROTOCOL.md; AGENTS.md; spec sections 10, 11.4, 24 ("Scanned-document OCR/Vision path is supported");
implement.md; docs/requirements_matrix.md; reports/attachment_inventory.md.
OWNS: DOC-07b, DOC-12, PRF-03.

TASK 1: Implement OcrReader behind the existing interface (e.g. Tesseract; binary/provider via env/config, documented in
.env.example). If the binary cannot be installed, implement + test the path with a mock OCR and record the limitation as
"real OCR NOT VERIFIED" - do not pretend.
TASK 2: OCR output becomes a UnifiedDocument (with page info) and flows through the SAME role validator and deterministic
extractor as native text (DOC-12). OCR-derived values get lower confidence and provenance noting OCR.
TASK 3: Gate OCR (PRF-03): only for image-only PDFs/images; configurable concurrency limit and per-run budget; call counts in
eval.md. No key/binary -> previous clean "unreadable" behaviour, never a crash.
TASK 4: Report reports/ocr_results.md: for every scanned/image document in the bundle - OCR ran?, text length, role
validation outcome, fields extracted, final outcome. Anything unreadable stays NEEDS_REVIEW/unreadable in the adapter.

GATES: tests for OCR success (mock), OCR unavailable, OCR garbage text -> UNRESOLVED not fabricated values; no regression in
Phase 5 semantics for non-scanned documents; make check PHASE=6A passes; make score PHASE=6A.

FINISH per docs/PHASE_PROTOCOL.md sections 7 and 8. Print the PHASE REPORT. STOP.

```

### PHASE 6B - OPTIONAL LLM hard-case resolvers

Run only if (a) ambiguous classification or (b) unresolved L2 comparisons or (c) hard extraction layouts materially remain
after Phase 6A. If you skip it, YOU must mark rows `EXT-05b` and `EXT-07` as `WAIVED` (only a human can).

```text
PHASE 6B - OPTIONAL LLM/VISION HARD-CASE RESOLVERS (FALLBACK ONLY)

READ FIRST: docs/PHASE_PROTOCOL.md; AGENTS.md; spec sections 8.4, 11.4, 15; AGENTS section 17; implement.md;
docs/requirements_matrix.md.
OWNS: EXT-05b, EXT-07 (and the LLM implementations behind CLS-04 / CMP-08).

Everything is fallback-only, behind the existing interfaces. Provider/keys from env (document in .env.example, never commit).
No key/provider -> degrade exactly to Phase 6A behaviour with a reason code.
1. LLM Stage-2 classifier: called ONLY when Stage 1/2 flag ambiguity. Input per spec 8.4 (subject, body, attachment metadata,
   Stage-1 candidates/scores, escalation reason, SI-field-block evidence, primary-action evidence). Output: exactly one of the
   five categories + confidence + reason_code + concise reason.
2. Extraction fallback: only for unresolved documents/fields; ONE request for all unresolved fields of a document.
3. L2 semantic comparison: only after L0 and L1 still differ AND equivalence is plausible; {equivalent, confidence, reason};
   uncertain -> UNRESOLVED.
4. Validate all model output against project-owned schemas (enums, numeric types, confidence 0..1, required keys); bounded
   repair/retry, then FAILED/BLOCKED. Cache by content hash + prompt version + model + purpose.
5. Config: max in-flight, max calls per run, timeout, retry limit; log calls by purpose.
6. Deterministic mock provider + record/replay fixtures. The whole automated suite must pass with no network and no key.
   Never put ground truth or anything from secrets/ into a prompt or fixture.

GATES: make check PHASE=6B passes with no key; malformed-output, timeout and budget-exhaustion tests pass; expensive calls
are a minority and reported by purpose; if no real key is available say NOT VERIFIED; if one is, record score/latency/call counts.
make score PHASE=6B if valid.

FINISH per docs/PHASE_PROTOCOL.md sections 7 and 8. Print the PHASE REPORT. STOP.

```

---

### PHASE 7 - Shared-backend API, live updates, continuous ingestion, demo

```text
PHASE 7 - SHARED BACKEND API + CONTINUOUS INGESTION + LIVE UPDATES + DEMO

READ FIRST: docs/PHASE_PROTOCOL.md; AGENTS.md; spec sections 4, 5, 18, 19, 23; AGENTS sections 4, 5; implement.md;
docs/requirements_matrix.md.
SCOPE: product-facing backend only. No UI, no Human Review.
OWNS: ING-01, ING-03, ING-04, ING-05, ING-08, ING-10, API-01..07, SEC-05.

TASK 1 - /api/v1 (API-01..05): GET /emails (filters status, category, received_from/to, has_mismatch), GET /emails/{id}
(metadata, classification, status, attachments, extraction, comparison), POST /sync/initial (job id + progress; dedupe; queue
only unprocessed), POST /ingestion/email (simulated/generic inbound with attachments), POST /emails/{id}/reprocess
(technical failures only). Keep old /api/* routes as aliases.
TASK 2 - Project-owned schemas (API-07): frontend-facing contracts independent of any provider/model shape. A true mismatch
shows SI and BL values side by side.
TASK 3 - Startup + continuous ingestion (ING-01, ING-03, ING-08): config flag to run the initial sync on startup; a polling
worker (default interval 60 s, configurable) with a persisted checkpoint and exponential backoff. It must not reprocess seen
emails or re-fetch their attachments. The organizer HTTP server has no "since" filter, so listing is unavoidable - document that
limitation and prove with a fake source that already-processed emails trigger no processing.
TASK 4 - Live updates (ING-05): SSE (or a documented polling-compatible event endpoint) publishing EMAIL_PROCESSING_UPDATED
with email_id, status, category, mismatch flag, updated_at, fed by ProcessingEvent.
TASK 5 - Shared state (ING-10): dashboard and future extension read the same case records; the backend processes emails
without the extension; no duplicated processing logic per frontend.
TASK 6 - Provider isolation (SEC-05): source adapters behind one interface. Add a MicrosoftGraphSource adapter skeleton behind
that interface with a contract test on a fake Graph payload; no credentials; never imported by the core pipeline.
TASK 7 - Exporter: CLI that exports the official submission JSON from persisted internal results and validates the shape.
TASK 8 - scripts/demo.sh (ING-04): from a clean start: initial sync (progressively populated) -> simulate NEW emails via
POST /api/v1/ingestion/email: normal SI/BL pair, XLSX pair, wrong document type, legitimate AWAITING_DOCUMENTS, scanned/image
case, spam -> assert the SSE event and the final API state for each. No "upload JSON and click Run".
TASK 9 - Docs: README run instructions, implement.md, .env.example, OpenAPI export, known limitations.

GATES: demo.sh passes from a clean start; API contract tests pass; legacy routes still work; make check PHASE=7 passes
(trace: rows owned by phases 0-7 PASS, except rows a human WAIVED); make score PHASE=7 does not regress.

FINISH per docs/PHASE_PROTOCOL.md sections 7 and 8. Print the PHASE REPORT. STOP.

```

---

### PHASE F - Final adversarial audit (fresh session)

```text
PHASE F - FINAL ADVERSARIAL AUDIT

READ FIRST: docs/PHASE_PROTOCOL.md; AGENTS.md; the entire spec; implement.md; docs/requirements_matrix.md.
Do not add features unless a release-blocking correctness/reliability defect is REPRODUCED first.
OWNS: SEC-04, SCP-02, SCP-06 and the independent verification of every row.

1. Matrix: run make check PHASE=F. Every row must be PASS or human-WAIVED. Verify docs/requirements_seed_ids.txt is a subset of
   the matrix IDs.
2. Independent re-verification: re-run every PASS row's evidence tests. Pick 15 rows across all categories and READ the test and
   the code to confirm the test actually asserts the requirement. For 5 of them do a mutation check: temporarily break the
   behaviour, confirm the test FAILS, then revert. Report any vacuous test and fix it.
3. AGENTS.md section 22: write one row per "MUST NOT" bullet into reports/final_audit.md: bullet | how verified
   (command/test/grep) | result.
4. AGENTS.md section 23: confirm each listed test category (ingestion, classification, attachment routing, extraction,
   comparison) has req-marked tests.
5. Prove with commands: no runtime/prompt/cache/fixture reads ground_truth.json, data_v2, secrets; no email_NNN-specific logic in
   src/; no hard-coded 520; exactly five final categories everywhere; SI is always the reference; NET WEIGHT never fills gross
   weight; missing data is never MATCH/MISMATCH; raw values preserved; container type never becomes a count mismatch.
6. Enum consistency: search every status/category/outcome enum; machine schemas and narrative docs must agree.
7. Security/config: no secrets committed; .env.example complete; dependencies documented; timeouts/retry limits configured;
   logs contain ids/diagnostics, not full document contents (SEC-04).
8. Documentation truth: implement.md matches actual routes, states, tests, metrics, limitations; list every UNVALIDATED /
   PROVISIONAL mapping still open.
9. Clean-run verification from a fresh clone: make check PHASE=F, scripts/demo.sh, the exporter validation. Paste the real
   output summary. Run make score once more only within the logged policy.
Write reports/final_audit.md. Update implement.md. Print the PHASE REPORT. STOP.

```

---

### PHASE R - Repair (when a gate fails or something regresses)

```text
PHASE R - TARGETED REPAIR

READ FIRST: docs/PHASE_PROTOCOL.md; AGENTS.md; implement.md; docs/requirements_matrix.md; the relevant spec sections.

Problem: <PASTE ONE failing gate / regression / PHASE REPORT excerpt / reproducible wrong behaviour / matrix row ID>

Rules: reproduce with a failing req-marked test FIRST; find the root cause; apply a GENERAL rule; no per-email or per-filename
hacks; do not weaken gates or delete valid tests; no private answers; no unrelated features.
Run make check-fast, then make check PHASE=<current phase>. Compare reports/latest/eval.md with the previous reports/history.csv
row. Use make score only if needed and within the logged limit.
Update implement.md (root cause, fix, regression checks, exact metrics). Print the PHASE REPORT. STOP.

```

---

## 4. Your 5-minute review after every phase

```bash
git diff --stat                                   # scope matches the phase?
cat reports/latest/eval.md | head -60             # numbers real?
tail -3 reports/history.csv                       # trend: accuracy proxy, p95, unresolved rate, FAILED
python scripts/trace_check.py --phase N --sample 5   # prints 5 random PASS rows with their evidence: open one and check it
grep -RInE "email_[0-9]+|ground_truth|data_v2" src backend scripts 2>/dev/null   # production code must be clean (tests may use fixture ids)

```

Then read the PHASE REPORT's **"Open decisions needing the human"** and **"Could NOT verify"** - those are the honest parts.
A score increase alone is not proof of correctness. Commit and tag only when the gate passed.
You can paste any PHASE REPORT back to Claude for a second opinion.

## 5. Decisions only you / the organizers can make

1. **AWAITING_DOCUMENTS -> official submission value.** The spec forbids guessing. Ask the organizers. Until then it is one UNVALIDATED config value.
2. **Mixed cases**: a confident MISMATCH on one field plus an UNRESOLVED field on another - reported as MISMATCH (PROVISIONAL). Confirm with the organizers if you can.
3. **MULTIPLE_CANDIDATES / readiness UNRESOLVED -> review_reason** (UNVALIDATED default `missing_value`).
4. **Port alias approvals** (`reports/port_aliases_review.md`) - you sign off every entry.
5. **Skip Phase 6B?** If yes, mark `EXT-05b` / `EXT-07` `WAIVED` yourself.
6. **Are image-only PDFs meant to be OCR-read or to be** **`unreadable`****?** Unknown; Phase 6A reports what OCR actually achieves.
7. The final judging data may differ from these 520 emails: rules must stay general, never fitted to the scoreboard.

## 6. If time is short

```text
MUST:      0, 1, 2, 3, 4, 6A, 7, F   and the targeted parts of 5 (idempotency, fault isolation, determinism)
OPTIONAL:  6B, the scale test in 5

```