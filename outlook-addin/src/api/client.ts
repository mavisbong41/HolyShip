import type {
  AIAssistantResponse,
  EmailQueuePage,
  EmailLifecycleStatus,
  OutlookReadState,
  ProductCategory,
  ProductDiscrepancyDetail,
  ProductEmailDetail,
  ProductReplyWorkflow,
  ProductReview,
  ProductReviewPlan,
} from "../types/product";
import type { MailContextItem } from "../types/context";

const DEFAULT_BASE_URL = "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function apiBaseUrl(): string {
  return (import.meta.env.VITE_API_BASE_URL || DEFAULT_BASE_URL).replace(/\/$/, "");
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    headers: { Accept: "application/json", ...init?.headers },
    ...init,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail ?? detail;
    } catch {
      // keep HTTP status text
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

function appendParam(params: URLSearchParams, key: string, value: unknown): void {
  if (value === undefined || value === null || value === "") return;
  params.set(key, String(value));
}

/**
 * Look up a case by external_message_id or subject+sender fallback.
 * Returns the first matching email or null when no match is found.
 */
export async function findEmailByMessageId(
  internetMessageId: string,
): Promise<ProductEmailDetail | null> {
  const cleanId = internetMessageId.replace(/^<|>$/g, "").trim();
  const params = new URLSearchParams();
  appendParam(params, "search", cleanId || internetMessageId);
  appendParam(params, "limit", 5);
  const page = await request<EmailQueuePage>(`/emails?${params.toString()}`);
  const match = page.items.find(
    (item) =>
      item.external_message_id === internetMessageId ||
      item.external_message_id === cleanId,
  );
  if (!match) return null;
  return request<ProductEmailDetail>(`/emails/${match.id}`);
}

/**
 * Look up a case by HolyShip internal case id directly.
 */
export async function getEmailDetail(emailId: string): Promise<ProductEmailDetail> {
  return request<ProductEmailDetail>(`/emails/${emailId}`);
}

export async function reprocessEmail(emailId: string): Promise<{ email_id: string; status: string }> {
  return request(`/emails/${emailId}/reprocess`, { method: "POST" });
}

export async function updateEmailCategory(
  emailId: string,
  category: ProductCategory,
  reviewerName?: string,
  reason?: string,
): Promise<ProductEmailDetail> {
  return request<ProductEmailDetail>(`/emails/${emailId}/category`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category, reviewer_name: reviewerName, reason }),
  });
}

/**
 * Ask the HolyShip AI Review Assistant for grounded case reasoning.
 */
export async function askAIAssistant(
  reviewId: string,
  question: string,
): Promise<AIAssistantResponse> {
  return request<AIAssistantResponse>(`/human-review/${reviewId}/ai/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}

export async function claimHumanReview(reviewId: string, reviewerName: string): Promise<ProductReview> {
  return request<ProductReview>(`/human-review/${reviewId}/claim`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewer_name: reviewerName }),
  });
}

export async function saveHumanReviewOverride(
  reviewId: string,
  payload: {
    document_side: "SI" | "BL";
    field: string;
    corrected_value: unknown;
    corrected_canonical_value?: unknown;
    reviewer_name?: string;
    note?: string;
  },
): Promise<ProductReview> {
  return request<ProductReview>(`/human-review/${reviewId}/overrides`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function resolveHumanReview(
  reviewId: string,
  reviewerName?: string,
  notes?: string,
): Promise<ProductReview> {
  return request<ProductReview>(`/human-review/${reviewId}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewer_name: reviewerName, notes }),
  });
}

export async function dismissHumanReview(
  reviewId: string,
  reason: string,
  reviewerName?: string,
  notes?: string,
): Promise<ProductReview> {
  return request<ProductReview>(`/human-review/${reviewId}/dismiss`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewer_name: reviewerName, reason, notes }),
  });
}

export async function acceptAISuggestion(
  reviewId: string,
  suggestionId: string,
  reviewerLabel: string,
): Promise<ProductReview> {
  return request<ProductReview>(`/human-review/${reviewId}/ai/suggestions/${suggestionId}/accept`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewer_label: reviewerLabel }),
  });
}

export async function applyEditedAISuggestion(
  reviewId: string,
  suggestionId: string,
  value: string,
  reviewerLabel: string,
  note?: string,
): Promise<ProductReview> {
  return request<ProductReview>(`/human-review/${reviewId}/ai/suggestions/${suggestionId}/apply-edited`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value, reviewer_label: reviewerLabel, note }),
  });
}

export async function dismissAISuggestion(
  reviewId: string,
  suggestionId: string,
  reviewerLabel: string,
): Promise<ProductReview> {
  return request<ProductReview>(`/human-review/${reviewId}/ai/suggestions/${suggestionId}/dismiss`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewer_label: reviewerLabel }),
  });
}

export async function createReplySummary(
  emailId: string,
  reviewerName?: string,
): Promise<ProductReplyWorkflow> {
  return request<ProductReplyWorkflow>(`/emails/${emailId}/reply/summary`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewer_name: reviewerName }),
  });
}

export async function generateReplyDraft(
  emailId: string,
  keyPoints: string[],
  reviewerName?: string,
): Promise<ProductReplyWorkflow> {
  return request<ProductReplyWorkflow>(`/emails/${emailId}/reply/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key_points: keyPoints, reviewer_name: reviewerName }),
  });
}

export async function refineReplyDraft(
  emailId: string,
  draft: string,
  instruction: string,
  reviewerName?: string,
): Promise<ProductReplyWorkflow> {
  return request<ProductReplyWorkflow>(`/emails/${emailId}/reply/refine`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ draft, instruction, reviewer_name: reviewerName }),
  });
}

export async function sendReplyDraft(
  emailId: string,
  finalMessage: string,
  reviewerName?: string,
): Promise<ProductReplyWorkflow> {
  const idempotencyKey = globalThis.crypto?.randomUUID?.() ?? `reply-${emailId}-${Date.now()}`;
  return request<ProductReplyWorkflow>(`/emails/${emailId}/reply/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      final_message: finalMessage,
      reviewer_name: reviewerName,
      confirmed: true,
      idempotency_key: idempotencyKey,
    }),
  });
}

export type ManualPlanItemInput = {
  document_side: "SI" | "BL";
  field: string;
  current_value: unknown;
  proposed_value: unknown;
  reason: string;
};

export async function listReviewPlans(reviewId: string): Promise<ProductReviewPlan[]> {
  return request<ProductReviewPlan[]>(`/human-review/${reviewId}/plans`);
}

export async function createReviewPlan(review: ProductReview, reviewer: string): Promise<ProductReviewPlan> {
  const items = (review.ai_suggestions ?? [])
    .filter((item) => item.status === "PENDING" && item.field && item.document_side && item.suggested_value != null)
    .map((item) => ({
      document_side: item.document_side, field: item.field,
      current_value: item.current_value, proposed_value: item.suggested_value,
      reason: item.reason ?? "AI-proposed correction", confidence: item.confidence,
      ai_suggestion_id: item.id, status: "PROPOSED",
    }));
  return request<ProductReviewPlan>(`/human-review/${review.id}/plans`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ created_by: reviewer, items }),
  });
}

export async function createManualReviewPlan(reviewId: string, reviewer: string, item: ManualPlanItemInput): Promise<ProductReviewPlan> {
  return request<ProductReviewPlan>(`/human-review/${reviewId}/plans`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ created_by: reviewer, items: [{ ...item, status: "APPROVED" }] }),
  });
}

export async function addManualReviewPlanItem(reviewId: string, planId: string, reviewer: string, item: ManualPlanItemInput): Promise<ProductReviewPlan> {
  const params = new URLSearchParams({ actor_name: reviewer });
  return request<ProductReviewPlan>(`/human-review/${reviewId}/plans/${planId}/items?${params}`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...item, status: "APPROVED" }),
  });
}

export async function updateReviewPlanItem(reviewId: string, planId: string, itemId: string, status: "APPROVED" | "EDITED" | "REJECTED", editedValue?: unknown): Promise<ProductReviewPlan> {
  return request<ProductReviewPlan>(`/human-review/${reviewId}/plans/${planId}/items/${itemId}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, edited_value: editedValue }),
  });
}

export async function removeManualReviewPlanItem(reviewId: string, planId: string, itemId: string, reviewer: string): Promise<ProductReviewPlan> {
  const params = new URLSearchParams({ actor_name: reviewer });
  return request<ProductReviewPlan>(`/human-review/${reviewId}/plans/${planId}/items/${itemId}?${params}`, { method: "DELETE" });
}

export async function confirmReviewPlan(reviewId: string, planId: string, reviewer: string): Promise<ProductReviewPlan> {
  return request<ProductReviewPlan>(`/human-review/${reviewId}/plans/${planId}/confirm`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confirmed_by: reviewer }),
  });
}

export async function cancelReviewPlan(reviewId: string, planId: string, reviewer: string): Promise<ProductReviewPlan> {
  return request<ProductReviewPlan>(`/human-review/${reviewId}/plans/${planId}/cancel`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ actor_name: reviewer }),
  });
}

export type ReconcileItemPayload = Partial<MailContextItem> & {
  lifecycle_status?: EmailLifecycleStatus | "RESTORED";
  outlook_item_id?: string | null;
  internet_message_id?: string | null;
  outlook_read_state?: OutlookReadState;
  outlook_categories?: string[];
  outlook_folder_id?: string | null;
  outlook_archived?: boolean | null;
};

export async function reconcileOutlookLifecycle(
  emailId: string,
  item: ReconcileItemPayload,
): Promise<void> {
  const folder = (item.outlookFolderId || item.outlook_folder_id || "").toLowerCase();
  const isDeletedFolder =
    folder.includes("deleted") ||
    folder.includes("trash") ||
    folder === "deleteditems" ||
    folder === "deleted items" ||
    folder === "trashbin";

  const lifecycleStatus =
    item.lifecycle_status ?? (isDeletedFolder ? "DELETED" : "ACTIVE");

  await request(`/outlook/reconcile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email_id: emailId,
      lifecycle_status: lifecycleStatus,
      outlook_read_state: (item.outlookReadState ?? "UNKNOWN") as OutlookReadState,
      outlook_categories: item.outlookCategories ?? [],
      outlook_folder_id: item.outlookFolderId ?? item.outlook_folder_id ?? undefined,
      outlook_archived: item.outlookArchived ?? item.outlook_archived ?? undefined,
      actor_name: "Outlook Add-in",
    }),
  });
}

/**
 * Search by subject / sender as fallback when no message-id match is possible.
 */
export async function searchEmailQueue(query: string): Promise<EmailQueuePage> {
  const params = new URLSearchParams();
  appendParam(params, "search", query);
  appendParam(params, "limit", 10);
  return request<EmailQueuePage>(`/emails?${params.toString()}`);
}

export async function getDiscrepancyDetail(
  discrepancyId: string,
): Promise<ProductDiscrepancyDetail> {
  return request<ProductDiscrepancyDetail>(`/discrepancies/${discrepancyId}`);
}

export async function saveDiscrepancyOverride(
  discrepancyId: string,
  payload: {
    document_side: "SI" | "BL";
    field_name: string;
    corrected_value: unknown;
    reviewer_name?: string;
    note?: string;
  },
): Promise<ProductDiscrepancyDetail> {
  return request<ProductDiscrepancyDetail>(`/discrepancies/${discrepancyId}/override`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function recompareDiscrepancy(
  discrepancyId: string,
  reviewerName?: string,
): Promise<ProductDiscrepancyDetail> {
  return request<ProductDiscrepancyDetail>(`/discrepancies/${discrepancyId}/recompare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewer_name: reviewerName }),
  });
}

export async function acknowledgeDiscrepancy(
  discrepancyId: string,
  operatorName?: string,
): Promise<ProductDiscrepancyDetail> {
  return request<ProductDiscrepancyDetail>(`/discrepancies/${discrepancyId}/acknowledge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ operator_name: operatorName }),
  });
}

export async function resolveDiscrepancy(
  discrepancyId: string,
  operatorName?: string,
  notes?: string,
): Promise<ProductDiscrepancyDetail> {
  return request<ProductDiscrepancyDetail>(`/discrepancies/${discrepancyId}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ operator_name: operatorName, notes }),
  });
}
