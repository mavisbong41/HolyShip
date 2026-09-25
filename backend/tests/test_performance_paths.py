from scripts.performance_paths import compare_paths, percentile


def test_percentiles_use_consistent_milliseconds():
    assert percentile([10, 20, 30], 0.5) == 20
    assert percentile([10, 20, 30], 0.95) >= 20
    assert percentile([], 0.95) is None


def test_path_report_counts_failures_and_ai_calls():
    report = {"sync": {"per_email": [
        {"duration_ms": 10, "resolver_calls": 0, "error": None},
        {"duration_ms": 20, "resolver_calls": 1, "resolver_failures": 1, "resolver_rejected": 0, "error": "timeout"},
    ]}}
    result = compare_paths(report)
    assert result["deterministic"]["count"] == 1
    assert result["ai_assisted"]["failure_count"] == 1
    assert result["ai_assisted"]["gemini_calls"] == 1
    assert result["ai_assisted"]["fallback_count"] == 1
