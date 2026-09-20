import type {
  CanonicalField,
  ComparisonReadiness,
  FieldStatus,
  ProcessingStatus,
  ProductCategory,
} from "../api/types";

export const categoryLabels: Record<ProductCategory, string> = {
  document_comparison: "Document Comparison",
  new_si_request: "New Shipping Instruction",
  invoice_query: "Invoice Query",
  general_message: "General Message",
  spam: "Spam",
};

export const statusLabels: Record<ProcessingStatus, string> = {
  NEW: "New",
  QUEUED: "Queued",
  CLASSIFYING: "Classifying",
  CLASSIFIED: "Classified",
  AWAITING_DOCUMENTS: "Awaiting Documents",
  RETRIEVING_ATTACHMENTS: "Retrieving Attachments",
  EXTRACTING: "Extracting",
  COMPARING: "Comparing",
  COMPLETED: "Completed",
  BLOCKED: "Needs Attention",
  FAILED: "Processing Failed",
};

export const readinessLabels: Record<ComparisonReadiness, string> = {
  READY_FOR_COMPARISON: "Ready for Comparison",
  AWAITING_DOCUMENTS: "Awaiting Documents",
  UNRESOLVED: "Readiness Unresolved",
};

export const fieldLabels: Record<CanonicalField, string> = {
  shipper: "Shipper",
  consignee: "Consignee",
  notify_party: "Notify Party",
  port_of_loading: "Port of Loading",
  port_of_discharge: "Port of Discharge",
  container_count: "Container Count",
  gross_weight_kg: "Gross Weight",
};

export const fieldStatusLabels: Record<FieldStatus, string> = {
  MATCH: "Match",
  MISMATCH: "Mismatch",
  UNRESOLVED: "Unresolved",
};

export function labelForField(field: string): string {
  return field in fieldLabels
    ? fieldLabels[field as CanonicalField]
    : field.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function formatDate(value: string | null): string {
  if (!value) {
    return "No timestamp";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "Missing";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}
