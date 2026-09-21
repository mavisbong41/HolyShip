// Shared canonical types — mirrors the Dashboard frontend types.
// Backend enum values are used verbatim; only presentation labels differ.

export const canonicalFields = [
  "shipper",
  "consignee",
  "notify_party",
  "port_of_loading",
  "port_of_discharge",
  "container_count",
  "gross_weight_kg",
] as const;

export type CanonicalField = (typeof canonicalFields)[number];

export type ProcessingStatus =
  | "NEW"
  | "QUEUED"
  | "CLASSIFYING"
  | "CLASSIFIED"
  | "AWAITING_DOCUMENTS"
  | "RETRIEVING_ATTACHMENTS"
  | "EXTRACTING"
  | "COMPARING"
  | "COMPLETED"
  | "BLOCKED"
  | "FAILED";

export type ProductCategory =
  | "document_comparison"
  | "new_si_request"
  | "invoice_query"
  | "general_message"
  | "spam";

export type ComparisonReadiness =
  | "READY_FOR_COMPARISON"
  | "AWAITING_DOCUMENTS"
  | "UNRESOLVED";

export type FieldStatus = "MATCH" | "MISMATCH" | "UNRESOLVED";
export type ComparisonState = "COMPLETED" | "BLOCKED";

export interface ProductValue {
  raw: unknown | null;
  canonical: unknown | null;
  normalized: unknown | null;
}

export interface ProductEvidence {
  document_id: string | null;
  document_role: string | null;
  attachment_id: string | null;
  filename: string | null;
  page: number | null;
  text_span: string | null;
  source_type: string | null;
  field: string | null;
  reason: string | null;
  details: Record<string, unknown>;
}

export interface ProductFieldComparison {
  field: CanonicalField | string;
  si: ProductValue;
  bl: ProductValue;
  status: FieldStatus;
  reason_code: string;
  evidence: ProductEvidence[];
}

export interface ProductComparison {
  state: ComparisonState;
  mismatch_found: boolean;
  mismatched_fields: string[];
  unresolved_fields: string[];
  reason_code: string;
  message: string;
  fields: ProductFieldComparison[];
}

export interface ProductClassification {
  category: ProductCategory;
  confidence: number;
  candidate_scores: Record<string, number>;
  reason: string;
  reason_code: string;
  evidence: ProductEvidence[];
  conflict_detected: boolean;
  resolved_at_stage: string;
  comparison_readiness: ComparisonReadiness | null;
  classifier_version: string;
  created_at: string;
}

export interface ProductEmailSummary {
  id: string;
  external_message_id: string;
  source_type: string;
  sender: string | null;
  subject: string;
  received_at: string | null;
  created_at: string;
  processing_status: ProcessingStatus;
  attachment_count: number;
  category: ProductCategory | null;
  classification_confidence: number | null;
  comparison_readiness: ComparisonReadiness | null;
  comparison_state: string | null;
  mismatch_count: number;
  unresolved_count: number;
  needs_review: boolean;
  review_id?: string | null;
  review_status: string | null;
  review_reason: string | null;
}

export interface ProductEmailDetail {
  email: ProductEmailSummary;
  body: string;
  recipients: string[];
  content_hash: string;
  attachments: ProductAttachment[];
  classification: ProductClassification | null;
  documents: ProductDocument[];
  comparison: ProductComparison | null;
  timeline: ProductTimelineEvent[];
  review: ProductReview[];
  resolutions: ProductResolution[];
}

export interface ProductAttachment {
  id: string;
  filename: string;
  content_type: string | null;
  external_attachment_id: string | null;
  retrieval_status: string;
  retrieval_reason_code: string | null;
  content_sha256: string | null;
}

export interface ProductExtractedField {
  field: CanonicalField | string;
  raw_label: string | null;
  raw_value: unknown | null;
  canonical_value: unknown | null;
  status: string;
  confidence: number;
  mapping_method: string | null;
  extraction_method: string | null;
  source_location: Record<string, unknown>;
  evidence: ProductEvidence[];
}

export interface ProductDocument {
  id: string;
  attachment_id: string | null;
  filename: string;
  role: string;
  format: string;
  source_reference: string;
  routing_outcome: string;
  role_confidence: number;
  role_evidence: Record<string, unknown>;
  validation_outcome: string;
  read_status: string | null;
  reader_used: string | null;
  extraction_quality: number | null;
  failure_reason: string | null;
  fields: ProductExtractedField[];
}

export interface ProductTimelineEvent {
  id: string;
  old_status: string | null;
  new_status: ProcessingStatus | string;
  reason_code: string;
  created_at: string;
}

export interface ProductResolution {
  attempted: boolean;
  purpose: string;
  field: string;
  accepted: boolean;
  confidence: number;
  reason: string;
  evidence: ProductEvidence[];
  provider_name: string | null;
  model_name: string | null;
  resolver_version: string | null;
}

export interface ProductReview {
  id: string;
  email_id: string;
  email: ProductEmailSummary | null;
  document_id: string | null;
  field: string | null;
  reason_code: string;
  reason_text: string;
  status: string;
  case_origin?: "LEGACY" | "ACTIVE";
  reviewer_name?: string | null;
  updated_at?: string | null;
  resolved_at?: string | null;
  confidence: number | null;
  evidence: ProductEvidence[];
  comparison: ProductComparison | null;
  resolutions: ProductResolution[];
  created_at: string;
}

export interface EmailQueuePage {
  items: ProductEmailSummary[];
  total: number;
  skip: number;
  limit: number;
}
