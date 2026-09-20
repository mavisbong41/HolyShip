# Phase 6 AI evaluation

## Status

**IMPLEMENTED — LIVE PROVIDER VERIFICATION INCOMPLETE**

The provider-independent resolver, validation, cache/audit persistence, pipeline integration, and OCR boundary are implemented and verified with deterministic fakes. No live AI credentials were available and no live-model accuracy is claimed.

## Phase 5 baseline and hard-case audit

| Metric | Phase 5-compatible baseline |
| --- | ---: |
| Total emails | 520 |
| Categories | BL_COMPARISON 203; SI_REQUEST 141; INVOICE_QUERY 84; GENERAL 66; SPAM 26 |
| Public statuses | OK 317; NEEDS_REVIEW 203; MISMATCH 0 |
| Persisted comparisons | 98 |
| Blocked comparisons | 98 |
| L2 semantic unresolved fields | 29 |
| Explicit unresolved extraction formats | 1 |
| OCR-routed documents | 6 |
| Provider calls | 0 |

The 29 semantic fields were shipper 3, consignee 3, notify party 5, port of loading 6, and port of discharge 12. Missing values, missing attachments, corrupt/unreadable inputs, and wrong document types are intentionally excluded from AI resolution.

## Mode A — AI-disabled compatibility

The final clean evaluation ran with `AI_ESCALATION_ENABLED=false` against the dedicated evaluation database and a clean migration chain through `20260920_0011`.

| Metric | Result |
| --- | ---: |
| Total emails | 520 |
| FAILED | 0 |
| Unhandled exceptions | 0 |
| Reader calls | 216 |
| Extractor calls | 196 |
| OCR calls | 6 |
| Vision calls | 0 |
| Resolver/LLM calls | 0 |
| Submission SHA-256 | `37b33169797c6aef6b781fbcbf1ba99cb92d3a8d96ac184235eeda167d2a4eab` |
| Phase 5 SHA-256 | `37b33169797c6aef6b781fbcbf1ba99cb92d3a8d96ac184235eeda167d2a4eab` |
| Byte-identical | YES |

No semantic drift was observed. Public statuses remained OK 317 / NEEDS_REVIEW 203 / MISMATCH 0.

## Mode B — deterministic fixture hard cases

Command: `python scripts/run_phase6_hard_cases.py`

| Metric | Result |
| --- | ---: |
| Hard cases attempted | 5 |
| Actually escalated cases | 4 |
| Provider calls | 4 |
| Accepted | 2 |
| Rejected provider results | 2 |
| Missing-evidence zero-call rejection | 1 |
| Remaining unresolved | 3 |
| Cache hits | 1 |
| Provider failures | 0 |
| Malformed responses | 0 |
| Average calls per escalated case | 1.0 |

Accepted fixtures were an evidence-anchored port extraction and a high-confidence party-name semantic equivalence. Low confidence, absent evidence, and a pounds-as-kilograms proposal remained unresolved. The repeat port request was served from cache.

This fixture suite proves routing and safety behavior, not statistical model accuracy. The public 29 semantic / 1 extraction hard cases were not sent to a live or fabricated model, so their enabled-mode before/after correctness and review reduction are **NOT VERIFIED**.

## Persistence and concurrency

- Alembic head: `20260920_0011`.
- Downgrade `0011 -> 0010` and upgrade `0010 -> 0011`: PASS.
- PostgreSQL resolver persistence, round-trip metadata, version coexistence, and concurrent duplicate insertion: PASS.
- Configured runtime reachability through `Settings -> provider factory -> SyncService -> eligible unresolved field -> validated result`: PASS with a deterministic fake provider.
- AI-disabled runtime constructs no provider and preserves the deterministic Phase 5 path: PASS.
- In-process duplicate escalation single-flight across separate database-session executors, including batched extraction: PASS.
- Cache identity covers content/evidence, role, field, purpose, provider, model, resolver version, and prompt schema version; provider/model/version changes invalidate reuse: PASS.
- Resolver and OCR concurrency/budgets are shared across the actual in-process multi-session worker pool: PASS.
- Cross-process provider-call single-flight is not implemented. Database uniqueness preserves idempotent persisted results, but two independent processes may both call the provider before one result is committed.
- Original extraction rows remain unchanged after accepted overlays: PASS.

## Reliability and rejection coverage

Tests cover high/low confidence, missing evidence with no provider call, conflicting candidates, malformed structured output, timeout, transient retry, retry exhaustion, invalid container count, unsupported gross-weight units, budget exhaustion, cache reuse, version invalidation, duplicate concurrency, persistence failure, definite mismatch bypass, and disabled compatibility.

OCR tests cover injected success through role validation/extraction, unavailable engine, garbage text, timeout, exhausted budget, content cache, and concurrency limit. No Vision or LLM value is fabricated after bounded OCR failure.

## Performance

| Metric | Pre-change Phase 6 machine baseline | Final AI-disabled run |
| --- | ---: | ---: |
| Wall time | 13.419s | 15.081s |
| Throughput | 38.752 emails/s | 34.480 emails/s |
| p50 | 0.026385s | 0.028657s |
| p95 | 0.106951s | 0.115928s |

Wall time increased 12.39%, below the 20% investigation threshold. Timing variance is environment-sensitive; submission semantics were byte-identical. Peak RSS and live AI/OCR latency were NOT MEASURED.

## Verification summary

- Focused resolver/OCR/runtime/PostgreSQL suite: 35 passed.
- Full suite: 257 passed, 0 failed, 0 skipped, 1 existing warning.
- Reliability target: 14 passed.
- Phase 6B trace: 89 PASS / 0 TODO / 0 FAIL.
- `make check-fast`: PASS.
- `make check PHASE=6B`: PASS.
- Leakage/overfit scan: no runtime private-answer references, hard-coded bundle-size decisions, model fixtures, or credentials found.
- Scoreboard calls: 0; result NOT VERIFIED.

Live provider verification: **NOT VERIFIED**. No credentials were available and no live provider was called. Mock/fake provider runtime integration is verified.
