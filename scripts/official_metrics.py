from __future__ import annotations

from collections import Counter
from typing import Any

CATEGORIES = ("document_comparison", "new_si_request", "invoice_query", "general_message", "spam")
ALIASES = {
    "BL_COMPARISON": "document_comparison", "SI_REQUEST": "new_si_request",
    "INVOICE_QUERY": "invoice_query", "GENERAL": "general_message", "SPAM": "spam",
}


def canonical_category(value: Any) -> str:
    text = str(value or "").strip()
    return ALIASES.get(text, text.lower())


def _ratio(n: int, d: int) -> float | None:
    return n / d if d else None


def classification_metrics(truth: dict[str, dict], predictions: dict[str, dict]) -> dict[str, Any]:
    ids = sorted(set(truth) & set(predictions))
    matrix = {actual: {predicted: 0 for predicted in CATEGORIES} for actual in CATEGORIES}
    for email_id in ids:
        actual = canonical_category(truth[email_id].get("category"))
        predicted = canonical_category(predictions[email_id].get("category"))
        if actual in matrix and predicted in matrix[actual]:
            matrix[actual][predicted] += 1
    per_category = {}
    for category in CATEGORIES:
        tp = matrix[category][category]
        fp = sum(matrix[row][category] for row in CATEGORIES if row != category)
        fn = sum(matrix[category][column] for column in CATEGORIES if column != category)
        support = sum(matrix[category].values())
        precision, recall = _ratio(tp, tp + fp), _ratio(tp, tp + fn)
        f1 = None if precision is None or recall is None or precision + recall == 0 else 2 * precision * recall / (precision + recall)
        per_category[category] = {"precision": precision, "recall": recall, "f1": f1, "support": support}
    total = sum(sum(row.values()) for row in matrix.values())
    correct = sum(matrix[c][c] for c in CATEGORIES)
    defined = [item for item in per_category.values() if item["f1"] is not None]
    macro_f1 = sum(item["f1"] for item in defined) / len(defined) if defined else None
    weighted_f1 = _ratio(sum((item["f1"] or 0) * item["support"] for item in per_category.values()), total)
    return {"evaluated": total, "accuracy": _ratio(correct, total), "macro_f1": macro_f1, "weighted_f1": weighted_f1, "per_category": per_category, "confusion_matrix": matrix}


def binary_metrics(truth_values: list[bool], predicted_values: list[bool]) -> dict[str, Any]:
    tp = sum(a and p for a, p in zip(truth_values, predicted_values))
    fp = sum((not a) and p for a, p in zip(truth_values, predicted_values))
    tn = sum((not a) and (not p) for a, p in zip(truth_values, predicted_values))
    fn = sum(a and (not p) for a, p in zip(truth_values, predicted_values))
    precision, recall = _ratio(tp, tp + fp), _ratio(tp, tp + fn)
    f1 = None if precision is None or recall is None or precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {"evaluated": len(truth_values), "true_positive": tp, "false_positive": fp, "true_negative": tn, "false_negative": fn, "precision": precision, "recall": recall, "f1": f1}


def evaluate(truth: dict[str, dict], predictions: dict[str, dict]) -> dict[str, Any]:
    ids = sorted(set(truth) & set(predictions))
    discrepancy_truth = [bool(truth[i].get("has_defect")) for i in ids]
    discrepancy_pred = [bool(predictions[i].get("has_defect")) for i in ids]
    escalation_truth = [str(truth[i].get("status")) == "NEEDS_REVIEW" for i in ids]
    escalation_pred = [str(predictions[i].get("status")) == "NEEDS_REVIEW" for i in ids]
    errors = []
    for index, email_id in enumerate(ids):
        kinds = []
        if canonical_category(truth[email_id].get("category")) != canonical_category(predictions[email_id].get("category")):
            kinds.append("classification")
        if discrepancy_truth[index] != discrepancy_pred[index]:
            kinds.append("discrepancy")
        if escalation_truth[index] != escalation_pred[index]:
            kinds.append("escalation")
        if kinds:
            errors.append({"case": f"case_{index + 1:04d}", "error_types": kinds})
    return {
        "coverage": {"ground_truth": len(truth), "predictions": len(predictions), "evaluated": len(ids), "missing_predictions": len(set(truth) - set(predictions))},
        "classification": classification_metrics(truth, predictions),
        "discrepancy": binary_metrics(discrepancy_truth, discrepancy_pred),
        "escalation": binary_metrics(escalation_truth, escalation_pred),
        "error_analysis": {"counts": dict(Counter(kind for item in errors for kind in item["error_types"])), "examples": errors[:25]},
    }
