import type {
  DiscrepancyPage,
  DiscrepancyQueueFilters,
  EmailQueuePage,
  HumanReviewAnalytics,
  HumanReviewPage,
  InitialSyncResult,
  ProductDiscrepancyDetail,
  ProductDiscrepancySummary,
  ProductEmailDetail,
  ProductEvent,
  ProductReview,
  ProductSummary,
  QueueFilters,
  ReviewQueueFilters,
} from "./types";

const defaultBaseUrl = "/api/v1";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function apiBaseUrl(): string {
  return (import.meta.env.VITE_API_BASE_URL || defaultBaseUrl).replace(/\/$/, "");
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
      detail = payload.detail || detail;
    } catch {
      // Keep the HTTP status text when the backend sends a non-JSON response.
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

function appendParam(params: URLSearchParams, key: string, value: unknown): void {
  if (value === undefined || value === null || value === "") {
    return;
  }
  params.set(key, String(value));
}

export async function getSummary(): Promise<ProductSummary> {
  return request<ProductSummary>("/summary");
}

export async function getEmailQueue(filters: QueueFilters): Promise<EmailQueuePage> {
  const params = new URLSearchParams();
  appendParam(params, "status", filters.status);
  appendParam(params, "category", filters.category);
  appendParam(params, "comparison_readiness", filters.comparison_readiness);
  appendParam(params, "needs_review", filters.needs_review);
  appendParam(params, "review_status", filters.review_status);
  appendParam(params, "comparison_state", filters.comparison_state);
  appendParam(params, "has_mismatch", filters.has_mismatch);
  appendParam(params, "search", filters.search?.trim());
  appendParam(params, "skip", filters.skip ?? 0);
  appendParam(params, "limit", filters.limit ?? 20);
  return request<EmailQueuePage>(`/emails?${params.toString()}`);
}

export async function getEmailDetail(emailId: string): Promise<ProductEmailDetail> {
  return request<ProductEmailDetail>(`/emails/${emailId}`);
}

export async function getHumanReviewQueue(filters: ReviewQueueFilters = {}): Promise<HumanReviewPage> {
  const params = new URLSearchParams();
  appendParam(params, "status", filters.status);
  appendParam(params, "reason", filters.reason?.trim());
  appendParam(params, "reviewer", filters.reviewer?.trim());
  appendParam(params, "search", filters.search?.trim());
  appendParam(params, "active_only", filters.active_only ?? true);
  appendParam(params, "sort", filters.sort);
  appendParam(params, "skip", filters.skip ?? 0);
  appendParam(params, "limit", filters.limit ?? 50);
  return request<HumanReviewPage>(`/human-review?${params.toString()}`);
}

export async function getAllHumanReviews(filters: ReviewQueueFilters = {}): Promise<HumanReviewPage> {
  const limit = 500;
  let skip = 0;
  let total = 0;
  const items: HumanReviewPage["items"] = [];

  do {
    const page = await getHumanReviewQueue({ ...filters, skip, limit });
    items.push(...page.items);
    total = page.total;
    skip += page.items.length;
    if (page.items.length === 0) break;
  } while (items.length < total);

  return { items, total, skip: 0, limit: Math.max(items.length, 1) };
}

export async function getHumanReviewDetail(reviewId: string): Promise<ProductReview> {
  return request<ProductReview>(`/human-review/${reviewId}`);
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

export async function reprocessEmail(emailId: string): Promise<{ email_id: string; status: string }> {
  return request(`/emails/${emailId}/reprocess`, { method: "POST" });
}

export async function runInitialSync(): Promise<InitialSyncResult> {
  return request<InitialSyncResult>("/sync/initial", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source: "static" }),
  });
}

export async function getEvents(since?: string): Promise<ProductEvent[]> {
  const params = new URLSearchParams();
  appendParam(params, "since", since);
  appendParam(params, "limit", 100);
  return request<ProductEvent[]>(`/events?${params.toString()}`);
}

export async function getHumanReviewAnalytics(): Promise<HumanReviewAnalytics> {
  return request<HumanReviewAnalytics>('/human-review-analytics');
}

export async function getDiscrepancies(filters: DiscrepancyQueueFilters = {}): Promise<DiscrepancyPage> {
  const params = new URLSearchParams();
  appendParam(params, "status", filters.status);
  appendParam(params, "search", filters.search?.trim());
  appendParam(params, "skip", filters.skip ?? 0);
  appendParam(params, "limit", filters.limit ?? 20);
  return request<DiscrepancyPage>(`/discrepancies?${params.toString()}`);
}

export async function getDiscrepancyDetail(discrepancyId: string): Promise<ProductDiscrepancyDetail> {
  return request<ProductDiscrepancyDetail>(`/discrepancies/${discrepancyId}`);
}

export async function acknowledgeDiscrepancy(
  discrepancyId: string,
  operatorName?: string,
): Promise<{ discrepancy: ProductDiscrepancySummary }> {
  return request<{ discrepancy: ProductDiscrepancySummary }>(`/discrepancies/${discrepancyId}/acknowledge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ operator_name: operatorName }),
  });
}

export async function resolveDiscrepancy(
  discrepancyId: string,
  operatorName?: string,
  notes?: string,
): Promise<{ discrepancy: ProductDiscrepancySummary }> {
  return request<{ discrepancy: ProductDiscrepancySummary }>(`/discrepancies/${discrepancyId}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ operator_name: operatorName, notes }),
  });
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
): Promise<{ discrepancy: ProductDiscrepancySummary; overrides: unknown[] }> {
  return request<{ discrepancy: ProductDiscrepancySummary; overrides: unknown[] }>(
    `/discrepancies/${discrepancyId}/override`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
}

export async function recompareDiscrepancy(
  discrepancyId: string,
  reviewerName?: string,
): Promise<{ discrepancy: ProductDiscrepancySummary; comparison: unknown }> {
  return request<{ discrepancy: ProductDiscrepancySummary; comparison: unknown }>(
    `/discrepancies/${discrepancyId}/recompare`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewer_name: reviewerName }),
    },
  );
}
