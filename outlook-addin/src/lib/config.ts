const DEFAULT_DASHBOARD_URL = "http://localhost:5173";

export function dashboardBaseUrl(): string {
  return (import.meta.env.VITE_DASHBOARD_BASE_URL || DEFAULT_DASHBOARD_URL).replace(/\/$/, "");
}

export function dashboardEmailUrl(emailId: string): string {
  return `${dashboardBaseUrl()}/?email=${encodeURIComponent(emailId)}`;
}

export function dashboardReviewUrl(reviewId: string): string {
  return `${dashboardBaseUrl()}/?review=${encodeURIComponent(reviewId)}`;
}
