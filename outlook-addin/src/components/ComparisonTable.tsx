import type React from "react";
import { canonicalFields } from "../types/product";
import type { ProductComparison } from "../types/product";
import { displayValue, labelForField } from "../lib/labels";

function fieldRowClass(status: string): string {
  if (status === "MISMATCH") return "row-mismatch";
  if (status === "UNRESOLVED") return "row-unresolved";
  if (status === "MATCH") return "row-match";
  return "";
}

function fieldStatusBadge(status: string): React.ReactElement {
  if (status === "MATCH") {
    return <span className="badge badge-good" aria-label="Match">Match</span>;
  }
  if (status === "MISMATCH") {
    return <span className="badge badge-bad" aria-label="Mismatch">Mismatch</span>;
  }
  if (status === "UNRESOLVED") {
    return <span className="badge badge-warn" aria-label="Unresolved">Unresolved</span>;
  }
  return <span className="badge badge-muted">{status}</span>;
}

export function ComparisonTable({
  comparison,
  onCorrectField,
}: {
  comparison: ProductComparison;
  onCorrectField?: (side: "SI" | "BL", field: string, currentValue: unknown) => void;
}): React.ReactElement {
  // Index fields from the backend by canonical field name
  const fieldMap = new Map(comparison.fields.map((f) => [f.field, f]));

  return (
    <div className="comparison-cards" role="list" aria-label="SI vs BL field comparison">
      {canonicalFields.map((field) => {
        const row = fieldMap.get(field);
        const status = row?.status ?? "UNRESOLVED";
        const siVal = row?.si?.effective_value ?? row?.si?.human_override_value ?? row?.si?.canonical ?? row?.si?.raw ?? null;
        const blVal = row?.bl?.effective_value ?? row?.bl?.human_override_value ?? row?.bl?.canonical ?? row?.bl?.raw ?? null;
        const siMissing = siVal === null || siVal === undefined || siVal === "";
        const blMissing = blVal === null || blVal === undefined || blVal === "";
        const hasSiOverride = row?.si?.human_override_value !== undefined && row?.si?.human_override_value !== null;
        const hasBlOverride = row?.bl?.human_override_value !== undefined && row?.bl?.human_override_value !== null;

        return (
          <article key={field} className={`comparison-field-card ${fieldRowClass(status)}`} role="listitem">
            <div className="comparison-field-heading">
              <strong>{labelForField(field)}</strong>
              {fieldStatusBadge(status)}
            </div>
            <dl className="comparison-values">
              <div>
                <dt>SI</dt>
                <dd className={`${siMissing ? "value-missing" : status === "MISMATCH" ? "value-mismatch" : ""}`}>
                  {displayValue(siVal)}
                  {hasSiOverride && (
                    <span style={{ display: "block", fontSize: "10.5px", color: "#16a34a" }}>
                      Override (Raw: {displayValue(row?.si?.raw)})
                    </span>
                  )}
                </dd>
              </div>
              <div>
                <dt>Draft BL</dt>
                <dd className={`${blMissing ? "value-missing" : status === "MISMATCH" ? "value-mismatch" : ""}`}>
                  {displayValue(blVal)}
                  {hasBlOverride && (
                    <span style={{ display: "block", fontSize: "10.5px", color: "#16a34a" }}>
                      Override (Raw: {displayValue(row?.bl?.raw)})
                    </span>
                  )}
                </dd>
              </div>
            </dl>
            {onCorrectField && (
              <div style={{ display: "flex", gap: "6px", marginTop: "6px" }}>
                <button
                  type="button"
                  className="btn-secondary"
                  style={{ fontSize: "11px", padding: "2px 8px" }}
                  onClick={() => onCorrectField("BL", field, blVal)}
                >
                  Correct BL
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  style={{ fontSize: "11px", padding: "2px 8px" }}
                  onClick={() => onCorrectField("SI", field, siVal)}
                >
                  Correct SI
                </button>
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}
