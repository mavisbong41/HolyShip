import type React from "react";
import {
  categoryLabels,
  fieldStatusLabels,
  readinessLabels,
  statusLabels,
} from "../lib/labels";
import type { ComparisonReadiness, FieldStatus, ProcessingStatus, ProductCategory } from "../types/product";

type BadgeTone = "neutral" | "good" | "warn" | "bad" | "orange" | "muted";

function resolveTone(value: string): BadgeTone {
  if (value === "FAILED") return "bad";
  if (value === "BLOCKED") return "warn";
  if (value === "AWAITING_DOCUMENTS" || value === "UNRESOLVED") return "warn";
  if (value === "COMPLETED" || value === "MATCH") return "good";
  if (value === "MISMATCH") return "bad";
  if (value === "document_comparison") return "orange";
  return "neutral";
}

function resolveLabel(value: string): string {
  if (value in statusLabels) return statusLabels[value as ProcessingStatus];
  if (value in categoryLabels) return categoryLabels[value as ProductCategory];
  if (value in readinessLabels) return readinessLabels[value as ComparisonReadiness];
  if (value in fieldStatusLabels) return fieldStatusLabels[value as FieldStatus];
  return value.replaceAll("_", " ");
}

export function StatusBadge({
  value,
  tone,
}: {
  value: string | null | undefined;
  tone?: BadgeTone;
}): React.ReactElement {
  if (!value) return <span className="badge badge-muted">Not set</span>;
  const t = tone ?? resolveTone(value);
  return <span className={`badge badge-${t}`}>{resolveLabel(value)}</span>;
}
