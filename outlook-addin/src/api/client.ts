import type { AIAssistantResponse, EmailQueuePage, ProductEmailDetail } from "../types/product";

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

/**
 * Search by subject / sender as fallback when no message-id match is possible.
 */
export async function searchEmailQueue(query: string): Promise<EmailQueuePage> {
  const params = new URLSearchParams();
  appendParam(params, "search", query);
  appendParam(params, "limit", 10);
  return request<EmailQueuePage>(`/emails?${params.toString()}`);
}
