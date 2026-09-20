# PHASE PROTOCOL

> Put this file at `docs/PHASE_PROTOCOL.md`.
> It is deliberately NOT appended to AGENTS.md: AGENTS.md is already ~30 KB and Codex's default
> instruction budget is 32 KiB, so anything appended to it can be silently truncated.
> Every phase prompt tells Codex to read this file explicitly.

Applies whenever the user sends a `PHASE <N>` prompt.

---

## 1. Authority order (what wins when documents disagree)

1. Public challenge contract: participant bundle `README.md`, `sample_submission.json`, `loader.py`
2. `backend_requirements_ingestion_to_compare.md` (the "spec")
3. `AGENTS.md`
4. This protocol, then the phase prompt
5. `implement.md`, then existing code

Rules:

- If a phase prompt disagrees with 1-3, follow 1-3 and list the discrepancy under "Spec conflicts" in the PHASE REPORT.
- If 1-3 disagree with each other, do NOT silently choose. Take the most conservative behaviour (never fabricate a decision), log it in implement.md under "Blocked / Open Questions", and continue.
- Do not invent behaviour the spec does not define. Put it in "Blocked / Open Questions" and make it a single configurable value marked `UNVALIDATED`.

## 2. Requirement traceability (how "follow the requirements" is enforced)

`docs/requirements_matrix.md` is the master list of requirements (ID, source section, owner phase, how to verify).

- Never delete or reword a seed row. You may ADD rows. You may only edit the Status, Evidence and Notes columns (and Phase only by splitting a row, e.g. `DOC-07` -> `DOC-07a`, `DOC-07b`, with a note).
- Status values: `TODO`, `PASS`, `FAIL`. `WAIVED` may be set ONLY by the human. Never set it yourself.
- `PASS` requires executable evidence: a test node id (`tests/...::test_name`) that carries `@pytest.mark.req("<ID>")` and passed in the latest run, or, for audit-type rows, an existing report path. Prose such as "implemented" is not evidence.
- `make trace PHASE=<N>` must fail if any row whose owner phase <= N is not PASS/WAIVED, if a cited test does not exist / does not carry the marker / did not pass, or if a seed ID is missing (compare with `docs/requirements_seed_ids.txt`).
- If a row cannot be made PASS within the phase: set `FAIL`, write the blocker in Notes, STOP and report it. Do not weaken the row.

Phase order for "owner phase <= N": `0, 1, 2, 3, 4, 5, 6A, 6B, 7, F`.

## 3. Work loop

1. Read the files the phase prompt lists, in that order. Inspect existing code before deciding anything.
2. Implement only the phase scope. Do not start the next phase. No unrelated refactors. Reuse the existing stack.
3. Inner loop: `make check-fast` after each change. Gate loop: `make check PHASE=<N>` (full).
4. Max 6 fix iterations per failing gate. Then STOP, write the blocker in implement.md, report it.
5. Never weaken a gate, delete or loosen a valid test, or special-case data to pass. Do not change an existing test's expected value unless the requirement changed; explain why in implement.md.
6. Smallest coherent change. Preserve backward compatibility unless the spec requires a break (then write a migration).

## 4. Evidence rules for accuracy

Allowed sources of accuracy evidence, in priority order:

1. deterministic unit tests
2. metamorphic tests (format-only perturbations must not change the result; injected single-field defects must be detected)
3. synthetic single-field defect tests
4. your own reading of the permitted input emails/documents (fixed-seed samples, written up in reports/)
5. the public `POST /submit` aggregate scoreboard

Forbidden:

- reading `ground_truth.json`, anything under `data_v2/`, `secrets/`, or any private evaluator answer
- per-`email_id` or per-filename rules, lookup tables of expected answers, hard-coded `520`
- putting any of the above into prompts, caches, dictionaries or fixtures
- adding a rule whose only justification is "it raised the score"

Every rule you add must be a general rule justified by input evidence, and recorded in implement.md.

## 5. Public score policy

- Use only `make score PHASE=<N>` at the end of a phase; max 2 calls per phase (Phase 0: 1).
- Log every call in `reports/score_history.jsonl`; save the aggregate response in `reports/latest/scoreboard.json`.
- The scoreboard is aggregate self-evaluation, not a per-email oracle. Do not run A/B mapping experiments against it unless the human explicitly asks.

## 6. Reliability and performance rules

- Every new code path survives missing/empty/corrupt input, timeouts and duplicate ingestion.
- Failures are isolated per email and persisted with a machine-readable reason code. No unbounded retries.
- `FAILED` = technical failure. `BLOCKED` = cannot safely continue. `AWAITING_DOCUMENTS` = legitimate waiting state. Never overload one status for unrelated meanings.
- `reports/latest/eval.md` records wall time, per-email p50/p95 per stage, LLM/OCR/Vision call counts, cache-hit rate, and peak memory where practical. A >20% regression vs the previous `reports/history.csv` row needs an explanation.
- Performance comes from avoiding unnecessary work, never from weakening correctness.

## 7. implement.md protocol (AGENTS.md section 25)

Before finishing every phase:

- keep all required sections: Project Snapshot, Current Milestone, Current Status, Architecture / Flow, Implemented, In Progress, Next, Blocked / Open Questions, Key Decisions, API / Data Contract Changes, Configuration / Environment, Tests & Validation, Known Limitations, Recent Change Log
- update `Last updated`, move finished items, record decisions, endpoint/schema/config changes
- record ONLY tests/commands you actually ran, with real results; never claim a pass you did not observe
- add one Recent Change Log entry: Changed / Why / Files / Validation / Next
- document each new dependency and why it was needed; update `.env.example` for every new env var

## 8. PHASE REPORT (print at the end, then STOP)

```text
PHASE REPORT - Phase <N>

Scope
- Done:
- Not done:

Requirements (docs/requirements_matrix.md)
- Rows owned by this phase: PASS x / FAIL y / TODO z
- Rows owned by earlier phases still PASS: yes/no
- Rows added / split:
- make trace PHASE=<N>: PASS/FAIL

Gates
- make check-fast:
- make check PHASE=<N>:
- make score PHASE=<N>:
- Phase-specific gates:

Accuracy
- Public self-eval metrics:
- Metamorphic / synthetic results:
- Unresolved / low-confidence rate:
- Failure patterns observed:

Reliability
- Unhandled exceptions:
- FAILED / BLOCKED (by reason code):
- Duplicate / idempotency issues:

Performance
- Full-run wall time / throughput:
- p50 / p95 by stage:
- LLM / OCR / Vision calls:
- Cache hit rate / peak memory:

Files changed:
New dependencies (+ reason):
Spec conflicts found:
Open decisions needing the human:
Could NOT verify:
implement.md updated: YES/NO
Recommended next step:

```

After printing the report: STOP. Do not begin the next phase.
