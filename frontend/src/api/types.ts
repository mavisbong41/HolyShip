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
export type LoadState = "idle" | "loading" | "ready" | "error";
export type EmailLifecycleStatus = "ACTIVE" | "DELETED" | "ARCHIVED";
export type OutlookReadState = "READ" | "UNREAD" | "UNKNOWN";

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

export interface ProductValue {
  raw: unknown | null;
  canonical: unknown | null;
  normalized: unknown | null;
}

export interface ProductFieldComparison {
  field: CanonicalField | string;
  si: ProductValue;
  bl: ProductValue;
  status: FieldStatus;
  reason_code: string;
  evidence: ProductEvidence[];
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

export interface ProductAttachment {
  id: string;
  filename: string;
  content_type: string | null;
  external_attachment_id: string | null;
  retrieval_status: string;
  retrieval_reason_code: string | null;
  content_sha256: string | null;
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

export interface ProductTimelineEvent {
  id: string;
  old_status: string | null;
  new_status: ProcessingStatus | string;
  reason_code: string;
  created_at: string;
}

export interface ProductEmailLifecycle {
  lifecycle_status: EmailLifecycleStatus;
  outlook_read_state: OutlookReadState;
  outlook_categories: string[];
  outlook_folder_id: string | null;
  outlook_archived: boolean;
  last_outlook_sync_at: string | null;
  outlook_sync_error: string | null;
  deleted_at: string | null;
  restored_at: string | null;
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
  lifecycle?: ProductEmailLifecycle;
}

export interface ProductSyncStatus {
  total_emails: number;
  active_count: number;
  deleted_count: number;
  archived_count: number;
  unread_count: number;
  sync_error_count: number;
  last_outlook_sync_at?: string | null;
  last_sync_at?: string | null;
  healthy: boolean;
}

export interface OutlookReconcileRequest {
  email_id?: string;
  external_message_id?: string;
  lifecycle_status?: EmailLifecycleStatus | "RESTORED";
  outlook_read_state?: OutlookReadState;
  outlook_categories?: string[];
  outlook_folder_id?: string;
  outlook_archived?: boolean;
  outlook_sync_error?: string;
  actor_name?: string;
}

export interface EmailQueuePage {
  items: ProductEmailSummary[];
  total: number;
  skip: number;
  limit: number;
}

export interface ProductSummary {
  total_emails: number;
  status_counts: Partial<Record<ProcessingStatus, number>>;
  needs_review_count: number;
  comparison_ready_count: number;
  mismatch_count: number;
  confirmed_discrepancies_count?: number;
  unresolved_count: number;
  completed_count?: number;
  awaiting_documents_count?: number;
  human_review_open_count?: number;
  failed_count?: number;
  processing_count?: number;
  deleted_count?: number;
  unread_count?: number;
  sync_error_count?: number;
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
  workflow_identity?: string | null;
  source_comparison_id?: string | null;
  reviewer_name?: string | null;
  claimed_at?: string | null;
  resolution?: string | null;
  notes?: string | null;
  confidence: number | null;
  evidence: ProductEvidence[];
  comparison: ProductComparison | null;
  priority: "HIGH" | "MEDIUM" | "LOW";
  presentation_title: string | null;
  human_explanation: string | null;
  affected_fields: string[];
  affected_area: string | null;
  suggested_action: string | null;
  semantic_style: string | null;
  canonical_reason?: string | null;
  trigger?: string | null;
  stage?: string | null;
  age_minutes: number;
  body?: string | null;
  documents?: ProductDocument[];
  overrides?: ProductReviewOverride[];
  actions?: ProductReviewAction[];
  resolutions: ProductResolution[];
  ai_suggestions?: ProductAISuggestion[];
  created_at: string;
  updated_at?: string | null;
  resolved_at?: string | null;
}

export interface ProductReviewOverride {
  id: string;
  document_side: "SI" | "BL";
  field: CanonicalField | string;
  original_field_id: string;
  corrected_value: unknown;
  corrected_canonical_value: unknown;
  reviewer_name: string | null;
  note: string | null;
  active: boolean;
  supersedes_override_id: string | null;
  ai_suggestion_id?: string | null;
  created_at: string;
}

export type AISuggestionMode = "EXPLANATION_ONLY" | "ACTIONABLE_SUGGESTION" | "INSUFFICIENT_EVIDENCE";
export type AISuggestionStatus = "PENDING" | "ACCEPTED" | "EDITED_APPLIED" | "DISMISSED";

export interface AISuggestionPayload {
  action: "FIELD_OVERRIDE";
  document_side: "SI" | "BL";
  field: CanonicalField | string;
  current_value: string;
  suggested_value: string;
  confidence: number;
  reason: string;
  evidence_refs: string[];
}

export interface ProductAISuggestion {
  id: string;
  human_review_case_id: string;
  mode: AISuggestionMode;
  message: string;
  document_side: "SI" | "BL" | null;
  field: CanonicalField | string | null;
  current_value: string | null;
  suggested_value: string | null;
  confidence: number | null;
  reason: string | null;
  evidence_refs: string[];
  provider_name: string;
  provider_model: string;
  status: AISuggestionStatus;
  created_at: string;
}

export interface AIAssistantResponse {
  message: string;
  mode: AISuggestionMode;
  suggestion?: AISuggestionPayload | null;
  suggestion_id?: string | null;
  provider_name: string;
  provider_model: string;
}

export interface ProductReviewAction {
  id: string;
  action: string;
  actor_name: string | null;
  details: Record<string, unknown>;
  created_at: string;
}

export interface HumanReviewPage {
  items: ProductReview[];
  total: number;
  skip: number;
  limit: number;
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

export interface ProductEvent {
  event: "EMAIL_PROCESSING_UPDATED";
  email_id: string;
  status: ProcessingStatus;
  category: ProductCategory | null;
  mismatch_found: boolean;
  updated_at: string;
  reason_code: string;
}

export interface QueueFilters {
  status?: ProcessingStatus | "";
  category?: ProductCategory | "";
  comparison_readiness?: ComparisonReadiness | "";
  needs_review?: "true" | "false" | "";
  review_status?: "OPEN" | "IN_REVIEW" | "RESOLVED" | "DISMISSED" | "";
  comparison_state?: "COMPLETED" | "BLOCKED" | "";
  has_mismatch?: "true" | "false" | "";
  has_unresolved?: "true" | "false" | "";
  is_processing?: "true" | "false" | "";
  lifecycle_status?: EmailLifecycleStatus | "";
  search?: string;
  skip?: number;
  limit?: number;
  sort?: "newest" | "oldest" | "priority" | "status" | "category" | "last_updated";
}

export interface ProductReviewPlanItem {
  id: string;
  ai_suggestion_id: string | null;
  document_side: "SI" | "BL";
  field: CanonicalField | string;
  current_value: unknown;
  proposed_value: unknown;
  human_edited_value: unknown;
  reason: string;
  confidence: number | null;
  action: string;
  status: "PROPOSED" | "APPROVED" | "EDITED" | "REJECTED" | "APPLIED";
  created_at: string;
  updated_at: string;
}

export interface ProductReviewPlan {
  id: string;
  review_case_id: string;
  status: "DRAFT" | "CONFIRMED" | "APPLIED" | "APPLY_FAILED" | "CANCELLED";
  created_by: string | null;
  confirmed_at: string | null;
  confirmed_by: string | null;
  applied_comparison_id: string | null;
  error_message: string | null;
  items: ProductReviewPlanItem[];
  created_at: string;
  updated_at: string;
}

export interface ReviewQueueFilters {
  status?: "OPEN" | "IN_REVIEW" | "RESOLVED" | "DISMISSED" | "";
  reason?: string;
  reviewer?: string;
  search?: string;
  active_only?: boolean;
  sort?: "priority" | "age" | "oldest" | "newest";
  skip?: number;
  limit?: number;
}

export interface InitialSyncResult {
  job_id: string;
  total: number;
  ingested: number;
  skipped: number;
  failed: number;
  progress: {
    total: number;
    processed: number;
    percent: number;
    ingested: number;
    skipped: number;
    failed: number;
  };
}

export interface HumanReviewAnalytics {
  open_count: number;
  in_review_count: number;
  resolved_count: number;
  dismissed_count: number;
  resolved_today_count: number;
  average_open_age_minutes: number | null;
  priority_distribution: Record<string, number>;
  reason_distribution: Record<string, number>;
  most_reviewed_fields: Record<string, number>;
  most_corrected_fields: Record<string, number>;
  correction_reasons: Record<string, number>;
}

export type DiscrepancyStatus = "OPEN" | "ACKNOWLEDGED" | "RESOLVED";

export interface ProductDiscrepancySummary {
  id: string;
  email_id: string;
  external_message_id: string;
  subject: string;
  sender: string | null;
  received_at: string | null;
  created_at: string;
  mismatch_count: number;
  mismatched_fields: string[];
  resolution_status: DiscrepancyStatus;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  resolved_at: string | null;
  resolved_by: string | null;
  resolution_notes: string | null;
  comparison_state: string;
}

export interface DiscrepancyPage {
  items: ProductDiscrepancySummary[];
  total: number;
  open_count: number;
  acknowledged_count: number;
  resolved_count: number;
  skip: number;
  limit: number;
}

export interface DiscrepancyOverrideOut {
  id: string;
  comparison_result_id: string;
  document_side: "SI" | "BL";
  field_name: string;
  original_field_id: string;
  corrected_value: unknown;
  corrected_canonical_value: unknown;
  reviewer_name: string | null;
  note: string | null;
  active: boolean;
  created_at: string;
}

export interface ProductDiscrepancyDetail {
  discrepancy: ProductDiscrepancySummary;
  email: ProductEmailSummary;
  email_body: string;
  comparison: ProductComparison;
  mismatched_fields_detail: ProductFieldComparison[];
  attachments: ProductAttachment[];
  documents: ProductDocument[];
  overrides: DiscrepancyOverrideOut[];
  timeline: ProductTimelineEvent[];
}

export interface DiscrepancyQueueFilters {
  status?: DiscrepancyStatus | "";
  search?: string;
  skip?: number;
  limit?: number;
}
