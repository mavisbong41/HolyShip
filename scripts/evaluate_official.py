from __future__ import annotations

import argparse
import json
from pathlib import Path

from official_metrics import evaluate


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluation-only official ground-truth metrics")
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, default=Path("reports/latest/submission.json"))
    parser.add_argument("--json-out", type=Path, default=Path("reports/latest/official_metrics.json"))
    parser.add_argument("--md-out", type=Path, default=Path("reports/latest/official_metrics.md"))
    args = parser.parse_args()
    if not args.ground_truth.is_file():
        raise SystemExit("Official ground truth is unavailable. No reliability score was fabricated.")
    truth = json.loads(args.ground_truth.read_text(encoding="utf-8"))
    predictions = json.loads(args.predictions.read_text(encoding="utf-8"))
    result = evaluate(truth, predictions)
    args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    c, d, e = result["classification"], result["discrepancy"], result["escalation"]
    def pct(value): return "N/A" if value is None else f"{value * 100:.2f}%"
    lines = [
        "# HolyShip Official Reliability Evaluation", "",
        f"Coverage: {result['coverage']['evaluated']} / {result['coverage']['ground_truth']}", "",
        "## Classification", "", f"- Accuracy: {pct(c['accuracy'])}", f"- Macro F1: {pct(c['macro_f1'])}", f"- Weighted F1: {pct(c['weighted_f1'])}", "",
        "## Discrepancy detection", "", f"- Precision: {pct(d['precision'])}", f"- Recall: {pct(d['recall'])}", f"- F1: {pct(d['f1'])}", "",
        "## Human Review escalation", "", f"- Precision: {pct(e['precision'])}", f"- Recall: {pct(e['recall'])}", f"- F1: {pct(e['f1'])}", "",
        "Identifiers in error examples are sanitized report-local case numbers.",
    ]
    args.md_out.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
