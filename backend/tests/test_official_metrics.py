from scripts.official_metrics import binary_metrics, classification_metrics, evaluate


def test_classification_metrics_confusion_and_empty_class_are_correct():
    truth = {"a": {"category": "BL_COMPARISON"}, "b": {"category": "GENERAL"}}
    pred = {"a": {"category": "BL_COMPARISON"}, "b": {"category": "SPAM"}}
    result = classification_metrics(truth, pred)
    assert result["evaluated"] == 2
    assert result["accuracy"] == 0.5
    assert result["confusion_matrix"]["general_message"]["spam"] == 1
    assert result["per_category"]["invoice_query"]["f1"] is None


def test_binary_metrics_include_failures_and_have_correct_f1():
    result = binary_metrics([True, True, False, False], [True, False, True, False])
    assert result == {"evaluated": 4, "true_positive": 1, "false_positive": 1, "true_negative": 1, "false_negative": 1, "precision": 0.5, "recall": 0.5, "f1": 0.5}


def test_evaluation_coverage_and_sanitized_errors():
    truth = {"secret-id": {"category": "GENERAL", "status": "OK", "has_defect": False}}
    pred = {"secret-id": {"category": "SPAM", "status": "NEEDS_REVIEW", "has_defect": False}}
    result = evaluate(truth, pred)
    assert result["coverage"]["evaluated"] == 1
    assert result["error_analysis"]["examples"][0]["case"] == "case_0001"
    assert "secret-id" not in str(result)
