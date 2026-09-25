from scripts.stress_metrics import binary_metrics, classification_metrics, discrepancy_metrics


def test_classification_metrics_include_macro_and_weighted_scores_and_matrix():
    result = classification_metrics([
        ("spam", "spam"),
        ("general_message", "spam"),
        ("invoice_query", "invoice_query"),
        ("new_si_request", "new_si_request"),
    ])
    assert result["evaluated"] == 4
    assert result["confusion_matrix"]["general_message"]["spam"] == 1
    assert result["macro"]["f1"] is not None
    assert result["weighted"]["f1"] is not None


def test_binary_metrics_zero_denominator_is_explicit_none():
    result = binary_metrics([(False, False), (False, False)])
    assert result["true_negative"] == 2
    assert result["precision"] is None
    assert result["recall"] is None
    assert result["f1"] is None


def test_unresolved_ground_truth_is_excluded_from_binary_field_score_and_reported():
    result = discrepancy_metrics([
        {"expected": "MISMATCH", "expected_mismatched_fields": ["gross_weight_kg"], "predicted": {"gross_weight_kg": "UNRESOLVED"}},
        {"expected": "UNRESOLVED", "expected_mismatched_fields": [], "predicted": {"gross_weight_kg": "UNRESOLVED"}},
    ])
    overall = result["field_level"]["overall"]
    assert overall["false_negative"] == 1
    assert result["case_unresolved_ground_truth"] == 1
    assert result["unresolved_predictions"] == 7
