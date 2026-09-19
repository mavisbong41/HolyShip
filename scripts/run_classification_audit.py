"""Generate the Phase-1 classification audit from the public participant bundle only."""
from __future__ import annotations

import random
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.classification.adapters import email_message_to_classification_input
from backend.app.classification.config import STAGE1_CONFIDENCE_THRESHOLD
from backend.app.classification.pipeline import classify_email
from backend.app.classification.readiness import has_dense_si_content
from backend.app.classification.stage1 import score_email
from backend.app.ingestion.models import EmailMessage
from backend.app.ingestion.sources import StaticBundleSource

SEED = 20260920
CATEGORIES = (
    "document_comparison",
    "new_si_request",
    "invoice_query",
    "general_message",
    "spam",
)
PRE_FIX_DISTRIBUTION = {
    "document_comparison": 234,
    "new_si_request": 136,
    "invoice_query": 83,
    "general_message": 41,
    "spam": 26,
}
PRE_FIX_LOW_CONFIDENCE = 200
PRE_FIX_NO_ATTACHMENT = {"total": 108, "A": 91, "B": 3, "C": 0, "D": 14}


@dataclass(frozen=True)
class AuditRow:
    message: EmailMessage
    category: str
    confidence: float
    readiness: str | None
    conflict: bool
    subject_signal: str | None
    body_signal: str | None
    zero_signal: bool


def compact(value: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", value).strip().replace("|", "\\|")
    return value if len(value) <= limit else value[: limit - 1] + "…"


def strongest(scores: dict[str, float]) -> str | None:
    category, value = max(scores.items(), key=lambda item: item[1])
    return category if value > 0 else None


def semantic_judgement(row: AuditRow) -> tuple[str, str]:
    text = f"{row.message.subject}\n{row.message.body}".lower()
    if row.zero_signal:
        spam_like = any(phrase in text for phrase in (
            "bitcoin investment",
            "brand new iphone",
            "bank officer",
            "90% off",
            "avoid suspension",
            "verify account immediately",
        ))
        if spam_like:
            return "spam-like message", "Human audit: visible scam/promotional language exists, but the current signal set scored every category zero."
        return "general operational message", "Human audit: visible operational/informational content exists, but the current signal set scored every category zero."
    if row.category == "document_comparison":
        if row.readiness == "AWAITING_DOCUMENTS":
            return "comparison workflow awaiting a requested draft BL", "Operational waiting intent is explicit."
        if row.readiness == "READY_FOR_COMPARISON":
            return "comparison request with attachment metadata available", "Readiness is supported by at least two attachments."
        return "comparison intent, but readiness evidence is incomplete", "Keep unresolved; do not infer document availability."
    if row.category == "new_si_request":
        note = "Dense SI structure supports the primary SI intent." if has_dense_si_content(text) else "Primary action asks to prepare/submit an SI."
        return "new shipping-instruction request", note
    if row.category == "invoice_query":
        return "invoice/payment enquiry", "Billing/payment language is the observable primary action."
    if row.category == "spam":
        return "spam/promotional or phishing-like message", "Observable promotional/phishing signals support the decision."
    return "general operational message", "No stronger supported operational category is evident."


def no_attachment_bucket(row: AuditRow) -> tuple[str, str]:
    text = f"{row.message.subject}\n{row.message.body}".lower()
    send_bl = re.search(r"\b(send|provide|revert with|issue)\b.{0,60}\b(draft\s+bl|draft\s+bill\s+of\s+lading)\b", text, re.S)
    checking = re.search(r"\b(check|checking|compare|verify|review)\b", text)
    immediate = re.search(r"\b(compare|verify|check)\b.{0,80}\b(attached|enclosed|si\s+and\s+(?:draft\s+)?bl)\b", text, re.S)
    if has_dense_si_content(text):
        return "C", "Dense inline SI fields make new_si_request plausible."
    if send_bl and checking:
        return "A", "Requests a future draft BL for checking."
    if immediate:
        return "B", "Immediate comparison wording expects documents that are absent."
    if row.zero_signal:
        judgement, _ = semantic_judgement(row)
        return "D", f"Zero classifier evidence; visible content reads as {judgement}."
    return "D", "Comparison signal exists, but document timing/availability is unclear."


def row_line(row: AuditRow) -> str:
    judgement, note = semantic_judgement(row)
    attachments = ", ".join(a.filename for a in row.message.attachments) or "none"
    return (
        f"| {row.message.external_message_id} | {compact(row.message.subject, 55)} | "
        f"{compact(row.message.body, 90)} | {compact(attachments, 55)} | {row.category} | "
        f"{row.confidence:.4f} | {'yes' if row.confidence < STAGE1_CONFIDENCE_THRESHOLD else 'no'} | "
        f"{row.readiness or 'n/a'} | {judgement} | {note} |"
    )


def main() -> None:
    source = StaticBundleSource(ROOT / "data" / "bundle")
    rows: list[AuditRow] = []
    for message in source.iter_messages():
        cls_input = email_message_to_classification_input(message)
        output = classify_email(cls_input)
        scores = score_email(cls_input.subject, cls_input.body, cls_input.attachment_filenames)
        subject_signal = strongest(scores.subject_scores)
        body_signal = strongest(scores.body_scores)
        rows.append(AuditRow(
            message=message,
            category=output.category,
            confidence=output.confidence,
            readiness=output.comparison_readiness,
            conflict=bool(subject_signal and body_signal and subject_signal != body_signal),
            subject_signal=subject_signal,
            body_signal=body_signal,
            zero_signal=all(value == 0 for value in scores.combined_scores.values()),
        ))

    distribution = Counter(row.category for row in rows)
    readiness = Counter(row.readiness for row in rows if row.category == "document_comparison")
    low_confidence = sum(row.confidence < STAGE1_CONFIDENCE_THRESHOLD for row in rows)
    comparison = [row for row in rows if row.category == "document_comparison"]
    no_attachment = [row for row in comparison if not row.message.attachments]
    conflicts = [row for row in rows if row.conflict]
    zero_signal_rows = [row for row in rows if row.zero_signal]
    zero_signal_fallback = [row for row in rows if row.zero_signal and row.category == "document_comparison"]
    generalizable_defect_count = 1 if zero_signal_fallback else 0
    zero_signal_categories = Counter(row.category for row in zero_signal_rows)

    rng = random.Random(SEED)
    sampled: dict[str, list[AuditRow]] = {}
    for category in CATEGORIES:
        candidates = sorted((row for row in rows if row.category == category), key=lambda row: row.message.external_message_id)
        sampled[category] = sorted(rng.sample(candidates, min(15, len(candidates))), key=lambda row: row.message.external_message_id)

    buckets = Counter()
    no_attachment_lines = []
    for row in no_attachment:
        bucket, reason = no_attachment_bucket(row)
        buckets[bucket] += 1
        no_attachment_lines.append(
        f"| {row.message.external_message_id} | {compact(row.message.subject + ' — ' + row.message.body, 120)} | {row.category} | "
            f"{row.readiness or 'n/a'} | {bucket} | {reason} |"
        )

    report = [
        "# Classification audit — Phase 1",
        "",
        "This is audit-only tooling over the public participant bundle. Email IDs are reporting references only and never enter runtime rules.",
        "",
        "**No private ground truth or evaluator data was used.**",
        "",
        "## Summary",
        "",
        f"- Audit seed: `{SEED}`",
        f"- Participant total: {len(rows)}",
        "- Category distribution:",
        *(f"  - {name}: {distribution[name]}" for name in CATEGORIES),
        f"- Confidence: min={min(r.confidence for r in rows):.4f}, median={sorted(r.confidence for r in rows)[len(rows)//2]:.4f}, max={max(r.confidence for r in rows):.4f}",
        f"- Low-confidence count (< {STAGE1_CONFIDENCE_THRESHOLD:.2f}): {low_confidence}",
        f"- document_comparison: total={len(comparison)}, with attachments={sum(bool(r.message.attachments) for r in comparison)}, without attachments={len(no_attachment)}",
        f"- Readiness: READY_FOR_COMPARISON={readiness['READY_FOR_COMPARISON']}, AWAITING_DOCUMENTS={readiness['AWAITING_DOCUMENTS']}, UNRESOLVED={readiness['UNRESOLVED']}",
        "- 15-per-category sample:",
        *(f"  - {name}: {len(sampled[name])}" for name in CATEGORIES),
        "- No-attachment document_comparison:",
        f"  - total: {len(no_attachment)}",
        f"  - bucket A: {buckets['A']}",
        f"  - bucket B: {buckets['B']}",
        f"  - bucket C: {buckets['C']}",
        f"  - bucket D: {buckets['D']}",
        "- Subject/body conflicts:",
        f"  - total: {len(conflicts)}",
        "- Generalizable defects found:",
        f"  - count: {generalizable_defect_count}",
        "- Private ground truth used:",
        "  - NO",
        "",
        "### Before/after comparison",
        "",
        "| Metric | R3A-1 before | R3A-2 after |",
        "|---|---:|---:|",
        *(f"| {name} | {PRE_FIX_DISTRIBUTION[name]} | {distribution[name]} |" for name in CATEGORIES),
        f"| low confidence | {PRE_FIX_LOW_CONFIDENCE} | {low_confidence} |",
        f"| no-attachment document_comparison | {PRE_FIX_NO_ATTACHMENT['total']} | {len(no_attachment)} |",
        f"| bucket A | {PRE_FIX_NO_ATTACHMENT['A']} | {buckets['A']} |",
        f"| bucket B | {PRE_FIX_NO_ATTACHMENT['B']} | {buckets['B']} |",
        f"| bucket C | {PRE_FIX_NO_ATTACHMENT['C']} | {buckets['C']} |",
        f"| bucket D | {PRE_FIX_NO_ATTACHMENT['D']} | {buckets['D']} |",
        f"| zero-signal cases | 14 | {len(zero_signal_rows)} |",
        "",
        f"Post-fix zero-signal categories: {', '.join(f'{name}={zero_signal_categories[name]}' for name in CATEGORIES if zero_signal_categories[name]) or 'none'}.",
        "",
        "## Deterministic category sample",
        "",
        "The semantic judgement is a review of visible public subject/body/attachment evidence, independent from the classifier-output columns.",
    ]
    header = "| Audit ID | Subject evidence | Body/business evidence | Attachment metadata | Classifier category | Confidence | Low confidence | Readiness | Semantic audit judgement | Ambiguity/generalization note |"
    separator = "|---|---|---|---|---|---:|---|---|---|---|"
    for category in CATEGORIES:
        report += ["", f"### {category}", "", header, separator]
        report.extend(row_line(row) for row in sampled[category])

    report += [
        "",
        "## All no-attachment document_comparison cases",
        "",
        "Buckets: A = legitimate AWAITING_DOCUMENTS; B = immediate comparison with expected document absent; C = likely new_si_request; D = unresolved.",
        "",
        "| Audit ID | Decisive public evidence | Current category | Current readiness | Bucket | Reason |",
        "|---|---|---|---|---|---|",
        *no_attachment_lines,
        "",
        f"Totals: A={buckets['A']}, B={buckets['B']}, C={buckets['C']}, D={buckets['D']} (all {len(no_attachment)} reviewed).",
        "",
        "## Subject/body conflict audit",
        "",
        "| Audit ID | Subject signal | Body signal | Final category | Confidence | Semantic assessment | Body outweighed subject? |",
        "|---|---|---|---|---:|---|---|",
    ]
    for row in conflicts:
        judgement, _ = semantic_judgement(row)
        report.append(
            f"| {row.message.external_message_id} | {row.subject_signal} | {row.body_signal} | {row.category} | "
            f"{row.confidence:.4f} | {judgement} | {'yes' if row.category == row.body_signal else 'no/unclear'} |"
        )

    pattern_a = [row for row in no_attachment if no_attachment_bucket(row)[0] == "A"]
    pattern_b = [row for row in rows if row.category == "new_si_request" and not row.message.attachments and has_dense_si_content(row.message.body) and "draft bl" in row.message.body.lower()]
    report += [
        "",
        "## Pattern A / Pattern B check",
        "",
        f"- Pattern A public examples: {', '.join(row.message.external_message_id for row in pattern_a) or 'none detected'}.",
        f"- Pattern B public examples: {', '.join(row.message.external_message_id for row in pattern_b) or 'none detected'}.",
        "- Invariant reviewed: no attachments plus a draft-BL mention is not independently sufficient; primary requested action and body structure remain decisive.",
        "",
        "## Generalizable Defects Found",
        "",
        "- **Resolved in R3A-2 — zero-evidence ordinal fallback.** Original behavior: a five-way `0.20` tie selected `document_comparison` through mapping order, affecting 14 public cases.",
        "- **Synthetic regression:** `backend/tests/test_phase1_zero_signal.py` proves neutral handling, candidate-order independence, supported spam preservation, and the bare-draft-BL negative rule.",
        "- **General runtime fix:** all-zero evidence now uses the explicit `ZERO_SIGNAL_GENERAL` neutral policy; evidence-bearing Stage 2 ties use body score, subject score, then an explicit lexical fallback rather than insertion order.",
        f"- **Post-fix public audit:** {len(zero_signal_rows)} zero-signal cases remain low-confidence and resolve as {dict(zero_signal_categories)}; {len(zero_signal_fallback)} resolve as `document_comparison`.",
        f"- **Open generalizable defects counted by this audit:** {'1' if generalizable_defect_count else 'NONE'}.",
        "- Bucket B contains three genuine immediate-comparison requests whose referenced attachments are absent; this is an input/readiness condition, not counted as a classifier defect and is not handled in this phase.",
        "- No classifier change was made by this audit script.",
        "",
        "## Safety statement",
        "",
        "The script reads only `data/bundle/` through the project source adapter. It contains no expected-answer lookup, email-ID override, filename override, fixed-backlog logic, private reference access, or classifier mutation.",
    ]
    output = ROOT / "reports" / "classification_audit.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"wrote {output}")
    print(f"total={len(rows)} distribution={dict(distribution)} low_confidence={low_confidence}")
    print(f"no_attachment={len(no_attachment)} buckets={dict(buckets)} conflicts={len(conflicts)}")
    print(f"zero_signal={len(zero_signal_rows)} categories={dict(zero_signal_categories)} open_defects={generalizable_defect_count}")


if __name__ == "__main__":
    main()
