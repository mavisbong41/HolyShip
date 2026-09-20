# Phase 4 public comparison sanity audit

This diagnostic uses only the public participant bundle. It reports observed pipeline behavior, not accuracy; no private reference labels or ground truth were read.

## Aggregate outcomes

- Comparison-ready emails: 112
- Comparison-ready SI/BL pairs attempted: 98
- Completed clean comparisons: 0
- Completed comparisons with mismatch: 0
- Blocked unresolved comparisons: 98
- Failed comparisons: 0

## Field outcomes

| Canonical field | Mismatch | Unresolved |
|---|---:|---:|
| shipper | 0 | 76 |
| consignee | 0 | 66 |
| notify_party | 0 | 51 |
| port_of_loading | 0 | 47 |
| port_of_discharge | 0 | 47 |
| container_count | 3 | 75 |
| gross_weight_kg | 4 | 50 |

## Layer and call diagnostics

- L0 outcomes: 267
- L1 outcomes: 7
- L2 invocations/outcomes: 29
- Default-L2 unresolved outcomes: 29
- Readers invoked during comparison itself: 0
- Extractor invocations caused by comparison itself: 0
- Materialization reader calls before comparison: 216
- Materialization extractor calls before comparison: 196
- LLM provider calls: 0
- OCR provider calls caused by comparison: 0
- Vision provider calls caused by comparison: 0

Counts are diagnostic only. No rules were tuned against these aggregate results.
