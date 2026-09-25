from __future__ import annotations

from collections import Counter
from typing import Any

CATEGORIES = ("document_comparison", "new_si_request", "invoice_query", "general_message", "spam")
FIELDS = ("shipper", "consignee", "notify_party", "port_of_loading", "port_of_discharge", "container_count", "gross_weight_kg")


def ratio(n: int, d: int) -> float | None:
    return n / d if d else None


def scores(tp: int, fp: int, fn: int) -> dict[str, float | None]:
    precision = ratio(tp, tp + fp)
    recall = ratio(tp, tp + fn)
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
    return {"precision": precision, "recall": recall, "f1": f1}


def classification_metrics(rows: list[tuple[str, str]]) -> dict[str, Any]:
    matrix = {actual: {predicted: 0 for predicted in CATEGORIES} for actual in CATEGORIES}
    for actual, predicted in rows:
        if actual in matrix and predicted in matrix[actual]:
            matrix[actual][predicted] += 1
    per_class: dict[str, Any] = {}
    for category in CATEGORIES:
        tp = matrix[category][category]
        fp = sum(matrix[actual][category] for actual in CATEGORIES if actual != category)
        fn = sum(matrix[category][predicted] for predicted in CATEGORIES if predicted != category)
        metric = scores(tp, fp, fn)
        metric["support"] = sum(matrix[category].values())
        per_class[category] = metric
    total = len(rows)
    correct = sum(matrix[c][c] for c in CATEGORIES)
    defined = [per_class[c]["f1"] for c in CATEGORIES if per_class[c]["f1"] is not None]
    macro = {key: (sum(per_class[c][key] for c in CATEGORIES if per_class[c][key] is not None) / len([c for c in CATEGORIES if per_class[c][key] is not None])) for key in ("precision", "recall", "f1")}
    weighted = {key: ratio(sum((per_class[c][key] or 0) * per_class[c]["support"] for c in CATEGORIES), total) for key in ("precision", "recall", "f1")}
    return {"evaluated": total, "accuracy": ratio(correct, total), "macro": macro, "weighted": weighted, "per_category": per_class, "confusion_matrix": matrix}


def binary_metrics(rows: list[tuple[bool, bool]]) -> dict[str, Any]:
    tp = sum(actual and predicted for actual, predicted in rows)
    fp = sum(not actual and predicted for actual, predicted in rows)
    tn = sum(not actual and not predicted for actual, predicted in rows)
    fn = sum(actual and not predicted for actual, predicted in rows)
    return {"evaluated": len(rows), "true_positive": tp, "false_positive": fp, "true_negative": tn, "false_negative": fn, **scores(tp, fp, fn)}


def discrepancy_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    decisions: list[tuple[bool, bool]] = []
    by_field: dict[str, list[tuple[bool, bool]]] = {field: [] for field in FIELDS}
    unresolved_truth = 0
    unresolved_predictions = 0
    for row in rows:
        expected = row["expected"]
        predicted = row["predicted"]
        if expected == "UNRESOLVED":
            unresolved_truth += 1
            continue
        for field in FIELDS:
            actual_mismatch = field in row.get("expected_mismatched_fields", [])
            predicted_status = predicted.get(field, "UNRESOLVED")
            predicted_mismatch = predicted_status == "MISMATCH"
            if predicted_status == "UNRESOLVED":
                unresolved_predictions += 1
            decisions.append((actual_mismatch, predicted_mismatch))
            by_field[field].append((actual_mismatch, predicted_mismatch))
    return {"field_level": {"overall": binary_metrics(decisions), "by_field": {field: binary_metrics(values) for field, values in by_field.items()}}, "case_unresolved_ground_truth": unresolved_truth, "unresolved_predictions": unresolved_predictions}


def error_counts(errors: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(error_type for error in errors for error_type in error.get("error_types", [])))
