import type {
  ProductEmailDetail,
  ProductEmailSummary,
  ProductComparison,
  ProductClassification,
} from "../src/types/product";

const baseSummary: ProductEmailSummary = {
  id: "email-001",
  external_message_id: "<msg-001@example.com>",
  source_type: "dataset",
  sender: "shipper@acme.com",
  subject: "Draft BL for BKG-20240501 for checking",
  received_at: "2024-05-01T09:00:00Z",
  created_at: "2024-05-01T09:01:00Z",
  processing_status: "COMPLETED",
  attachment_count: 2,
  category: "document_comparison",
  classification_confidence: 0.93,
  comparison_readiness: "READY_FOR_COMPARISON",
  comparison_state: "COMPLETED",
  mismatch_count: 0,
  unresolved_count: 0,
  needs_review: false,
  review_status: null,
  review_reason: null,
};

const baseClassification: ProductClassification = {
  category: "document_comparison",
  confidence: 0.93,
  candidate_scores: { document_comparison: 0.93, new_si_request: 0.05 },
  reason: "Request to send draft BL for checking",
  reason_code: "DRAFT_BL_CHECK_REQUEST",
  evidence: [],
  conflict_detected: false,
  resolved_at_stage: "stage1",
  comparison_readiness: "READY_FOR_COMPARISON",
  classifier_version: "1.0",
  created_at: "2024-05-01T09:01:05Z",
};

const cleanComparison: ProductComparison = {
  state: "COMPLETED",
  mismatch_found: false,
  mismatched_fields: [],
  unresolved_fields: [],
  reason_code: "ALL_MATCH",
  message: "No mismatch detected.",
  fields: [
    {
      field: "shipper",
      si: { raw: "ACME Trading Ltd", canonical: "ACME Trading Ltd", normalized: "acme trading ltd" },
      bl: { raw: "ACME Trading Ltd", canonical: "ACME Trading Ltd", normalized: "acme trading ltd" },
      status: "MATCH",
      reason_code: "L0_MATCH",
      evidence: [],
    },
    {
      field: "consignee",
      si: { raw: "Buyer Corp Sdn Bhd", canonical: "Buyer Corp Sdn Bhd", normalized: "buyer corp sdn bhd" },
      bl: { raw: "Buyer Corp Sdn Bhd", canonical: "Buyer Corp Sdn Bhd", normalized: "buyer corp sdn bhd" },
      status: "MATCH",
      reason_code: "L0_MATCH",
      evidence: [],
    },
    {
      field: "notify_party",
      si: { raw: "Same as Consignee", canonical: "Same as Consignee", normalized: "same as consignee" },
      bl: { raw: "Same as Consignee", canonical: "Same as Consignee", normalized: "same as consignee" },
      status: "MATCH",
      reason_code: "L0_MATCH",
      evidence: [],
    },
    {
      field: "port_of_loading",
      si: { raw: "Port Klang, Malaysia", canonical: "Port Klang, Malaysia", normalized: "port klang malaysia" },
      bl: { raw: "Port Klang, Malaysia", canonical: "Port Klang, Malaysia", normalized: "port klang malaysia" },
      status: "MATCH",
      reason_code: "L0_MATCH",
      evidence: [],
    },
    {
      field: "port_of_discharge",
      si: { raw: "Tanjung Priok, Indonesia", canonical: "Tanjung Priok, Indonesia", normalized: "tanjung priok indonesia" },
      bl: { raw: "Tanjung Priok, Indonesia", canonical: "Tanjung Priok, Indonesia", normalized: "tanjung priok indonesia" },
      status: "MATCH",
      reason_code: "L0_MATCH",
      evidence: [],
    },
    {
      field: "container_count",
      si: { raw: "2 x 40'HC", canonical: 2, normalized: 2 },
      bl: { raw: "2 x 40'HC", canonical: 2, normalized: 2 },
      status: "MATCH",
      reason_code: "L0_MATCH",
      evidence: [],
    },
    {
      field: "gross_weight_kg",
      si: { raw: "22,000 KG", canonical: 22000, normalized: 22000 },
      bl: { raw: "22,000 KG", canonical: 22000, normalized: 22000 },
      status: "MATCH",
      reason_code: "L0_MATCH",
      evidence: [],
    },
  ],
};

const mismatchComparison: ProductComparison = {
  ...cleanComparison,
  mismatch_found: true,
  mismatched_fields: ["gross_weight_kg", "container_count"],
  unresolved_fields: ["notify_party"],
  reason_code: "MISMATCH_DETECTED",
  message: "2 fields mismatched, 1 unresolved.",
  fields: cleanComparison.fields.map((f) => {
    if (f.field === "gross_weight_kg") {
      return {
        ...f,
        bl: { raw: "24,500 KG", canonical: 24500, normalized: 24500 },
        status: "MISMATCH" as const,
        reason_code: "VALUE_DIFFERENT",
      };
    }
    if (f.field === "container_count") {
      return {
        ...f,
        bl: { raw: "3 x 40'HC", canonical: 3, normalized: 3 },
        status: "MISMATCH" as const,
        reason_code: "VALUE_DIFFERENT",
      };
    }
    if (f.field === "notify_party") {
      return {
        ...f,
        bl: { raw: null, canonical: null, normalized: null },
        status: "UNRESOLVED" as const,
        reason_code: "FIELD_MISSING_IN_BL",
      };
    }
    return f;
  }),
};

function makeDetail(
  overrides: Partial<ProductEmailSummary>,
  comparison: ProductComparison | null = cleanComparison,
): ProductEmailDetail {
  return {
    email: { ...baseSummary, ...overrides },
    body: "Please assist to send the draft BL for BKG-20240501 for checking.",
    recipients: ["ops@holyship.com"],
    content_hash: "sha256-abc123",
    attachments: [],
    classification: baseClassification,
    documents: [],
    comparison,
    timeline: [],
    review: [],
    resolutions: [],
  };
}

export const fixtures = {
  cleanMatch: makeDetail({}, cleanComparison),
  mismatchDetected: makeDetail(
    { mismatch_count: 2, unresolved_count: 1, needs_review: false },
    mismatchComparison,
  ),
  awaitingDocuments: makeDetail({
    processing_status: "AWAITING_DOCUMENTS",
    comparison_readiness: "AWAITING_DOCUMENTS",
    mismatch_count: 0,
    unresolved_count: 0,
  }, null),
  blocked: makeDetail({
    processing_status: "BLOCKED",
    needs_review: true,
    review_id: "review-001",
    review_status: "IN_REVIEW",
    review_reason: "COMPARISON_UNRESOLVED",
  }, mismatchComparison),
  failed: makeDetail({ processing_status: "FAILED" }, null),
  processing: makeDetail({ processing_status: "EXTRACTING" }, null),
  newSiRequest: makeDetail({
    category: "new_si_request",
    processing_status: "COMPLETED",
    comparison_readiness: null,
  }, null),
};

fixtures.blocked.review = [
  {
    id: "review-001",
    email_id: "email-001",
    email: fixtures.blocked.email,
    document_id: null,
    field: "notify_party",
    reason_code: "COMPARISON_UNRESOLVED",
    reason_text: "One comparison field needs a reviewer decision.",
    status: "IN_REVIEW",
    case_origin: "ACTIVE",
    reviewer_name: "Jordan Lee",
    confidence: 0.72,
    evidence: [],
    comparison: mismatchComparison,
    resolutions: [],
    created_at: "2024-05-01T09:02:00Z",
  },
];
