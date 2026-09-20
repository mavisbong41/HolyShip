import type {
  EmailQueuePage,
  HumanReviewPage,
  ProductEmailDetail,
  ProductEvent,
  ProductSummary,
  QueueFilters,
} from "./types";

const defaultBaseUrl = "http://localhost:8000/api/v1";

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
  appendParam(params, "has_mismatch", filters.has_mismatch);
  appendParam(params, "search", filters.search?.trim());
  appendParam(params, "skip", filters.skip ?? 0);
  appendParam(params, "limit", filters.limit ?? 25);
  return request<EmailQueuePage>(`/emails?${params.toString()}`);
}

export async function getEmailDetail(emailId: string): Promise<ProductEmailDetail> {
  return request<ProductEmailDetail>(`/emails/${emailId}`);
}

export async function getHumanReviewQueue(): Promise<HumanReviewPage> {
  return request<HumanReviewPage>("/human-review?limit=50");
}

export async function getEvents(since?: string): Promise<ProductEvent[]> {
  const params = new URLSearchParams();
  appendParam(params, "since", since);
  appendParam(params, "limit", 100);
  return request<ProductEvent[]>(`/events?${params.toString()}`);
}
