# HolyShip Independent Labeled Stress Test

## Evaluation Design

Frozen team-authored dataset `v1` with 40 cases. Ground truth was joined only after processing. This is not official organizer accuracy.

## Dataset Composition

| Scenario | Cases |
|---|---:|
| classification/readiness | 10 |
| formatting-equivalent comparisons | 3 |
| single-field discrepancies | 7 |
| multi-field discrepancies | 3 |
| ambiguous/missing evidence | 3 |
| wrong/missing/unreadable documents | 5 |
| structured/readable document cases | 3 |

## Ground-Truth Integrity

- SHA-256: `afd7b7ac9e81cf3bab1ab1bfc179ae4e45a554d7d326d1b7effce9ca3eced1d1`
- Frozen before execution: **True**
- Leakage scan: **PASS**

## Classification Results

- Accuracy: 0.975; macro F1: 0.968; weighted F1: 0.977

```json
{
  "document_comparison": {
    "document_comparison": 31,
    "new_si_request": 0,
    "invoice_query": 0,
    "general_message": 1,
    "spam": 0
  },
  "new_si_request": {
    "document_comparison": 0,
    "new_si_request": 2,
    "invoice_query": 0,
    "general_message": 0,
    "spam": 0
  },
  "invoice_query": {
    "document_comparison": 0,
    "new_si_request": 0,
    "invoice_query": 2,
    "general_message": 0,
    "spam": 0
  },
  "general_message": {
    "document_comparison": 0,
    "new_si_request": 0,
    "invoice_query": 0,
    "general_message": 3,
    "spam": 0
  },
  "spam": {
    "document_comparison": 0,
    "new_si_request": 0,
    "invoice_query": 0,
    "general_message": 0,
    "spam": 1
  }
}
```

## Discrepancy Detection Results

- Field-level TP/FP/TN/FN: 17/0/121/2
- Precision/Recall/F1: 1.0/0.8947368421052632/0.9444444444444444
- Ground-truth unresolved cases: 3; unresolved predictions: 3

## Human Review Escalation Results

- TP/FP/TN/FN: 7/2/30/1
- Precision/Recall/F1: 0.7777777777777778/0.875/0.823529411764706

## Representative Errors

- `STRESS-CMP-016`: extraction or normalization, unnecessary escalation — Bilingual/descriptive labels map to the same seven fields and values match.
- `STRESS-CMP-020`: extraction or normalization, unnecessary escalation — Meaningful entity differences must not be normalized away.
- `STRESS-ESC-002`: classification signal ambiguity, readiness interpretation, missed escalation — Comparison intent is clear but the readiness evidence is contradictory.

## Interpretation

Primary results use all frozen cases. Definite MISMATCH is not itself treated as a Human Review requirement; only uncertainty, missing/wrong/unreadable evidence, or unresolved routing escalates.

## Limitations

Team-authored sample of 40 constructed cases; not organizer labels. The harness exercises the deterministic in-process production boundaries and does not claim live Gemini/OCR performance.

## Presentation Block

HolyShip Independent Labeled Stress Test\nN = 40 frozen cases\n\nClassification\nAccuracy: 97.5%\nMacro F1: 0.968\n\nDiscrepancy Detection\nPrecision: 1.000\nRecall: 0.895\nF1: 0.944\n\nHuman Review Escalation\nPrecision: 0.778\nRecall: 0.875\nF1: 0.824\n\nUnsafe confident errors: 0\nCorrect safe abstentions: 3
