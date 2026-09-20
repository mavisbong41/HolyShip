# Phase 3 public extraction coverage

This audit uses only the public participant bundle. It reports extraction coverage, not accuracy; no reference labels or private ground truth were used.

## Run summary

- Validated SI documents: 106
- Validated BL documents: 98
- Extraction attempts: 204
- Fresh extraction computations: 204
- Cache hits: 0
- Cache misses: 204
- Extraction failures: 0
- SI/BL pairs started in a bounded two-worker pool: 98
- Total extraction wall time: 2.305 seconds
- LLM calls: 0
- OCR calls: 0
- Vision calls: 0

## Format distribution

| Format | Validated documents |
|---|---:|
| DOCX | 8 |
| PDF_TEXT | 14 |
| PLAIN_TEXT | 160 |
| XLSX | 22 |

## Canonical field coverage

| Field | Resolved | Missing | Unresolved | Ambiguous |
|---|---:|---:|---:|---:|
| shipper | 100 | 104 | 0 | 0 |
| consignee | 121 | 83 | 0 | 0 |
| notify_party | 152 | 52 | 0 | 0 |
| port_of_loading | 160 | 44 | 0 | 0 |
| port_of_discharge | 165 | 39 | 0 | 0 |
| container_count | 100 | 104 | 0 | 0 |
| gross_weight_kg | 139 | 64 | 1 | 0 |

## Missing/unresolved reasons

- `shipper`: FIELD_NOT_PRESENT=104
- `consignee`: FIELD_NOT_PRESENT=83
- `notify_party`: FIELD_NOT_PRESENT=52
- `port_of_loading`: FIELD_NOT_PRESENT=44
- `port_of_discharge`: FIELD_NOT_PRESENT=39
- `container_count`: FIELD_NOT_PRESENT=104
- `gross_weight_kg`: FIELD_NOT_PRESENT=64, VALUE_UNRESOLVED=1

## Interpretation

A missing field means no supported public label/value was present in the materialized content. Unresolved and ambiguous rows retain their machine-readable reason from deterministic extraction. Percent accuracy is intentionally not reported because this audit has no reference labels.
