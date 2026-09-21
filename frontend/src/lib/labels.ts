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
  AWAITING_DOCUMENTS: "Waiting for Documents",
  RETRIEVING_ATTACHMENTS: "Retrieving Attachments",
  EXTRACTING: "Extracting",
  COMPARING: "Comparing",
  COMPLETED: "Completed",
  BLOCKED: "Needs Review",
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

export const reviewStatusLabels: Record<string, string> = {
  OPEN: "Needs Review",
  IN_REVIEW: "Being Reviewed",
  RESOLVED: "Review Completed",
  DISMISSED: "Review Dismissed",
};

export const reasonLabels: Record<string, string> = {
  COMPARISON_UNRESOLVED: "One or more document fields could not be verified",
  COMPARISON_MISMATCH: "The SI and BL contain different values",
  CLASSIFICATION_UNRESOLVED: "Email type unclear",
  DOCUMENT_ROLE_UNRESOLVED: "Document role unclear",
  WRONG_DOCUMENT_TYPE: "Wrong document type",
  MISSING_REQUIRED_ATTACHMENT: "Required shipping document is missing",
  UNREADABLE_ATTACHMENT: "Document could not be read reliably",
  UNSUPPORTED_ATTACHMENT: "Document format is unsupported",
  CORRUPTED_ATTACHMENT: "Document could not be read",
  MULTIPLE_CANDIDATES: "More than one document may match",
  READINESS_UNRESOLVED: "Document readiness unclear",
  DOCUMENT_FIELD_EXTRACTION_FAILED: "Document extraction failed",
  NOT_ACTIONABLE: "Not actionable",
};

export const reviewActionLabels: Record<string, string> = {
  CASE_CREATED: "Review case created",
  CASE_CLAIMED: "Review claimed",
  FIELD_OVERRIDE_ADDED: "Field correction added",
  FIELD_OVERRIDE_REPLACED: "Field correction replaced",
  RESOLVE_REQUESTED: "Resolve and recompare requested",
  RECOMPARISON_COMPLETED: "Recomparison completed",
  CASE_RESOLVED: "Review resolved",
  CASE_DISMISSED: "Review dismissed",
};

export type SemanticTone = "neutral" | "good" | "warn" | "bad" | "attention" | "info" | "muted";

export function semanticTone(value: string): SemanticTone {
  if (value === "FAILED" || value === "MISMATCH") return "bad";
  if (value === "AWAITING_DOCUMENTS") return "info";
  if (value === "UNRESOLVED") return "warn";
  if (value === "BLOCKED" || value === "OPEN" || value === "IN_REVIEW") return "attention";
  if (value === "COMPLETED" || value === "MATCH" || value === "RESOLVED") return "good";
  if (value === "DISMISSED") return "muted";
  return "neutral";
}

export function displayLabel(value: string): string {
  if (value in statusLabels) return statusLabels[value as ProcessingStatus];
  if (value in categoryLabels) return categoryLabels[value as ProductCategory];
  if (value in readinessLabels) return readinessLabels[value as ComparisonReadiness];
  if (value in fieldStatusLabels) return fieldStatusLabels[value as FieldStatus];
  if (value in reviewStatusLabels) return reviewStatusLabels[value];
  if (value in reasonLabels) return reasonLabels[value];
  if (value in reviewActionLabels) return reviewActionLabels[value];
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

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
