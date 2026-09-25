# HolyShip Independent Labeled Stress Test v1

This is a team-authored, independently labeled benchmark. It is not organizer ground truth and must remain separate from the public 520-email operational benchmark.

The frozen evaluation order is:

1. define cases and labels independently;
2. validate and fingerprint the dataset;
3. run the existing HolyShip boundaries on fixture inputs only;
4. join predictions to labels after processing;
5. write metrics and error analysis.

Run from the repository root:

```text
python scripts/run_stress_evaluation.py --freeze
python scripts/run_stress_evaluation.py
```

The first command writes `frozen_sha256.txt`; later runs refuse to execute if the frozen files changed. Reports are written to `reports/latest/stress_test_metrics.json` and `reports/latest/stress_test_metrics.md`.

The fixtures intentionally include classification ambiguity, misleading subjects, no-attachment waiting states, formatting variation, true discrepancies, unresolved evidence, bilingual/contextual labels, wrong documents, and missing/unreadable documents. Inputs contain no expected labels. Labels and reasons are in `ground_truth.json` and are never imported by production code.

Primary metrics are classification macro F1, field-level discrepancy precision/recall/F1, and escalation precision/recall/F1. `UNRESOLVED` is reported separately and is not silently converted to MATCH.
