# Phase 6 Targeted Hard-Case AI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bounded, auditable fallback layer that resolves supported OCR, extraction, and semantic-comparison hard cases without changing the deterministic path or inventing missing evidence.

**Architecture:** Extend the existing reader, extraction, comparison, reliability, cache, and persistence boundaries. A project-owned resolver executor validates structured provider output and persists versioned cache/audit records; accepted extraction values are non-destructive overlays and semantic decisions are limited to unresolved L2 comparisons.

**Tech Stack:** Python 3.14, dataclasses/Pydantic settings, SQLAlchemy 2, PostgreSQL, Alembic, pytest, existing retry/timeout helpers.

## Global Constraints

- AI escalation is disabled by default.
- Compare exactly the existing seven canonical fields; SI remains the reference.
- Never invoke AI for definite deterministic matches or mismatches.
- Never infer a value when source evidence is absent.
- Preserve all deterministic raw extraction rows and Phase 5 behavior.
- Automated tests use deterministic fakes only; no live network or credentials.
- Work only on Phase 6; do not add Phase 7 APIs or Human Review UI.

---

### Task 1: Close inherited traceability bookkeeping and freeze the baseline

**Files:**
- Modify: `docs/requirements_matrix.md`
- Create: `reports/phase6_hard_cases.md`

**Interfaces:**
- Consumes: existing req-marked Phase 5 tests and Phase 5 reports.
- Produces: a truthful Phase 5 trace gate and a permitted-data hard-case taxonomy.

- [ ] **Step 1: Verify each stale Phase 5 row has executable evidence**

Run targeted `pytest --collect-only` and inspect req markers for `ING-02`, `PRF-02`, `PRF-04`, `REL-01`, `REL-02`, `REL-03`, `REL-05`, and `REL-06`.

- [ ] **Step 2: Update only Status/Evidence/Notes for proven rows**

Set a row to `PASS` only when an existing passing test carries its requirement marker; otherwise add a focused evidence test first.

- [ ] **Step 3: Verify inherited trace and baseline**

Run `mingw32-make trace PHASE=5` and record the clean submission SHA-256, distributions, unresolved counts, provider calls, and performance.

### Task 2: Resolver contracts, validation, budgets, and cache

**Files:**
- Create: `backend/app/resolution/models.py`
- Create: `backend/app/resolution/service.py`
- Create: `backend/app/resolution/providers.py`
- Create: `backend/app/resolution/__init__.py`
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`
- Test: `backend/tests/test_phase6_resolver.py`

**Interfaces:**
- Produces: `HardCaseResolver`, extraction/semantic request and result dataclasses, `ResolutionExecutor.resolve_extraction()`, `ResolutionExecutor.resolve_semantic()`, metrics, and stable cache keys.

- [ ] **Step 1: Write failing contract tests**

Cover valid high confidence, low confidence, missing evidence without a call, contradictory extraction, malformed response, timeout, transient retry, retry exhaustion, unsupported field, invalid numeric/unit output, budget exhaustion, cached repeat, concurrent single-flight, and resolver-version invalidation.

- [ ] **Step 2: Run focused tests and confirm RED**

Run `python -m pytest backend/tests/test_phase6_resolver.py -vv` and confirm failure because the resolution package does not exist.

- [ ] **Step 3: Implement the smallest structured resolver boundary**

Use existing `retry_call` and `run_with_timeout`; validate confidence, evidence anchoring, field types, units, contradictions, budget, and result schema. Keep provider code behind a protocol and expose deterministic fake support only in tests.

- [ ] **Step 4: Run focused tests GREEN**

Run `python -m pytest backend/tests/test_phase6_resolver.py -vv`.

### Task 3: Add additive resolver persistence and concurrency-safe cache

**Files:**
- Modify: `backend/app/storage/models.py`
- Modify: `backend/app/storage/repositories.py`
- Create: `backend/alembic/versions/20260920_0011_phase6_ai_resolution_cache.py`
- Test: `backend/tests/test_phase6_resolution_postgres.py`

**Interfaces:**
- Produces: `AIResolutionRecord` and `AIResolutionRepository.get()/store()` keyed by the complete stable request identity.

- [ ] **Step 1: Write failing PostgreSQL tests**

Assert accepted/rejected metadata persistence, one row under concurrent duplicate insertion, cache reuse, resolver/prompt version invalidation, rollback isolation, and clean migration constraints/indexes.

- [ ] **Step 2: Confirm RED**

Run `python -m pytest backend/tests/test_phase6_resolution_postgres.py -vv`.

- [ ] **Step 3: Implement model, repository, and migration**

Use one additive table with a unique request hash, explicit purpose/field/config dimensions, structured request/response JSON, decision, confidence, validation reason, source identities, provider-call count, and timestamps. Recover insertion races with a savepoint and re-fetch.

- [ ] **Step 4: Run migration and focused tests GREEN**

Run Alembic upgrade against the isolated dev database and the focused PostgreSQL suite.

### Task 4: Integrate non-destructive extraction overlays and semantic L2

**Files:**
- Create: `backend/app/resolution/integration.py`
- Modify: `backend/app/comparison/service.py`
- Modify: `backend/app/comparison/persistence.py`
- Modify: `backend/app/storage/repositories.py`
- Modify: `backend/app/documents/materialization.py`
- Modify: `backend/app/sync/service.py`
- Test: `backend/tests/test_phase6_pipeline_postgres.py`

**Interfaces:**
- Consumes: persisted Phase 3 extraction rows and the resolver executor.
- Produces: AI-assisted comparison rows with original extraction foreign keys plus audited overlay evidence.

- [ ] **Step 1: Write failing pipeline tests**

Cover extraction recovery from explicit evidence, missing evidence remaining unresolved without a call, semantic party/port assistance, definite mismatches bypassing AI, conflicting candidates remaining unresolved, pounds-to-kilograms rejection, provider failure isolation, and AI-disabled compatibility.

- [ ] **Step 2: Confirm RED**

Run `python -m pytest backend/tests/test_phase6_pipeline_postgres.py -vv`.

- [ ] **Step 3: Implement overlay and L2 integration**

Decorate only unresolved/ambiguous fields with accepted proposals, never mutate `extracted_fields`, persist comparison values/evidence from the decorated domain objects, and use an AI-specific comparison version only when enabled.

- [ ] **Step 4: Run focused and Phase 4 regression tests GREEN**

Run the Phase 6 pipeline suite plus Phase 3/4 extraction/comparison suites.

### Task 5: Bound OCR and prove same-pipeline behavior

**Files:**
- Modify: `backend/app/documents/readers/ocr_reader.py`
- Modify: `backend/app/documents/readers/composite.py`
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`
- Test: `backend/tests/test_phase6_ocr.py`

**Interfaces:**
- Produces: injectable OCR engine support, thread-safe call budget/concurrency, and OCR `UnifiedDocument` output consumed by the existing role validator and deterministic extractor.

- [ ] **Step 1: Write failing OCR tests**

Cover mock OCR success through role validation/extraction, unavailable backend, garbage text remaining unresolved, timeout/failure isolation, and budget exhaustion without Vision/LLM fabrication.

- [ ] **Step 2: Confirm RED and implement bounded OCR**

Reuse the current native-first routing and add only the injection/budget/concurrency behavior required by tests.

- [ ] **Step 3: Run focused OCR/document regression tests GREEN**

Run the Phase 6 OCR suite and existing document reader/materialization suites.

### Task 6: Metrics, fixture evaluation, reports, and documentation

**Files:**
- Modify: `backend/app/sync/service.py`
- Modify: `scripts/run_baseline.py`
- Create: `scripts/run_phase6_hard_cases.py`
- Modify: `Makefile`
- Modify: `reports/phase6_hard_cases.md`
- Create: `reports/phase6_ai_evaluation.md`
- Modify: `reports/latest/eval.md`
- Modify: `reports/latest/eval.json`
- Modify: `reports/history.csv`
- Modify: `docs/requirements_matrix.md`
- Modify: `implement.md`

**Interfaces:**
- Produces: resolver metrics by purpose and deterministic fixture-backed enabled evaluation; preserves normal eval output when disabled.

- [ ] **Step 1: Add failing metric/evaluation tests where needed**

Assert call, acceptance, rejection, cache, failure, malformed, and per-case averages are truthful and zero when disabled.

- [ ] **Step 2: Implement metrics and targeted evaluation**

The evaluator must use only synthetic/public evidence and explicitly distinguish fixture-backed behavior from live-provider verification.

- [ ] **Step 3: Update traceability and handoff documents**

Mark Phase 6 rows only with passing req-marked evidence, record migration/config/interfaces, measured results, limitations, and live-provider status.

### Task 7: Full verification, review, commit, and push

**Files:** all changed files.

**Interfaces:**
- Produces: verified `origin/phase6` branch with no merge.

- [ ] **Step 1: Run focused Phase 6 suites**

Run all new resolver, OCR, pipeline, and PostgreSQL tests with the isolated test database.

- [ ] **Step 2: Verify AI-disabled compatibility**

Run clean evaluation with AI disabled and compare the submission SHA-256 to `37b33169797c6aef6b781fbcbf1ba99cb92d3a8d96ac184235eeda167d2a4eab`.

- [ ] **Step 3: Run phase gates**

Run `git diff --check`, `mingw32-make check-fast`, and `mingw32-make check PHASE=6B`. Do not weaken gates.

- [ ] **Step 4: Run leakage/security scans and inspect every production diff**

Search runtime code for private data, per-email answers, secrets, hard-coded bundle size, unbounded retries/concurrency, and fixture leakage.

- [ ] **Step 5: Request focused code review and fix Critical/Important findings**

Review against this plan, the Phase 6 brief, and the base/final SHAs; rerun affected tests.

- [ ] **Step 6: Commit and push**

Create a small number of meaningful commits, push `phase6`, verify a clean worktree, and confirm local/remote HEAD match. Do not merge.
