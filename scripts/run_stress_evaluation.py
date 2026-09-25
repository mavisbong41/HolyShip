from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.classification.models import HUMAN_REVIEW, ClassificationInput
from backend.app.classification.pipeline import classify_email
from backend.app.documents.models import DocumentFormat, DocumentType, UnifiedDocument
from backend.app.documents.router import DocumentRouter
from backend.app.extraction.extractor import DeterministicDocumentExtractor
from backend.app.comparison.models import FieldComparisonStatus
from backend.app.comparison.service import ComparisonService
from backend.app.ingestion.models import AttachmentMetadata
from scripts.stress_metrics import FIELDS, classification_metrics, discrepancy_metrics, binary_metrics, error_counts

DATASET = ROOT / "evaluation" / "stress_test" / "v1"
REPORTS = ROOT / "reports" / "latest"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dataset_hash() -> str:
    digest = hashlib.sha256()
    for path in (DATASET / "manifest.json", DATASET / "cases" / "cases.json", DATASET / "ground_truth.json"):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def validate_dataset(cases: list[dict], truth: dict[str, dict]) -> None:
    ids = [case["case_id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate case_id in stress dataset")
    if len(ids) != 40:
        raise SystemExit(f"expected 40 cases, found {len(ids)}")
    if set(ids) != set(truth):
        raise SystemExit("fixture and ground-truth case IDs differ")
    allowed = {"document_comparison", "new_si_request", "invoice_query", "general_message", "spam"}
    for case_id, label in truth.items():
        if label.get("expected_category") not in allowed:
            raise SystemExit(f"unsupported expected category for {case_id}")
        if label.get("should_escalate") not in (True, False):
            raise SystemExit(f"missing should_escalate for {case_id}")
        if "expected_mismatched_fields" in label and not set(label["expected_mismatched_fields"]) <= set(FIELDS):
            raise SystemExit(f"unsupported comparison field for {case_id}")


def leakage_scan() -> str:
    """Production application code must not know this benchmark's answers."""
    forbidden = ("STRESS-CLS-", "STRESS-CMP-", "STRESS-ESC-", "ground_truth.json", "expected_mismatched_fields", "should_escalate")
    offenders: list[str] = []
    for path in (ROOT / "backend" / "app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            if marker in text:
                offenders.append(f"{path.relative_to(ROOT)}:{marker}")
    if offenders:
        raise SystemExit("production leakage detected: " + ", ".join(offenders))
    return "PASS"


def doc_text(values: dict[str, Any], role: str, style: str | None = None, extra: dict[str, Any] | None = None) -> str:
    if style == "bilingual":
        labels = {"shipper":"Shipper (Principal or Seller) (发货人)", "consignee":"Consignee (收货人)", "notify_party":"Notify Party (通知方)", "port_of_loading":"Port of Loading (POL) (装货港)", "port_of_discharge":"Port of Discharge (POD) (卸货港)", "container_count":"Container Count (集装箱数量)", "gross_weight_kg":"Gross Wt (kgs) (毛重 KGS)"}
    else:
        labels = {"shipper":"Shipper", "consignee":"Consignee", "notify_party":"Notify Party", "port_of_loading":"POL", "port_of_discharge":"POD", "container_count":"Container Count", "gross_weight_kg":"Gross Weight"}
    lines = ["SHIPPING INSTRUCTION" if role == "SI" else "DRAFT BILL OF LADING"]
    if style == "order_consignee" and role == "DRAFT_BL":
        lines.append(f"To the Order of: {values['consignee']}")
        fields_to_write = [field for field in FIELDS if field != "consignee"]
    else:
        fields_to_write = list(FIELDS)
    for field in fields_to_write:
        value = values.get(field)
        if value is not None:
            lines.append(f"{labels[field]}: {value}")
    if extra and extra.get("net_weight"):
        lines.append(f"NET WEIGHT: {extra['net_weight']}")
    for value in (extra or {}).get("extra_consignees", []):
        lines.append(f"Consignee: {value}")
    return "\n".join(lines)


def make_documents(case: dict, base: dict[str, Any]) -> tuple[list[AttachmentMetadata], dict[str, UnifiedDocument]]:
    kind = case.get("document_kind")
    filenames = case.get("attachments", [])
    if kind == "wrong":
        texts = {filenames[0]: "COMMERCIAL INVOICE\nInvoice number: INV-1"}
    elif kind == "unreadable":
        texts = {filenames[0]: ""}
    else:
        si_values = dict(base); si_values.update(case.get("si_overrides", {}))
        bl_values = dict(base); bl_values.update(case.get("bl_overrides", {}))
        texts = {}
        if kind != "multiple_si":
            for name in filenames:
                if "si" in name.lower() and not name.lower().startswith("si2"):
                    texts[name] = doc_text(si_values, "SI", case.get("label_style"))
                elif "bl" in name.lower():
                    texts[name] = doc_text(bl_values, "DRAFT_BL", case.get("label_style"), case.get("bl_overrides"))
                else:
                    texts[name] = doc_text(base, "SI")
        else:
            texts = {"si1.txt": doc_text(base, "SI"), "si2.txt": doc_text(base, "SI"), "bl.txt": doc_text(base, "DRAFT_BL")}
    attachments = [AttachmentMetadata(filename=name, source_reference=f"{case['case_id']}::{name}", content_type=None) for name in filenames]
    documents: dict[str, UnifiedDocument] = {}
    for name, text in texts.items():
        suffix = Path(name).suffix.lower()
        fmt = {".pdf": DocumentFormat.PDF_TEXT, ".xlsx": DocumentFormat.XLSX, ".docx": DocumentFormat.DOCX}.get(suffix, DocumentFormat.PLAIN_TEXT)
        status = "UNREADABLE" if kind == "unreadable" else "EXTRACTED"
        documents[name] = UnifiedDocument(raw_text=text, format=fmt, filename=name, source_reference=f"{case['case_id']}::{name}", extraction_status=status, document_type=DocumentType.UNKNOWN)
    return attachments, documents


def run_case(case: dict, base: dict[str, Any]) -> dict[str, Any]:
    attachments, documents = make_documents(case, base)
    email = ClassificationInput(external_message_id=case["case_id"], subject=case["subject"], body=case["body"], attachment_filenames=case["attachments"], attachment_count=len(case["attachments"]))
    classification = classify_email(email)
    result: dict[str, Any] = {"case_id": case["case_id"], "category": classification.category, "readiness": classification.comparison_readiness, "classification_reason": classification.reason, "classification_evidence": classification.evidence_summary, "escalate": classification.resolved_at_stage == HUMAN_REVIEW}
    if classification.category != "document_comparison" or classification.comparison_readiness != "READY_FOR_COMPARISON":
        result["escalation_reason"] = "classification_or_readiness"
        return result
    router = DocumentRouter()
    routed = router.route_attachments(attachments, {att.source_reference: documents[att.filename].raw_text for att in attachments if att.filename in documents})
    result["route_reason"] = routed.human_review_reason_code
    result["escalate"] = result["escalate"] or routed.human_review_required
    if routed.human_review_required or not routed.si_attachment or not routed.bl_attachment:
        result["escalation_reason"] = routed.human_review_reason_code
        return result
    si_doc = documents[routed.si_attachment.filename]; si_doc.document_type = DocumentType.SI
    bl_doc = documents[routed.bl_attachment.filename]; bl_doc.document_type = DocumentType.DRAFT_BL
    if si_doc.extraction_status == "UNREADABLE" or bl_doc.extraction_status == "UNREADABLE":
        result["escalate"] = True; result["escalation_reason"] = "UNREADABLE_DOCUMENT"; return result
    extractor = DeterministicDocumentExtractor()
    comparison = ComparisonService().compare(extractor.extract(si_doc), extractor.extract(bl_doc))
    statuses = {field.value: item.status.value for field, item in comparison.fields.items()}
    result["fields"] = statuses
    result["overall_comparison"] = "UNRESOLVED" if any(value == "UNRESOLVED" for value in statuses.values()) else ("MISMATCH" if any(value == "MISMATCH" for value in statuses.values()) else "MATCH")
    result["mismatched_fields"] = [field for field, value in statuses.items() if value == "MISMATCH"]
    result["unresolved_fields"] = [field for field, value in statuses.items() if value == "UNRESOLVED"]
    result["escalate"] = result["escalate"] or bool(result["unresolved_fields"])
    result["escalation_reason"] = "UNRESOLVED_COMPARISON" if result["unresolved_fields"] else None
    return result


def render_markdown(report: dict[str, Any]) -> str:
    c = report["classification"]; d = report["discrepancy"]["field_level"]["overall"]; e = report["escalation"]
    lines = ["# HolyShip Independent Labeled Stress Test", "", "## Evaluation Design", "", f"Frozen team-authored dataset `{report['dataset']['version']}` with {report['dataset']['case_count']} cases. Ground truth was joined only after processing. This is not official organizer accuracy.", "", "## Dataset Composition", "", "| Scenario | Cases |", "|---|---:|", *[f"| {key} | {value} |" for key, value in report["dataset"]["composition"].items()], "", "## Ground-Truth Integrity", "", f"- SHA-256: `{report['dataset']['sha256']}`", f"- Frozen before execution: **{report['dataset']['frozen_before_execution']}**", f"- Leakage scan: **{report['integrity']['leakage_scan']}**", "", "## Classification Results", "", f"- Accuracy: {c['accuracy']:.3f}; macro F1: {c['macro']['f1']:.3f}; weighted F1: {c['weighted']['f1']:.3f}", "", "```json", json.dumps(c["confusion_matrix"], indent=2), "```", "", "## Discrepancy Detection Results", "", f"- Field-level TP/FP/TN/FN: {d['true_positive']}/{d['false_positive']}/{d['true_negative']}/{d['false_negative']}", f"- Precision/Recall/F1: {d['precision']}/{d['recall']}/{d['f1']}", f"- Ground-truth unresolved cases: {report['discrepancy']['case_unresolved_ground_truth']}; unresolved predictions: {report['discrepancy']['unresolved_predictions']}", "", "## Human Review Escalation Results", "", f"- TP/FP/TN/FN: {e['true_positive']}/{e['false_positive']}/{e['true_negative']}/{e['false_negative']}", f"- Precision/Recall/F1: {e['precision']}/{e['recall']}/{e['f1']}", "", "## Representative Errors", ""]
    if report["errors"]:
        lines.extend(f"- `{item['case_id']}`: {', '.join(item['error_types'])} — {item['reason']}" for item in report["errors"])
    else:
        lines.append("No errors recorded.")
    lines += ["", "## Interpretation", "", "Primary results use all frozen cases. Definite MISMATCH is not itself treated as a Human Review requirement; only uncertainty, missing/wrong/unreadable evidence, or unresolved routing escalates.", "", "## Limitations", "", "Team-authored sample of 40 constructed cases; not organizer labels. The harness exercises the deterministic in-process production boundaries and does not claim live Gemini/OCR performance.", "", "## Presentation Block", "", f"HolyShip Independent Labeled Stress Test\\nN = {report['dataset']['case_count']} frozen cases\\n\\nClassification\\nAccuracy: {c['accuracy']:.1%}\\nMacro F1: {c['macro']['f1']:.3f}\\n\\nDiscrepancy Detection\\nPrecision: {d['precision']:.3f}\\nRecall: {d['recall']:.3f}\\nF1: {d['f1']:.3f}\\n\\nHuman Review Escalation\\nPrecision: {e['precision']:.3f}\\nRecall: {e['recall']:.3f}\\nF1: {e['f1']:.3f}\\n\\nUnsafe confident errors: {report['safety']['unsafe_confident_errors']}\\nCorrect safe abstentions: {report['safety']['correct_safe_abstentions']}" ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze", action="store_true", help="write the dataset fingerprint if it does not exist")
    args = parser.parse_args()
    manifest = load_json(DATASET / "manifest.json"); raw_cases = load_json(DATASET / "cases" / "cases.json"); raw_truth = load_json(DATASET / "ground_truth.json")
    cases = raw_cases["cases"]; truth = {row["case_id"]: row for row in raw_truth["cases"]}; validate_dataset(cases, truth)
    fingerprint = dataset_hash(); frozen_path = DATASET / "frozen_sha256.txt"
    if args.freeze and not frozen_path.exists(): frozen_path.write_text(fingerprint + "\n", encoding="utf-8")
    if not frozen_path.exists(): raise SystemExit("dataset is not frozen; run with --freeze before evaluation")
    if frozen_path.read_text(encoding="utf-8").strip() != fingerprint: raise SystemExit("frozen stress-test files changed; create a new dataset version")
    leakage_result = leakage_scan()
    predictions = [run_case(case, raw_cases["base_values"]) for case in cases]
    by_id = {item["case_id"]: item for item in predictions}
    classification_rows = [(truth[item["case_id"]]["expected_category"], item["category"]) for item in predictions]
    c_metrics = classification_metrics(classification_rows)
    discrepancy_rows = []
    errors = []
    safe_abstentions = 0; unsafe_confident = 0; unnecessary_abstentions = 0
    for item in predictions:
        label = truth[item["case_id"]]
        if "expected_overall_comparison" in label:
            discrepancy_rows.append({"expected": label["expected_overall_comparison"], "expected_mismatched_fields": label.get("expected_mismatched_fields", []), "predicted": item.get("fields", {})})
            if label["expected_overall_comparison"] == "UNRESOLVED" and item.get("overall_comparison") == "UNRESOLVED": safe_abstentions += 1
            if label["expected_overall_comparison"] == "UNRESOLVED" and item.get("overall_comparison") in ("MATCH", "MISMATCH"): unsafe_confident += 1
            if label["expected_overall_comparison"] != "UNRESOLVED" and item.get("overall_comparison") == "UNRESOLVED": unnecessary_abstentions += 1
        error_types = []
        if label["expected_category"] != item["category"]: error_types.append("classification signal ambiguity")
        if label.get("expected_readiness") and label["expected_readiness"] != item.get("readiness"): error_types.append("readiness interpretation")
        if "expected_overall_comparison" in label and label["expected_overall_comparison"] != item.get("overall_comparison"): error_types.append("extraction or normalization")
        if label["should_escalate"] != item.get("escalate", False): error_types.append("missed escalation" if label["should_escalate"] else "unnecessary escalation")
        if error_types: errors.append({"case_id": item["case_id"], "error_types": error_types, "reason": label["ground_truth_reason"]})
    d_metrics = discrepancy_metrics(discrepancy_rows)
    escalation_rows = [(truth[item["case_id"]]["should_escalate"], item.get("escalate", False)) for item in predictions]
    report = {"dataset":{"name":manifest["dataset_name"],"version":manifest["dataset_version"],"case_count":len(cases),"sha256":fingerprint,"frozen_before_execution":True,"execution_timestamp":datetime.now(timezone.utc).isoformat(),"git_commit":os.popen("git rev-parse HEAD 2>NUL").read().strip() or None,"composition":{"classification/readiness":10,"formatting-equivalent comparisons":3,"single-field discrepancies":7,"multi-field discrepancies":3,"ambiguous/missing evidence":3,"wrong/missing/unreadable documents":5,"structured/readable document cases":3}},"integrity":{"leakage_scan":leakage_result,"prediction_case_count":len(predictions)},"classification":c_metrics,"discrepancy":d_metrics,"escalation":binary_metrics(escalation_rows),"errors":errors,"error_counts":error_counts(errors),"safety":{"unresolved_predictions":sum(1 for item in predictions if item.get("overall_comparison")=="UNRESOLVED"),"correct_safe_abstentions":safe_abstentions,"unnecessary_abstentions":unnecessary_abstentions,"unsafe_confident_errors":unsafe_confident}}
    REPORTS.mkdir(parents=True, exist_ok=True); (REPORTS / "stress_test_metrics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8"); (REPORTS / "stress_test_metrics.md").write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"dataset_sha256": fingerprint, "cases": len(cases), "classification_macro_f1": c_metrics["macro"]["f1"], "discrepancy_f1": d_metrics["field_level"]["overall"]["f1"], "escalation_f1": report["escalation"]["f1"], "errors": len(errors)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
