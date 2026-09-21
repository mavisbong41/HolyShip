# Phase 4 public comparison sanity audit

This diagnostic uses only the public participant bundle. It reports observed pipeline behavior, not accuracy; no private reference labels or ground truth were read.

## Aggregate outcomes

- Comparison-ready emails: 129
- Comparison-ready SI/BL pairs attempted: 114
- Completed clean comparisons: 63
- Completed comparisons with mismatch: 46
- Blocked unresolved comparisons: 5
- Failed comparisons: 0

## Field outcomes

| Canonical field | Mismatch | Unresolved |
|---|---:|---:|
| shipper | 7 | 1 |
| consignee | 7 | 1 |
| notify_party | 8 | 0 |
| port_of_loading | 6 | 1 |
| port_of_discharge | 13 | 2 |
| container_count | 19 | 1 |
| gross_weight_kg | 12 | 2 |

## Layer and call diagnostics

- L0 outcomes: 690
- L1 outcomes: 100
- L2 invocations/outcomes: 0
- Default-L2 unresolved outcomes: 0
- Readers invoked during comparison itself: 0
- Extractor invocations caused by comparison itself: 0
- Materialization reader calls before comparison: 250
- Materialization extractor calls before comparison: 228
- LLM provider calls: 0
- OCR provider calls caused by comparison: 0
- Vision provider calls caused by comparison: 0

Counts are diagnostic only. No rules were tuned against these aggregate results.
