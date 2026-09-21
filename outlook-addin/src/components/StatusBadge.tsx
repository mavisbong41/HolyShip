import type React from "react";
import { displayLabel, semanticTone } from "../lib/labels";

type BadgeTone = "neutral" | "good" | "warn" | "bad" | "attention" | "info" | "orange" | "muted";

function resolveTone(value: string): BadgeTone {
  if (value === "document_comparison") return "orange";
  return semanticTone(value);
}

function resolveLabel(value: string): string {
  return displayLabel(value);
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
