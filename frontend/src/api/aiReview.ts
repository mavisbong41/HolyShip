import { apiBaseUrl, ApiError } from "./client";
import type { AIAssistantResponse, ProductReview } from "./types";

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
