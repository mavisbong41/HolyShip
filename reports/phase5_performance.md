# Phase 5 Performance Report

Date: 2026-09-20  
Branch: `phase5`

## Comparable measurement

The final clean Phase 5 evaluation used the public 520-email bundle, a clean isolated `holyship_eval` database, and the normal `SYNC_MAX_WORKERS=4` configuration.

| Metric | Phase 4 baseline | Phase 5 final | Difference |
|---|---:|---:|---:|
| Full-run wall time | 15.284 s | 13.351 s | -1.933 s (-12.65%) |
| Throughput | 34.023 emails/s | 38.949 emails/s | +4.926 emails/s (+14.48%) |
| Per-email p50 | NOT MEASURED | 0.024455 s | measured |
| Per-email p95 | NOT MEASURED | 0.106313 s | measured |
| Peak RSS | NOT MEASURED | NOT MEASURED | no cross-platform metrics dependency |

The comparable wall-time result is faster than the Phase 4 baseline; the greater-than-20% regression gate is **NO**.

## Phase 5 instrumentation

Final evaluation metrics:

- Workers: 4
- Cache hits / misses: 0 / 196
- Reader calls: 216
- Extractor calls: 196
- OCR calls: 6
- Vision calls: 0
- LLM/resolver calls: 0
- Retries: 0
- Failed emails: 0
- Unhandled exceptions: 0

The cache correctness gate was exercised separately against PostgreSQL. The clean public-bundle run has zero cache hits because it starts from a clean evaluation database by design; this is not evidence that cache reuse is disabled.

## Worker comparison

Clean worker evaluations produced the same byte-identical submission SHA-256 with workers=1 and workers=4. Measured wall times were 14.843 s and 14.198 s respectively for those runs; the semantic comparison ignores timing metadata and found no business-output difference. The final post-gate workers=4 run was 13.351 s.

## Limitations

- Peak RSS was not measured because adding a process-metrics dependency was outside this closure task.
- No optimization was made after measurement; the observed Phase 5 run is already faster than the baseline.
