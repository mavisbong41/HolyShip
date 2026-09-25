import { apiBaseUrl, ApiError } from "./client";
import type { AIAssistantResponse, ProductReview, ProductReviewPlan } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...init?.headers,
    },
    ...init,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = (await response.json()) as { detail?: string };
      detail = payload.detail || detail;
    } catch {
      // Keep status text
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

export async function askAIAssistant(
  reviewId: string,
  question: string,
): Promise<AIAssistantResponse> {
  return request<AIAssistantResponse>(`/human-review/${reviewId}/ai/ask`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

export async function acceptAISuggestion(
  reviewId: string,
  suggestionId: string,
  reviewerLabel: string,
): Promise<ProductReview> {
  return request<ProductReview>(
    `/human-review/${reviewId}/ai/suggestions/${suggestionId}/accept`,
    {
      method: "POST",
      body: JSON.stringify({ reviewer_label: reviewerLabel }),
    },
  );
}

export async function applyEditedAISuggestion(
  reviewId: string,
  suggestionId: string,
  value: string,
  reviewerLabel: string,
  note?: string,
): Promise<ProductReview> {
  return request<ProductReview>(
    `/human-review/${reviewId}/ai/suggestions/${suggestionId}/apply-edited`,
    {
      method: "POST",
      body: JSON.stringify({
        value,
        reviewer_label: reviewerLabel,
        note,
      }),
    },
  );
}

export async function dismissAISuggestion(
  reviewId: string,
  suggestionId: string,
  reviewerLabel: string,
): Promise<ProductReview> {
  return request<ProductReview>(
    `/human-review/${reviewId}/ai/suggestions/${suggestionId}/dismiss`,
    {
      method: "POST",
      body: JSON.stringify({ reviewer_label: reviewerLabel }),
    },
  );
}

export async function listReviewPlans(reviewId: string): Promise<ProductReviewPlan[]> {
  return request<ProductReviewPlan[]>(`/human-review/${reviewId}/plans`);
}

export async function createReviewPlan(review: ProductReview, reviewer: string): Promise<ProductReviewPlan> {
  const items = (review.ai_suggestions ?? [])
    .filter((item) => item.status === "PENDING" && item.field && item.document_side && item.suggested_value != null)
    .map((item) => ({
      document_side: item.document_side,
      field: item.field,
      current_value: item.current_value,
      proposed_value: item.suggested_value,
      reason: item.reason ?? "AI-proposed correction",
      confidence: item.confidence,
      ai_suggestion_id: item.id,
      status: "PROPOSED",
    }));
  return request<ProductReviewPlan>(`/human-review/${review.id}/plans`, {
    method: "POST",
    body: JSON.stringify({ created_by: reviewer, items }),
  });
}

export interface ReviewPlanItemInput {
  document_side: "SI" | "BL";
  field: string;
  current_value: unknown;
  proposed_value: unknown;
  reason: string;
  confidence?: number | null;
  ai_suggestion_id?: string | null;
  status?: "PROPOSED" | "APPROVED" | "REJECTED";
}

export type ManualPlanItemInput = ReviewPlanItemInput;

export async function createReviewPlanWithItem(
  reviewId: string, reviewer: string, item: ReviewPlanItemInput,
): Promise<ProductReviewPlan> {
  return request<ProductReviewPlan>(`/human-review/${reviewId}/plans`, {
    method: "POST",
    body: JSON.stringify({ created_by: reviewer, items: [{ ...item, status: item.status ?? "APPROVED" }] }),
  });
}

export async function addReviewPlanItem(
  reviewId: string, planId: string, reviewer: string, item: ReviewPlanItemInput,
): Promise<ProductReviewPlan> {
  const params = new URLSearchParams({ actor_name: reviewer });
  return request<ProductReviewPlan>(`/human-review/${reviewId}/plans/${planId}/items?${params}`, {
    method: "POST",
    body: JSON.stringify({ ...item, status: item.status ?? "APPROVED" }),
  });
}

export async function createManualReviewPlan(
  reviewId: string, reviewer: string, item: ManualPlanItemInput,
): Promise<ProductReviewPlan> {
  return createReviewPlanWithItem(reviewId, reviewer, item);
}

export async function addManualReviewPlanItem(
  reviewId: string, planId: string, reviewer: string, item: ManualPlanItemInput,
): Promise<ProductReviewPlan> {
  return addReviewPlanItem(reviewId, planId, reviewer, item);
}

export async function removeManualReviewPlanItem(
  reviewId: string, planId: string, itemId: string, reviewer: string,
): Promise<ProductReviewPlan> {
  const params = new URLSearchParams({ actor_name: reviewer });
  return request<ProductReviewPlan>(`/human-review/${reviewId}/plans/${planId}/items/${itemId}?${params}`, {
    method: "DELETE",
  });
}

export async function cancelReviewPlan(
  reviewId: string, planId: string, reviewer: string,
): Promise<ProductReviewPlan> {
  return request<ProductReviewPlan>(`/human-review/${reviewId}/plans/${planId}/cancel`, {
    method: "POST", body: JSON.stringify({ actor_name: reviewer }),
  });
}

export async function updateReviewPlanItem(
  reviewId: string, planId: string, itemId: string,
  status: "APPROVED" | "EDITED" | "REJECTED", editedValue?: unknown,
): Promise<ProductReviewPlan> {
  return request<ProductReviewPlan>(`/human-review/${reviewId}/plans/${planId}/items/${itemId}`, {
    method: "PATCH", body: JSON.stringify({ status, edited_value: editedValue }),
  });
}

export async function confirmReviewPlan(reviewId: string, planId: string, reviewer: string): Promise<ProductReviewPlan> {
  return request<ProductReviewPlan>(`/human-review/${reviewId}/plans/${planId}/confirm`, {
    method: "POST", body: JSON.stringify({ confirmed_by: reviewer }),
  });
}
