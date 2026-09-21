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
}: {
  comparison: ProductComparison;
}): React.ReactElement {
  // Index fields from the backend by canonical field name
  const fieldMap = new Map(comparison.fields.map((f) => [f.field, f]));

  return (
    <div className="comparison-cards" role="list" aria-label="SI vs BL field comparison">
          {canonicalFields.map((field) => {
            const row = fieldMap.get(field);
            const status = row?.status ?? "UNRESOLVED";
            const siRaw = row?.si?.raw ?? row?.si?.canonical ?? null;
            const blRaw = row?.bl?.raw ?? row?.bl?.canonical ?? null;
            const siMissing = siRaw === null || siRaw === undefined || siRaw === "";
            const blMissing = blRaw === null || blRaw === undefined || blRaw === "";
            return (
              <article key={field} className={`comparison-field-card ${fieldRowClass(status)}`} role="listitem">
                <div className="comparison-field-heading">
                  <strong>{labelForField(field)}</strong>
                  {fieldStatusBadge(status)}
                </div>
                <dl className="comparison-values">
                  <div><dt>SI</dt><dd className={`${siMissing ? "value-missing" : status === "MISMATCH" ? "value-mismatch" : ""}`}>{displayValue(siRaw)}</dd></div>
                  <div><dt>Draft BL</dt><dd className={`${blMissing ? "value-missing" : status === "MISMATCH" ? "value-mismatch" : ""}`}>{displayValue(blRaw)}</dd></div>
                </dl>
              </article>
            );
          })}
    </div>
  );
}
