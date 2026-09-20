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
    <div className="comparison-wrap">
      <table className="comparison-table" aria-label="SI vs BL field comparison">
        <thead>
          <tr>
            <th scope="col">Field</th>
            <th scope="col">SI</th>
            <th scope="col">Draft BL</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {canonicalFields.map((field) => {
            const row = fieldMap.get(field);
            const status = row?.status ?? "UNRESOLVED";
            const siRaw = row?.si?.raw ?? row?.si?.canonical ?? null;
            const blRaw = row?.bl?.raw ?? row?.bl?.canonical ?? null;
            const siMissing = siRaw === null || siRaw === undefined || siRaw === "";
            const blMissing = blRaw === null || blRaw === undefined || blRaw === "";
            return (
              <tr key={field} className={fieldRowClass(status)}>
                <td className="field-name-cell">{labelForField(field)}</td>
                <td
                  className={`value-cell ${siMissing ? "value-missing" : status === "MISMATCH" ? "value-mismatch" : ""}`}
                >
                  {displayValue(siRaw)}
                </td>
                <td
                  className={`value-cell ${blMissing ? "value-missing" : status === "MISMATCH" ? "value-mismatch" : ""}`}
                >
                  {displayValue(blRaw)}
                </td>
                <td>{fieldStatusBadge(status)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
