# Phase 5 Performance Report

Date: 2026-09-20  
Branch: `phase5`

## Baseline

The preserved Phase 4/pre-Phase-5 evaluation artifact reports:

- Workload: 520 emails (observed bundle size, not a runtime assumption)
- Full-run wall time: 15.284 seconds
- Throughput: 34.023 emails/second
- Per-email p50/p95: NOT MEASURED by the legacy harness
- Peak RSS: NOT MEASURED
- Cache/reader/extractor/OCR/Vision counts: legacy artifact recorded only `cache=0`, `llm=0`, `ocr=0`, `vision=0`; reader/extractor call counts were NOT MEASURED in that run
- Unhandled exceptions: 0 in the preserved artifact
- Baseline submission SHA-256: `37b33169797c6aef6b781fbcbf1ba99cb92d3a8d96ac184235eeda167d2a4eab`

## Measured bottlenecks

No new full evaluation was available on this host, so a Phase 5 bottleneck ranking is NOT MEASURED. The implementation adds instrumentation for wall time, throughput, per-email p50/p95, worker count, retries, reader/extractor/OCR/Vision calls, cache hits/misses, and unhandled worker exceptions for the next database-enabled run.

## Optimizations implemented

### Bounded email-level concurrency

- What changed: `SyncService` uses a bounded in-flight window and one session per worker when configured; default-safe callers remain sequential.
- Why: Allows backlog work to progress without unbounded task creation or sharing a SQLAlchemy session across threads.
- Correctness risk: Completion order can differ; semantic output must not. A PostgreSQL single-vs-parallel regression test protects this.
- Before/after: NOT MEASURED; no comparable Phase 5 full run was possible.

### Durable duplicate protection and resume

- What changed: Content-version identities and unique constraints cover jobs, classifications, attachments, documents, and extraction cache entries; savepoint conflict recovery re-fetches the winner.
- Why: Avoids duplicate graphs under concurrent ingestion and enables safe continuation of interrupted technical states.
- Correctness risk: Integrity-conflict handling must not hide a real content change; changed content remains a new classification version.
- Before/after: NOT MEASURED.

### Bounded HTTP/resolver work

- What changed: Finite exponential backoff, transient-status filtering, request timeouts, structured retry events, resolver timeout, and malformed-output validation.
- Why: Prevents infinite waits/retry loops and isolates provider failures.
- Correctness risk: A transient service may be unavailable after the finite budget; the final state remains structured failure/unresolved rather than fabricated success.
- Before/after: NOT MEASURED for a live provider.

### Versioned extraction cache

- What changed: Added durable `(content_sha256, extractor_version)` cache identity with race-safe registration and current-document field copying.
- Why: Reuses exact deterministic work while invalidating stale extractor versions.
- Correctness risk: Cache reuse must preserve current document provenance; field rows are copied into the target extraction rather than re-pointed.
- Before/after: Existing Phase 3 tests cover the logical contract; live Phase 5 cache-race measurements are NOT VERIFIED here.

## Final metrics

- Post-Phase-5 full-run wall time: NOT MEASURED
- Post-Phase-5 throughput: NOT MEASURED
- Post-Phase-5 p50/p95: NOT MEASURED
- Post-Phase-5 peak RSS: NOT MEASURED
- Post-Phase-5 cache hit rate: NOT MEASURED
- Performance regression/improvement: NOT CLAIMED

The next database-enabled run should compare the new `reports/latest/eval.json` fields with the preserved baseline, repeat clean evaluation twice, and investigate any slowdown greater than approximately 20% before declaring the performance gate.
