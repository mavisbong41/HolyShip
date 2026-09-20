# Phase F Final Adversarial Audit Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Independently verify the integrated backend, close the three Phase F-owned requirements with executable evidence, and produce a pushed, clean-room-verified backend freeze candidate or an exact blocker report.

**Architecture:** Treat Phase F as an evidence-first audit. Production code changes are forbidden unless a release-blocking defect is reproduced, captured by a failing requirement-marked regression test, and repaired with the smallest general fix. Audit evidence lives in `reports/final_audit.md`; requirement status changes stay limited to the three Phase F rows; teammate state is updated in `implement.md`.

**Tech Stack:** Python 3, pytest, FastAPI, SQLAlchemy, Alembic, PostgreSQL 16 via Docker Compose, PowerShell/Git Bash, Git.

## Global Constraints

- Work only on branch `phaseF`, based on verified `feature/email-classification` commit `f4081afcdafdb7466d5ff4e2c4c3d53662aac2b8`.
- Do not merge, force-push, add frontend work, extend Human Review actions, call private evaluator data, or tune from hidden answers.
- Use isolated `holyship_dev`, `holyship_test`, and `holyship_eval` PostgreSQL databases; run the repository isolation guard before destructive test/eval work.
- Maximum six repair iterations for one failing phase gate.
- Do not call the scoreboard unless the configured organizer endpoint exists and the logged Phase F budget permits it.
- Do not commit temporary mutation code.

---

### Task 1: Establish the executable baseline

**Files:**
- Inspect: `backend/requirements.txt`
- Inspect: `scripts/database_isolation.py`
- Inspect: `.env`

- [ ] **Step 1: Verify Docker, Compose, PostgreSQL health, database identities, Python, and Make availability.**

Run: `docker --version`, `docker compose version`, `docker info`, `docker compose ps`, `python --version`, `mingw32-make --version`.

- [ ] **Step 2: Run non-destructive baseline checks.**

Run: `python -m compileall -q backend/app backend/tests scripts`, `git diff --check`, and `mingw32-make check-fast`.

- [ ] **Step 3: Record exact baseline results for the final report.**

Expected: every command and exit status is captured; any failure is investigated before later audit claims.

### Task 2: Verify matrix and every existing PASS evidence reference

**Files:**
- Inspect/modify only statuses and evidence: `docs/requirements_matrix.md`
- Inspect: `docs/requirements_seed_ids.txt`
- Inspect: `scripts/trace_phase0.py`
- Create/modify: `reports/final_audit.md`

- [ ] **Step 1: Programmatically parse matrix rows and validate unique IDs, allowed statuses, seed inclusion, evidence paths, pytest nodes, and `@pytest.mark.req` markers.**

- [ ] **Step 2: Execute every PASS row's executable evidence, ensuring no required test skips.**

- [ ] **Step 3: Audit the trace checker against missing evidence, missing markers, missing seeds, and skipped required tests.**

- [ ] **Step 4: Record matrix totals and evidence-integrity results in `reports/final_audit.md`.**

### Task 3: Perform the independent deep audit and mutation analysis

**Files:**
- Inspect: selected production files under `backend/app/`
- Inspect/strengthen only when necessary: selected files under `backend/tests/`
- Modify: `reports/final_audit.md`

- [ ] **Step 1: Select at least 15 difficult rows spanning ingestion, classification, readiness, document routing, role validation, extraction, mapping, comparison, persistence, reliability, OCR/AI, continuous ingestion, API, security, and scope.**

- [ ] **Step 2: For each row, read the requirement, test, fixture/mocks, and production path; classify evidence as VALID, WEAK, VACUOUS, or STALE.**

- [ ] **Step 3: Perform five reversible production mutations, run the targeted evidence to prove RED, restore immediately, and rerun to prove GREEN.**

- [ ] **Step 4: If a mutation test stays green, add the smallest requirement-marked test, demonstrate RED/GREEN, then rerun `mingw32-make check-fast`.**

### Task 4: Complete the static adversarial audits

**Files:**
- Inspect: all tracked source/config/tests/docs
- Modify: `reports/final_audit.md`

- [ ] **Step 1: Add one evidence row for every AGENTS §22 MUST-NOT bullet and one category-evidence section for AGENTS §23.**

- [ ] **Step 2: Audit private-data access, per-email/per-filename rules, hard-coded `520`, secrets, logging, SQL construction, subprocess use, filesystem/archive handling, input bounds, timeouts, retries, prompt leakage, dependencies, and configuration.**

- [ ] **Step 3: Audit exact five categories, exact seven fields, SI-reference direction, raw preservation, three comparison states, NET-weight exclusion, container type/count separation, ports, lazy attachment loading, provider isolation, GET purity, exporter persistence-only behavior, Human Review scope, and enum consistency.**

- [ ] **Step 4: Audit all `UNVALIDATED`, `PROVISIONAL`, `TODO`, `FIXME`, `TBD`, and human-decision text and classify each item truthfully.**

### Task 5: Exercise service-backed behavior and failure boundaries

**Files:**
- Inspect: migrations, API, ingestion, resolver/OCR, persistence, and error-handling code/tests
- Modify: `reports/final_audit.md`

- [ ] **Step 1: Verify one Alembic head and perform a clean migration against the isolated development database.**

- [ ] **Step 2: Exercise required failure cases, concurrency/idempotency, checkpoint restart, polling backoff/reset, API filters/pagination/events/reprocess, query counts/N+1 protection, and deterministic AI-disabled behavior through existing tests and scripts.**

- [ ] **Step 3: Run metamorphic and synthetic single-field defect evidence and enumerate all skip/xfail outcomes.**

- [ ] **Step 4: Run `scripts/demo.sh`, exporter validation, and compare the AI-disabled submission SHA-256 to `37b33169797c6aef6b781fbcbf1ba99cb92d3a8d96ac184235eeda167d2a4eab`.**

### Task 6: Close Phase F evidence and documentation

**Files:**
- Modify: `reports/final_audit.md`
- Modify: `docs/requirements_matrix.md`
- Modify: `implement.md`

- [ ] **Step 1: Complete `reports/final_audit.md` with every mandatory section, exact commands/results, findings, and open human decisions.**

- [ ] **Step 2: Set `SEC-04`, `SCP-02`, and `SCP-06` to PASS only after their audit evidence exists.**

- [ ] **Step 3: Correct stale current-branch claims in `implement.md`, preserve historical Phase 7 evidence, and record only executed validation.**

- [ ] **Step 4: Run `git diff --check`, inspect `git diff --stat`, and verify no temporary mutation remains.**

### Task 7: Run all local Phase F gates and publish the candidate

**Files:**
- Generated reports under `reports/latest/`
- Updated audit/docs evidence from Task 6

- [ ] **Step 1: Run `mingw32-make reliability`, `mingw32-make perf`, the full PostgreSQL test suite, `mingw32-make trace PHASE=F`, and `mingw32-make check PHASE=F`.**

- [ ] **Step 2: If production code changed, rerun every regression command mandated by the Phase F brief, including demo, exporter, and compatibility SHA.**

- [ ] **Step 3: Commit coherent Phase F evidence changes on `phaseF` after fresh verification.**

- [ ] **Step 4: Push only `phaseF` to `origin/phaseF`; do not merge.**

### Task 8: Fresh-clone verification and final parity

**Files:**
- Fresh checkout of exact `origin/phaseF`
- Final updates to `reports/final_audit.md` and `implement.md` if clean-room evidence changes the result

- [ ] **Step 1: Create a separate fresh clone/check-out of exact `origin/phaseF` outside the working repository and configure only documented environment variables.**

- [ ] **Step 2: Perform clean migration, `mingw32-make check-fast`, `mingw32-make check PHASE=F`, `scripts/demo.sh`, exporter validation, and compatibility SHA verification.**

- [ ] **Step 3: If clean-room verification changes evidence, return to `phaseF`, update reports, recommit/push, and rerun the affected clean-room gates.**

- [ ] **Step 4: Verify branch `phaseF`, clean worktree, `HEAD == origin/phaseF`, and merge-base equals the integration base; print the required Phase F report and stop.**
