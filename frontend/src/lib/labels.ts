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
  AWAITING_DOCUMENTS: "Waiting for Documents",
  UNRESOLVED: "Document readiness unclear",
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
  COMPARISON_UNRESOLVED: "Missing Required Value",
  COMPARISON_MISMATCH: "Field Mismatch",
  CLASSIFICATION_UNRESOLVED: "Email Type Unclear",
  DOCUMENT_ROLE_UNRESOLVED: "Wrong Document Type",
  WRONG_DOCUMENT_TYPE: "Wrong Document Type",
  MISSING_REQUIRED_ATTACHMENT: "Missing Attachment",
  MISSING_ATTACHMENT: "Missing Attachment",
  UNREADABLE_ATTACHMENT: "Unreadable Document",
  UNSUPPORTED_ATTACHMENT: "Unreadable Document",
  CORRUPTED_ATTACHMENT: "Unreadable Document",
  MULTIPLE_CANDIDATES: "Wrong Document Type",
  READINESS_UNRESOLVED: "Missing Attachment",
  DOCUMENT_FIELD_EXTRACTION_FAILED: "Document Extraction Failed",
  NOT_ACTIONABLE: "Not Actionable",
  STAGE2_UNRESOLVED: "Historical Review Record",
  OCR_BACKEND_UNAVAILABLE: "Document Processing Unavailable",
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

export function displayLabel(value?: string | null): string {
  if (!value) return "—";
  if (value in statusLabels) return statusLabels[value as ProcessingStatus];
  if (value in categoryLabels) return categoryLabels[value as ProductCategory];
  if (value in fieldStatusLabels) return fieldStatusLabels[value as FieldStatus];
  if (value in readinessLabels) return readinessLabels[value as ComparisonReadiness];
  if (value in reviewStatusLabels) return reviewStatusLabels[value];
  if (value in reasonLabels) return reasonLabels[value];
  if (value in reviewActionLabels) return reviewActionLabels[value];
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function labelForField(field?: string | null): string {
  if (!field) return "—";
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
