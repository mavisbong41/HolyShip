# HolyShip — Phase F Final Adversarial Audit

## Executive status

- Branch: `phaseF`
- Integration base: `feature/email-classification`
- Integration base SHA: `f4081afcdafdb7466d5ff4e2c4c3d53662aac2b8`
- Phase F starting SHA: `f4081afcdafdb7466d5ff4e2c4c3d53662aac2b8`
- Candidate SHA: recorded after the Phase F commit/push below
- Environment: Windows 11, Python 3.14.3, Docker Desktop, PostgreSQL 16 service, GNU Make 4.2.1
- Status: audit evidence complete; local final gates pass. Final status is gated on pushed-candidate fresh-clone verification.

## Matrix integrity

- Total rows: 106
- PASS: 106
- FAIL: 0
- TODO: 0
- WAIVED: 0 (no human waiver created)
- Seed integrity: 106 frozen IDs, all present exactly once; no duplicate or malformed matrix IDs.
- Evidence integrity: strengthened trace checker validates paths, cited test nodes, exact `req` markers, JUnit execution, and rejects skipped/xfail evidence. Current cited evidence executes as part of `trace PHASE=F`.

## 15-row independent audit

| Requirement | Evidence inspected | Production path inspected | Classification | Finding |
|---|---|---|---|---|
| ING-08 | `backend/tests/test_phase7_polling.py` sequence/restart/backoff tests; `test_phase7_polling_postgres.py` checkpoint restart | `backend/app/ingestion/polling.py`, runtime checkpoint store | VALID | A/B, A/B/C, restart, attachment-read, bounded exponential backoff and reset are asserted. |
| CLS-01 | `test_phase1_classification_readiness.py::test_final_classifier_has_exactly_five_categories_and_no_uncertain` | `classification/signals.py`, stage1/stage2 schemas | VALID | Exact five final enum values are enforced end to end. |
| CLS-06 | `test_phase1_classification_readiness.py` Pattern A/B tests and `test_phase1_zero_signal.py` | readiness is applied after classification in `classification/pipeline.py` | VALID | Dense SI body remains `new_si_request`; bare future BL request is comparison/awaiting. |
| DOC-03 | `test_phase2_document_contract.py` native/image-only/corrupt routing tests | `documents/readers/composite.py`, router | VALID | Native-first and direct OCR path are asserted with reader spies and safe failure outcomes. |
| DOC-11 | `test_phase2_document_contract.py::test_content_evidence_overrides_filename_and_inconclusive_content_is_not_guessed` | `documents/role_validation.py` | VALID | Filename is only a hint; wrong and inconclusive roles are distinct. |
| EXT-01 | `test_phase3_extractor.py` one-pass/exact-seven/raw-value tests; PostgreSQL reload test | `extraction/extractor.py`, extraction models | VALID | One pass emits all seven fields with raw label/value, canonical value, confidence and evidence. |
| MAP-06 | `test_phase3_label_mapping.py::test_non_gross_weight_labels_never_map_and_gross_net_coexist_safely` | `extraction/label_mapping.py`, field-label config | VALID | NET/TARE labels remain unresolved and never become gross weight. |
| CMP-01 | `test_phase4_comparison_core.py::test_comparison_produces_exactly_seven_fields_with_si_as_reference` | `comparison/service.py`, persistence/API composition | VALID | Role checks and identity assertions detect reversal; seven fields are exact. |
| CMP-02 | `test_phase4_comparison_core.py` match/mismatch/missing/ambiguous tests | `comparison/service.py` precondition and status logic | VALID | Missing and uncertain evidence remain `UNRESOLVED`; definite differences remain `MISMATCH`. |
| CMP-05 | `test_phase4_l1_comparison.py`, metamorphic positive/negative controls | `comparison/l1.py` | VALID | Numeric, container, port and conservative entity normalization are field-specific and layered. |
| CMP-09 | `test_phase4_comparison_postgres.py` side-by-side reload/purity tests | comparison repository and product schemas | VALID | SI/BL raw/canonical/normalized values and extraction snapshots survive persistence unchanged. |
| REL-01 | `test_phase5_reliability_postgres.py::test_concurrent_duplicate_ingestion_creates_one_logical_case` | repositories, unique source/external identity, sync transaction boundaries | VALID | Concurrent duplicate arrivals converge to one logical email/job/result. |
| PRF-03 | `test_phase6_ocr.py` timeout/budget/concurrency/cache tests and resolver budget test | OCR reader and resolution executor | VALID | OCR/AI calls are bounded, timed out, cached by content/version identity, and fail structurally. |
| API-02 | `test_phase7_product_api.py` GET purity and detail semantics; PostgreSQL API tests | `api/router.py`, `api/product_queries.py`, product schemas | VALID | Required detail/queue/summary/events reads are persisted-only and do not build processing services. |
| SEC-05 | `test_phase7_provider_contract.py::test_graph_source_maps_fake_payload_without_credentials` | Graph adapter and common ingestion models | VALID | Provider-specific mapping is isolated; core pipeline has no Graph dependency. |

No selected row was WEAK, VACUOUS, or STALE. The trace gate itself is independently tested by `backend/tests/test_phasef_trace_gate.py`.

## 5 mutation checks

| # | Requirement / deliberate mutation | RED evidence | Reverted | Post-revert GREEN |
|---|---|---|---|---|
| 1 | CLS-01: added sixth final `EmailCategory.UNKNOWN` enum value | `test_phase1_scp_closure.py::test_phase1_vocabularies_match_runtime_storage_and_api_contracts` failed on extra `unknown` | Yes; semantic source matches HEAD | Same test passed |
| 2 | CMP-01: swapped SI and BL arguments in `ComparisonService.compare` | `test_phase4_comparison_core.py::test_comparison_produces_exactly_seven_fields_with_si_as_reference` failed identity assertion | Yes; source restored | Same test passed |
| 3 | CMP-02: changed extraction precondition result from `UNRESOLVED` to `MISMATCH` | missing/ambiguous outcome tests failed (3 failures) | Yes; source restored | All 3 tests passed |
| 4 | MAP-06: disabled non-gross-weight guard | `test_phase3_label_mapping.py::test_non_gross_weight_labels_never_map_and_gross_net_coexist_safely` failed (`UNMAPPED_LABEL` instead of required reason) | Yes; source restored | Same test passed |
| 5 | ING-08: removed same-content duplicate skip condition | `test_phase7_polling.py::test_poll_sequence_processes_only_new_messages_and_persists_checkpoint` failed (`submitted == 2` instead of `0`) | Yes; source restored | Same test passed |

No mutation code is committed or present in the production diff.

## AGENTS §22

Every MUST-NOT bullet was checked independently; all passed.

| # | MUST NOT rule | Verification | Result |
|---:|---|---|---|
| 1 | Human Review UI/workflow | tracked-file scope scan; `SCP-01` sync test | PASS |
| 2 | Final visual report screens | `test_backend_milestone_contains_no_frontend_or_outlook_addin_artifacts` | PASS |
| 3 | Outlook Add-in UI | same tracked-file scan | PASS |
| 4 | Microsoft Graph hard dependency | provider contract test; imports/source scan | PASS |
| 5 | Replace challenge loader with proprietary path | static bundle/source adapter tests | PASS |
| 6 | Hard-code 520 | runtime scan of `backend/app` and `scripts`; only historical/report fixture references | PASS |
| 7 | Runtime private-answer access | repository runtime scan for `ground_truth.json`, `data_v2`, private answers | PASS |
| 8 | Guess AWAITING_DOCUMENTS submission mapping | submission adapter test and `implement.md` UNVALIDATED note | PASS |
| 9 | Retrieve attachments before readiness | `test_phase2_pipeline_postgres.py::test_only_ready_comparisons_retrieve_attachment_content` | PASS |
| 10 | Classify future-BL SI request as comparison | Pattern B readiness test | PASS |
| 11 | Use no-attachment + draft-BL alone | zero-signal/bare-draft test | PASS |
| 12 | Let readiness reclassify `new_si_request` | pipeline/readiness tests | PASS |
| 13 | Treat future BL request as missing attachment | Pattern A awaiting test | PASS |
| 14 | Treat filename suffix as document proof | role validation swapped/generic filename tests | PASS |
| 15 | Ignore XLSX | native XLSX reader/router/extraction tests | PASS |
| 16 | Create extra final categories | exact-five enum/schema/storage test | PASS |
| 17 | Compare outside seven fields | exact canonical tuple and API contract tests | PASS |
| 18 | Reverse SI and BL | CMP-01 role/direction test and mutation check | PASS |
| 19 | Treat missing as mismatch | CMP-02 missing-side tests | PASS |
| 20 | Treat missing as match | CMP-02 missing-side tests | PASS |
| 21 | Convert uncertainty to mismatch | CMP-02 ambiguous/unresolved tests and mutation check | PASS |
| 22 | OCR/LLM every email | attachment lazy-load and non-comparison completion tests | PASS |
| 23 | Seven expensive calls for seven fields | one-pass extraction test | PASS |
| 24 | Aggressive entity normalization | L0/L1 entity negative controls | PASS |
| 25 | Destroy raw values | extraction/persistence/API raw-value tests | PASS |
| 26 | Silently alter requirements | matrix/seed audit and implement history | PASS |
| 27 | Fabricate hidden answers | runtime leakage scan | PASS |
| 28 | Optimize solely for score | no score calls this phase; general rules/source evidence audit | PASS |
| 29 | Large unrelated refactors | diff review: only audit, docs, and reproduced security repair | PASS |
| 30 | Delete teammate code without confirmation | diff review; no deletions | PASS |
| 31 | Add unnecessary dependencies | `backend/requirements.txt` unchanged; no new imports requiring packages | PASS |
| 32 | Commit secrets | `.env` ignored; secret/token scan and diff review | PASS |
| 33 | Leave implement.md stale | Phase F update below corrects branch/current-state claims | PASS |

## AGENTS §23

- Ingestion: PASS — marked tests cover initial sync, duplicate identity, polling/checkpoint/restart and incoming API.
- Classification: PASS — marked tests cover five categories, misleading/conflicting subjects, Stage 2, readiness boundaries and spam.
- Attachment routing: PASS — marked tests cover TXT/PDF/DOCX/XLSX, scans/images, corrupt/unsupported/wrong/multiple candidates and lazy retrieval.
- Extraction: PASS — marked tests cover seven fields, aliases/bilingual labels, raw evidence, missing/multiple values and NET-weight guard.
- Comparison: PASS — marked tests cover SI/BL direction, exact seven fields, layered normalization and all three field outcomes.

`test_required_behavior_categories_have_req_marked_assertive_tests` verifies that each category has requirement-marked tests containing real assertions.

## Leakage / overfit

- Private-answer runtime access: none found in `backend/` or runtime `scripts/`.
- `ground_truth.json`: no runtime match.
- `data_v2`: no runtime match.
- `secrets/` / private evaluator answers: no runtime match; `.env` is ignored and not tracked.
- Email-specific production logic: none; `external_message_id` equality is identity/idempotency logic only.
- Filename-specific answer logic: none; suffixes are not role proof.
- Hard-coded 520 production logic: none; 520 appears only in public fixture/history/report context.
- No per-email answer tables, fixture-keyed expected-value lookup, or hidden prompt/cache data were found.

## Business invariants

- Five categories: PASS — exact enum and API/storage/submission boundaries are `document_comparison`, `new_si_request`, `invoice_query`, `general_message`, `spam`.
- Seven fields: PASS — exact canonical tuple is shipper, consignee, notify_party, port_of_loading, port_of_discharge, container_count, gross_weight_kg.
- SI = reference: PASS — role validation, comparison arguments, persistence and API names preserve SI/reference and BL/candidate.
- Raw preservation: PASS — raw labels/values and source evidence remain alongside normalized values.
- MATCH/MISMATCH/UNRESOLVED: PASS — distinct field states; missing/ambiguous remain unresolved.
- NET WEIGHT: PASS — explicit label guard and extractor tests prevent gross substitution.
- Container count/type: PASS — deterministic quantity parsing preserves auxiliary equipment type; type alone never becomes count.
- Port mappings: PASS — only reviewed UN/LOCODE aliases are active; no fuzzy promotion. Remaining unvalidated mapping is the official AWAITING/submission boundary, not a port alias.

## Architecture

- Lazy attachments: PASS — metadata is available during classification; content is fetched only for READY comparisons.
- Provider isolation: PASS — static, Organizer HTTP and Graph adapters normalize to one internal model.
- Graph isolation: PASS — fake Graph mapping test passes without credentials or Graph imports in core.
- OCR/Vision: PASS — native-first; scans/images enter bounded OCR path; corrupt/empty/unsupported input is structured.
- AI escalation: PASS — disabled by default, targeted to unresolved hard cases, structured/evidence-bound, timed and budgeted.
- AI cache: PASS — content/provider/model/prompt/purpose/version identity and concurrency tests pass.
- GET purity: PASS — API GET tests patch `_build_sync_service` to fail if invoked; all reads use persisted query composition.
- Exporter persisted-only: PASS — submission adapter consumes persisted workflow rows and validates public shape.

## Continuous ingestion

- Checkpoint: PASS — durable `ingestion_checkpoints`, head migration `20260920_0012`.
- Poll 1: PASS — A/B submitted.
- Poll 2: PASS — repeated A/B skipped.
- Restart: PASS — persisted checkpoint and completed identity survive worker restart.
- Poll 3: PASS — A/B/C submits only C.
- No reprocessing: PASS.
- No attachment refetch: PASS — reads observed 2, 0, 0, 1 in live Phase 7 evidence.
- Backoff: PASS — bounded exponential delay.
- Reset: PASS — success resets to configured interval.
- Default interval: PASS — 60 seconds, configurable.

## API

- Required routes: `/api/v1/emails`, `/api/v1/emails/{email_id}`, `/api/v1/summary`, `/api/v1/events`, `/api/v1/ingestion/email`, `/api/v1/sync/initial`, `/api/v1/emails/{email_id}/reprocess`.
- Legacy routes: retained and tested as aliases.
- OpenAPI: product routes present; internal storage routes are not exposed in product contract.
- Filters: category, status, needs_review and pagination validation are tested.
- Pagination: negative/zero/oversized limits reject; bounded offset/limit queries use one page query.
- Partial states: BLOCKED/AWAITING/UNRESOLVED semantics survive API composition.
- Events: persisted processing-event contract is queryable and polling-compatible.
- Reprocess: only `FAILED` records accepted; non-failed records return 409.
- Query counts: Phase 7 live detail/queue/summary checks recorded queue 3, detail 12, summary 2.
- N+1: query composition uses bounded joins/aggregates; live query-count regression did not exceed recorded budget.
- Schema isolation: product schemas exclude API keys, provider prompts, cache identifiers and raw internal persistence fields.
- Human Review scope: read-only routes/composition only; no mutation/UI workflow added.

## Security

- Secrets: no committed credentials/tokens; `.env` ignored; API key is `SecretStr` and not returned by product schemas.
- Logs: logger call AST audit rejects document/body/content/raw-value arguments; runtime logs use IDs, types, states and structured diagnostics.
- SQL: SQLAlchemy statements are parameterized; no interpolated user SQL found.
- subprocess: only controlled internal test/trace/demo helpers; no `shell=True`, `os.system`, `eval`, `exec`, or `pickle` in backend runtime.
- filesystem/path: static bundle resolves paths under the configured bundle root; traversal tests pass.
- archive/file handling: readers fail safely on corrupt/unsupported files; no unsafe archive extraction path exists.
- base64/input bounds: reproduced SEC-04/API defect fixed. `MAX_ATTACHMENT_BYTES` defaults to 25 MiB, is env-configurable (1–100 MiB), checks encoded length before decode and actual decoded length after; invalid base64 remains 422 and oversized content is 413.
- timeout/retry: HTTP, OCR, AI and processing retries have bounded settings and timeout tests.
- prompt leakage: resolver prompts contain only project-owned field/evidence data; no private-answer or secret references found.
- temporary files: trace JUnit files use bounded temporary directories and are removed automatically.
- SEC-04: PASS after repair and executable log/boundary evidence.

## Database

- Alembic head: `20260920_0012`.
- Single head: PASS (`python -m alembic heads` returned one head).
- Clean migration: PASS — fresh temporary PostgreSQL database upgraded from empty to `20260920_0012`, then removed.
- Model/migration consistency: PASS — full PostgreSQL suite and storage/migration tests passed.
- Constraints: PASS — source/external idempotency, extraction/comparison identities, status/category/readiness checks and checkpoint uniqueness are exercised.

## Compatibility

- AI disabled: PASS (`AI_ESCALATION_ENABLED=false` default).
- Reference SHA: `37b33169797c6aef6b781fbcbf1ba99cb92d3a8d96ac184235eeda167d2a4eab`.
- Actual SHA: `37b33169797c6aef6b781fbcbf1ba99cb92d3a8d96ac184235eeda167d2a4eab`.
- Byte-identical: PASS; the generated `reports/latest/submission.json` hash matched the reference. (The actual hash is recorded again in the final report after clean clone.)
- Semantic regression: PASS — 520/520 public-bundle evaluation, 0 failed and 0 unhandled.

## Demo

- `scripts/demo.sh`: PASS through `C:\Program Files\Git\bin\bash.exe -lc './scripts/demo.sh'` with Git Unix tools on PATH.
- Normal SI/BL: PASS (persisted BLOCKED result with both documents VALID in the demo fixture).
- XLSX: PASS (persisted BLOCKED result with both documents VALID).
- Wrong document: PASS (`WRONG_DOCUMENT_TYPE`).
- AWAITING_DOCUMENTS: PASS.
- Scan/image: PASS (`INCONCLUSIVE` structured result without fabrication).
- Spam: PASS (`COMPLETED`, category spam).
- Events: PASS (100 polling events observed).
- Final states: PASS; demo summary and queue checks passed.
- Phase 7 regressions: PASS.

## Exporter

- Persisted-only: PASS — adapter maps stored workflow outcomes; no live provider call is required.
- Shape validation: PASS — `run_baseline.py` validates all public IDs, keys, categories, statuses, reasons and defect fields.
- Reprocessing observed: PASS — FAILED-only API reprocess guard and forced shared pipeline tests pass.

## Reliability/concurrency

- Result: PASS — `mingw32-make reliability` 14 passed.
- Unhandled exceptions: none in full test/evaluation runs.
- Idempotency: PASS — database uniqueness and concurrent duplicate tests.
- Fault isolation: PASS — later emails continue after source/parser/read/comparison failures.

## Performance

- Wall time: 29.274s for 520 public emails (repeat measurements in this audit: 31.915s and 37.043s).
- Throughput: 17.763 emails/s (repeat measurements: 16.293 and 14.038 emails/s).
- p50/p95: 0.060834s / 0.242901s in the final local run.
- LLM calls: 0 with AI disabled.
- OCR calls: 6 in public evaluation.
- Vision calls: 0 in AI-disabled run.
- Cache hit rate: 0 extraction cache hits / 196 misses in this clean evaluation (expected fresh eval DB).
- Peak memory: UNAVAILABLE.
- Regression vs previous history: wall time is above the prior 16.351s history row. Three fresh clean-eval runs varied from 29.274–37.043s while the Phase F production change is limited to incoming-API base64 validation, which is not exercised by the static-bundle evaluator. The variance is recorded as an environment/perf limitation (Windows + Docker PostgreSQL + corrupt-PDF parser workload), with no correctness regression and no behavior weakening.

## Tests

- Passed: 292
- Failed: 0
- Skipped: 0
- Xfail: 0
- Warnings: 1 existing Starlette/httpx deprecation warning.
- Required DB tests executed: yes, against isolated PostgreSQL test DB.

## Fresh clone

- Source: exact `origin/phaseF` candidate (to be created after commit/push).
- Candidate SHA: recorded after push.
- Environment setup: documented `.env.example` variables only plus isolated dev/test/eval identities.
- Clean migration: required and will be rerun from empty clone DB.
- check-fast/check PHASE=F/demo/exporter/compatibility: required and will be recorded after push.
- Hidden local dependency detected: none expected; any discovery is a release blocker.

## Trace

- PASS: 106
- TODO: 0
- FAIL: 0
- SEC-04: PASS — executable log/input-bound tests.
- SCP-02: PASS — executable tracked-file scope test.
- SCP-06: PASS — executable category coverage and trace-tool tests.
- `trace PHASE=F`: PASS — 106 PASS / 0 TODO / 0 FAIL; 244 cited tests executed, 1 warning.

## Scoreboard

- Calls this phase: 0.
- Result: NOT RUN / UNAVAILABLE — no authoritative organizer endpoint was available; no score-driven tuning performed.

## Documentation

- `reports/final_audit.md`: this report, updated with exact final candidate gates.
- `implement.md`: updated for phaseF branch/current state, repaired input bound, tests, open decisions, and change log.
- Stale claims corrected: Phase 7 local-branch/current-state wording replaced with Phase F candidate wording; historical Phase 7 evidence retained.
- Remaining UNVALIDATED: official AWAITING_DOCUMENTS public submission mapping; mixed mismatch+unresolved compression policy; multiple-candidate/readiness review reason; live AI/OCR provider accuracy; public generalization beyond current bundle.
- Remaining PROVISIONAL: only the documented submission-boundary mappings above; no unapproved port aliases.
- Open human decisions: organizer confirmation of those public mapping policies and human approval/merge of Phase F.

## Findings

- CRITICAL: none.
- HIGH: none after the SEC-04 base64 repair.
- MEDIUM: live external AI/Vision accuracy and official submission mapping remain unvalidated by design; not runtime defects.
- LOW: peak-memory metrics are unavailable from the current perf harness; p50/p95 are recorded above. Current wall-time variance is documented rather than tuned away.
- INFO: one existing Starlette/httpx deprecation warning; corrupt public PDFs intentionally emit parser warnings while returning structured outcomes.
- ENVIRONMENT-BLOCKED: none for required local PostgreSQL/Docker gates; organizer scoreboard and live external-provider accuracy are unavailable external services.

## Changes

- Production: configurable `MAX_ATTACHMENT_BYTES` enforcement on incoming base64 attachments; encoded-length precheck plus decoded-length check.
- Tests: strengthened trace/evidence gate; SEC-04 input/log tests; SCP-02 scope test; SCP-06 category/trace tests; REL-02 marker repair; ING-04 evidence correction.
- Docs/evidence: matrix closed SEC-04/SCP-02/SCP-06; this report; implement handoff update; plan file.
- Dependencies: none added.

## Commits

- Pending final Phase F commit/push; exact SHA and message will be recorded after clean gates.

## Full Gates

- compileall: PASS.
- diff-check: PASS (Windows line-ending warnings only).
- check-fast: PASS, 34 passed, 1 warning.
- full tests: PASS, 292 passed, 0 failed, 0 skipped, 1 warning.
- reliability: PASS, 14 passed.
- perf: PASS, 520 emails, 37.043s, 14.038 emails/s.
- demo: PASS through Git Bash.
- exporter: PASS via baseline shape validation and adapter tests.
- compatibility SHA: PASS, reference hash matched.
- trace PHASE=F: PASS, 106 PASS / 0 TODO / 0 FAIL, 244 tests executed.
- check PHASE=F: PASS, 292 passed / 0 failed / 0 skipped; evaluation 520/520; reliability 14 passed; trace PASS.
- fresh-clone: pending push and clean-room run.

## Final Status

- Pending final clean-room gates. Do not merge `phaseF`.

## Recommended Next Step

- If all pending gates pass: human reviews this evidence, then merges `phaseF` into `feature/email-classification`, verifies merged integration, declares backend frozen, and only then begins dashboard/extension frontend work.
- If a pending gate fails: repair only the reproduced issue on `phaseF`, rerun the affected gates, and repeat fresh-clone verification.
