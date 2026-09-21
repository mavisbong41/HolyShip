import {
  AlertCircle,
  AlertTriangle,
  Archive,
  ArrowDownRight,
  ArrowUpRight,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  ClipboardList,
  Clock,
  FileSearch,
  FileText,
  Inbox,
  Mail,
  MailCheck,
  Maximize2,
  Minimize2,
  MoreHorizontal,
  LogOut,
  RefreshCw,
  Search,
  ShieldAlert,
  ShipWheel,
  X,
} from "lucide-react";
import React from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  getEmailDetail,
  getEmailQueue,
  getEvents,
  getHumanReviewAnalytics,
  getHumanReviewDetail,
  getAllHumanReviews,
  getSummary,
  claimHumanReview,
  dismissHumanReview,
  reprocessEmail,
  resolveHumanReview,
  runInitialSync,
  saveHumanReviewOverride,
} from "./api/client";
import { AIReviewPanel } from "./components/ai-review/AIReviewPanel";
import type {
  EmailQueuePage,
  HumanReviewAnalytics,
  HumanReviewPage,
  ProcessingStatus,
  ProductCategory,
  ProductEmailDetail,
  ProductEmailSummary,
  ProductReview,
  ProductSummary,
  QueueFilters,
} from "./api/types";
import { canonicalFields } from "./api/types";
import {
  categoryLabels,
  displayLabel,
  displayValue,
  fieldStatusLabels,
  formatDate,
  labelForField,
  readinessLabels,
  reasonLabels,
  reviewActionLabels,
  reviewStatusLabels,
  semanticTone,
  statusLabels,
} from "./lib/labels";

type Page = "overview" | "queue" | "review";
type LoadState = "idle" | "loading" | "ready" | "error";
export type ReviewViewMode = "ACTIVE" | "HISTORY";

const pageTitles: Record<Page, string> = {
  overview: "Overview",
  queue: "Email Queue",
  review: "Human Review",
};

const statusOptions: ProcessingStatus[] = [
  "NEW",
  "QUEUED",
  "CLASSIFYING",
  "AWAITING_DOCUMENTS",
  "RETRIEVING_ATTACHMENTS",
  "EXTRACTING",
  "COMPARING",
  "COMPLETED",
  "BLOCKED",
  "FAILED",
];

const categoryOptions: ProductCategory[] = [
  "document_comparison",
  "new_si_request",
  "invoice_query",
  "general_message",
  "spam",
];

const defaultReviewerName = "Demo Reviewer";

function cx(...items: Array<string | false | null | undefined>): string {
  return items.filter(Boolean).join(" ");
}

function metricFromStatus(summary: ProductSummary | null, status: ProcessingStatus): number {
  return summary?.status_counts[status] ?? 0;
}

function reviewAnalyticsFallback(page: HumanReviewPage): HumanReviewAnalytics {
  const analytics: HumanReviewAnalytics = {
    open_count: 0,
    in_review_count: 0,
    resolved_count: 0,
    dismissed_count: 0,
    resolved_today_count: 0,
    average_open_age_minutes: null,
    priority_distribution: {},
    reason_distribution: {},
    most_reviewed_fields: {},
    most_corrected_fields: {},
    correction_reasons: {},
  };
  const openAges: number[] = [];
  const today = new Date().toDateString();

  for (const review of page.items) {
    if (review.status === "OPEN") {
      analytics.open_count += 1;
      if (typeof review.age_minutes === "number") openAges.push(review.age_minutes);
    } else if (review.status === "IN_REVIEW") {
      analytics.in_review_count += 1;
    } else if (review.status === "RESOLVED") {
      analytics.resolved_count += 1;
      if (review.resolved_at && new Date(review.resolved_at).toDateString() === today) {
        analytics.resolved_today_count += 1;
      }
    } else if (review.status === "DISMISSED") {
      analytics.dismissed_count += 1;
    }

    analytics.priority_distribution[review.priority] = (analytics.priority_distribution[review.priority] ?? 0) + 1;
    analytics.reason_distribution[review.reason_code] = (analytics.reason_distribution[review.reason_code] ?? 0) + 1;
    for (const field of review.affected_fields ?? []) {
      analytics.most_reviewed_fields[field] = (analytics.most_reviewed_fields[field] ?? 0) + 1;
    }
  }

  if (openAges.length) {
    analytics.average_open_age_minutes = openAges.reduce((sum, value) => sum + value, 0) / openAges.length;
  }
  return analytics;
}

function StatusBadge({
  value,
  tone,
}: {
  value: string | null | undefined;
  tone?: "neutral" | "good" | "warn" | "bad" | "attention" | "info" | "muted";
}) {
  if (!value) return <span className="badge badge-muted">Not set</span>;
  return <span className={`badge badge-${tone ?? semanticTone(value)}`}>{displayLabel(value)}</span>;
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="empty-state">
      <Archive aria-hidden="true" size={22} />
      <h3>{title}</h3>
      <p>{body}</p>
    </div>
  );
}

function LoadingRows() {
  return (
    <div className="skeleton-stack" aria-label="Loading">
      {Array.from({ length: 5 }).map((_, index) => (
        <div className="skeleton-row" key={index} />
      ))}
    </div>
  );
}

function formatRelativeTime(date: Date | null): string {
  if (!date) return "No timestamp";
  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (seconds < 10) return "Just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours} hr ago`;
}

function AppHeader({
  page,
  state,
  lastSyncedAt,
  onRefresh,
  onInitialSync,
  syncState,
}: {
  page: Page;
  state: LoadState;
  lastSyncedAt: Date | null;
  onRefresh?: () => void;
  onInitialSync?: () => void;
  syncState?: LoadState;
}) {
  const [syncTimeText, setSyncTimeText] = useState(() => formatRelativeTime(lastSyncedAt));
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [isLoggedOut, setIsLoggedOut] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setSyncTimeText(formatRelativeTime(lastSyncedAt));
    const interval = window.setInterval(() => {
      setSyncTimeText(formatRelativeTime(lastSyncedAt));
    }, 5000);
    return () => window.clearInterval(interval);
  }, [lastSyncedAt]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false);
      }
    };
    if (userMenuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [userMenuOpen]);

  const eyebrowText =
    page === "overview"
      ? "OPERATIONS WORKBENCH"
      : page === "queue"
        ? "OPERATIONAL QUEUE"
        : "EXCEPTION HANDLING";

  return (
    <div className="overview-header-bar">
      <div>
        <p className="eyebrow" style={{ margin: 0 }}>{eyebrowText}</p>
        <h1 className="sr-only">Shipping document operations, at a glance.</h1>
      </div>
      <div className="overview-header-actions">
        <div className="tooltip-wrap">
          <span className={cx("connection", state === "error" ? "offline" : "online")}>
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: state === "error" ? "var(--color-danger)" : "var(--color-success)",
                display: "inline-block",
                marginRight: 6,
              }}
            />
            {state === "error" ? "API Attention" : "Backend Online"}
            <span style={{ opacity: 0.65, marginLeft: 6, fontWeight: 400, fontSize: "11px" }}>
              Synced {syncTimeText}
            </span>
          </span>
          <div className="tooltip-bubble">
            <strong>Backend Online</strong>
            <span>API service operational with automated live event sync</span>
          </div>
        </div>

        <div className="topbar-divider" />

        <div className="tooltip-wrap">
          <button
            className="sync-button"
            type="button"
            onClick={onInitialSync}
            disabled={syncState === "loading"}
          >
            {syncState === "loading" ? "Syncing…" : "Initial Sync"}
          </button>
          <div className="tooltip-bubble tooltip-right">
            <strong>Initial Sync</strong>
            <span>Batch ingests inbox backlog and runs SI/BL verification pipeline</span>
          </div>
        </div>

        <div className="tooltip-wrap">
          <button
            className="icon-button"
            onClick={onRefresh}
            type="button"
            aria-label="Refresh overview"
          >
            <RefreshCw size={14} />
          </button>
          <div className="tooltip-bubble tooltip-right">
            <strong>Refresh Dashboard</strong>
            <span>Reloads latest metrics and email queue from database</span>
          </div>
        </div>

        <div className="user-menu-wrap" ref={userMenuRef}>
          <div className="tooltip-wrap">
            <button
              className="avatar-badge avatar-button"
              type="button"
              onClick={() => setUserMenuOpen((prev) => !prev)}
              aria-label="User profile menu"
            >
              {isLoggedOut ? "?" : "JD"}
            </button>
            {!userMenuOpen && (
              <div className="tooltip-bubble tooltip-right">
                <strong>{isLoggedOut ? "Signed Out" : "John Doe"}</strong>
                <span>{isLoggedOut ? "Click to sign in" : "john.doe@outlook.com · Manage account"}</span>
              </div>
            )}
          </div>

          {userMenuOpen && (
            <div className="user-dropdown-menu" role="menu">
              <div className="user-dropdown-header">
                <div className="dropdown-avatar">{isLoggedOut ? "?" : "JD"}</div>
                <div className="dropdown-user-info">
                  <strong>{isLoggedOut ? "Signed Out" : "John Doe"}</strong>
                  <span className="dropdown-email">{isLoggedOut ? "No active account" : "john.doe@outlook.com"}</span>
                  <span className="dropdown-tenant">
                    <span className="tenant-dot" />
                    {isLoggedOut ? "Session closed" : "Connected to Outlook 365"}
                  </span>
                </div>
              </div>

              <div className="user-dropdown-body">
                <div className="user-info-row">
                  <span>Role:</span>
                  <strong>Shipping Operator</strong>
                </div>
                <div className="user-info-row">
                  <span>Mailbox:</span>
                  <strong>inbox@holyship.outlook.com</strong>
                </div>
                <div className="user-info-row">
                  <span>Organization:</span>
                  <strong>HolyShip Global Ops</strong>
                </div>
              </div>

              <div className="user-dropdown-footer">
                {isLoggedOut ? (
                  <button
                    className="user-login-btn"
                    type="button"
                    onClick={() => {
                      setIsLoggedOut(false);
                      setUserMenuOpen(false);
                    }}
                  >
                    <Mail size={14} />
                    Sign in with Outlook
                  </button>
                ) : (
                  <button
                    className="user-logout-btn"
                    type="button"
                    onClick={() => {
                      setIsLoggedOut(true);
                      setTimeout(() => setUserMenuOpen(false), 600);
                    }}
                  >
                    <LogOut size={14} />
                    Log out (outlook.com)
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function OverviewPage({
  summary,
  queue,
  state,
  onOpenQueue,
}: {
  summary: ProductSummary | null;
  queue: EmailQueuePage | null;
  state: LoadState;
  onOpenQueue: () => void;
}) {
  const completed = metricFromStatus(summary, "COMPLETED");
  const completionRate =
    summary && summary.total_emails > 0
      ? Math.round((completed / summary.total_emails) * 100)
      : 0;

  return (
    <section className="page-grid">
      <section className="overview-summary-panel" aria-label="Operational summary">
        <div className="metric-grid overview-metric-grid">
          <MetricCard
            cardIndex={0}
            icon={<MailCheck size={18} color="currentColor" />}
            label="Total Emails"
            value={summary?.total_emails ?? 0}
            trendText={`${summary?.processing_count ?? 0} processing`}
            tone="attention"
          />
          <MetricCard
            cardIndex={1}
            icon={<CircleCheck size={18} color="var(--color-success)" />}
            label="Completed"
            value={completed}
            trendText={`${completionRate}% of total`}
            trend="up"
            tone="good"
          />
          <MetricCard
            cardIndex={2}
            icon={<ShieldAlert size={18} color="var(--color-warn)" />}
            label="Human Review Open"
            value={summary?.human_review_open_count ?? summary?.needs_review_count ?? 0}
            trendText="Actionable business cases"
            trend="up"
            tone="warn"
          />
          <MetricCard
            cardIndex={3}
            icon={<AlertTriangle size={18} color="var(--color-danger)" />}
            label="Emails with Mismatch"
            value={summary?.mismatch_count ?? 0}
            trendText={`${summary && summary.total_emails > 0 ? Math.round(((summary.mismatch_count ?? 0) / summary.total_emails) * 100) : 0}% of total emails`}
            trend="down"
            tone="bad"
          />
          <MetricCard
            cardIndex={4}
            icon={<Clock size={18} color="var(--color-warn)" />}
            label="Awaiting Documents"
            value={summary?.awaiting_documents_count ?? metricFromStatus(summary, "AWAITING_DOCUMENTS")}
            trendText="Operational waiting state"
            tone="warn"
          />
          <MetricCard
            cardIndex={5}
            icon={<AlertCircle size={18} color="var(--color-danger)" />}
            label="Failed"
            value={summary?.failed_count ?? metricFromStatus(summary, "FAILED")}
            trendText="Retry / reprocess"
            tone="bad"
          />
          <MetricCard
            cardIndex={6}
            icon={<RefreshCw size={18} color="var(--color-info)" />}
            label="Currently Processing"
            value={summary?.processing_count ?? 0}
            trendText="Active pipeline work"
            tone="neutral"
          />
        </div>
      </section>

      <div className="overview-tri-grid">
        {/* Col 1: Processing Load */}
        <section className="surface-panel has-accent-bar">
          <div className="section-header">
            <div>
              <p className="eyebrow">STATUS DISTRIBUTION</p>
              <h2>Processing Load</h2>
            </div>
            <span className="section-header-total">Total: {summary?.total_emails ?? 0} emails</span>
          </div>
          {state === "loading" ? (
            <LoadingRows />
          ) : (
            <div className="status-bars-compact">
              {statusOptions.map((status) => {
                const count = summary?.status_counts[status] ?? 0;
                const total = summary?.total_emails ?? 0;
                const pct = total > 0 ? Math.round((count / total) * 100) : 0;
                const barClass =
                  status === "COMPLETED"
                    ? "completed"
                    : status === "BLOCKED" || status === "FAILED"
                      ? "attention"
                      : "in-progress";
                return (
                  <div className="status-row-compact" key={status}>
                    <span className="status-row-label">{statusLabels[status]}</span>
                    <div className="status-row-bar">
                      <span className={barClass} style={{ width: `${Math.min(100, Math.max(count > 0 ? 5 : 0, pct))}%` }} />
                    </div>
                    <div className="status-row-values">
                      <span className="status-row-count">{count}</span>
                      <span className="status-row-pct">{pct}%</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Col 2: Recent Activity */}
        <section className="surface-panel">
          <div className="section-header">
            <div>
              <p className="eyebrow">NEWEST CASES</p>
              <h2>Recent Activity</h2>
            </div>
            <button className="section-link-btn" onClick={onOpenQueue} type="button">
              View all →
            </button>
          </div>
          {queue?.items.length ? (
            <div className="activity-list-compact">
              {queue.items.slice(0, 6).map((item) => {
                const isCompleted = item.processing_status === "COMPLETED";
                const isMismatch = item.mismatch_count > 0;
                const isReview = item.needs_review;
                const isFailed = item.processing_status === "FAILED";
                const circleTone = isCompleted ? "good" : isMismatch ? "warn" : isReview ? "attention" : isFailed ? "bad" : "neutral";
                return (
                  <div className="activity-row-compact" key={item.id}>
                    <div className="activity-row-left">
                      <div className={`activity-circle-icon ${circleTone}`}>
                        {isCompleted ? (
                          <CheckCircle2 size={13} />
                        ) : isMismatch ? (
                          <AlertTriangle size={13} />
                        ) : isReview ? (
                          <AlertCircle size={13} />
                        ) : isFailed ? (
                          <X size={13} />
                        ) : (
                          <FileText size={13} />
                        )}
                      </div>
                      <div className="activity-row-info">
                        <strong>{item.sender ? item.sender.split("@")[0].replace(/[._]/g, " ") : "Unknown Shipper"}</strong>
                        <p>{item.subject}</p>
                      </div>
                    </div>
                    <span className="activity-row-time">{formatDate(item.received_at || item.created_at)}</span>
                  </div>
                );
              })}
            </div>
          ) : (
            <EmptyState
              title="No recent cases"
              body="Run initial sync or ingest an email to populate this list."
            />
          )}
        </section>

        {/* Col 3: Comparison Summary / Verification Alerts */}
        <section className="surface-panel">
          <div className="section-header">
            <div>
              <p className="eyebrow">VERIFICATION ALERTS</p>
              <h2>Comparison Summary</h2>
            </div>
            <button className="section-link-btn" onClick={onOpenQueue} type="button">
              View all →
            </button>
          </div>
          <div className="alert-summary-list">
            <div className="alert-row-compact" onClick={onOpenQueue}>
              <div className="alert-row-left">
                <div className="activity-circle-icon bad">
                  <X size={13} />
                </div>
                <div className="alert-row-info">
                  <strong>Emails with BL vs SI mismatch</strong>
                  <p>At least one comparison field differs between the SI and BL</p>
                </div>
              </div>
              <div className="alert-row-right">
                <span>{summary?.mismatch_count ?? 0}</span>
                <ChevronRight size={14} color="var(--color-grey-500)" />
              </div>
            </div>

            <div className="alert-row-compact" onClick={onOpenQueue}>
              <div className="alert-row-left">
                <div className="activity-circle-icon warn">
                  <AlertCircle size={13} />
                </div>
                <div className="alert-row-info">
                  <strong>Missing documents</strong>
                  <p>Awaiting draft BL or SI attachment</p>
                </div>
              </div>
              <div className="alert-row-right">
                <span>{summary?.awaiting_documents_count ?? metricFromStatus(summary, "AWAITING_DOCUMENTS")}</span>
                <ChevronRight size={14} color="var(--color-grey-500)" />
              </div>
            </div>

            <div className="alert-row-compact" onClick={onOpenQueue}>
              <div className="alert-row-left">
                <div className="activity-circle-icon attention">
                  <AlertTriangle size={13} />
                </div>
                <div className="alert-row-info">
                  <strong>Data inconsistency</strong>
                  <p>Blocked or conflicted entity data</p>
                </div>
              </div>
              <div className="alert-row-right">
                <span>{metricFromStatus(summary, "BLOCKED")}</span>
                <ChevronRight size={14} color="var(--color-grey-500)" />
              </div>
            </div>

            <div className="alert-row-compact" onClick={onOpenQueue}>
              <div className="alert-row-left">
                <div className="activity-circle-icon neutral">
                  <AlertCircle size={13} />
                </div>
                <div className="alert-row-info">
                  <strong>Emails with unresolved fields</strong>
                  <p>At least one comparison field could not be verified</p>
                </div>
              </div>
              <div className="alert-row-right">
                <span>{summary?.unresolved_count ?? 0}</span>
                <ChevronRight size={14} color="var(--color-grey-500)" />
              </div>
            </div>

            <div className="alert-row-compact" onClick={onOpenQueue}>
              <div className="alert-row-left">
                <div className="activity-circle-icon neutral">
                  <FileText size={13} />
                </div>
                <div className="alert-row-info">
                  <strong>Processing exceptions</strong>
                  <p>Technical or parse retry failure</p>
                </div>
              </div>
              <div className="alert-row-right">
                <span>{summary?.failed_count ?? metricFromStatus(summary, "FAILED")}</span>
                <ChevronRight size={14} color="var(--color-grey-500)" />
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* Bottom Queue Preview Card */}
      <section className="surface-panel queue-preview-panel has-accent-bar">
        <div className="section-header">
          <div>
            <p className="eyebrow">QUEUE PREVIEW</p>
            <h2>Recent Email Queue (Latest 5)</h2>
          </div>
          <button className="section-link-btn" onClick={onOpenQueue} type="button">
            View all →
          </button>
        </div>
        {queue?.items.length ? (
          <div className="table-wrap">
            <table className="queue-preview-table" aria-label="Queue preview">
              <thead>
                <tr>
                  <th style={{ width: 32 }}>
                    <input type="checkbox" readOnly />
                  </th>
                  <th>Received ▾</th>
                  <th>Sender</th>
                  <th>Subject</th>
                  <th>Category</th>
                  <th>Status</th>
                  <th>Needs Review</th>
                  <th style={{ width: 40, textAlign: "center" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {queue.items.slice(0, 5).map((item) => {
                  const statusKey = item.processing_status.toLowerCase().replace(/_/g, "-");
                  return (
                    <tr key={item.id} onClick={onOpenQueue} style={{ cursor: "pointer" }}>
                      <td>
                        <input type="checkbox" readOnly onClick={(e) => e.stopPropagation()} />
                      </td>
                      <td style={{ whiteSpace: "nowrap" }}>{formatDate(item.received_at || item.created_at)}</td>
                      <td>
                        <strong>{item.sender?.split("@")[0].replace(/[._]/g, " ") || item.sender}</strong>
                      </td>
                      <td>
                        <span style={{ fontWeight: 600, color: "var(--color-black)" }}>{item.subject}</span>
                      </td>
                      <td>{categoryLabels[item.category ?? "general_message"] || item.category}</td>
                      <td>
                        <span className={`status-pill ${statusKey}`}>
                          {item.processing_status === "COMPLETED" && <Check size={11} />}
                          {item.processing_status === "AWAITING_DOCUMENTS" && <Clock size={11} />}
                          {item.processing_status === "BLOCKED" && <AlertCircle size={11} />}
                          {item.processing_status === "FAILED" && <X size={11} />}
                          {statusLabels[item.processing_status] || item.processing_status}
                        </span>
                      </td>
                      <td>
                        <span className={item.needs_review ? "review-text-yes" : "review-text-no"}>
                          {item.needs_review ? "Yes" : "No"}
                        </span>
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <button
                          type="button"
                          style={{ border: 0, background: "transparent", cursor: "pointer", color: "var(--color-grey-500)" }}
                          onClick={(e) => {
                            e.stopPropagation();
                            onOpenQueue();
                          }}
                        >
                          <MoreHorizontal size={16} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState
            title="No emails in queue"
            body="Run initial sync or ingest emails to preview latest activity."
          />
        )}
      </section>
    </section>
  );
}

const MASTER_WAVE_MAIN =
  "M -20,7 C 60,7 100,16 160,16 C 220,16 260,3 295,3 C 330,3 370,6 420,9 C 470,12 510,13 550,11 C 580,9 610,4 660,3 C 720,2 750,14 800,14 C 850,14 880,1 930,1 C 970,1 1010,6 1040,10 C 1070,14 1100,15 1130,12 C 1160,8 1190,2 1230,1";

const MASTER_WAVE_SHEEN =
  "M -20,4 C 60,4 100,13 160,13 C 220,13 260,0 295,0 C 330,0 370,3 420,6 C 470,9 510,10 550,8 C 580,6 610,1 660,0 C 720,-1 750,11 800,11 C 850,11 880,-2 930,-2 C 970,-2 1010,3 1040,7 C 1070,11 1100,12 1130,9 C 1160,5 1190,-1 1230,-2";

function MetricCardWave({ index, totalCards = 7 }: { index: number; totalCards?: number }) {
  const cardCount = Math.max(totalCards, 1);
  const sliceW = 1200 / cardCount;
  const sliceX = (index % cardCount) * sliceW;
  const gradId = `cardWaveGrad_${index}_${cardCount}`;
  const glowId = `cardWaveGlow_${index}_${cardCount}`;
  const sheenId = `cardWaveSheen_${index}_${cardCount}`;

  return (
    <svg
      className="card-ribbon-svg"
      viewBox={`${sliceX} -2 ${sliceW} 26`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#e39439" stopOpacity="0.32" />
          <stop offset="35%" stopColor="#f59e0b" stopOpacity="0.48" />
          <stop offset="70%" stopColor="#f97316" stopOpacity="0.40" />
          <stop offset="100%" stopColor="#e39439" stopOpacity="0.26" />
        </linearGradient>
        <linearGradient id={glowId} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#e39439" stopOpacity="0.10" />
          <stop offset="50%" stopColor="#f59e0b" stopOpacity="0.18" />
          <stop offset="100%" stopColor="#ea580c" stopOpacity="0.08" />
        </linearGradient>
        <linearGradient id={sheenId} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.45" />
          <stop offset="50%" stopColor="#fff7ed" stopOpacity="0.80" />
          <stop offset="100%" stopColor="#fed7aa" stopOpacity="0.30" />
        </linearGradient>
      </defs>
      <path
        d={MASTER_WAVE_MAIN}
        fill="none"
        stroke={`url(#${glowId})`}
        strokeWidth="14"
        strokeLinecap="round"
      />
      <path
        d={MASTER_WAVE_MAIN}
        fill="none"
        stroke={`url(#${gradId})`}
        strokeWidth="7"
        strokeLinecap="round"
      />
      <path
        d={MASTER_WAVE_SHEEN}
        fill="none"
        stroke={`url(#${sheenId})`}
        strokeWidth="1.2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function MetricCard({
  icon,
  label,
  value,
  trendText,
  subTrendText,
  trend,
  tone = "neutral",
  cardIndex = 0,
  totalCards = 7,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  trendText?: string;
  subTrendText?: string;
  trend?: "up" | "down";
  tone?: "neutral" | "good" | "warn" | "bad" | "attention";
  cardIndex?: number;
  totalCards?: number;
}) {
  return (
    <article className={`metric-card metric-${tone}`}>
      <MetricCardWave index={cardIndex} totalCards={totalCards} />
      <div className="metric-card-top">
        <div className="metric-header-left">
          {icon}
          <p>{label}</p>
        </div>
        <div className="sparkline-bars">
          <span style={{ height: 6 }} />
          <span style={{ height: 10 }} />
          <span style={{ height: 14 }} />
        </div>
      </div>
      <div className="metric-value-row">
        <strong>{typeof value === "number" ? value.toLocaleString() : value}</strong>
      </div>
      <div className="metric-footer">
        {trendText && (
          <span className={cx("trend-badge", trend)}>
            {trend === "up" ? <ArrowUpRight size={13} /> : trend === "down" ? <ArrowDownRight size={13} /> : null}
            {trendText}
          </span>
        )}
        {subTrendText && (
          <span className={cx("trend-badge", trend)}>
            {trend === "up" ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
            {subTrendText}
          </span>
        )}
      </div>
    </article>
  );
}

function getPaginationItems(current: number, totalPages: number): Array<number | string> {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, i) => i);
  }

  const pages = new Set<number>();
  pages.add(0);
  pages.add(totalPages - 1);

  for (let i = Math.max(0, current - 1); i <= Math.min(totalPages - 1, current + 1); i++) {
    pages.add(i);
  }

  if (current === 0) {
    pages.add(1);
    pages.add(2);
  } else if (current === 1) {
    pages.add(2);
    pages.add(3);
  } else if (current === totalPages - 1) {
    pages.add(totalPages - 2);
    pages.add(totalPages - 3);
  } else if (current === totalPages - 2) {
    pages.add(totalPages - 3);
    pages.add(totalPages - 4);
  }

  const sorted = Array.from(pages).sort((a, b) => a - b);
  const result: Array<number | string> = [];

  for (let i = 0; i < sorted.length; i++) {
    const pageNum = sorted[i];
    if (i > 0) {
      const prev = sorted[i - 1];
      if (pageNum - prev === 2) {
        result.push(prev + 1);
      } else if (pageNum - prev > 2) {
        result.push(`ellipsis-${prev}`);
      }
    }
    result.push(pageNum);
  }

  return result;
}

function QueuePage({
  page,
  queue,
  detail,
  detailState,
  queueState,
  filters,
  onFilters,
  onSelect,
  onOpenReview,
  onReprocess,
  onCloseDetail,
  onPage,
  onGoToPage,
}: {
  page: number;
  queue: EmailQueuePage | null;
  detail: ProductEmailDetail | null;
  detailState: LoadState;
  queueState: LoadState;
  filters: QueueFilters;
  onFilters: (filters: QueueFilters) => void;
  onSelect: (email: ProductEmailSummary) => void;
  onOpenReview: (reviewId: string) => void;
  onReprocess: (emailId: string) => void;
  onCloseDetail?: () => void;
  onPage: (direction: "next" | "previous") => void;
  onGoToPage: (pageIndex: number) => void;
}) {
  const [isFloating, setIsFloating] = useState(false);
  const [panelWidth, setPanelWidth] = useState(520);
  const [isResizing, setIsResizing] = useState(false);
  const tableWrapRef = useRef<HTMLDivElement>(null);

  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    const startX = e.clientX;
    const startW = panelWidth;

    const onMouseMove = (moveEvent: MouseEvent) => {
      const delta = startX - moveEvent.clientX;
      const newWidth = Math.min(Math.max(startW + delta, 360), Math.round(window.innerWidth * 0.65));
      setPanelWidth(newWidth);
    };

    const onMouseUp = () => {
      setIsResizing(false);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  }, [panelWidth]);

  const scrollTable = (direction: "left" | "right") => {
    if (tableWrapRef.current) {
      const scrollAmount = direction === "left" ? -300 : 300;
      tableWrapRef.current.scrollBy({ left: scrollAmount, behavior: "smooth" });
    }
  };

  const pageSize = filters.limit ?? 20;
  const total = queue?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const canPrevious = page > 0;
  const canNext = queue ? queue.skip + pageSize < total : false;
  const startItem = total === 0 ? 0 : page * pageSize + 1;
  const endItem = Math.min(total, (page + 1) * pageSize);
  const paginationItems = getPaginationItems(page, totalPages);

  const layoutStyle = !isFloating && detail
    ? ({
        "--queue-detail-width": `${panelWidth}px`,
      } as React.CSSProperties)
    : undefined;

  return (
    <section
      className={cx("queue-layout", isFloating && "floating-layout", isResizing && "is-resizing", !detail && "queue-layout-empty")}
      style={layoutStyle}
    >
      <div className="surface-panel queue-panel">
        <div className="section-header queue-header">
          <div>
            <p className="eyebrow">Operational queue</p>
            <h2>Email Queue</h2>
          </div>
          <div className="queue-header-right">
            <button
              type="button"
              className={cx("floating-panel-btn", isFloating && "active")}
              onClick={() => setIsFloating(!isFloating)}
              title={isFloating ? "Switch back to side-by-side split view" : "Expand table to full width to view all columns"}
            >
              {isFloating ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
              <span>{isFloating ? "Split View" : "Full Table View"}</span>
            </button>
            <span className="total-pill">{queue?.total ?? 0} cases</span>
          </div>
        </div>

        <div className="filters" aria-label="Queue filters">
          <label>
            <Search size={16} aria-hidden="true" />
            <input
              aria-label="Search queue"
              placeholder="Search sender, subject, reference"
              value={filters.search ?? ""}
              onChange={(event) => onFilters({ ...filters, search: event.target.value, skip: 0 })}
            />
          </label>
          <select
            aria-label="Filter by status"
            value={filters.status ?? ""}
            onChange={(event) =>
              onFilters({ ...filters, status: event.target.value as ProcessingStatus | "", skip: 0 })
            }
          >
            <option value="">All statuses</option>
            {statusOptions.map((status) => (
              <option key={status} value={status}>
                {statusLabels[status]}
              </option>
            ))}
          </select>
          <select
            aria-label="Filter by category"
            value={filters.category ?? ""}
            onChange={(event) =>
              onFilters({ ...filters, category: event.target.value as ProductCategory | "", skip: 0 })
            }
          >
            <option value="">All categories</option>
            {categoryOptions.map((category) => (
              <option key={category} value={category}>
                {categoryLabels[category]}
              </option>
            ))}
          </select>
          <select
            aria-label="Filter by review need"
            value={filters.needs_review ?? ""}
            onChange={(event) =>
              onFilters({ ...filters, needs_review: event.target.value as "true" | "false" | "", skip: 0 })
            }
          >
            <option value="">All review states</option>
            <option value="true">Needs review</option>
            <option value="false">No review need</option>
          </select>
        </div>

        <div className="table-scroll-bar">
          <button
            type="button"
            className="table-scroll-arrow left"
            onClick={() => scrollTable("left")}
            aria-label="Scroll table left"
            title="Scroll table left"
          >
            <ChevronLeft size={16} />
          </button>
          <button
            type="button"
            className="table-scroll-arrow right"
            onClick={() => scrollTable("right")}
            aria-label="Scroll table right"
            title="Scroll table right"
          >
            <ChevronRight size={16} />
          </button>
        </div>

        {queueState === "loading" ? (
          <LoadingRows />
        ) : queue?.items.length ? (
          <>
            <div className="table-wrap" ref={tableWrapRef}>
              <table className="queue-table" aria-label="Email queue">
                <thead>
                  <tr>
                    <th scope="col">Sender</th>
                    <th scope="col">Subject</th>
                    <th scope="col">Category</th>
                    <th scope="col">Status</th>
                    <th scope="col">Readiness</th>
                    <th scope="col">Review</th>
                    <th scope="col">Received</th>
                  </tr>
                </thead>
                <tbody>
                  {queue.items.map((item) => (
                    <tr
                      key={item.id}
                      className={cx(detail?.email.id === item.id && "selected-row")}
                      onClick={() => onSelect(item)}
                      aria-selected={detail?.email.id === item.id}
                    >
                      <td>
                        <strong>{item.sender?.split("@")[0]?.replace(/[._]/g, " ") || item.sender}</strong>
                        <span className="subtle">{item.external_message_id}</span>
                      </td>
                      <td>
                        <button
                          className="table-link"
                          onClick={(event) => {
                            event.stopPropagation();
                            onSelect(item);
                          }}
                          type="button"
                        >
                          {item.subject}
                        </button>
                        <span className="subtle">{item.attachment_count} attachment(s)</span>
                      </td>
                      <td>
                        <StatusBadge value={item.category} />
                      </td>
                      <td>
                        <StatusBadge value={item.processing_status} />
                      </td>
                      <td>
                        <span className="subtle">
                          {item.comparison_readiness ? readinessLabels[item.comparison_readiness] || item.comparison_readiness : "—"}
                        </span>
                      </td>
                      <td>
                        {item.review_id ? (
                          <button
                            type="button"
                            className="table-link"
                            aria-label="Open Review"
                            onClick={(event) => {
                              event.stopPropagation();
                              onOpenReview(item.review_id!);
                            }}
                          >
                            <StatusBadge value={item.review_status || "OPEN"} />
                            <span className="sr-only">Open Review</span>
                          </button>
                        ) : item.processing_status === "AWAITING_DOCUMENTS" ? (
                          <span className="badge badge-warn">Awaiting Documents</span>
                        ) : item.processing_status === "FAILED" ? (
                          <button
                            type="button"
                            className="table-link"
                            onClick={(event) => {
                              event.stopPropagation();
                              onReprocess(item.id);
                            }}
                          >
                            Retry/Reprocess
                          </button>
                        ) : (
                          <span className="badge badge-muted">No active review</span>
                        )}
                      </td>
                      <td>
                        <span className="subtle">{formatDate(item.received_at || item.created_at)}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="pagination">
              <span className="pagination-info">
                Showing {startItem}–{endItem} of {total}
              </span>
              <div className="pagination-nav">
                <button
                  className="pagination-btn pagination-btn-nav"
                  disabled={!canPrevious}
                  onClick={() => onPage("previous")}
                  type="button"
                >
                  ‹ Previous
                </button>
                {paginationItems.map((item) =>
                  typeof item === "number" ? (
                    <button
                      key={item}
                      type="button"
                      className={cx("pagination-btn pagination-btn-page", item === page && "active")}
                      onClick={() => onGoToPage(item)}
                    >
                      {item + 1}
                    </button>
                  ) : (
                    <span key={item} className="pagination-ellipsis">
                      …
                    </span>
                  )
                )}
                <button
                  className="pagination-btn pagination-btn-nav"
                  disabled={!canNext}
                  onClick={() => onPage("next")}
                  type="button"
                >
                  Next ›
                </button>
              </div>
            </div>
          </>
        ) : (
          <EmptyState
            title="No emails match your filter"
            body="Try adjusting your status, category, or search term to see more cases."
          />
        )}
      </div>

      {isFloating ? (
        detail ? (
          <>
            <div className="floating-backdrop" onClick={onCloseDetail} />
            <div className="surface-panel detail-panel floating-modal">
              <EmailDetailContent detail={detail} onClose={onCloseDetail} onOpenReview={onOpenReview} onReprocess={onReprocess} />
            </div>
          </>
        ) : null
      ) : (
        <div className="detail-panel-wrapper">
          {detail ? (
            <div
              className={cx("panel-resize-handle", isResizing && "dragging")}
              onMouseDown={startResize}
              title="Drag to resize inspector panel width"
              role="separator"
              aria-orientation="vertical"
            >
              <div className="resize-handle-bar" />
            </div>
          ) : null}
          <div className={cx("surface-panel detail-panel", !detail && "detail-panel-empty")}>
            {detailState === "loading" ? (
              <LoadingRows />
            ) : detail ? (
              <EmailDetailContent detail={detail} onClose={onCloseDetail} onOpenReview={onOpenReview} onReprocess={onReprocess} />
            ) : (
              <EmptyState
                title="Select an email"
                body="Choose any message from the operational queue to view classification, attachments, timeline, and document comparison."
              />
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function EmailDetailContent({
  detail,
  onClose,
  onOpenReview,
  onReprocess,
}: {
  detail: ProductEmailDetail;
  onClose?: () => void;
  onOpenReview: (reviewId: string) => void;
  onReprocess: (emailId: string) => void;
}) {
  const latestFailure = [...detail.timeline].reverse().find((event) => event.new_status === "FAILED");
  return (
    <div>
      <div className="detail-title">
        <div className="detail-header-top">
          <p className="eyebrow" style={{ margin: 0 }}>Case inspector</p>
          {onClose && (
            <button
              type="button"
              className="close-detail-btn"
              onClick={onClose}
              aria-label="Close case inspector"
              title="Close case inspector"
            >
              <X size={15} />
            </button>
          )}
        </div>
        <h2>{detail.email.subject}</h2>
        <p>
          {detail.email.sender || "Unknown sender"} · {formatDate(detail.email.received_at || detail.email.created_at)}
        </p>
        <div className="detail-badge-row">
          <StatusBadge value={detail.email.category} />
          <StatusBadge value={detail.email.processing_status} />
          {detail.email.review_status &&
          displayLabel(detail.email.processing_status) !== displayLabel(detail.email.review_status) ? (
            <StatusBadge value={detail.email.review_status} />
          ) : null}
        </div>
        <div className="detail-actions">
          {detail.email.review_id ? (
            <button
              className="button-primary button-action-cta"
              type="button"
              onClick={() => onOpenReview(detail.email.review_id!)}
              title="Open Human Review workspace for this case"
            >
              <ShieldAlert size={15} />
              <span>Open Human Review</span>
              <ArrowUpRight size={15} />
            </button>
          ) : null}
          {detail.email.processing_status === "FAILED" ? (
            <button className="button-primary" type="button" onClick={() => onReprocess(detail.email.id)}>Retry / Reprocess</button>
          ) : null}
        </div>
      </div>

      <div className="detail-section">
        <h3>Email information</h3>
        <div className="info-grid">
          <div className="info-item">
            <span>Category</span>
            <strong>{categoryLabels[detail.email.category ?? "general_message"]}</strong>
          </div>
          <div className="info-item">
            <span>Recipients</span>
            <strong>{detail.recipients.length ? detail.recipients.join(", ") : "Not supplied"}</strong>
          </div>
          <div className="info-item">
            <span>Status</span>
            <strong>{statusLabels[detail.email.processing_status]}</strong>
          </div>
          <div className="info-item">
            <span>Attachments</span>
            <strong>{detail.attachments.length}</strong>
          </div>
        </div>
        <details className="body-preview">
          <summary>Message preview</summary>
          <p>{detail.body || "No message body available."}</p>
        </details>
      </div>

      {detail.email.processing_status === "FAILED" ? (
        <div className="detail-section">
          <div className="state-note failed" role="alert">
            <strong>Processing failed</strong>
            <span>{latestFailure ? displayLabel(latestFailure.reason_code) : "A technical processing error occurred."}</span>
            <small>Retrying reprocesses this email from backend truth; it does not send the case to Human Review.</small>
          </div>
        </div>
      ) : null}

      {detail.comparison ? (
        <div className="detail-section">
          <div className="section-heading-row">
            <h3>Seven-Field Verification</h3>
            {detail.comparison.mismatch_found ? (
              <span className="comparison-pill mismatch">
                Mismatch ({detail.comparison.mismatched_fields.length})
              </span>
            ) : detail.comparison.unresolved_fields.length ? (
              <span className="comparison-pill unresolved">
                {detail.comparison.unresolved_fields.length} field(s) require human review
              </span>
            ) : (
              <span className="comparison-pill match">
                No mismatch detected
              </span>
            )}
          </div>
          <div className="comparison-table-wrap">
            <table
              className="comparison-table"
              aria-label="Seven-field SI and Draft BL comparison"
            >
              <colgroup>
                <col style={{ width: "23%", minWidth: "100px" }} />
                <col style={{ width: "32%", minWidth: "120px" }} />
                <col style={{ width: "26%", minWidth: "90px" }} />
                <col style={{ width: "19%", minWidth: "85px" }} />
              </colgroup>
              <thead>
                <tr>
                  <th scope="col">Field</th>
                  <th scope="col">Shipping Instruction</th>
                  <th scope="col">Draft BL</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {canonicalFields.map((fieldKey) => {
                  const field = detail.comparison?.fields.find((f) => f.field === fieldKey);
                  const status = field?.status ?? "UNRESOLVED";
                  const isMismatch = status === "MISMATCH";
                  const isUnresolved = status === "UNRESOLVED";
                  return (
                    <React.Fragment key={fieldKey}>
                    <tr
                      className={cx(
                        isMismatch && "field-mismatch",
                        isUnresolved && "field-unresolved",
                      )}
                    >
                      <th scope="row">{labelForField(fieldKey)}</th>
                      <td>{displayValue(field?.si.raw)}</td>
                      <td>{displayValue(field?.bl.raw)}</td>
                      <td>
                        <StatusBadge
                          tone={isMismatch ? "bad" : isUnresolved ? "warn" : "good"}
                          value={fieldStatusLabels[status]}
                        />
                      </td>
                    </tr>
                    {field?.evidence?.length ? (
                      <tr className="evidence-row">
                        <td colSpan={4}>
                          <details>
                            <summary>View evidence for {labelForField(fieldKey)}</summary>
                            <div className="evidence-grid">
                              {field.evidence.map((item, index) => (
                                <div key={`${fieldKey}-${index}`}>
                                  <strong>{item.filename || item.document_role || "Source evidence"}</strong>
                                  <span>{item.text_span || item.reason || "Structured source evidence"}</span>
                                  <small>{item.page ? `Page ${item.page}` : item.source_type || "Document"}</small>
                                </div>
                              ))}
                            </div>
                          </details>
                        </td>
                      </tr>
                    ) : null}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : detail.email.comparison_readiness === "AWAITING_DOCUMENTS" ? (
        <div className="detail-section">
          <h3>Comparison Status</h3>
          <div className="state-note awaiting">
            <strong>Awaiting Documents</strong>
            <span>The comparison request is valid, but a required document has not arrived yet.</span>
            <small>{detail.documents.length ? `${detail.documents.length} document(s) are currently available.` : "No SI or Draft BL document is currently available."}</small>
          </div>
        </div>
      ) : null}

      <div className="detail-section">
        <h3>Documents ({detail.documents.length})</h3>
        {detail.documents.length ? (
          <div className="attachment-list">
            {detail.documents.map((document) => (
              <div className="attachment-row" key={document.id}>
                <FileSearch size={16} />
                <div>
                  <strong>{document.filename}</strong>
                  <p>{displayLabel(document.role)} · {displayLabel(document.validation_outcome)} · {displayLabel(document.read_status || "NOT_READ")}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="No documents materialized" body="This email has no validated SI or Draft BL document to display." />
        )}
      </div>

      <div className="detail-section">
        <h3>Processing Timeline</h3>
        {detail.timeline.length ? <div className="timeline">
          {detail.timeline.map((event) => (
            <div className="timeline-row" key={event.id}>
              <span />
              <div>
                <strong>{(statusLabels as Record<string, string>)[event.new_status] || event.new_status}</strong>
                <p>{displayLabel(event.reason_code)} · {formatDate(event.created_at)}</p>
                <small className="technical-code">{event.reason_code}</small>
              </div>
            </div>
          ))}
        </div> : <EmptyState title="No events yet" body="Processing and review events will appear here as the case advances." />}
      </div>
    </div>
  );
}

function getReviewActionGuidance(
  review: ProductReview,
  isFieldLevel: boolean,
  unresolvedCount: number,
  affectedFieldCount?: number
): { actionTitle: string; instruction: string } {
  if (review.case_origin === "LEGACY") {
    return {
      actionTitle: "No action required",
      instruction: "Historical review record is read-only.",
    };
  }

  if (isFieldLevel) {
    const count = affectedFieldCount ?? (review.affected_fields?.length || unresolvedCount || 1);
    const isMismatch = review.reason_code === "COMPARISON_MISMATCH";
    return {
      actionTitle: isMismatch ? "Review mismatched fields" : (review.suggested_action || "Review unresolved fields"),
      instruction: `Please review the ${count} ${isMismatch ? "mismatched" : "unresolved"} field(s) below. Click any field chip or table row to edit, enter verified values from documents, and submit "Resolve & Recompare".`,
    };
  }

  switch (review.reason_code) {
    case "WRONG_DOCUMENT_TYPE":
    case "MULTIPLE_CANDIDATES":
      return {
        actionTitle: "Confirm attached shipping documents",
        instruction:
          "The attached file does not appear to be the required shipping document. Verify the document role and obtain the valid Shipping Instruction or Draft BL from the sender.",
      };
    case "MISSING_REQUIRED_ATTACHMENT":
    case "MISSING_ATTACHMENT":
    case "READINESS_UNRESOLVED":
      return {
        actionTitle: "Request or provide the missing document",
        instruction:
          "The required Shipping Instruction or Draft Bill of Lading is missing. Review the available evidence and obtain the missing document from the sender before comparison can continue.",
      };
    case "UNREADABLE_ATTACHMENT":
    case "CORRUPTED_ATTACHMENT":
    case "UNSUPPORTED_ATTACHMENT":
      return {
        actionTitle: "Inspect document readability",
        instruction:
          "The attached document could not be read reliably. Inspect the source file and OCR diagnostics under 'Email & Documents', obtain a clear machine-readable digital document, or reprocess.",
      };
    case "DOCUMENT_ROLE_UNRESOLVED":
      return {
        actionTitle: "Confirm document roles",
        instruction:
          "HolyShip could not determine which file is the Shipping Instruction and which is the Draft BL. Inspect both documents under 'Email & Documents' to verify document types.",
      };
    case "CLASSIFICATION_UNRESOLVED":
      return {
        actionTitle: "Confirm email intent",
        instruction:
          "The email intent is ambiguous between document comparison and other request types. Review the email body and subject under 'Email & Documents' to determine if this requires document comparison, or dismiss with INCORRECT_ROUTING.",
      };
    default:
      return {
        actionTitle: review.suggested_action || "Investigate case exception",
        instruction:
          review.human_explanation ||
          review.reason_text ||
          "Inspect email and document evidence under 'Email & Documents', then decide whether to dismiss or reprocess.",
      };
  }
}

function HumanReviewPageView({
  reviews,
  analytics,
  state,
  selected,
  actionState,
  reviewViewMode,
  onChangeReviewViewMode,
  onSelect,
  onClaim,
  onOverride,
  onResolve,
  onDismiss,
  onReprocess,
  onCaseUpdated,
}: {
  reviews: HumanReviewPage | null;
  analytics: HumanReviewAnalytics | null;
  state: LoadState;
  selected: ProductReview | null;
  actionState: LoadState;
  reviewViewMode: ReviewViewMode;
  onChangeReviewViewMode: (mode: ReviewViewMode) => void;
  onSelect: (reviewId: string) => void;
  onClaim: (reviewer: string) => Promise<void>;
  onOverride: (payload: { document_side: "SI" | "BL"; field: string; corrected_value: string; reviewer_name: string; note?: string }) => Promise<void>;
  onResolve: (reviewer: string, notes?: string) => Promise<void>;
  onDismiss: (reviewer: string, reason: string, notes?: string) => Promise<void>;
  onReprocess?: (emailId: string) => void | Promise<void>;
  onCaseUpdated?: (review: ProductReview) => void | Promise<void>;
}) {
  const [activeStatusFilter, setActiveStatusFilter] = useState("ACTIVE");
  const [historyStatusFilter, setHistoryStatusFilter] = useState("ALL_HISTORY");
  const [reasonFilter, setReasonFilter] = useState("");
  const [reviewerFilter, setReviewerFilter] = useState("");
  const [searchFilter, setSearchFilter] = useState("");
  const [sortFilter, setSortFilter] = useState("newest");
  const [reviewer, setReviewer] = useState(defaultReviewerName);
  const [side, setSide] = useState<"SI" | "BL">("BL");
  const [field, setField] = useState("notify_party");
  const [correctedValue, setCorrectedValue] = useState("");
  const [note, setNote] = useState("");
  const [dismissReason, setDismissReason] = useState("NOT_ACTIONABLE");
  const [detailTab, setDetailTab] = useState<"fields" | "context" | "audit">("fields");

  const [showActionGuidance, setShowActionGuidance] = useState(false);

  useEffect(() => {
    setShowActionGuidance(false);
    if (selected?.reviewer_name) {
      setReviewer(selected.reviewer_name);
    } else {
      setReviewer(defaultReviewerName);
    }

    if (selected?.reason_code) {
      if (selected.reason_code === "CLASSIFICATION_UNRESOLVED") {
        setDismissReason("INCORRECT_ROUTING");
      } else {
        setDismissReason("NOT_ACTIONABLE");
      }
    } else {
      setDismissReason("NOT_ACTIONABLE");
    }
  }, [selected?.id, selected?.reviewer_name, selected?.reason_code]);

  const [reviewPage, setReviewPage] = useState(0);
  const pageSize = 5;

  useEffect(() => {
    setReviewPage(0);
  }, [
    reviewViewMode,
    activeStatusFilter,
    historyStatusFilter,
    reasonFilter,
    reviewerFilter,
    sortFilter,
    searchFilter,
  ]);

  const [panelWidth, setPanelWidth] = useState(540);
  const [isResizing, setIsResizing] = useState(false);

  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    const startX = e.clientX;
    const startW = panelWidth;

    const onMouseMove = (moveEvent: MouseEvent) => {
      const delta = startX - moveEvent.clientX;
      const newWidth = Math.min(Math.max(startW + delta, 380), Math.round(window.innerWidth * 0.7));
      setPanelWidth(newWidth);
    };

    const onMouseUp = () => {
      setIsResizing(false);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  }, [panelWidth]);

  const visibleReviews = (reviews?.items ?? []).filter((review) => {
    const search = searchFilter.trim().toLowerCase();
    const matchesSearch = !search || `${review.email?.subject ?? ""} ${review.email?.sender ?? ""} ${review.reason_code}`.toLowerCase().includes(search);
    const matchesReason =
      !reasonFilter ||
      review.reason_code === reasonFilter ||
      review.canonical_reason === reasonFilter ||
      review.presentation_title === reasonFilter ||
      reasonLabels[review.reason_code] === reasonFilter;
    const matchesReviewer = !reviewerFilter || (review.reviewer_name ?? "").toLowerCase().includes(reviewerFilter.toLowerCase());

    if (reviewViewMode === "ACTIVE") {
      const isActionable = review.case_origin === "ACTIVE" && ["OPEN", "IN_REVIEW"].includes(review.status);
      if (!isActionable) return false;

      const matchesStatus =
        activeStatusFilter === "ACTIVE" || !activeStatusFilter
          ? true
          : activeStatusFilter === "OPEN"
          ? review.status === "OPEN"
          : activeStatusFilter === "IN_REVIEW"
          ? review.status === "IN_REVIEW"
          : true;
      return matchesStatus && matchesReason && matchesReviewer && matchesSearch;
    } else {
      // HISTORY mode
      const isHistorical = review.case_origin === "LEGACY" || review.status === "RESOLVED" || review.status === "DISMISSED";
      if (!isHistorical) return false;

      const matchesStatus =
        historyStatusFilter === "ALL_HISTORY"
          ? true
          : historyStatusFilter === "LEGACY"
          ? review.case_origin === "LEGACY"
          : historyStatusFilter === "RESOLVED"
          ? review.status === "RESOLVED"
          : historyStatusFilter === "DISMISSED"
          ? review.status === "DISMISSED"
          : true;
      return matchesStatus && matchesReason && matchesReviewer && matchesSearch;
    }
  }).sort((left, right) => {
    if (sortFilter === "priority") {
      const rank = { HIGH: 0, MEDIUM: 1, LOW: 2 } as const;
      const priorityDelta = (rank[left.priority] ?? 3) - (rank[right.priority] ?? 3);
      if (priorityDelta !== 0) return priorityDelta;
      return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
    }
    const delta = new Date(left.created_at).getTime() - new Date(right.created_at).getTime();
    return sortFilter === "oldest" || sortFilter === "age" ? delta : -delta;
  });

  const reasons = [
    ...new Set(
      (reviews?.items ?? []).map(
        (review) => review.canonical_reason || review.presentation_title || reasonLabels[review.reason_code] || review.reason_code
      )
    ),
  ].sort();
  const activeOverrides = selected?.overrides?.filter((item) => item.active) ?? [];
  const selectedUnresolved = selected?.comparison?.unresolved_fields.length ?? 0;
  const inputType = field === "container_count" || field === "gross_weight_kg" ? "number" : "text";
  const inputStep = field === "container_count" ? "1" : field === "gross_weight_kg" ? "any" : undefined;
  const rawExplanation = selected?.human_explanation || selected?.reason_text || "";
  const cleanExplanation = rawExplanation.replace(/\s*Affected fields:.*$/i, "").trim() || rawExplanation;

  const nonFieldReasonCodes = new Set([
    "WRONG_DOCUMENT_TYPE",
    "MISSING_REQUIRED_ATTACHMENT",
    "MISSING_ATTACHMENT",
    "UNREADABLE_ATTACHMENT",
    "UNSUPPORTED_ATTACHMENT",
    "CORRUPTED_ATTACHMENT",
    "MULTIPLE_CANDIDATES",
    "DOCUMENT_ROLE_UNRESOLVED",
    "READINESS_UNRESOLVED",
    "CLASSIFICATION_UNRESOLVED",
    "STAGE2_UNRESOLVED",
  ]);

  const isMissingAttachment = Boolean(
    selected &&
    (selected.reason_code === "MISSING_REQUIRED_ATTACHMENT" ||
     selected.reason_code === "MISSING_ATTACHMENT" ||
     selected.reason_code === "READINESS_UNRESOLVED")
  );

  const isWrongDocumentType = Boolean(
    selected &&
    (selected.reason_code === "WRONG_DOCUMENT_TYPE" ||
     selected.reason_code === "MULTIPLE_CANDIDATES")
  );

  const isUnreadableDocument = Boolean(
    selected &&
    (selected.reason_code === "UNREADABLE_ATTACHMENT" ||
     selected.reason_code === "CORRUPTED_ATTACHMENT" ||
     selected.reason_code === "UNSUPPORTED_ATTACHMENT")
  );

  const docs = selected?.documents ?? [];
  const hasSI = docs.some(
    (d) => d.role === "SI" && (d.validation_outcome === "VALID" || !d.validation_outcome)
  );
  const hasBL = docs.some(
    (d) => (d.role === "BL" || d.role === "DRAFT_BL") && (d.validation_outcome === "VALID" || !d.validation_outcome)
  );

  const missingDocName = !hasSI && !hasBL
    ? "Shipping Instruction (SI) and Draft Bill of Lading (BL)"
    : !hasBL
    ? "Draft BL"
    : "Shipping Instruction (SI)";

  const isFieldLevel = Boolean(
    selected &&
    selected.comparison &&
    !nonFieldReasonCodes.has(selected.reason_code) &&
    ((selected.affected_fields && selected.affected_fields.length > 0) ||
     selected.reason_code === "COMPARISON_UNRESOLVED" ||
     selected.reason_code === "COMPARISON_MISMATCH" ||
     selected.reason_code === "MISSING_REQUIRED_VALUE")
  );

  const isMissingRequiredValue = Boolean(
    selected &&
    isFieldLevel &&
    (selected.reason_code === "MISSING_REQUIRED_VALUE" ||
     selected.reason_code === "COMPARISON_UNRESOLVED")
  );

  const actuallyAffectedFields = (
    selected?.affected_fields && selected.affected_fields.length > 0
      ? selected.affected_fields
      : canonicalFields
  ).filter((f) => {
    const compared = selected?.comparison?.fields.find((item) => item.field === f);
    return !compared || compared.status !== "MATCH";
  });

  const guidance = selected
    ? getReviewActionGuidance(selected, isFieldLevel, selectedUnresolved, actuallyAffectedFields.length)
    : { actionTitle: "Review unresolved fields", instruction: "" };

  // Total count in current view mode population
  const totalInCurrentMode = (reviews?.items ?? []).filter((review) => {
    if (reviewViewMode === "ACTIVE") {
      return review.case_origin === "ACTIVE" && ["OPEN", "IN_REVIEW"].includes(review.status);
    }
    return review.case_origin === "LEGACY" || review.status === "RESOLVED" || review.status === "DISMISSED";
  }).length;

  const countLabel =
    reviewViewMode === "ACTIVE"
      ? visibleReviews.length === totalInCurrentMode
        ? `${totalInCurrentMode} active`
        : `${visibleReviews.length} shown · ${totalInCurrentMode} active`
      : visibleReviews.length === totalInCurrentMode
      ? `${totalInCurrentMode} historical`
      : `${visibleReviews.length} shown · ${totalInCurrentMode} historical`;

  const totalReviews = visibleReviews.length;
  const totalPages = Math.max(1, Math.ceil(totalReviews / pageSize));
  const safePage = Math.min(reviewPage, totalPages - 1);
  const canPrevious = safePage > 0;
  const canNext = safePage + 1 < totalPages;
  const startItem = totalReviews === 0 ? 0 : safePage * pageSize + 1;
  const endItem = Math.min(totalReviews, (safePage + 1) * pageSize);
  const paginatedReviews = visibleReviews.slice(safePage * pageSize, (safePage + 1) * pageSize);
  const paginationItems = getPaginationItems(safePage, totalPages);

  const layoutStyle = selected
    ? ({
        "--queue-detail-width": `${panelWidth}px`,
      } as React.CSSProperties)
    : undefined;

  return (
    <section className="page-grid">
      <section className="overview-summary-panel" aria-label="Human Review analytics">
        <div className="metric-grid human-review-metric-grid" aria-label="Human Review analytics">
          <MetricCard cardIndex={0} totalCards={5} icon={<ShieldAlert size={18} color="currentColor" />} label="Open" value={analytics?.open_count ?? 0} trendText="Active review cases" tone="attention" />
          <MetricCard cardIndex={1} totalCards={5} icon={<Clock size={18} color="var(--color-warn)" />} label="In Review" value={analytics?.in_review_count ?? 0} trendText="Currently claimed" tone="neutral" />
          <MetricCard cardIndex={2} totalCards={5} icon={<CircleCheck size={18} color="var(--color-success)" />} label="Resolved Today" value={analytics?.resolved_today_count ?? 0} trendText={analytics?.resolved_count ? String(analytics.resolved_count) + " resolved total" : "No resolved cases"} tone="good" />
          <MetricCard cardIndex={3} totalCards={5} icon={<Archive size={18} color="var(--color-grey-700)" />} label="Dismissed" value={analytics?.dismissed_count ?? 0} trendText="Review decisions" tone="neutral" />
          <MetricCard cardIndex={4} totalCards={5} icon={<Clock size={18} color="var(--color-warn)" />} label="Avg Open Age" value={analytics?.average_open_age_minutes == null ? "—" : String(Math.round(analytics.average_open_age_minutes)) + "m"} trendText="Current open cases" tone="neutral" />
        </div>
      </section>
      <section className={cx("queue-layout", isResizing && "is-resizing", !selected && "queue-layout-empty")} style={layoutStyle}>
      <div className="surface-panel queue-panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Actionable exception handling</p>
            <h2>Human Review Queue</h2>
          </div>
          <span className="total-pill">{countLabel}</span>
        </div>
        <div className="review-filters" aria-label="Human Review filters">
          <div className="review-filters-row-1">
            <label><Search size={16} /><input aria-label="Search reviews" placeholder="Search subject, sender, reason" value={searchFilter} onChange={(event) => setSearchFilter(event.target.value)} /></label>
            <div className="review-view-switch" role="tablist" aria-label="Review view mode">
              <button
                type="button"
                role="tab"
                aria-selected={reviewViewMode === "ACTIVE"}
                className={cx(reviewViewMode === "ACTIVE" && "active")}
                onClick={() => onChangeReviewViewMode("ACTIVE")}
              >
                Active Reviews
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={reviewViewMode === "HISTORY"}
                className={cx(reviewViewMode === "HISTORY" && "active")}
                onClick={() => onChangeReviewViewMode("HISTORY")}
              >
                History
              </button>
            </div>
          </div>
          <div className="review-filters-row">
            {reviewViewMode === "ACTIVE" ? (
              <select aria-label="Filter review status" value={activeStatusFilter} onChange={(event) => setActiveStatusFilter(event.target.value)}>
                <option value="ACTIVE">Open and in review</option>
                <option value="OPEN">Open</option>
                <option value="IN_REVIEW">In Review</option>
                <option value="">All active statuses</option>
              </select>
            ) : (
              <select aria-label="Filter review status" value={historyStatusFilter} onChange={(event) => setHistoryStatusFilter(event.target.value)}>
                <option value="ALL_HISTORY">All history</option>
                <option value="LEGACY">Legacy review records</option>
                <option value="RESOLVED">Resolved</option>
                <option value="DISMISSED">Dismissed</option>
              </select>
            )}
            <select aria-label="Filter review reason" value={reasonFilter} onChange={(event) => setReasonFilter(event.target.value)}>
              <option value="">All reasons</option>{reasons.map((reason) => <option key={reason}>{reason}</option>)}
            </select>
          </div>
          <div className="review-filters-row">
            <input aria-label="Filter reviewer" placeholder="Reviewer" value={reviewerFilter} onChange={(event) => setReviewerFilter(event.target.value)} />
            <select aria-label="Sort queue" value={sortFilter} onChange={(event) => setSortFilter(event.target.value)}>
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="age">Review age</option>
              <option value="priority">Priority</option>
            </select>
          </div>
        </div>
        {state === "loading" ? <LoadingRows /> : visibleReviews.length ? (
          <>
            <div className="review-list">
              {paginatedReviews.map((review) => (
                <article className={cx("review-card", selected?.id === review.id && "selected", review.case_origin === "LEGACY" && "legacy")} key={review.id}>
                  <div className="review-card-header">
                    <div>
                      <h2>{review.email?.subject ?? "Unknown subject"}</h2>
                      <p>{review.email?.sender || "Unknown sender"}</p>
                      <strong className="review-reason">{review.case_origin === "LEGACY" ? "Historical review record" : (review.canonical_reason || review.presentation_title || reasonLabels[review.reason_code] || review.reason_text || displayLabel(review.reason_code))}</strong>
                      <p className="human-explanation">{review.human_explanation}</p>
                      {review.affected_fields?.length ? (
                        <p className="affected-fields-summary">Affected fields: {review.affected_fields.map((f) => labelForField(f)).join(", ")}</p>
                      ) : (
                        <p className="affected-fields-summary">Affected area: {review.affected_area || "Review case"}</p>
                      )}
                      <p className="suggested-action-summary">Next action: {review.case_origin === "LEGACY" ? "No action required" : (review.suggested_action || "Open Human Review")}</p>
                      <p className="age-summary">Age: {review.age_minutes} mins</p>
                    </div>
                    <button
                      type="button"
                      className={cx(review.case_origin === "LEGACY" && "button-view-history")}
                      onClick={() => onSelect(review.id)}
                    >
                      {review.case_origin === "LEGACY" ? "View History" : "Open Review"}
                    </button>
                  </div>
                  <div className="review-meta">
                    <StatusBadge value={review.priority} />
                    {review.case_origin === "LEGACY" ? (
                      <span className="badge badge-neutral">COMPLETED</span>
                    ) : (
                      <StatusBadge value={review.status} />
                    )}
                    {review.email?.processing_status && statusLabels[review.email.processing_status] !== reviewStatusLabels[review.status] ? (
                      <StatusBadge value={review.email.processing_status} />
                    ) : null}
                    {review.case_origin === "LEGACY" ? <span className="badge badge-muted">Historical review record</span> : null}
                    <span className="subtle">{review.reviewer_name || "Unassigned"}</span>{review.claimed_at ? <span className="subtle">Claimed {formatDate(review.claimed_at)}</span> : null}
                    <span className="subtle">{review.case_origin === "LEGACY" ? "No action required" : (review.affected_fields.length ? review.affected_fields.length + " affected field(s)" : (review.affected_area || "Email-level issue"))}</span>
                    <span className="subtle">{formatDate(review.created_at)}</span>
                  </div>
                </article>
              ))}
            </div>

            <div className="pagination">
              <span className="pagination-info">
                Showing {startItem}–{endItem} of {totalReviews}
              </span>
              <div className="pagination-nav">
                <button
                  className="pagination-btn pagination-btn-nav"
                  disabled={!canPrevious}
                  onClick={() => setReviewPage((p) => Math.max(0, p - 1))}
                  type="button"
                >
                  ‹ Previous
                </button>
                {paginationItems.map((item) =>
                  typeof item === "number" ? (
                    <button
                      key={item}
                      type="button"
                      className={cx("pagination-btn pagination-btn-page", item === safePage && "active")}
                      onClick={() => setReviewPage(item)}
                    >
                      {item + 1}
                    </button>
                  ) : (
                    <span key={item} className="pagination-ellipsis">
                      …
                    </span>
                  )
                )}
                <button
                  className="pagination-btn pagination-btn-nav"
                  disabled={!canNext}
                  onClick={() => setReviewPage((p) => Math.min(totalPages - 1, p + 1))}
                  type="button"
                >
                  Next ›
                </button>
              </div>
            </div>
          </>
        ) : reviewViewMode === "ACTIVE" ? (
          <EmptyState title="No active review cases" body="Awaiting-document and technical-failure states are intentionally handled outside Human Review." />
        ) : (
          <EmptyState title="No review history" body="No historical, resolved, or dismissed review records match the current filters." />
        )}
      </div>

      <div className="detail-panel-wrapper">
        {selected ? (
          <div
            className={cx("panel-resize-handle", isResizing && "dragging")}
            onMouseDown={startResize}
            title="Drag to resize detail panel"
          >
            <div className="resize-handle-bar" />
          </div>
        ) : null}
        <div className={cx("surface-panel detail-panel", !selected && "detail-panel-empty")}>
          {!selected ? <EmptyState title="Select a review" body="Open an actionable case to inspect documents, seven fields, provenance, overrides, and its audit trail." /> : (
            <div className="review-detail">
              <header className="detail-sticky-header">
                <div className="detail-header-meta">
                  <div className="detail-header-info">
                    <div className="detail-eyebrow-row">
                      <span className="eyebrow">Human Review</span>
                      <span className="case-id-badge">#{selected.id ? String(selected.id).slice(0, 8) : "case"}</span>
                    </div>
                    <h2 className="detail-title-text" title={selected.email?.subject || "Review case"}>
                      {selected.email?.subject || "Review case"}
                    </h2>
                    <p className="detail-sender-text">
                      {selected.email?.sender || "Unknown sender"} · {formatDate(selected.created_at)}
                    </p>
                  </div>
                  <div className="detail-header-badges">
                    <StatusBadge value={selected.priority} />
                    <StatusBadge value={selected.status} />
                    {selected.email?.processing_status && statusLabels[selected.email.processing_status] !== reviewStatusLabels[selected.status] ? (
                      <StatusBadge value={selected.email.processing_status} />
                    ) : null}
                  </div>
                </div>

                {selected.case_origin === "ACTIVE" ? (
                  <div className="detail-top-action-bar">
                    <div className="reviewer-identity-group">
                      <span className="reviewer-avatar-badge" title="Active operator session">JD</span>
                      <div className="reviewer-input-wrap">
                        <label htmlFor="top-reviewer-input">Reviewer</label>
                        <input
                          id="top-reviewer-input"
                          aria-label="Reviewer name"
                          value={reviewer}
                          onChange={(event) => setReviewer(event.target.value)}
                          placeholder="Reviewer name"
                        />
                      </div>
                    </div>
                    <div className="top-action-buttons">
                      {selected.status === "OPEN" ? (
                        <button
                          className="button-secondary btn-compact"
                          type="button"
                          disabled={actionState === "loading"}
                          onClick={() => void onClaim(reviewer)}
                        >
                          Start / Claim
                        </button>
                      ) : null}
                      {isFieldLevel ? (
                        <button
                          className="button-primary btn-compact"
                          type="button"
                          disabled={actionState === "loading" || selected.status === "DISMISSED"}
                          onClick={() => void onResolve(reviewer, note)}
                        >
                          {actionState === "loading" ? "Recomparing…" : "Resolve & Recompare"}
                        </button>
                      ) : (
                        <button
                          className="button-secondary btn-compact"
                          type="button"
                          disabled={actionState === "loading" || selected.status === "DISMISSED"}
                          onClick={() => void onDismiss(reviewer, dismissReason || "NOT_ACTIONABLE", note)}
                        >
                          {actionState === "loading" ? "Dismissing…" : selected.status === "DISMISSED" ? "Dismissed" : "Dismiss Review"}
                        </button>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="state-note-inline">
                    <span>Historical review record (read-only)</span>
                  </div>
                )}

                <nav className="detail-nav-tabs" role="tablist" aria-label="Review case workspace">
                  <button
                    type="button"
                    role="tab"
                    aria-selected={detailTab === "fields"}
                    className={cx("detail-tab-btn", detailTab === "fields" && "active")}
                    onClick={() => setDetailTab("fields")}
                  >
                    {isFieldLevel ? <CheckCircle2 size={13} /> : <AlertCircle size={13} />}
                    <span>{isFieldLevel ? "Comparison & Overrides" : "Document Exception"}</span>
                    {isFieldLevel ? (
                      selectedUnresolved > 0 ? (
                        <span className="tab-pill-badge unresolved">{selectedUnresolved}</span>
                      ) : null
                    ) : (
                      <span className="tab-pill-badge unresolved">Action Needed</span>
                    )}
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={detailTab === "context"}
                    className={cx("detail-tab-btn", detailTab === "context" && "active")}
                    onClick={() => setDetailTab("context")}
                  >
                    <Mail size={13} />
                    <span>Email & Documents</span>
                    {selected.documents?.length ? (
                      <span className="tab-pill-badge neutral">{selected.documents.length}</span>
                    ) : null}
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={detailTab === "audit"}
                    className={cx("detail-tab-btn", detailTab === "audit" && "active")}
                    onClick={() => setDetailTab("audit")}
                  >
                    <Clock size={13} />
                    <span>Audit Trail</span>
                    {selected.actions?.length ? (
                      <span className="tab-pill-badge neutral">{selected.actions.length}</span>
                    ) : null}
                  </button>
                </nav>
              </header>

              <div className="review-callout">
                <AlertTriangle size={18} aria-hidden="true" />
                <div className="callout-body">
                  <strong className="callout-title">
                    {selected.case_origin === "LEGACY"
                      ? "Historical review record"
                      : isMissingRequiredValue
                      ? "Missing Required Value"
                      : isWrongDocumentType
                      ? "Wrong Document Type"
                      : isUnreadableDocument
                      ? "Unreadable Document"
                      : isMissingAttachment
                      ? "Missing Attachment"
                      : (selected.canonical_reason || selected.presentation_title || reasonLabels[selected.reason_code] || selected.reason_text || displayLabel(selected.reason_code))}
                  </strong>
                  <p className="callout-desc">
                    {isMissingRequiredValue
                      ? "The SI and BL evidence was not sufficient to determine one or more required field values confidently."
                      : isWrongDocumentType
                      ? "The attached file does not appear to be the required shipping document."
                      : isUnreadableDocument
                      ? "The attached document could not be read reliably."
                      : isMissingAttachment
                      ? (cleanExplanation || "A required shipping document is not available for comparison.")
                      : cleanExplanation}
                  </p>

                  <div className="action-guidance-wrapper">
                    <button
                      type="button"
                      className={cx("action-guidance-toggle-btn", showActionGuidance && "is-open")}
                      onClick={() => setShowActionGuidance((prev) => !prev)}
                      aria-expanded={showActionGuidance}
                      title={showActionGuidance ? "Click vibrating icon to close action instructions" : "Click vibrating icon to view action instructions"}
                    >
                      <span className="vibrating-alert-icon" aria-hidden="true">
                        <AlertTriangle size={16} />
                      </span>
                      <span className="action-guidance-badge">ACTION REQUIRED</span>
                      <span className="action-guidance-chevron">{showActionGuidance ? "▲" : "▼"}</span>
                    </button>

                    {showActionGuidance && (
                      <div className="action-guidance-expanded">
                        <p className="action-guidance-text">
                          <strong>{guidance.actionTitle}:</strong> {guidance.instruction}
                        </p>
                      </div>
                    )}
                  </div>

                  {isFieldLevel && actuallyAffectedFields.length ? (
                    <div className="callout-chips-row">
                      <span className="chips-title">Affected fields (click to edit):</span>
                      <div className="chips-container">
                        {actuallyAffectedFields.map((f) => (
                          <button
                            key={f}
                            type="button"
                            className="affected-field-chip"
                            onClick={() => {
                              setField(f);
                              setDetailTab("fields");
                              const el = document.getElementById("review-editor-box");
                              if (el) {
                                el.scrollIntoView({ behavior: "smooth" });
                                const valInput = el.querySelector("input[aria-label='Corrected value']") as HTMLInputElement | null;
                                if (valInput) valInput.focus();
                              }
                            }}
                            title={`Click to edit ${labelForField(f)}`}
                          >
                            {labelForField(f)}
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <p className="affected-fields-summary">
                      Affected area: {isMissingAttachment || isWrongDocumentType || isUnreadableDocument ? "Documents" : (selected.affected_area || (isFieldLevel ? "Document fields" : "Documents"))}
                    </p>
                  )}

                  <details className="callout-pipeline-details">
                    <summary>System diagnostics (Trigger · Stage · Code)</summary>
                    <div className="callout-pipeline-meta">
                      <span className="pipeline-pill"><strong>Trigger:</strong> {selected.trigger || "Uncertainty"}</span>
                      <span className="pipeline-pill"><strong>Stage:</strong> {selected.stage || "Comparison"}</span>
                      {selected.reason_code ? (
                        <span className="pipeline-pill"><strong>Internal code:</strong> <small className="technical-code">{selected.reason_code}</small></span>
                      ) : null}
                    </div>
                  </details>
                </div>
              </div>

              {selected.case_origin === "ACTIVE" ? (
                <AIReviewPanel
                  review={selected}
                  reviewerName={selected.reviewer_name || reviewer}
                  onCaseUpdated={(updated) => onCaseUpdated?.(updated)}
                />
              ) : null}

              {detailTab === "fields" && (
                <div className="tab-pane">
                  {!isFieldLevel ? (
                    <div className="detail-section document-exception-panel">
                      <div className="section-heading-row">
                        <div>
                          <h3>
                            {isMissingAttachment
                              ? "Missing required document exception"
                              : isWrongDocumentType
                              ? "Document role & validation exception"
                              : isUnreadableDocument
                              ? "Document readability & parsing exception"
                              : "Document role & validation exception"}
                          </h3>
                          <p>
                            {isMissingAttachment
                              ? "Automated comparison was halted because a required shipping document (Shipping Instruction or Draft Bill of Lading) is missing."
                              : isWrongDocumentType
                              ? "Automated comparison was halted before field extraction because valid Shipping Instruction (SI) and Draft Bill of Lading (BL) documents could not be established."
                              : isUnreadableDocument
                              ? "Automated comparison was halted because the attached document could not be reliably parsed or read."
                              : "Automated comparison was halted before field extraction because valid Shipping Instruction (SI) and Draft Bill of Lading (BL) documents could not be established."}
                          </p>
                        </div>
                        <span className="badge badge-bad">
                          {isMissingAttachment
                            ? "Missing Attachment"
                            : isWrongDocumentType
                            ? "Wrong Document Type"
                            : isUnreadableDocument
                            ? "Unreadable Document"
                            : displayLabel(selected.reason_code)}
                        </span>
                      </div>

                      <div className="document-exception-alert-box">
                        <div className="exception-alert-header">
                          <AlertCircle size={20} className="exception-alert-icon" />
                          <div>
                            <strong>
                              {isMissingAttachment
                                ? "Document Status: Missing Attachment"
                                : isWrongDocumentType
                                ? "Document Status: Wrong Document Type"
                                : isUnreadableDocument
                                ? "Document Status: Unreadable Document"
                                : `Validation Outcome: ${selected.canonical_reason || displayLabel(selected.reason_code)}`}
                            </strong>
                            <p>
                              {isMissingAttachment
                                ? "A required shipping document is not available for comparison."
                                : isWrongDocumentType
                                ? "The attached file does not appear to be the required shipping document."
                                : isUnreadableDocument
                                ? "The attached document could not be read reliably."
                                : cleanExplanation}
                            </p>
                          </div>
                        </div>

                        <div className="exception-sop-guide">
                          <span className="sop-guide-title">Standard Operational Procedure (SOP):</span>
                          {isMissingAttachment ? (
                            <ol className="sop-steps-list">
                              <li>
                                <strong>Verify attached files:</strong> Confirm that the required SI or Draft BL is genuinely missing and was not misclassified.
                              </li>
                              <li>
                                <strong>Inspect email context:</strong> Review the email body and received attachments under &quot;Email &amp; Documents&quot;.
                              </li>
                              <li>
                                <strong>Determine next action:</strong> Obtain the missing shipping document before comparison can continue. Dismiss the review only if the case is not actionable, incorrectly routed, duplicated, or otherwise does not require further verification.
                              </li>
                            </ol>
                          ) : isWrongDocumentType ? (
                            <ol className="sop-steps-list">
                              <li>
                                <strong>Confirm the invalid attachment:</strong> Verify that the file identified by HolyShip is not a valid Shipping Instruction or Draft Bill of Lading. Review the detected document role and supporting evidence.
                              </li>
                              <li>
                                <strong>Inspect email context:</strong> Review the email body and attachments under &quot;Email &amp; Documents&quot; to determine whether the sender intended to provide the required SI or Draft BL.
                              </li>
                              <li>
                                <strong>Determine the operational next step:</strong> The correct shipping document is required before automated comparison can proceed. Keep the review open while follow-up is required. Dismiss the review only when the case itself should no longer be actionable, such as incorrect routing or duplication.
                              </li>
                            </ol>
                          ) : isUnreadableDocument ? (
                            <ol className="sop-steps-list">
                              <li>
                                <strong>Inspect the affected document:</strong> Open the attachment under &quot;Email &amp; Documents&quot; and determine whether the content is visually readable.
                              </li>
                              <li>
                                <strong>Review processing evidence:</strong> Check the available OCR / parsing diagnostic information to understand why automated extraction could not proceed.
                              </li>
                              <li>
                                <strong>Determine the next step:</strong> If the document itself is unclear, damaged, or unreadable, obtain a clearer source document before comparison continues. If the diagnostic evidence indicates a system-side processing issue, follow the application&apos;s existing retry/reprocess workflow if one is already available.
                              </li>
                            </ol>
                          ) : (
                            <ol className="sop-steps-list">
                              <li>
                                <strong>Verify attached files:</strong> Check whether the sender mistakenly attached an unrelated document (e.g. Commercial Invoice, Packing List) instead of a draft B/L or SI.
                              </li>
                              <li>
                                <strong>Inspect email body:</strong> Review the message context in the <em>Email &amp; Documents</em> tab to check for customer notes, instructions, or booking numbers.
                              </li>
                              <li>
                                <strong>Record auditable decision:</strong> Dismiss this review case with the appropriate reason code below, or request the customer to supply the correct document.
                              </li>
                            </ol>
                          )}
                        </div>
                      </div>

                      <div className="detail-section-nested">
                        <div className="nested-section-header">
                          <h4>Received Attachments ({selected.documents?.length || 0})</h4>
                          <button
                            type="button"
                            className="button-secondary btn-compact view-in-email-btn"
                            onClick={() => setDetailTab("context")}
                          >
                            <Mail size={13} />
                            <span>Open Email &amp; Documents Tab</span>
                          </button>
                        </div>

                        {selected.documents?.length ? (
                          <div className="documents-card-list">
                            {selected.documents.map((doc) => {
                              const evidenceSummary =
                                doc.role_evidence && typeof doc.role_evidence === "object" && "summary" in doc.role_evidence
                                  ? String((doc.role_evidence as { summary?: string }).summary || "")
                                  : null;
                              const technicalDetail =
                                doc.failure_reason ||
                                (doc.role_evidence && typeof doc.role_evidence === "object" && "summary" in doc.role_evidence
                                  ? String((doc.role_evidence as { summary?: string }).summary || "")
                                  : null);

                              return (
                                <div className="attachment-row document-card" key={doc.id}>
                                  <FileText size={20} className="doc-icon" />
                                  <div className="doc-info">
                                    <strong className="doc-name">{doc.filename}</strong>
                                    <div className="doc-badges">
                                      <span className="badge badge-info">Role: {doc.role === "SI" || doc.role === "BL" ? doc.role : displayLabel(doc.role)}</span>
                                      <span
                                        className={cx(
                                          "badge",
                                          doc.validation_outcome === "VALID"
                                            ? "badge-good"
                                            : doc.validation_outcome === "INVALID" ||
                                              doc.validation_outcome === "WRONG_DOCUMENT_TYPE" ||
                                              doc.validation_outcome === "CONFLICTING_MARKER"
                                            ? "badge-bad"
                                            : "badge-warn"
                                        )}
                                      >
                                        Validation: {doc.validation_outcome === "VALID" || doc.validation_outcome === "INVALID" ? doc.validation_outcome : displayLabel(doc.validation_outcome)}
                                      </span>
                                      {doc.routing_outcome ? (
                                        <span className="badge badge-muted">Router: {doc.routing_outcome === "SI_FOUND" ? "SI FOUND" : doc.routing_outcome === "BL_FOUND" ? "BL FOUND" : displayLabel(doc.routing_outcome)}</span>
                                      ) : null}
                                    </div>
                                    {isUnreadableDocument ? (
                                      <div className="doc-evidence-block">
                                        <div className="doc-evidence-summary">Document content could not be extracted reliably.</div>
                                        {technicalDetail ? (
                                          <div className="doc-evidence-technical">
                                            <strong>Technical details:</strong> <code>{technicalDetail}</code>
                                          </div>
                                        ) : null}
                                      </div>
                                    ) : evidenceSummary ? (
                                      <small className="doc-evidence-hint">{evidenceSummary}</small>
                                    ) : null}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        ) : (
                          <EmptyState title="No attachments found" body="The email contained no attached documents to extract or compare." />
                        )}

                        {isMissingAttachment && (
                          <div className="unresolved-requirement-box">
                            <AlertCircle size={18} className="unresolved-req-icon" />
                            <div>
                              <div className="unresolved-req-title-row">
                                <strong>Unresolved Requirement: {missingDocName}</strong>
                                <span className="badge badge-bad">MISSING</span>
                              </div>
                              <p>
                                {missingDocName} is required for comparison but was not provided in this email or its attachments.
                              </p>
                            </div>
                          </div>
                        )}
                      </div>

                      {selected.case_origin === "ACTIVE" ? (
                        isMissingAttachment ? (
                          <div className="detail-section missing-resolution-section" style={{ marginTop: "24px" }}>
                            <div className="missing-resolution-box">
                              <div className="missing-resolution-header">
                                <div className="dismiss-zone-title-row">
                                  <span className="dismiss-tag" style={{ background: "#e0f2fe", color: "#0369a1" }}>Operational Resolution</span>
                                  <strong className="missing-resolution-title">Missing Document Resolution</strong>
                                </div>
                                <p className="missing-resolution-desc">
                                  The required Shipping Instruction or Draft Bill of Lading is missing. Review the available evidence and determine the appropriate operational next step.
                                </p>
                              </div>

                              <div className="missing-next-step-card">
                                <AlertCircle size={18} className="next-step-icon" />
                                <div>
                                  <div style={{ marginBottom: "2px" }}>
                                    <strong>Recommended Action:</strong> Request or provide the missing document
                                  </div>
                                  <p className="next-step-instruction">
                                    <strong>Required next step:</strong> Obtain the missing {missingDocName} from the sender.
                                  </p>
                                  <p className="next-step-hint">
                                    This review case remains open while awaiting the required document. Dismiss only if verification is no longer needed.
                                  </p>
                                </div>
                              </div>

                              <div className="dismiss-zone secondary-dismiss-zone" id="dismiss-zone-box">
                                <div className="dismiss-zone-header">
                                  <div className="dismiss-zone-title-row">
                                    <span className="dismiss-tag secondary-tag">Secondary Action</span>
                                    <strong className="dismiss-title">Dismiss Review</strong>
                                  </div>
                                  <p className="dismiss-subtitle">
                                    Dismiss the review only if the case is not actionable, incorrectly routed, duplicated, or otherwise does not require further verification. Dismissing records an audited resolution in the review history.
                                  </p>
                                </div>
                                <div className="dismiss-form-grid">
                                  <label>
                                    Dismiss reason
                                    <input
                                      aria-label="Dismiss reason"
                                      value={dismissReason}
                                      onChange={(event) => setDismissReason(event.target.value)}
                                      placeholder="e.g. NOT_ACTIONABLE"
                                    />
                                  </label>
                                  <button
                                    className="button-secondary btn-dismiss-secondary"
                                    type="button"
                                    disabled={actionState === "loading" || !dismissReason.trim()}
                                    onClick={() => void onDismiss(reviewer, dismissReason, note)}
                                  >
                                    {actionState === "loading" ? "Dismissing…" : "Dismiss Review"}
                                  </button>
                                </div>
                                <label style={{ marginTop: "6px" }}>
                                  Resolution Note (Optional)
                                  <input
                                    aria-label="Dismiss note"
                                    value={note}
                                    onChange={(event) => setNote(event.target.value)}
                                    placeholder="e.g. Booking cancelled or not actionable"
                                  />
                                </label>
                                <div className="dismiss-presets">
                                  <span className="dismiss-presets-label">Quick presets:</span>
                                  {[
                                    "NOT_ACTIONABLE",
                                    "INCORRECT_ROUTING",
                                    "DUPLICATE_CASE",
                                    "COMMERCIAL_SETTLEMENT",
                                  ].map((preset) => (
                                    <button
                                      key={preset}
                                      type="button"
                                      className={cx("dismiss-preset-chip", dismissReason === preset && "active")}
                                      onClick={() => setDismissReason(preset)}
                                    >
                                      {preset}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            </div>
                          </div>
                        ) : isWrongDocumentType ? (
                          <div className="detail-section document-resolution-section" style={{ marginTop: "24px" }}>
                            <div className="document-resolution-box">
                              <div className="document-resolution-header">
                                <div className="dismiss-zone-title-row">
                                  <span className="dismiss-tag" style={{ background: "#e0f2fe", color: "#0369a1" }}>Operational Resolution</span>
                                  <strong className="document-resolution-title">Document Resolution</strong>
                                </div>
                                <p className="document-resolution-desc">
                                  Automated comparison was halted because the attached file does not appear to be the required shipping document.
                                </p>
                              </div>

                              <div className="document-next-step-card">
                                <AlertCircle size={18} className="next-step-icon" />
                                <div>
                                  <div style={{ marginBottom: "2px" }}>
                                    <strong>Recommended Action:</strong> Obtain valid shipping documents
                                  </div>
                                  <p className="next-step-instruction">
                                    <strong>Required next step:</strong> Obtain the correct Shipping Instruction or Draft Bill of Lading before comparison can continue.
                                  </p>
                                  <p className="next-step-hint">
                                    This review case remains open while awaiting the required document. Dismiss only if verification is no longer needed.
                                  </p>
                                </div>
                              </div>

                              <div className="dismiss-zone secondary-dismiss-zone" id="dismiss-zone-box">
                                <div className="dismiss-zone-header">
                                  <div className="dismiss-zone-title-row">
                                    <span className="dismiss-tag secondary-tag">Secondary Action</span>
                                    <strong className="dismiss-title">Dismiss Review</strong>
                                  </div>
                                  <p className="dismiss-subtitle">
                                    Dismiss the review only if the case is not actionable, incorrectly routed, duplicated, or otherwise does not require further verification. Dismissing records an audited resolution in the review history.
                                  </p>
                                </div>
                                <div className="dismiss-form-grid">
                                  <label>
                                    Dismiss reason
                                    <input
                                      aria-label="Dismiss reason"
                                      value={dismissReason}
                                      onChange={(event) => setDismissReason(event.target.value)}
                                      placeholder="e.g. NOT_ACTIONABLE"
                                    />
                                  </label>
                                  <button
                                    className="button-secondary btn-dismiss-secondary"
                                    type="button"
                                    disabled={actionState === "loading" || !dismissReason.trim()}
                                    onClick={() => void onDismiss(reviewer, dismissReason, note)}
                                  >
                                    {actionState === "loading" ? "Dismissing…" : "Dismiss Review"}
                                  </button>
                                </div>
                                <label style={{ marginTop: "6px" }}>
                                  Resolution Note (Optional)
                                  <input
                                    aria-label="Dismiss note"
                                    value={note}
                                    onChange={(event) => setNote(event.target.value)}
                                    placeholder="e.g. Sender attached packing list instead of draft BL"
                                  />
                                </label>
                                <div className="dismiss-presets">
                                  <span className="dismiss-presets-label">Quick presets:</span>
                                  {[
                                    "NOT_ACTIONABLE",
                                    "INCORRECT_ROUTING",
                                    "DUPLICATE_CASE",
                                    "COMMERCIAL_SETTLEMENT",
                                  ].map((preset) => (
                                    <button
                                      key={preset}
                                      type="button"
                                      className={cx("dismiss-preset-chip", dismissReason === preset && "active")}
                                      onClick={() => setDismissReason(preset)}
                                    >
                                      {preset}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            </div>
                          </div>
                        ) : isUnreadableDocument ? (
                          <div className="detail-section readability-resolution-section" style={{ marginTop: "24px" }}>
                            <div className="readability-resolution-box">
                              <div className="readability-resolution-header">
                                <div className="dismiss-zone-title-row">
                                  <span className="dismiss-tag" style={{ background: "#fef3c7", color: "#92400e" }}>Readability Resolution</span>
                                  <strong className="readability-resolution-title">Document Readability Resolution</strong>
                                </div>
                                <p className="readability-resolution-desc">
                                  HolyShip could not reliably extract the document content. Inspect the source file and processing evidence before deciding how to proceed.
                                </p>
                              </div>

                              <div className="readability-next-step-card">
                                <AlertCircle size={18} className="next-step-icon" />
                                <div style={{ flex: 1 }}>
                                  <div style={{ marginBottom: "2px" }}>
                                    <strong>Recommended Action:</strong> Inspect document and retry processing
                                  </div>
                                  <p className="next-step-instruction">
                                    <strong>Required next step:</strong> Obtain a clearer, machine-readable digital document, or reprocess if diagnostic indicates a transient issue.
                                  </p>
                                  <p className="next-step-hint">
                                    This review case remains open while investigating document readability. Dismiss only if verification is no longer needed.
                                  </p>
                                  {onReprocess && (selected.email?.id || selected.email_id) ? (
                                    <div style={{ marginTop: "10px" }}>
                                      <button
                                        type="button"
                                        className="button-primary btn-compact"
                                        disabled={actionState === "loading"}
                                        onClick={() => void onReprocess((selected.email?.id || selected.email_id)!)}
                                      >
                                        Retry / Reprocess Email
                                      </button>
                                    </div>
                                  ) : null}
                                </div>
                              </div>

                              <div className="dismiss-zone secondary-dismiss-zone" id="dismiss-zone-box">
                                <div className="dismiss-zone-header">
                                  <div className="dismiss-zone-title-row">
                                    <span className="dismiss-tag secondary-tag">Secondary Action</span>
                                    <strong className="dismiss-title">Dismiss Review</strong>
                                  </div>
                                  <p className="dismiss-subtitle">
                                    Dismiss the review only if the case is not actionable, incorrectly routed, duplicated, or otherwise does not require further verification. Dismissing records an audited resolution in the review history.
                                  </p>
                                </div>
                                <div className="dismiss-form-grid">
                                  <label>
                                    Dismiss reason
                                    <input
                                      aria-label="Dismiss reason"
                                      value={dismissReason}
                                      onChange={(event) => setDismissReason(event.target.value)}
                                      placeholder="e.g. NOT_ACTIONABLE"
                                    />
                                  </label>
                                  <button
                                    className="button-secondary btn-dismiss-secondary"
                                    type="button"
                                    disabled={actionState === "loading" || !dismissReason.trim()}
                                    onClick={() => void onDismiss(reviewer, dismissReason, note)}
                                  >
                                    {actionState === "loading" ? "Dismissing…" : "Dismiss Review"}
                                  </button>
                                </div>
                                <label style={{ marginTop: "6px" }}>
                                  Resolution Note (Optional)
                                  <input
                                    aria-label="Dismiss note"
                                    value={note}
                                    onChange={(event) => setNote(event.target.value)}
                                    placeholder="e.g. Low resolution scan cannot be read"
                                  />
                                </label>
                                <div className="dismiss-presets">
                                  <span className="dismiss-presets-label">Quick presets:</span>
                                  {[
                                    "NOT_ACTIONABLE",
                                    "INCORRECT_ROUTING",
                                    "DUPLICATE_CASE",
                                    "COMMERCIAL_SETTLEMENT",
                                  ].map((preset) => (
                                    <button
                                      key={preset}
                                      type="button"
                                      className={cx("dismiss-preset-chip", dismissReason === preset && "active")}
                                      onClick={() => setDismissReason(preset)}
                                    >
                                      {preset}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            </div>
                          </div>
                        ) : (
                          <div className="detail-section dismiss-section" style={{ marginTop: "24px" }}>
                            <div id="dismiss-zone-box" className="dismiss-zone secondary-dismiss-zone">
                              <div className="dismiss-zone-header">
                                <div className="dismiss-zone-title-row">
                                  <span className="dismiss-tag secondary-tag">Secondary Action</span>
                                  <strong className="dismiss-title">Dismiss Review</strong>
                                </div>
                                <p className="dismiss-subtitle">
                                  Dismissing records an audited resolution in the review history. Closed cases remain available in History for compliance.
                                </p>
                              </div>
                              <div className="dismiss-form-grid">
                                <label>
                                  Dismiss reason
                                  <input
                                    aria-label="Dismiss reason"
                                    value={dismissReason}
                                    onChange={(event) => setDismissReason(event.target.value)}
                                    placeholder="e.g. NOT_ACTIONABLE"
                                  />
                                </label>
                                <button
                                  className="button-secondary btn-dismiss-secondary"
                                  type="button"
                                  disabled={actionState === "loading" || !dismissReason.trim()}
                                  onClick={() => void onDismiss(reviewer, dismissReason, note)}
                                >
                                  {actionState === "loading" ? "Dismissing…" : "Dismiss Review"}
                                </button>
                              </div>
                              <label style={{ marginTop: "6px" }}>
                                Resolution Note (Optional)
                                <input
                                  aria-label="Dismiss note"
                                  value={note}
                                  onChange={(event) => setNote(event.target.value)}
                                  placeholder="e.g. Booking cancelled or not actionable"
                                />
                              </label>
                              <div className="dismiss-presets">
                                <span className="dismiss-presets-label">Quick presets:</span>
                                {[
                                  "NOT_ACTIONABLE",
                                  "INCORRECT_ROUTING",
                                  "DUPLICATE_CASE",
                                  "COMMERCIAL_SETTLEMENT",
                                ].map((preset) => (
                                  <button
                                    key={preset}
                                    type="button"
                                    className={cx("dismiss-preset-chip", dismissReason === preset && "active")}
                                    onClick={() => setDismissReason(preset)}
                                  >
                                    {preset}
                                  </button>
                                ))}
                              </div>
                            </div>
                          </div>
                        )
                      ) : (
                        <div className="detail-section">
                          <div className="state-note">
                            <strong>Historical review record</strong>
                            <span>This record is retained for audit history and is read-only.</span>
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <>
                      <div className="detail-section">
                        <div className="section-heading-row">
                          <div>
                            <h3>Seven reviewed fields</h3>
                            <p>Original extraction remains immutable. Reviewed values are applied only during recomparison.</p>
                          </div>
                          <span className="total-pill pill-unresolved">{selectedUnresolved} unresolved</span>
                        </div>
                        <div className="comparison-table-wrap">
                          <table className="comparison-table review-comparison" aria-label="Human Review seven-field comparison">
                            <colgroup>
                              <col style={{ width: "18%", minWidth: "80px" }} />
                              <col style={{ width: "28%", minWidth: "110px" }} />
                              <col style={{ width: "26%", minWidth: "100px" }} />
                              <col style={{ width: "18%", minWidth: "105px" }} />
                              <col style={{ width: "10%", minWidth: "60px" }} />
                            </colgroup>
                            <thead>
                              <tr>
                                <th>Field</th>
                                <th>Shipping Instruction</th>
                                <th>Draft BL</th>
                                <th style={{ textAlign: "center", whiteSpace: "nowrap" }}>System result</th>
                                <th style={{ textAlign: "center", whiteSpace: "nowrap" }}>Action</th>
                              </tr>
                            </thead>
                            <tbody>
                              {canonicalFields.map((name) => {
                                const compared = selected.comparison?.fields.find((item) => item.field === name);
                                const siOverride = activeOverrides.find((item) => item.field === name && item.document_side === "SI");
                                const blOverride = activeOverrides.find((item) => item.field === name && item.document_side === "BL");
                                return (
                                  <tr
                                    key={name}
                                    className={cx(
                                      compared?.status === "MISMATCH" && "field-mismatch",
                                      compared?.status === "UNRESOLVED" && "field-unresolved"
                                    )}
                                  >
                                    <th>{labelForField(name)}</th>
                                    <td>
                                      <span className="value-label">Original SI</span>
                                      {displayValue(compared?.si.raw)}
                                      {siOverride ? (
                                        <span className="reviewed-value">
                                          <span>Reviewed SI</span>
                                          {displayValue(siOverride.corrected_value)}
                                        </span>
                                      ) : null}
                                      <span className="effective-value">
                                        Effective: {displayValue(siOverride?.corrected_value ?? compared?.si.canonical ?? compared?.si.raw)}
                                      </span>
                                    </td>
                                    <td>
                                      <span className="value-label">Original BL</span>
                                      {displayValue(compared?.bl.raw)}
                                      {blOverride ? (
                                        <span className="reviewed-value">
                                          <span>Reviewed BL</span>
                                          {displayValue(blOverride.corrected_value)}
                                        </span>
                                      ) : null}
                                      <span className="effective-value">
                                        Effective: {displayValue(blOverride?.corrected_value ?? compared?.bl.canonical ?? compared?.bl.raw)}
                                      </span>
                                    </td>
                                    <td style={{ textAlign: "center", whiteSpace: "nowrap" }}>
                                      <StatusBadge value={compared?.status ?? "UNRESOLVED"} />
                                    </td>
                                    <td style={{ textAlign: "center" }}>
                                      {selected.case_origin === "ACTIVE" ? (
                                        <button
                                          type="button"
                                          className={cx(
                                            "row-edit-action-btn",
                                            compared?.status === "MATCH" ? "is-matched" : "is-unresolved"
                                          )}
                                          title={`Quick edit ${labelForField(name)}`}
                                          onClick={() => {
                                            setField(name);
                                            if (compared?.bl.raw == null && compared?.si.raw != null) {
                                              setSide("BL");
                                            } else if (compared?.si.raw == null && compared?.bl.raw != null) {
                                              setSide("SI");
                                            } else {
                                              setSide("BL");
                                            }
                                            const el = document.getElementById("review-editor-box");
                                            if (el) el.scrollIntoView({ behavior: "smooth" });
                                          }}
                                        >
                                          Edit
                                        </button>
                                      ) : (
                                        <span className="subtle">—</span>
                                      )}
                                    </td>
                                  </tr>
                                );
                              })}
                            </tbody>
                          </table>
                        </div>
                      </div>

                      {activeOverrides.length > 0 && (
                        <div className="staged-overrides-card">
                          <div className="staged-overrides-header">
                            <strong>Staged Overrides ({activeOverrides.length})</strong>
                            <span>Applied on Recomparison</span>
                          </div>
                          <div className="staged-overrides-list">
                            {activeOverrides.map((ov) => (
                              <div key={ov.id || `${ov.document_side}-${ov.field}`} className="staged-override-chip">
                                <span className="override-side-tag">{ov.document_side}</span>
                                <span className="override-field-name">{labelForField(ov.field)}:</span>
                                <strong className="override-val">{displayValue(ov.corrected_value)}</strong>
                                {ov.reviewer_name && <small className="override-by">({ov.reviewer_name})</small>}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {selected.case_origin === "ACTIVE" ? (
                        <div id="review-editor-box" className="detail-section review-editor">
                          <h3>Save a correction</h3>
                          <p>Corrections are stored separately from original extraction evidence.</p>
                          <div className="form-grid">
                            <label>
                              Document side
                              <select
                                aria-label="Override side"
                                value={side}
                                onChange={(event) => setSide(event.target.value as "SI" | "BL")}
                              >
                                <option>SI</option>
                                <option>BL</option>
                              </select>
                            </label>
                            <label>
                              Field
                              <select
                                aria-label="Override field"
                                value={field}
                                onChange={(event) => setField(event.target.value)}
                              >
                                {canonicalFields.map((name) => (
                                  <option key={name} value={name}>{labelForField(name)}</option>
                                ))}
                              </select>
                            </label>
                            <label className="form-span">
                              Corrected value{field === "gross_weight_kg" ? " (kg)" : ""}
                              <input
                                type={inputType}
                                step={inputStep}
                                min={inputType === "number" ? "0" : undefined}
                                aria-label="Corrected value"
                                aria-describedby="correction-help"
                                value={correctedValue}
                                onChange={(event) => setCorrectedValue(event.target.value)}
                                placeholder={field === "gross_weight_kg" ? "e.g. 22000" : field === "container_count" ? "e.g. 6" : "Enter reviewed value"}
                              />
                            </label>
                            <label className="form-span">
                              Reviewer note
                              <textarea
                                aria-label="Reviewer note"
                                value={note}
                                onChange={(event) => setNote(event.target.value)}
                                placeholder="Explain the evidence for this correction"
                              />
                            </label>
                          </div>
                          <p id="correction-help" className="form-help">
                            The saved correction is stored as a review override and used as the effective value during Resolve & Recompare. The original extraction remains unchanged.
                          </p>
                          <div className="editor-button-row">
                            <button
                              className="button-primary"
                              type="button"
                              disabled={!correctedValue || actionState === "loading"}
                              onClick={() => void onOverride({ document_side: side, field, corrected_value: correctedValue, reviewer_name: reviewer, note })}
                            >
                              {actionState === "loading" ? "Saving…" : "Save Correction"}
                            </button>
                            {actionState === "ready" && activeOverrides.length ? (
                              <span className="inline-success" role="status"><CheckCircle2 size={14} /> Saved</span>
                            ) : null}
                          </div>
                        </div>
                      ) : (
                        <div className="detail-section">
                          <div className="state-note">
                            <strong>Historical review record</strong>
                            <span>This record is retained for audit history and is read-only.</span>
                            <small>No correction, claim, resolve, or dismiss action is available.</small>
                          </div>
                        </div>
                      )}

                      {selected.case_origin === "ACTIVE" ? (
                        <div className="detail-section dismiss-section">
                          <div id="dismiss-zone-box" className="dismiss-zone">
                            <div className="dismiss-zone-header">
                              <div className="dismiss-zone-title-row">
                                <span className="dismiss-tag">Danger Zone</span>
                                <strong className="dismiss-title">Dismiss without resolving</strong>
                              </div>
                              <p className="dismiss-subtitle">
                                Dismiss records an audited decision. It does not mark the comparison completed.
                              </p>
                            </div>
                            <div className="dismiss-form-grid">
                              <label>
                                Dismiss reason
                                <input
                                  aria-label="Dismiss reason"
                                  value={dismissReason}
                                  onChange={(event) => setDismissReason(event.target.value)}
                                  placeholder="e.g. NOT_ACTIONABLE"
                                />
                              </label>
                              <button
                                className="button-danger-secondary"
                                type="button"
                                disabled={actionState === "loading" || !dismissReason.trim()}
                                onClick={() => void onDismiss(reviewer, dismissReason, note)}
                              >
                                {actionState === "loading" ? "Dismissing…" : "Dismiss Review"}
                              </button>
                            </div>
                            <div className="dismiss-presets">
                              <span className="dismiss-presets-label">Quick presets:</span>
                              {["NOT_ACTIONABLE", "DUPLICATE_CASE", "INCORRECT_ROUTING", "COMMERCIAL_SETTLEMENT"].map((preset) => (
                                <button
                                  key={preset}
                                  type="button"
                                  className={cx("dismiss-preset-chip", dismissReason === preset && "active")}
                                  onClick={() => setDismissReason(preset)}
                                >
                                  {preset}
                                </button>
                              ))}
                            </div>
                          </div>
                        </div>
                      ) : null}
                    </>
                  )}
                </div>
              )}


              {detailTab === "context" && (
                <div className="tab-pane">
                  <div className="detail-section">
                    <h3>Source documents</h3>
                    {selected.documents?.length ? (
                      <div className="documents-card-list">
                        {selected.documents.map((doc) => (
                          <div className="attachment-row document-card" key={doc.id}>
                            <FileText size={18} className="doc-icon" />
                            <div className="doc-info">
                              <strong>{doc.filename}</strong>
                              <div className="doc-badges">
                                <span className="badge badge-info">{displayLabel(doc.role)}</span>
                                <span className="badge badge-neutral">{displayLabel(doc.validation_outcome)}</span>
                                <span className="badge badge-muted">{displayLabel(doc.routing_outcome)}</span>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <EmptyState title="No documents available" body="Document evidence was not materialized for this review." />
                    )}
                  </div>
                  <div className="detail-section">
                    <h3>Email context</h3>
                    <div className="email-card-container">
                      <div className="email-meta-header">
                        <div><strong>Subject:</strong> {selected.email?.subject || "No subject"}</div>
                        <div><strong>From:</strong> {selected.email?.sender || "Unknown sender"}</div>
                        <div><strong>Date:</strong> {formatDate(selected.created_at)}</div>
                      </div>
                      <p className="body-copy email-body-box">{selected.body || "No body text available."}</p>
                    </div>
                  </div>
                </div>
              )}

              {detailTab === "audit" && (
                <div className="tab-pane">
                  <div className="detail-section">
                    <h3>Review audit trail</h3>
                    {selected.actions?.length ? (
                      <div className="timeline">
                        {selected.actions.map((action) => (
                          <div className="timeline-row" key={action.id}>
                            <span />
                            <div>
                              <strong>{reviewActionLabels[action.action] || displayLabel(action.action)}</strong>
                              <p>{action.actor_name || "System"} · {formatDate(action.created_at)}</p>
                              <small className="technical-code">{action.action}</small>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <EmptyState title="No review events yet" body="Claims, corrections, recomparison, and decisions will appear here." />
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      </section>
    </section>
  );
}

export default function App() {
  const [page, setPage] = useState<Page>("overview");
  const [summary, setSummary] = useState<ProductSummary | null>(null);
  const [queue, setQueue] = useState<EmailQueuePage | null>(null);
  const [detail, setDetail] = useState<ProductEmailDetail | null>(null);
  const [reviews, setReviews] = useState<HumanReviewPage | null>(null);
  const [reviewAnalytics, setReviewAnalytics] = useState<HumanReviewAnalytics | null>(null);
  const [selectedReview, setSelectedReview] = useState<ProductReview | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [detailState, setDetailState] = useState<LoadState>("idle");
  const [reviewState, setReviewState] = useState<LoadState>("idle");
  const [reviewActionState, setReviewActionState] = useState<LoadState>("idle");
  const [syncState, setSyncState] = useState<LoadState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [pageIndex, setPageIndex] = useState(0);
  const [filters, setFilters] = useState<QueueFilters>({ limit: 20, skip: 0 });
  const [reviewViewMode, setReviewViewMode] = useState<ReviewViewMode>("ACTIVE");
  const [lastEventAt, setLastEventAt] = useState<string | undefined>(undefined);
  const [lastSyncedAt, setLastSyncedAt] = useState<Date | null>(null);
  const deepLinkHandled = useRef(false);

  const loadDashboard = useCallback(async () => {
    setLoadState("loading");
    setError(null);
    try {
      const [sumRes, queueRes] = await Promise.all([
        getSummary(),
        getEmailQueue(filters),
      ]);
      setSummary(sumRes);
      setQueue(queueRes);
      setLastSyncedAt(new Date());
      setLoadState("ready");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to connect to backend");
      setLoadState("error");
    }
  }, [filters]);

  const loadReviews = useCallback(async () => {
    setReviewState("loading");
    try {
      const showAllReviews = reviewViewMode === "HISTORY";
      const reviewPage = await getAllHumanReviews({ active_only: !showAllReviews });
      setReviews(reviewPage);
      try {
        setReviewAnalytics(await getHumanReviewAnalytics());
      } catch {
        setReviewAnalytics(reviewAnalyticsFallback(reviewPage));
      }
      setReviewState("ready");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load review queue");
      setReviewState("error");
    }
  }, [reviewViewMode]);

  const selectEmailById = useCallback(async (emailId: string, updateUrl = true) => {
    setPage("queue");
    setDetailState("loading");
    try {
      setDetail(await getEmailDetail(emailId));
      setDetailState("ready");
      if (updateUrl) window.history.replaceState({}, "", `?email=${encodeURIComponent(emailId)}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load email detail");
      setDetailState("error");
    }
  }, []);

  const selectReviewById = useCallback(async (reviewId: string, updateUrl = true) => {
    setPage("review");
    setReviewActionState("loading");
    try {
      const reviewDetail = await getHumanReviewDetail(reviewId);
      setSelectedReview(reviewDetail);
      if (reviewDetail.case_origin === "LEGACY" || reviewDetail.status === "RESOLVED" || reviewDetail.status === "DISMISSED") {
        setReviewViewMode("HISTORY");
      } else {
        setReviewViewMode("ACTIVE");
      }
      setReviewActionState("ready");
      if (updateUrl) window.history.replaceState({}, "", `?review=${encodeURIComponent(reviewId)}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load review detail");
      setReviewActionState("error");
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    if (deepLinkHandled.current) return;
    deepLinkHandled.current = true;
    const params = new URLSearchParams(window.location.search);
    const reviewId = params.get("review");
    const emailId = params.get("email");
    if (reviewId) void selectReviewById(reviewId, false);
    else if (emailId) void selectEmailById(emailId, false);
  }, [selectEmailById, selectReviewById]);

  useEffect(() => {
    if (page === "review") {
      void loadReviews();
    }
  }, [loadReviews, page]);

  useEffect(() => {
    const timer = window.setInterval(async () => {
      try {
        const events = await getEvents(lastEventAt);
        if (events.length > 0) {
          setLastEventAt(events[events.length - 1]?.updated_at);
          void loadDashboard();
        }
      } catch {
        // The header connection state already reflects the latest manual load.
      }
    }, 15000);
    return () => window.clearInterval(timer);
  }, [lastEventAt, loadDashboard]);

  const selectEmail = async (email: ProductEmailSummary) => {
    await selectEmailById(email.id);
  };

  const refreshAfterReview = async (updated: ProductReview) => {
    setSelectedReview(updated);
    await Promise.all([loadReviews(), loadDashboard()]);
    if (detail?.email.id === updated.email_id) setDetail(await getEmailDetail(updated.email_id));
  };

  const reviewMutation = async (operation: () => Promise<ProductReview>) => {
    setReviewActionState("loading");
    setError(null);
    try {
      await refreshAfterReview(await operation());
      setReviewActionState("ready");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Human Review action failed");
      setReviewActionState("error");
    }
  };

  const reprocess = async (emailId: string) => {
    setError(null);
    try {
      await reprocessEmail(emailId);
      await loadDashboard();
      setDetail(await getEmailDetail(emailId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Reprocess failed");
    }
  };

  const initialSync = async () => {
    setSyncState("loading");
    setError(null);
    try {
      await runInitialSync();
      await loadDashboard();
      setSyncState("ready");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Initial sync failed");
      setSyncState("error");
    }
  };

  const updateFilters = (nextFilters: QueueFilters) => {
    setPageIndex(0);
    setFilters({ ...nextFilters, skip: 0, limit: nextFilters.limit ?? 20 });
  };

  const movePage = (direction: "next" | "previous") => {
    const nextIndex = direction === "next" ? pageIndex + 1 : Math.max(0, pageIndex - 1);
    const limit = filters.limit ?? 20;
    setPageIndex(nextIndex);
    setFilters({ ...filters, skip: nextIndex * limit, limit });
  };

  const goToPage = (targetPageIndex: number) => {
    const limit = filters.limit ?? 20;
    setPageIndex(targetPageIndex);
    setFilters({ ...filters, skip: targetPageIndex * limit, limit });
  };

  const navigate = (nextPage: Page) => {
    setPage(nextPage);
    window.history.replaceState({}, "", window.location.pathname);
  };

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="brand">
          <img src="/holyship-logo.png" alt="HolyShip" className="brand-logo" />
        </div>
        <nav>
          <button className={cx(page === "overview" && "active")} onClick={() => navigate("overview")} type="button">
            <ShipWheel size={18} />
            Overview
          </button>
          <button className={cx(page === "queue" && "active")} onClick={() => navigate("queue")} type="button">
            <Inbox size={18} />
            Email Queue
          </button>
          <button className={cx(page === "review" && "active")} onClick={() => navigate("review")} type="button">
            <ClipboardList size={18} />
            Human Review
          </button>
        </nav>
        <div className="sidebar-footer">
          <div className="sidebar-divider" />
          <p className="sidebar-motto">
            FASTER DOCUMENTS
            <br />
            SAFER SHIPPING
          </p>
          <div className="sidebar-orange-bar" />
          <strong className="sidebar-footer-brand">HolyShip</strong>
        </div>
      </aside>

      <main className="main-shell">
        <AppHeader
          page={page}
          state={loadState}
          lastSyncedAt={lastSyncedAt}
          onRefresh={() => void loadDashboard()}
          onInitialSync={() => void initialSync()}
          syncState={syncState}
        />

        {error ? <div className="error-banner" role="alert">{error}</div> : null}

        {page === "overview" ? (
          <OverviewPage
            summary={summary}
            queue={queue}
            state={loadState}
            onOpenQueue={() => navigate("queue")}
          />
        ) : null}

        {page === "queue" ? (
          <QueuePage
            page={pageIndex}
            queue={queue}
            detail={detail}
            detailState={detailState}
            queueState={loadState}
            filters={filters}
            onFilters={updateFilters}
            onSelect={(item) => void selectEmail(item)}
            onOpenReview={(reviewId) => void selectReviewById(reviewId)}
            onReprocess={(emailId) => void reprocess(emailId)}
            onCloseDetail={() => setDetail(null)}
            onPage={movePage}
            onGoToPage={goToPage}
          />
        ) : null}

        {page === "review" ? (
          <HumanReviewPageView
            reviews={reviews}
            analytics={reviewAnalytics}
            state={reviewState}
            selected={selectedReview}
            actionState={reviewActionState}
            reviewViewMode={reviewViewMode}
            onChangeReviewViewMode={(mode) => setReviewViewMode(mode)}
            onSelect={(reviewId) => void selectReviewById(reviewId)}
            onClaim={(reviewer) => reviewMutation(() => claimHumanReview(selectedReview!.id, reviewer))}
            onOverride={(payload) => reviewMutation(() => saveHumanReviewOverride(selectedReview!.id, payload))}
            onResolve={(reviewer, notes) => reviewMutation(() => resolveHumanReview(selectedReview!.id, reviewer, notes))}
            onDismiss={(reviewer, reason, notes) => reviewMutation(() => dismissHumanReview(selectedReview!.id, reason, reviewer, notes))}
            onReprocess={(emailId) => void reprocess(emailId)}
            onCaseUpdated={(updated) => void refreshAfterReview(updated)}
          />
        ) : null}
      </main>
    </div>
  );
}
