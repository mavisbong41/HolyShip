from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * p
    lo, hi = int(rank), min(int(rank) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (rank - lo)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    durations = [float(row.get("duration_ms") or 0) for row in rows]
    wall_seconds = sum(durations) / 1000
    return {
        "count": len(rows),
        "success_count": sum(not row.get("error") for row in rows),
        "failure_count": sum(bool(row.get("error")) for row in rows),
        "p50_ms": percentile(durations, 0.50),
        "p95_ms": percentile(durations, 0.95),
        "mean_ms": statistics.fmean(durations) if durations else None,
        "throughput_per_second": len(rows) / wall_seconds if wall_seconds else None,
        "gemini_calls": sum(int(row.get("resolver_calls") or 0) for row in rows),
        "gemini_failures": sum(int(row.get("resolver_failures") or 0) for row in rows),
        "fallback_count": sum(int(row.get("resolver_rejected") or 0) + int(row.get("resolver_failures") or 0) for row in rows),
    }


def compare_paths(report: dict[str, Any]) -> dict[str, Any]:
    sync = report.get("sync") or {}
    rows = list(sync.get("outcomes") or sync.get("per_email") or [])
    ai = [row for row in rows if int(row.get("resolver_calls") or 0) > 0]
    deterministic = [row for row in rows if int(row.get("resolver_calls") or 0) == 0]
    overall = summarize(rows)
    measured_throughput = report.get("throughput_emails_per_second")
    if measured_throughput is None:
        measured_throughput = sync.get("throughput_emails_per_second")
    if measured_throughput is not None:
        overall["throughput_per_second"] = float(measured_throughput)
    if sync.get("p50_per_email_ms") is not None:
        overall["p50_ms"] = float(sync["p50_per_email_ms"])
    if sync.get("p95_per_email_ms") is not None:
        overall["p95_ms"] = float(sync["p95_per_email_ms"])
    deterministic_summary = summarize(deterministic)
    if len(deterministic) == len(rows) and measured_throughput is not None:
        deterministic_summary["throughput_per_second"] = float(measured_throughput)
    deterministic_summary["measurement_status"] = "MEASURED" if deterministic else "NO_SAMPLE"
    ai_summary = summarize(ai)
    ai_summary["measurement_status"] = "MEASURED" if ai else "NOT_MEASURED_NO_PROVIDER_CALLS"
    overall["measurement_status"] = "MEASURED" if rows else "NO_SAMPLE"
    return {"deterministic": deterministic_summary, "ai_assisted": ai_summary, "overall": overall}


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Performance paths",
        "",
        "| Path | Measurement | Count | Success | Failure | P50 ms | P95 ms | Throughput/s | Provider calls | Provider failures | Fallbacks |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key, label in (("deterministic", "Deterministic"), ("ai_assisted", "AI-assisted"), ("overall", "Overall")):
        row = result[key]
        lines.append(
            f"| {label} | {row.get('measurement_status')} | {row.get('count')} | {row.get('success_count')} | "
            f"{row.get('failure_count')} | {row.get('p50_ms')} | {row.get('p95_ms')} | "
            f"{row.get('throughput_per_second')} | {row.get('gemini_calls')} | {row.get('gemini_failures')} | "
            f"{row.get('fallback_count')} |"
        )
    lines.extend([
        "",
        "> `NOT_MEASURED_NO_PROVIDER_CALLS` means the run made no live AI-provider calls; it is not a zero-latency or zero-failure claim.",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("reports/latest/eval.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/latest/performance_paths.json"))
    parser.add_argument("--markdown-output", type=Path, default=Path("reports/latest/performance_paths.md"))
    args = parser.parse_args()
    result = compare_paths(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(result), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
