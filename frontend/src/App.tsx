import {
  AlertCircle,
  AlertTriangle,
  Archive,
  ArrowDownRight,
  ArrowUpRight,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  CircleCheck,
  ClipboardList,
  Clock,
  FileCheck2,
  FileSearch,
  FileText,
  Inbox,
  Mail,
  MailCheck,
  Maximize2,
  Menu,
  Minimize2,
  MoreHorizontal,
  LogOut,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldAlert,
  ShipWheel,
  Trash2,
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
  getDiscrepancies,
  getDiscrepancyDetail,
  acknowledgeDiscrepancy,
  resolveDiscrepancy,
  saveDiscrepancyOverride,
  recompareDiscrepancy,
  reconcileOutlookLifecycle,
} from "./api/client";
import { AIReviewPanel } from "./components/ai-review/AIReviewPanel";
import {
  askAIAssistant,
  listReviewPlans,
  confirmReviewPlan,
  addReviewPlanItem,
  createReviewPlanWithItem,
  updateReviewPlanItem,
  removeManualReviewPlanItem,
  cancelReviewPlan,
} from "./api/aiReview";
import type { ReviewPlanItemInput } from "./api/aiReview";
import type { ProductReviewPlan } from "./api/types";
import { ReplyEmailSection } from "./components/ReplyEmailSection";
import { MetricCard } from "./components/common/MetricCard";
import { ConfirmedDiscrepanciesPageView } from "./components/discrepancies/ConfirmedDiscrepanciesPageView";
import type {
  DiscrepancyPage,
  DiscrepancyQueueFilters,
  EmailLifecycleStatus,
  EmailQueuePage,
  HumanReviewAnalytics,
  HumanReviewPage,
  ProcessingStatus,
  ProductCategory,
  ProductDiscrepancyDetail,
  ProductDiscrepancySummary,
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

type Page = "overview" | "queue" | "review" | "discrepancies";
type LoadState = "idle" | "loading" | "ready" | "error";
export type ReviewViewMode = "ACTIVE" | "HISTORY";

const pageTitles: Record<Page, string> = {
  overview: "Overview",
  queue: "Email Queue",
  review: "Human Review",
  discrepancies: "Confirmed Discrepancies",
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

const defaultReviewerName = "Captain Jack";

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
  onToggleMobileMenu,
}: {
  page: Page;
  state: LoadState;
  lastSyncedAt: Date | null;
  onRefresh?: () => void;
  onInitialSync?: () => void;
  syncState?: LoadState;
  onToggleMobileMenu?: () => void;
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
        : page === "discrepancies"
          ? "DISCREPANCY RESOLUTION"
          : "EXCEPTION HANDLING";

  return (
    <div className="overview-header-bar">
      <div className="header-left-wrap">
        {onToggleMobileMenu && (
          <button
            type="button"
            className="mobile-menu-toggle-btn"
            onClick={onToggleMobileMenu}
            aria-label="Toggle navigation menu"
            title="Open navigation menu"
          >
            <Menu size={20} />
          </button>
        )}
        <div>
          <p className="eyebrow" style={{ margin: 0 }}>{eyebrowText}</p>
          <h1 className="sr-only">Shipping document operations, at a glance.</h1>
        </div>
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
              {isLoggedOut ? "?" : "CJ"}
            </button>
            {!userMenuOpen && (
              <div className="tooltip-bubble tooltip-right">
                <strong>{isLoggedOut ? "Signed Out" : "Captain Jack"}</strong>
                <span>{isLoggedOut ? "Click to sign in" : "captain.holyship@outlook.com · Manage account"}</span>
              </div>
            )}
          </div>

          {userMenuOpen && (
            <div className="user-dropdown-menu" role="menu">
              <div className="user-dropdown-header">
                <div className="dropdown-avatar">{isLoggedOut ? "?" : "CJ"}</div>
                <div className="dropdown-user-info">
                  <strong>{isLoggedOut ? "Signed Out" : "Captain Jack"}</strong>
                  <span className="dropdown-email">{isLoggedOut ? "No active account" : "captain.holyship@outlook.com"}</span>
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
                  <strong>captain.holyship@outlook.com</strong>
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
  onOpenQueueWithFilters,
  onSelectEmail,
}: {
  summary: ProductSummary | null;
  queue: EmailQueuePage | null;
  state: LoadState;
  onOpenQueue: () => void;
  onOpenQueueWithFilters: (filters: Partial<QueueFilters>) => void;
  onSelectEmail: (item: ProductEmailSummary) => void;
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
            onClick={() => onOpenQueueWithFilters({ limit: 20, skip: 0 })}
          />
          <MetricCard
            cardIndex={1}
            icon={<CircleCheck size={18} color="var(--color-success)" />}
            label="Completed"
            value={completed}
            trendText={`${completionRate}% of total`}
            trend="up"
            tone="good"
            onClick={() => onOpenQueueWithFilters({ status: "COMPLETED" })}
          />
          <MetricCard
            cardIndex={2}
            icon={<ShieldAlert size={18} color="var(--color-warn)" />}
            label="Human Review Open"
            value={summary?.human_review_open_count ?? summary?.needs_review_count ?? 0}
            trendText="Actionable business cases"
            trend="up"
            tone="warn"
            onClick={() => onOpenQueueWithFilters({ needs_review: "true" })}
          />
          <MetricCard
            cardIndex={3}
            icon={<AlertTriangle size={18} color="var(--color-danger)" />}
            label="Emails with Mismatch"
            value={summary?.mismatch_count ?? 0}
            trendText={`${summary && summary.total_emails > 0 ? Math.round(((summary.mismatch_count ?? 0) / summary.total_emails) * 100) : 0}% of total emails`}
            trend="down"
            tone="bad"
            onClick={() => onOpenQueueWithFilters({ has_mismatch: "true" })}
          />
          <MetricCard
            cardIndex={4}
            icon={<Clock size={18} color="var(--color-warn)" />}
            label="Awaiting Documents"
            value={summary?.awaiting_documents_count ?? metricFromStatus(summary, "AWAITING_DOCUMENTS")}
            trendText="Operational waiting state"
            tone="warn"
            onClick={() => onOpenQueueWithFilters({ status: "AWAITING_DOCUMENTS" })}
          />
          <MetricCard
            cardIndex={5}
            icon={<AlertCircle size={18} color="var(--color-danger)" />}
            label="Failed"
            value={summary?.failed_count ?? metricFromStatus(summary, "FAILED")}
            trendText="Retry / reprocess"
            tone="bad"
            onClick={() => onOpenQueueWithFilters({ status: "FAILED" })}
          />
          <MetricCard
            cardIndex={6}
            icon={<RefreshCw size={18} color="var(--color-info)" />}
            label="Currently Processing"
            value={summary?.processing_count ?? 0}
            trendText="Active pipeline work"
            tone="neutral"
            onClick={() => onOpenQueueWithFilters({ is_processing: "true" })}
          />
        </div>

        {summary && (summary.deleted_count ?? 0) > 0 && (
          <div
            className="deleted-lifecycle-banner"
            role="button"
            tabIndex={0}
            onClick={() => onOpenQueueWithFilters({ lifecycle_status: "DELETED" })}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                onOpenQueueWithFilters({ lifecycle_status: "DELETED" });
              }
            }}
          >
            <div className="deleted-lifecycle-banner-left">
              <Archive size={14} className="deleted-banner-icon" />
              <span>
                <strong>{summary.deleted_count ?? 0}</strong> email{(summary.deleted_count ?? 0) === 1 ? "" : "s"} deleted in Outlook — historical comparisons, overrides, and audit events preserved.
              </span>
            </div>
            <span className="deleted-banner-link">View deleted queue →</span>
          </div>
        )}
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
                  <div
                    className="status-row-compact"
                    key={status}
                    role="button"
                    tabIndex={0}
                    title={`Filter queue by ${statusLabels[status]} (${count})`}
                    onClick={() => onOpenQueueWithFilters({ status })}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        onOpenQueueWithFilters({ status });
                      }
                    }}
                  >
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
            <button className="section-link-btn" onClick={() => onOpenQueueWithFilters({ limit: 20, skip: 0 })} type="button">
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
                  <div
                    className="activity-row-compact"
                    key={item.id}
                    role="button"
                    tabIndex={0}
                    title={`Open email ${item.subject}`}
                    onClick={() => onSelectEmail(item)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        onSelectEmail(item);
                      }
                    }}
                  >
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
            <button className="section-link-btn" onClick={() => onOpenQueueWithFilters({ limit: 20, skip: 0 })} type="button">
              View all →
            </button>
          </div>
          <div className="alert-summary-list">
            <div
              className="alert-row-compact"
              role="button"
              tabIndex={0}
              title="Filter queue to emails with BL vs SI mismatch"
              onClick={() => onOpenQueueWithFilters({ has_mismatch: "true" })}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  onOpenQueueWithFilters({ has_mismatch: "true" });
                }
              }}
            >
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

            <div
              className="alert-row-compact"
              role="button"
              tabIndex={0}
              title="Filter queue to emails awaiting documents"
              onClick={() => onOpenQueueWithFilters({ status: "AWAITING_DOCUMENTS" })}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  onOpenQueueWithFilters({ status: "AWAITING_DOCUMENTS" });
                }
              }}
            >
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

            <div
              className="alert-row-compact"
              role="button"
              tabIndex={0}
              title="Filter queue to blocked or conflicted emails"
              onClick={() => onOpenQueueWithFilters({ status: "BLOCKED" })}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  onOpenQueueWithFilters({ status: "BLOCKED" });
                }
              }}
            >
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

            <div
              className="alert-row-compact"
              role="button"
              tabIndex={0}
              title="Filter queue to emails with unresolved fields"
              onClick={() => onOpenQueueWithFilters({ has_unresolved: "true" })}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  onOpenQueueWithFilters({ has_unresolved: "true" });
                }
              }}
            >
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

            <div
              className="alert-row-compact"
              role="button"
              tabIndex={0}
              title="Filter queue to processing exceptions and failures"
              onClick={() => onOpenQueueWithFilters({ status: "FAILED" })}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  onOpenQueueWithFilters({ status: "FAILED" });
                }
              }}
            >
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
          <button className="section-link-btn" onClick={() => onOpenQueueWithFilters({ limit: 20, skip: 0 })} type="button">
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
                    <tr key={item.id} onClick={() => onSelectEmail(item)} style={{ cursor: "pointer" }} title={`Open email ${item.subject}`}>
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
  onRestoreEmail,
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
  onRestoreEmail?: (emailId: string) => void;
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
      <div className={cx("surface-panel queue-panel", detail && "mobile-hide-when-detail-open")}>
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
            value={filters.is_processing === "true" ? "PROCESSING" : filters.status ?? ""}
            onChange={(event) => {
              const val = event.target.value;
              if (val === "PROCESSING") {
                onFilters({ ...filters, status: "", is_processing: "true", skip: 0 });
              } else {
                onFilters({ ...filters, status: val as ProcessingStatus | "", is_processing: "", skip: 0 });
              }
            }}
          >
            <option value="">All statuses</option>
            <option value="PROCESSING">Currently Processing (Active Pipeline)</option>
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
            aria-label="Filter by verification"
            value={
              filters.has_mismatch === "true"
                ? "mismatch"
                : filters.has_unresolved === "true"
                  ? "unresolved"
                  : filters.has_mismatch === "false"
                    ? "no_mismatch"
                    : ""
            }
            onChange={(event) => {
              const val = event.target.value;
              if (val === "mismatch") {
                onFilters({ ...filters, has_mismatch: "true", has_unresolved: "", skip: 0 });
              } else if (val === "unresolved") {
                onFilters({ ...filters, has_mismatch: "", has_unresolved: "true", skip: 0 });
              } else if (val === "no_mismatch") {
                onFilters({ ...filters, has_mismatch: "false", has_unresolved: "", skip: 0 });
              } else {
                onFilters({ ...filters, has_mismatch: "", has_unresolved: "", skip: 0 });
              }
            }}
          >
            <option value="">All verification states</option>
            <option value="mismatch">BL vs SI Mismatch</option>
            <option value="unresolved">Unresolved fields</option>
            <option value="no_mismatch">No mismatch detected</option>
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
          <select
            aria-label="Filter by lifecycle"
            value={filters.lifecycle_status ?? ""}
            onChange={(event) =>
              onFilters({ ...filters, lifecycle_status: event.target.value as EmailLifecycleStatus | "", skip: 0 })
            }
          >
            <option value="">Active mailbox</option>
            <option value="DELETED">Deleted in Outlook</option>
            <option value="ARCHIVED">Archived in Outlook</option>
          </select>
        </div>

        {Boolean(
          filters.search ||
          filters.status ||
          filters.category ||
          filters.needs_review ||
          filters.lifecycle_status ||
          filters.has_mismatch ||
          filters.has_unresolved ||
          filters.is_processing
        ) && (
          <div className="active-filter-chips" aria-label="Active filters">
            <span className="active-filters-label">Active filters:</span>
            {filters.status && (
              <button
                type="button"
                className="filter-chip"
                onClick={() => onFilters({ ...filters, status: "", skip: 0 })}
                title="Remove status filter"
              >
                Status: {statusLabels[filters.status]} ✕
              </button>
            )}
            {filters.is_processing === "true" && (
              <button
                type="button"
                className="filter-chip"
                onClick={() => onFilters({ ...filters, is_processing: "", skip: 0 })}
                title="Remove processing filter"
              >
                Active Processing Pipeline ✕
              </button>
            )}
            {filters.category && (
              <button
                type="button"
                className="filter-chip"
                onClick={() => onFilters({ ...filters, category: "", skip: 0 })}
                title="Remove category filter"
              >
                Category: {categoryLabels[filters.category]} ✕
              </button>
            )}
            {filters.has_mismatch === "true" && (
              <button
                type="button"
                className="filter-chip"
                onClick={() => onFilters({ ...filters, has_mismatch: "", skip: 0 })}
                title="Remove mismatch filter"
              >
                Verification: BL vs SI Mismatch ✕
              </button>
            )}
            {filters.has_unresolved === "true" && (
              <button
                type="button"
                className="filter-chip"
                onClick={() => onFilters({ ...filters, has_unresolved: "", skip: 0 })}
                title="Remove unresolved filter"
              >
                Verification: Unresolved fields ✕
              </button>
            )}
            {filters.has_mismatch === "false" && (
              <button
                type="button"
                className="filter-chip"
                onClick={() => onFilters({ ...filters, has_mismatch: "", skip: 0 })}
                title="Remove no mismatch filter"
              >
                Verification: No mismatch ✕
              </button>
            )}
            {filters.needs_review === "true" && (
              <button
                type="button"
                className="filter-chip"
                onClick={() => onFilters({ ...filters, needs_review: "", skip: 0 })}
                title="Remove review filter"
              >
                Review: Needs review ✕
              </button>
            )}
            {filters.needs_review === "false" && (
              <button
                type="button"
                className="filter-chip"
                onClick={() => onFilters({ ...filters, needs_review: "", skip: 0 })}
                title="Remove review filter"
              >
                Review: No review need ✕
              </button>
            )}
            {filters.lifecycle_status === "DELETED" && (
              <button
                type="button"
                className="filter-chip"
                onClick={() => onFilters({ ...filters, lifecycle_status: "", skip: 0 })}
                title="Remove deleted filter"
              >
                Lifecycle: Deleted in Outlook ✕
              </button>
            )}
            {filters.lifecycle_status === "ARCHIVED" && (
              <button
                type="button"
                className="filter-chip"
                onClick={() => onFilters({ ...filters, lifecycle_status: "", skip: 0 })}
                title="Remove archived filter"
              >
                Lifecycle: Archived in Outlook ✕
              </button>
            )}
            {filters.search && (
              <button
                type="button"
                className="filter-chip"
                onClick={() => onFilters({ ...filters, search: "", skip: 0 })}
                title="Remove search query"
              >
                Search: "{filters.search}" ✕
              </button>
            )}
            <button
              type="button"
              className="filter-chip-clear"
              onClick={() => onFilters({ limit: 20, skip: 0 })}
            >
              Reset all filters
            </button>
          </div>
        )}

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
                      className={cx(detail?.email.id === item.id && "selected-row", item.lifecycle?.lifecycle_status === "DELETED" && "deleted-row")}
                      onClick={() => onSelect(item)}
                      aria-selected={detail?.email.id === item.id}
                    >
                      <td>
                        <strong>{item.sender?.split("@")[0]?.replace(/[._]/g, " ") || item.sender}</strong>
                        <span className="subtle">
                          {item.lifecycle?.outlook_read_state === "UNREAD" && <span className="unread-dot" title="Unread in Outlook" aria-label="Unread in Outlook">● </span>}
                          {item.external_message_id}
                        </span>
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
                        <div style={{ display: "flex", gap: "4px", flexWrap: "wrap", alignItems: "center" }}>
                          <StatusBadge value={item.processing_status} />
                          {item.lifecycle?.lifecycle_status && item.lifecycle.lifecycle_status !== "ACTIVE" && (
                            <StatusBadge value={item.lifecycle.lifecycle_status} />
                          )}
                        </div>
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
              <EmailDetailContent detail={detail} onClose={onCloseDetail} onOpenReview={onOpenReview} onReprocess={onReprocess} onRestoreEmail={onRestoreEmail} />
            </div>
          </>
        ) : null
      ) : (
        <div className={cx("detail-panel-wrapper", !detail && "mobile-hide-when-no-detail")}>
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
              <EmailDetailContent detail={detail} onClose={onCloseDetail} onOpenReview={onOpenReview} onReprocess={onReprocess} onRestoreEmail={onRestoreEmail} />
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
  onRestoreEmail,
}: {
  detail: ProductEmailDetail;
  onClose?: () => void;
  onOpenReview: (reviewId: string) => void;
  onReprocess: (emailId: string) => void;
  onRestoreEmail?: (emailId: string) => void;
}) {
  const [isTimelineExpanded, setIsTimelineExpanded] = useState(false);

  useEffect(() => {
    setIsTimelineExpanded(false);
  }, [detail.email.id]);

  const latestFailure = [...detail.timeline].reverse().find((event) => event.new_status === "FAILED");
  return (
    <div>
      {/* Mobile Back to List Button */}
      {onClose && (
        <div className="mobile-detail-nav-row">
          <button
            type="button"
            className="mobile-back-to-list-btn"
            onClick={onClose}
          >
            <ChevronLeft size={16} />
            Back to Queue
          </button>
        </div>
      )}
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
          {detail.email.lifecycle?.lifecycle_status && detail.email.lifecycle.lifecycle_status !== "ACTIVE" ? (
            <StatusBadge value={detail.email.lifecycle.lifecycle_status} />
          ) : null}
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
          {detail.email.lifecycle?.lifecycle_status === "DELETED" ? (
            <button
              className="button-primary button-action-cta"
              type="button"
              onClick={() => onRestoreEmail?.(detail.email.id)}
              title="Restore this email to active mailbox queue"
            >
              <RotateCcw size={15} />
              <span>Restore Email</span>
            </button>
          ) : null}
        </div>
      </div>

      {detail.email.lifecycle?.lifecycle_status === "DELETED" ? (
        <div className="detail-section">
          <div className="state-note failed" role="status">
            <strong>Mailbox item deleted</strong>
            <span>This email was marked DELETED in Outlook. It is excluded from active queues, but verification evidence, audit trail, and Human Review records remain intact.</span>
          </div>
        </div>
      ) : null}

      {detail.email.lifecycle?.outlook_sync_error ? (
        <div className="detail-section">
          <div className="state-note failed" role="alert">
            <strong>Outlook Sync Warning</strong>
            <span>{detail.email.lifecycle.outlook_sync_error}</span>
          </div>
        </div>
      ) : null}

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
          <div className="info-item">
            <span>Mailbox state</span>
            <strong>{displayLabel(detail.email.lifecycle?.lifecycle_status || "ACTIVE")}</strong>
          </div>
          <div className="info-item">
            <span>Outlook read</span>
            <strong>{displayLabel(detail.email.lifecycle?.outlook_read_state || "UNKNOWN")}</strong>
          </div>
          {detail.email.lifecycle?.outlook_categories && detail.email.lifecycle.outlook_categories.length > 0 ? (
            <div className="info-item">
              <span>Outlook tags</span>
              <strong>{detail.email.lifecycle.outlook_categories.join(", ")}</strong>
            </div>
          ) : null}
          <div className="info-item">
            <span>Last Outlook sync</span>
            <strong>{formatDate(detail.email.lifecycle?.last_outlook_sync_at ?? null)}</strong>
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
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <h3 style={{ margin: 0 }}>
            Processing Timeline
            {detail.timeline.length > 5 && (
              <span style={{ fontSize: "11px", fontWeight: "normal", color: "var(--color-grey-500)", marginLeft: "8px" }}>
                ({isTimelineExpanded ? `all ${detail.timeline.length} events` : `latest 5 of ${detail.timeline.length}`})
              </span>
            )}
          </h3>
          {detail.timeline.length > 5 && (
            <button
              type="button"
              className="timeline-expand-btn"
              onClick={() => setIsTimelineExpanded(!isTimelineExpanded)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                fontSize: "12px",
                fontWeight: 600,
                color: "#e66800",
                background: "rgba(227, 148, 57, 0.08)",
                border: "1px solid rgba(227, 148, 57, 0.25)",
                borderRadius: "6px",
                padding: "3px 10px",
                cursor: "pointer",
                transition: "all 120ms ease",
              }}
            >
              {isTimelineExpanded ? (
                <>
                  <ChevronUp size={13} />
                  <span>Show latest 5</span>
                </>
              ) : (
                <>
                  <ChevronDown size={13} />
                  <span>Expand all ({detail.timeline.length})</span>
                </>
              )}
            </button>
          )}
        </div>
        {detail.timeline.length ? (
          <div className="timeline">
            {(isTimelineExpanded || detail.timeline.length <= 5
              ? detail.timeline
              : detail.timeline.slice(-5)
            ).map((event) => (
              <div className="timeline-row" key={event.id}>
                <span />
                <div>
                  <strong>{(statusLabels as Record<string, string>)[event.new_status] || event.new_status}</strong>
                  <p>{displayLabel(event.reason_code)} · {formatDate(event.created_at)}</p>
                  <small className="technical-code">{event.reason_code}</small>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="No events yet" body="Processing and review events will appear here as the case advances." />
        )}
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
  onDeselect,
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
  onDeselect?: () => void;
}) {
  const [activeStatusFilter, setActiveStatusFilter] = useState("ACTIVE");
  const [historyStatusFilter, setHistoryStatusFilter] = useState("ALL_HISTORY");
  const [reasonFilter, setReasonFilter] = useState("");
  const [reviewerFilter, setReviewerFilter] = useState("");
  const [searchFilter, setSearchFilter] = useState("");
  const [sortFilter, setSortFilter] = useState("newest");
  const problematicFields = useMemo(() => {
    if (!selected?.comparison?.fields) return [];
    return selected.comparison.fields.filter(
      (f) => f.status === "MISMATCH" || f.status === "UNRESOLVED"
    );
  }, [selected?.comparison?.fields]);

  const firstProblematicField = useMemo(() => {
    if (problematicFields.length > 0) {
      return problematicFields[0].field;
    }
    if (selected?.affected_fields && selected.affected_fields.length > 0) {
      const candidate = selected.affected_fields[0];
      const comp = selected?.comparison?.fields?.find((f) => f.field === candidate);
      if (!comp || comp.status !== "MATCH") {
        return candidate;
      }
    }
    return null;
  }, [problematicFields, selected]);

  const initialSide = useMemo<"SI" | "BL">(() => {
    if (!firstProblematicField) return "BL";
    const comp = selected?.comparison?.fields?.find((f) => f.field === firstProblematicField);
    return (comp?.si.raw == null && comp?.bl.raw != null) ? "SI" : "BL";
  }, [firstProblematicField, selected?.comparison?.fields]);

  const [reviewer, setReviewer] = useState(defaultReviewerName);
  const [side, setSide] = useState<"SI" | "BL">(() => initialSide);
  const [field, setField] = useState<string>(() => firstProblematicField || "gross_weight_kg");
  const [editingField, setEditingField] = useState<string | null>(() => firstProblematicField);
  const [prevReviewId, setPrevReviewId] = useState<string | undefined>(undefined);
  const [correctedValue, setCorrectedValue] = useState(() => {
    if (!firstProblematicField) return "";
    const initialSugg = (selected?.ai_suggestions ?? []).find(
      (s) => s.field === firstProblematicField && s.document_side === initialSide && (s.status === "PENDING" || !s.status)
    ) ?? (selected?.ai_suggestions ?? []).find(
      (s) => s.field === firstProblematicField && (s.status === "PENDING" || !s.status)
    );
    return initialSugg && initialSugg.suggested_value != null ? String(initialSugg.suggested_value) : "";
  });
  const [note, setNote] = useState("");
  const [dismissReason, setDismissReason] = useState("NOT_ACTIONABLE");
  const [detailTab, setDetailTab] = useState<"fields" | "context" | "audit">("fields");
  const [replyDetail, setReplyDetail] = useState<ProductEmailDetail | null>(null);
  const [reviewSubTab, setReviewSubTab] = useState<"issue" | "compare" | "assistant" | "actions" | "resolve">("issue");
  const [showAllFields, setShowAllFields] = useState(false);

  const [showActionGuidance, setShowActionGuidance] = useState(false);
  const [plan, setPlan] = useState<ProductReviewPlan | null>(null);
  const [rejectedFieldKeys, setRejectedFieldKeys] = useState<Set<string>>(new Set());
  const [isPlanActionLoading, setIsPlanActionLoading] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiUnavailable, setAiUnavailable] = useState(false);
  const [stagedSuccess, setStagedSuccess] = useState(false);
  const [planErrorMessage, setPlanErrorMessage] = useState<string | null>(null);
  const requestedAiRef = useRef<Set<string>>(new Set());

  // Load active review plan when selected review changes
  useEffect(() => {
    if (!selected?.id) {
      setPlan(null);
      return;
    }
    let active = true;
    void listReviewPlans(selected.id)
      .then((plans) => {
        if (active) {
          setPlan(plans.find((item) => item.status !== "CANCELLED") ?? null);
        }
      })
      .catch(() => {
        if (active) setPlan(null);
      });
    return () => {
      active = false;
    };
  }, [selected?.id]);

  // Request AI proposal on-demand if no proposal exists yet for active case
  useEffect(() => {
    if (!selected?.id || selected.case_origin !== "ACTIVE") return;
    if (selected.ai_suggestions && selected.ai_suggestions.length > 0) return;
    if (requestedAiRef.current.has(selected.id)) return;
    requestedAiRef.current.add(selected.id);
    setAiLoading(true);
    setAiUnavailable(false);
    void askAIAssistant(selected.id, "Why does this need Human Review?")
      .then(async (resp) => {
        if (resp.suggestion) {
          const fresh = await getHumanReviewDetail(selected.id);
          onCaseUpdated?.(fresh);
        } else {
          setAiUnavailable(true);
        }
      })
      .catch(() => {
        setAiUnavailable(true);
      })
      .finally(() => {
        setAiLoading(false);
      });
  }, [selected?.id, selected?.case_origin, selected?.ai_suggestions, onCaseUpdated]);

  const activeAiSuggestion = useMemo(() => {
    if (!selected?.ai_suggestions || rejectedFieldKeys.has(`${side}-${field}`)) return null;
    return (
      selected.ai_suggestions.find(
        (s) => s.field === field && s.document_side === side && (s.status === "PENDING" || !s.status)
      ) ??
      selected.ai_suggestions.find(
        (s) => s.field === field && s.document_side === side
      ) ??
      selected.ai_suggestions.find(
        (s) => s.field === field && (s.status === "PENDING" || !s.status)
      ) ??
      null
    );
  }, [selected?.ai_suggestions, field, side, rejectedFieldKeys]);

  const currentDiff = useMemo(() => {
    return selected?.comparison?.fields?.find((f) => f.field === field);
  }, [selected?.comparison?.fields, field]);

  const currentTargetValue = useMemo(() => {
    if (!currentDiff) return "";
    const sideObj = side === "SI" ? currentDiff.si : currentDiff.bl;
    return String(sideObj.canonical ?? sideObj.normalized ?? sideObj.raw ?? "");
  }, [currentDiff, side]);

  const isAiSuggested = Boolean(activeAiSuggestion && activeAiSuggestion.suggested_value != null);
  const isAiEdited = isAiSuggested && correctedValue !== String(activeAiSuggestion?.suggested_value ?? "");

  const handleApproveSuggestion = async () => {
    if (!selected || !correctedValue.trim()) return;
    setIsPlanActionLoading(true);
    setPlanErrorMessage(null);
    try {
      const item: ReviewPlanItemInput = {
        document_side: side,
        field: field,
        current_value: currentTargetValue,
        proposed_value: correctedValue,
        reason: note.trim() || activeAiSuggestion?.reason || "AI proposed correction",
        confidence: activeAiSuggestion?.confidence,
        ai_suggestion_id: isAiEdited ? null : (activeAiSuggestion?.id || null),
        status: "APPROVED",
      };
      const updatedPlan = plan
        ? await addReviewPlanItem(selected.id, plan.id, reviewer, item)
        : await createReviewPlanWithItem(selected.id, reviewer, item);
      setPlan(updatedPlan);
      setStagedSuccess(true);
      setTimeout(() => setStagedSuccess(false), 3000);
    } catch (caught) {
      setPlanErrorMessage(caught instanceof Error ? caught.message : "Failed to add suggestion to review plan");
    } finally {
      setIsPlanActionLoading(false);
    }
  };

  const handleRejectSuggestion = () => {
    setRejectedFieldKeys((prev) => new Set(prev).add(`${side}-${field}`));
    setCorrectedValue("");
  };

  const handleAddManualToPlan = async () => {
    if (!selected || !correctedValue.trim()) return;
    setIsPlanActionLoading(true);
    setPlanErrorMessage(null);
    try {
      const item: ReviewPlanItemInput = {
        document_side: side,
        field: field,
        current_value: currentTargetValue,
        proposed_value: correctedValue,
        reason: note.trim() || "Manual reviewer correction",
        status: "APPROVED",
      };
      const updatedPlan = plan
        ? await addReviewPlanItem(selected.id, plan.id, reviewer, item)
        : await createReviewPlanWithItem(selected.id, reviewer, item);
      setPlan(updatedPlan);
      setStagedSuccess(true);
      setTimeout(() => setStagedSuccess(false), 3000);
    } catch (caught) {
      setPlanErrorMessage(caught instanceof Error ? caught.message : "Failed to add manual correction to review plan");
    } finally {
      setIsPlanActionLoading(false);
    }
  };

  const handleConfirmImplementation = async () => {
    if (!plan || !selected) return;
    setIsPlanActionLoading(true);
    setPlanErrorMessage(null);
    try {
      const updatedPlan = await confirmReviewPlan(selected.id, plan.id, reviewer);
      setPlan(updatedPlan);
      const fresh = await getHumanReviewDetail(selected.id);
      onCaseUpdated?.(fresh);
    } catch (caught) {
      try {
        const plans = await listReviewPlans(selected.id);
        setPlan(plans.find((p) => p.id === plan.id) ?? null);
        const fresh = await getHumanReviewDetail(selected.id);
        onCaseUpdated?.(fresh);
      } catch {
        // ignore secondary lookup
      }
      setPlanErrorMessage(caught instanceof Error ? caught.message : "Plan confirmation failed");
    } finally {
      setIsPlanActionLoading(false);
    }
  };

  // Sync state cleanly when selected review changes
  if (selected?.id !== prevReviewId) {
    setPrevReviewId(selected?.id);
    setEditingField(firstProblematicField);
    setRejectedFieldKeys(new Set());
    if (firstProblematicField) {
      setField(firstProblematicField);
      const comp = selected?.comparison?.fields?.find((f) => f.field === firstProblematicField);
      const initialSide = (comp?.si.raw == null && comp?.bl.raw != null) ? "SI" : "BL";
      setSide(initialSide);
      const initialSugg = (selected?.ai_suggestions ?? []).find(
        (s) => s.field === firstProblematicField && s.document_side === initialSide && (s.status === "PENDING" || !s.status)
      ) ?? (selected?.ai_suggestions ?? []).find(
        (s) => s.field === firstProblematicField && (s.status === "PENDING" || !s.status)
      );
      if (initialSugg && initialSugg.suggested_value != null) {
        setCorrectedValue(String(initialSugg.suggested_value));
      } else {
        setCorrectedValue("");
      }
    }
  }

  const currentCaseIdRef = useRef(selected?.id);
  useEffect(() => {
    if (currentCaseIdRef.current && selected?.id && currentCaseIdRef.current !== selected.id) {
      setReviewSubTab("issue");
      setShowAllFields(false);
    }
    currentCaseIdRef.current = selected?.id;
  }, [selected?.id]);

  useEffect(() => {
    let active = true;
    setReplyDetail(null);
    if (!selected?.email_id) return () => { active = false; };
    void getEmailDetail(selected.email_id).then((detail) => {
      if (active) setReplyDetail(detail);
    }).catch(() => {
      if (active) setReplyDetail(null);
    });
    return () => { active = false; };
  }, [selected?.email_id, selected?.status, selected?.updated_at]);

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

  const sortedFields = useMemo(() => {
    if (!selected?.comparison?.fields) {
      return canonicalFields;
    }
    return [...canonicalFields].sort((a, b) => {
      const compA = selected.comparison?.fields.find((item) => item.field === a);
      const compB = selected.comparison?.fields.find((item) => item.field === b);
      const statusA = compA?.status ?? "UNRESOLVED";
      const statusB = compB?.status ?? "UNRESOLVED";

      const priority = (s: string) => {
        if (s === "MISMATCH") return 0;
        if (s === "UNRESOLVED") return 1;
        if (s === "MATCH") return 2;
        return 3;
      };

      const diff = priority(statusA) - priority(statusB);
      if (diff !== 0) return diff;
      return canonicalFields.indexOf(a) - canonicalFields.indexOf(b);
    });
  }, [selected?.comparison?.fields]);

  const activeOverrides = selected?.overrides?.filter((item) => item.active) ?? [];
  const selectedUnresolved = selected?.comparison?.unresolved_fields.length ?? 0;
  const inputType = "text";
  const inputStep = undefined;
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
      <section className={cx("overview-summary-panel", selected && "mobile-hide-when-detail-open")} aria-label="Human Review analytics">
        <div className="metric-grid human-review-metric-grid" aria-label="Human Review analytics">
          <MetricCard cardIndex={0} totalCards={5} icon={<ShieldAlert size={18} color="currentColor" />} label="Open" value={analytics?.open_count ?? 0} trendText="Active review cases" tone="attention" />
          <MetricCard cardIndex={1} totalCards={5} icon={<Clock size={18} color="var(--color-warn)" />} label="In Review" value={analytics?.in_review_count ?? 0} trendText="Currently claimed" tone="neutral" />
          <MetricCard cardIndex={2} totalCards={5} icon={<CircleCheck size={18} color="var(--color-success)" />} label="Resolved Today" value={analytics?.resolved_today_count ?? 0} trendText={analytics?.resolved_count ? String(analytics.resolved_count) + " resolved total" : "No resolved cases"} tone="good" />
          <MetricCard cardIndex={3} totalCards={5} icon={<Archive size={18} color="var(--color-grey-700)" />} label="Dismissed" value={analytics?.dismissed_count ?? 0} trendText="Review decisions" tone="neutral" />
          <MetricCard cardIndex={4} totalCards={5} icon={<Clock size={18} color="var(--color-warn)" />} label="Avg Open Age" value={analytics?.average_open_age_minutes == null ? "—" : String(Math.round(analytics.average_open_age_minutes)) + "m"} trendText="Current open cases" tone="neutral" />
        </div>
      </section>
      <section className={cx("queue-layout", isResizing && "is-resizing", !selected && "queue-layout-empty")} style={layoutStyle}>
      <div className={cx("surface-panel queue-panel", selected && "mobile-hide-when-detail-open")}>
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

      <div className={cx("detail-panel-wrapper", !selected && "mobile-hide-when-no-detail")}>
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
              {onDeselect && (
                <div className="mobile-detail-nav-row">
                  <button
                    type="button"
                    className="mobile-back-to-list-btn"
                    onClick={onDeselect}
                  >
                    <ChevronLeft size={16} />
                    Back to Reviews
                  </button>
                </div>
              )}
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
                      <span className="reviewer-avatar-badge" title="Active operator session">CJ</span>
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

              {detailTab === "fields" && (
                <div className="tab-pane">
                  {!isFieldLevel ? (
                    <>
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

                          <p className="affected-fields-summary">
                            Affected area: {isMissingAttachment || isWrongDocumentType || isUnreadableDocument ? "Documents" : (selected.affected_area || (isFieldLevel ? "Document fields" : "Documents"))}
                          </p>

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
                  </>
                ) : (
                    <>
                      <nav className="in-page-anchor-bar sub-tabs-bar" aria-label="Review case quick navigation">
                        <button
                          type="button"
                          className={cx("sub-tab-btn", reviewSubTab === "issue" && "active")}
                          onClick={() => setReviewSubTab("issue")}
                        >
                          Review Issue
                        </button>
                        <span className="anchor-sep">·</span>
                        <button
                          type="button"
                          className={cx("sub-tab-btn", reviewSubTab === "compare" && "active")}
                          onClick={() => setReviewSubTab("compare")}
                        >
                          Compare Fields
                          {selectedUnresolved > 0 ? (
                            <span className="sub-tab-pill-badge">{selectedUnresolved}</span>
                          ) : null}
                        </button>
                        <span className="anchor-sep">·</span>
                        <button
                          type="button"
                          className={cx("sub-tab-btn", reviewSubTab === "assistant" && "active")}
                          onClick={() => setReviewSubTab("assistant")}
                        >
                          AI Assistant
                        </button>
                        <span className="anchor-sep">·</span>
                        <button
                          type="button"
                          className={cx("sub-tab-btn", reviewSubTab === "actions" && "active")}
                          onClick={() => setReviewSubTab("actions")}
                        >
                          Review Actions
                        </button>
                        <span className="anchor-sep">·</span>
                        <button
                          type="button"
                          className={cx("sub-tab-btn", reviewSubTab === "resolve" && "active")}
                          onClick={() => setReviewSubTab("resolve")}
                        >
                          Resolve
                        </button>
                      </nav>

                      <div
                        className={cx("sub-tab-panel", reviewSubTab !== "issue" && "sub-tab-panel-hidden")}
                        id="issue-banner-section"
                      >
                        <div className="compact-issue-banner">
                          <div className="issue-banner-main">
                            <div className="issue-banner-lead">
                              <AlertTriangle size={16} className="text-orange" aria-hidden="true" />
                              <div>
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
                                <p className="callout-desc" style={{ margin: "2px 0 0 0", fontSize: "12.5px" }}>
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
                              </div>
                            </div>

                            {actuallyAffectedFields.length > 0 && (
                              <div className="issue-banner-actions">
                                <div className="chips-container">
                                  {actuallyAffectedFields.map((f) => (
                                    <button
                                      key={f}
                                      type="button"
                                      className="affected-field-chip"
                                      onClick={() => {
                                        setReviewSubTab("compare");
                                        setField(f);
                                        setEditingField(f);
                                        const el = document.getElementById(`row-${f}`);
                                        if (el) el.scrollIntoView({ behavior: "smooth" });
                                      }}
                                      title={`Click to edit ${labelForField(f)}`}
                                    >
                                      {labelForField(f)}
                                    </button>
                                  ))}
                                </div>
                                <button
                                  type="button"
                                  className="button-primary btn-sm btn-dark-charcoal review-jump-btn"
                                  onClick={() => {
                                    const firstUnresolved = actuallyAffectedFields[0] || canonicalFields[0];
                                    setReviewSubTab("compare");
                                    setField(firstUnresolved);
                                    setEditingField(firstUnresolved);
                                    const el = document.getElementById(`row-${firstUnresolved}`);
                                    if (el) el.scrollIntoView({ behavior: "smooth" });
                                  }}
                                >
                                  Review →
                                </button>
                              </div>
                            )}
                          </div>

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

                      <div
                        className={cx("sub-tab-panel", reviewSubTab !== "compare" && "sub-tab-panel-hidden")}
                        id="fields-table-section-panel"
                      >
                        {/* 1. TOP SECTION: CONFIRMED DIFFERENCES (Matching Figure 2) */}
                        <div className="detail-section" style={{ marginBottom: "14px" }}>
                          {problematicFields.length > 0 ? (
                            <>
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                                <div>
                                  <h3 style={{ fontSize: "14.5px", fontWeight: 700, margin: 0, display: "flex", alignItems: "center", gap: "6px" }}>
                                    <AlertTriangle size={16} color="var(--color-review)" />
                                    Confirmed Differences ({problematicFields.length})
                                  </h3>
                                  <p style={{ fontSize: "11.5px", color: "var(--color-grey-500)", margin: "2px 0 0" }}>
                                    SI is authoritative reference document; BL values differ.
                                  </p>
                                </div>
                              </div>

                              <div className="discrepancy-diff-grid">
                                {problematicFields.map((diff) => (
                                  <div
                                    key={diff.field}
                                    className="discrepancy-diff-card is-mismatch"
                                  >
                                    <div className="diff-card-header-row">
                                      <div className="diff-card-field-info">
                                        <strong className="diff-field-name">
                                          {labelForField(diff.field)}
                                        </strong>
                                        <span className="badge badge-attention diff-reason-badge">
                                          {reasonLabels[diff.reason_code] || displayLabel(diff.reason_code)}
                                        </span>
                                      </div>
                                      {selected.case_origin === "ACTIVE" && (
                                        <div className="diff-card-actions-row">
                                          <button
                                            type="button"
                                            className="button-secondary"
                                            onClick={() => {
                                              setSide("BL");
                                              setField(diff.field);
                                              setEditingField(diff.field);
                                              const blSugg = (selected.ai_suggestions ?? []).find(
                                                (s) => s.field === diff.field && s.document_side === "BL" && (s.status === "PENDING" || !s.status)
                                              );
                                              if (blSugg && blSugg.suggested_value != null && !rejectedFieldKeys.has(`BL-${diff.field}`)) {
                                                setCorrectedValue(String(blSugg.suggested_value));
                                              } else {
                                                setCorrectedValue(String(diff.bl.canonical ?? diff.bl.raw ?? ""));
                                              }
                                              const el = document.getElementById("review-editor-box");
                                              if (el) el.scrollIntoView({ behavior: "smooth" });
                                            }}
                                          >
                                            Correct BL
                                          </button>
                                          <button
                                            type="button"
                                            className="button-secondary"
                                            onClick={() => {
                                              setSide("SI");
                                              setField(diff.field);
                                              setEditingField(diff.field);
                                              const siSugg = (selected.ai_suggestions ?? []).find(
                                                (s) => s.field === diff.field && s.document_side === "SI" && (s.status === "PENDING" || !s.status)
                                              );
                                              if (siSugg && siSugg.suggested_value != null && !rejectedFieldKeys.has(`SI-${diff.field}`)) {
                                                setCorrectedValue(String(siSugg.suggested_value));
                                              } else {
                                                setCorrectedValue(String(diff.si.canonical ?? diff.si.raw ?? ""));
                                              }
                                              const el = document.getElementById("review-editor-box");
                                              if (el) el.scrollIntoView({ behavior: "smooth" });
                                            }}
                                          >
                                            Correct SI
                                          </button>
                                        </div>
                                      )}
                                    </div>

                                    {/* Side by side comparison cards */}
                                    <div className="diff-side-by-side">
                                      {/* SI Box */}
                                      <div className="diff-box si-side">
                                        <div className="diff-box-label">
                                          SI (Reference Document)
                                        </div>
                                        <div className="diff-box-value">
                                          {diff.field === "container_count" && typeof (diff.si.canonical ?? diff.si.normalized) === "number"
                                            ? `${diff.si.canonical ?? diff.si.normalized} containers`
                                            : displayValue(diff.si.canonical ?? diff.si.normalized ?? diff.si.raw)}
                                        </div>
                                        {diff.si.raw !== undefined && diff.si.raw !== diff.si.canonical && (
                                          <div className="diff-box-raw">
                                            Raw: <code>{displayValue(diff.si.raw)}</code>
                                          </div>
                                        )}
                                      </div>

                                      {/* BL Box */}
                                      <div className="diff-box bl-side">
                                        <div className="diff-box-label">
                                          Draft BL (Document Checked)
                                        </div>
                                        <div className="diff-box-value">
                                          {diff.field === "container_count" && typeof (diff.bl.canonical ?? diff.bl.normalized) === "number"
                                            ? `${diff.bl.canonical ?? diff.bl.normalized} containers`
                                            : displayValue(diff.bl.canonical ?? diff.bl.normalized ?? diff.bl.raw)}
                                        </div>
                                        {diff.bl.raw !== undefined && diff.bl.raw !== diff.bl.canonical && (
                                          <div className="diff-box-raw">
                                            Raw: <code>{displayValue(diff.bl.raw)}</code>
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </>
                          ) : (
                            <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "12px", background: "var(--color-success-bg)", border: "1px solid rgba(34, 197, 94, 0.2)", borderRadius: "var(--radius-md)" }}>
                              <CheckCircle2 size={16} color="var(--color-success)" />
                              <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--color-success)" }}>
                                No mismatch detected. All 7 canonical fields match.
                              </span>
                            </div>
                          )}
                        </div>

                        {/* 2. DEDICATED FIELD CORRECTION CARD */}
                        {editingField && selected.case_origin === "ACTIVE" && (
                          <div id="review-editor-box" className="detail-section review-editor" style={{ marginBottom: "16px", border: "1px solid var(--color-orange-300)", borderRadius: "var(--radius-md)", background: "var(--color-white)", padding: "14px 16px", boxShadow: "0 2px 8px rgba(0,0,0,0.06)" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                              <h3 style={{ margin: 0, fontSize: "14px", fontWeight: 700 }}>Save a correction</h3>
                              <button
                                type="button"
                                className="button-secondary btn-sm"
                                onClick={() => setEditingField(null)}
                              >
                                Cancel
                              </button>
                            </div>
                            <p style={{ margin: "0 0 12px", fontSize: "12px", color: "var(--color-grey-600)" }}>
                              Proposed corrections stage into the Review Plan and preserve original extraction evidence.
                            </p>
                            <div className="form-grid">
                              <label>
                                Target
                                <select
                                  aria-label="Override side"
                                  value={side}
                                  onChange={(event) => {
                                    const newSide = event.target.value as "SI" | "BL";
                                    setSide(newSide);
                                    const sugg = (selected.ai_suggestions ?? []).find(
                                      (s) => s.field === field && s.document_side === newSide && (s.status === "PENDING" || !s.status)
                                    );
                                    if (sugg && sugg.suggested_value != null && !rejectedFieldKeys.has(`${newSide}-${field}`)) {
                                      setCorrectedValue(String(sugg.suggested_value));
                                    }
                                  }}
                                >
                                  <option value="SI">SI</option>
                                  <option value="BL">Draft BL</option>
                                </select>
                              </label>
                              <label>
                                Field
                                <select
                                  aria-label="Override field"
                                  value={field}
                                  onChange={(event) => {
                                    const newField = event.target.value;
                                    setField(newField);
                                    setEditingField(newField);
                                    const sugg = (selected.ai_suggestions ?? []).find(
                                      (s) => s.field === newField && s.document_side === side && (s.status === "PENDING" || !s.status)
                                    );
                                    if (sugg && sugg.suggested_value != null && !rejectedFieldKeys.has(`${side}-${newField}`)) {
                                      setCorrectedValue(String(sugg.suggested_value));
                                    }
                                  }}
                                >
                                  {sortedFields.map((fName) => (
                                    <option key={fName} value={fName}>{labelForField(fName)}</option>
                                  ))}
                                </select>
                              </label>
                              <div className="form-span" style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                                <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--color-grey-700)" }}>Current Value</span>
                                <div style={{ padding: "8px 12px", background: "var(--color-grey-100)", border: "1px solid var(--color-grey-300)", borderRadius: "var(--radius-sm)", fontSize: "13px", color: "var(--color-grey-900)", fontFamily: "monospace" }}>
                                  {currentTargetValue || "—"}
                                </div>
                              </div>
                              <div className="form-span">
                                <label htmlFor="correction-input-val" style={{ display: "block", marginBottom: "4px" }}>
                                  Proposed Corrected Value{field === "gross_weight_kg" ? " (kg)" : ""}
                                </label>
                                <input
                                  id="correction-input-val"
                                  type={inputType}
                                  step={inputStep}
                                  aria-label="Corrected value"
                                  aria-describedby="correction-help"
                                  className={cx("manual-field-input", isAiSuggested && !isAiEdited && "input-ai-suggested")}
                                  value={correctedValue}
                                  onChange={(event) => setCorrectedValue(event.target.value)}
                                  placeholder={field === "gross_weight_kg" ? "e.g. 22000" : field === "container_count" ? "e.g. 6" : "Enter proposed corrected value"}
                                />
                                {isAiSuggested && activeAiSuggestion ? (
                                  <div className={cx("ai-suggestion-meta", isAiEdited && "is-edited")}>
                                    {isAiEdited ? (
                                      <span>✎ Edited by reviewer <small className="subtle">(Original AI suggestion: {displayValue(activeAiSuggestion.suggested_value)})</small></span>
                                    ) : (
                                      <span>✦ AI suggested · {Math.round((activeAiSuggestion.confidence ?? 0.9) * 100)}% confidence</span>
                                    )}
                                  </div>
                                ) : aiLoading ? (
                                  <div className="ai-suggestion-meta subtle">
                                    <RefreshCw size={12} className="spin-icon" />
                                    <span>✦ Analyzing evidence for AI suggestion…</span>
                                  </div>
                                ) : aiUnavailable ? (
                                  <div className="ai-suggestion-meta subtle" style={{ color: "var(--color-grey-600)" }}>
                                    <span>✦ AI suggestion unavailable · Manual correction</span>
                                  </div>
                                ) : null}
                              </div>

                              {(activeAiSuggestion?.reason || note) && (
                                <div className="form-span" style={{ fontSize: "12px", color: "var(--color-grey-700)" }}>
                                  <strong>Reason:</strong> {activeAiSuggestion?.reason || note}
                                </div>
                              )}

                              <label className="form-span">
                                Reviewer note
                                <textarea
                                  aria-label="Reviewer note"
                                  value={note}
                                  onChange={(event) => setNote(event.target.value)}
                                  placeholder="Explain the rationale for this correction..."
                                />
                              </label>
                            </div>
                            <p id="correction-help" className="form-help">
                              The saved correction is stored as a review override and used as the effective value during Resolve & Recompare. The original extraction remains unchanged.
                            </p>
                            <div className="editor-button-row" style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                              {isAiSuggested && !isAiEdited ? (
                                <>
                                  <button
                                    className="button-primary btn-dark-charcoal"
                                    type="button"
                                    disabled={!correctedValue || isPlanActionLoading}
                                    onClick={() => void handleApproveSuggestion()}
                                  >
                                    Approve Suggestion
                                  </button>
                                  <button
                                    className="button-danger-secondary"
                                    type="button"
                                    disabled={isPlanActionLoading}
                                    onClick={handleRejectSuggestion}
                                  >
                                    Reject
                                  </button>
                                </>
                              ) : isAiSuggested && isAiEdited ? (
                                <>
                                  <button
                                    className="button-primary btn-dark-charcoal"
                                    type="button"
                                    disabled={!correctedValue || isPlanActionLoading}
                                    onClick={() => void handleApproveSuggestion()}
                                  >
                                    Approve Edited Suggestion
                                  </button>
                                  <button
                                    className="button-danger-secondary"
                                    type="button"
                                    disabled={isPlanActionLoading}
                                    onClick={handleRejectSuggestion}
                                  >
                                    Reject
                                  </button>
                                </>
                              ) : (
                                <>
                                  <button
                                    className="button-primary btn-dark-charcoal"
                                    type="button"
                                    disabled={!correctedValue || isPlanActionLoading}
                                    onClick={() => void handleAddManualToPlan()}
                                  >
                                    Add to Plan
                                  </button>
                                  <button
                                    className="button-secondary"
                                    type="button"
                                    disabled={!correctedValue || actionState === "loading"}
                                    onClick={() => void onOverride({ document_side: side, field, corrected_value: correctedValue, reviewer_name: reviewer, note })}
                                  >
                                    Save Correction
                                  </button>
                                </>
                              )}
                              <button
                                type="button"
                                className="button-secondary"
                                onClick={() => setEditingField(null)}
                              >
                                Cancel
                              </button>
                              {stagedSuccess && (
                                <span className="inline-success" role="status"><CheckCircle2 size={14} /> Staged in Review Plan</span>
                              )}
                              {planErrorMessage && (
                                <span className="text-danger" role="alert" style={{ fontSize: "12px" }}>{planErrorMessage}</span>
                              )}
                            </div>
                          </div>
                        )}

                        {/* 2b. STRUCTURED REVIEW PLAN */}
                        {reviewSubTab === "compare" && plan && plan.items && plan.items.length > 0 && selected.case_origin === "ACTIVE" && (
                          <div className="review-plan-card" role="region" aria-label="Review Plan" style={{ marginBottom: "16px" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                <FileCheck2 size={16} className="text-orange" />
                                <h3 style={{ margin: 0, fontSize: "14px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em" }}>Review Plan</h3>
                              </div>
                              <span className="badge badge-info">{plan.status}</span>
                            </div>

                            <div style={{ display: "grid", gap: 10 }}>
                              {plan.items.map((item) => (
                                <article key={item.id} className="suggestion-val-box" style={{ padding: "10px 14px", background: "var(--color-grey-50)" }}>
                                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                                    <strong style={{ fontSize: "13px" }}>{labelForField(item.field)}</strong>
                                    <span className={cx("badge", item.status === "APPROVED" ? "badge-good" : item.status === "REJECTED" ? "badge-danger" : "badge-info")}>
                                      {item.status === "APPROVED" ? "Approved" : item.status === "REJECTED" ? "Rejected" : "Proposed"}
                                    </span>
                                  </div>
                                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))", gap: 8, fontSize: "12px" }}>
                                    <div><span className="val-caption">Target</span> <strong>{item.document_side === "BL" ? "Draft BL" : "SI"}</strong></div>
                                    <div><span className="val-caption">Current</span> <span>{displayValue(item.current_value)}</span></div>
                                    <div><span className="val-caption">Proposed</span> <strong>{displayValue(item.human_edited_value ?? item.proposed_value)}</strong></div>
                                    <div><span className="val-caption">Source</span> <span className="badge badge-muted" style={{ fontSize: "10.5px" }}>{item.human_edited_value ? "Edited by reviewer" : item.ai_suggestion_id ? "AI Suggested" : "Manual"}</span></div>
                                  </div>
                                  {item.reason && <p style={{ margin: "6px 0 0", fontSize: "11.5px", color: "var(--color-grey-600)" }}>{item.reason}</p>}
                                  {plan.status === "DRAFT" && (
                                    <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                                      {item.status !== "APPROVED" && (
                                        <button type="button" className="button-primary btn-sm" onClick={() => void updateReviewPlanItem(selected.id, plan.id, item.id, "APPROVED").then(setPlan)}>Approve</button>
                                      )}
                                      {item.status !== "REJECTED" && (
                                        <button type="button" className="button-danger-secondary btn-sm" onClick={() => void updateReviewPlanItem(selected.id, plan.id, item.id, "REJECTED").then(setPlan)}>Reject</button>
                                      )}
                                      {!item.ai_suggestion_id && (
                                        <button type="button" className="button-danger-secondary btn-sm" onClick={() => void removeManualReviewPlanItem(selected.id, plan.id, item.id, reviewer).then(setPlan)}><Trash2 size={12} /> Remove</button>
                                      )}
                                    </div>
                                  )}
                                </article>
                              ))}
                            </div>

                            {(plan.status === "DRAFT" || plan.status === "APPLY_FAILED") && (
                              <div style={{ marginTop: 14, paddingTop: 10, borderTop: "1px solid var(--color-grey-200)", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                                <span style={{ fontSize: "12.5px", fontWeight: 600, color: "var(--color-grey-700)" }}>
                                  {plan.items.filter((i) => i.status === "APPROVED" || i.status === "EDITED").length} approved {plan.items.filter((i) => i.status === "APPROVED" || i.status === "EDITED").length === 1 ? "change" : "changes"} ready
                                </span>
                                <div style={{ display: "flex", gap: 8 }}>
                                  <button
                                    type="button"
                                    className="button-primary btn-dark-charcoal"
                                    disabled={isPlanActionLoading || (plan.status === "DRAFT" && !plan.items.some((i) => i.status === "APPROVED" || i.status === "EDITED"))}
                                    onClick={() => void handleConfirmImplementation()}
                                  >
                                    {plan.status === "APPLY_FAILED" ? "Retry Re-comparison" : "Confirm Implementation"}
                                  </button>
                                  {plan.status === "DRAFT" && (
                                    <button
                                      type="button"
                                      className="button-secondary btn-sm"
                                      onClick={() => void cancelReviewPlan(selected.id, plan.id, reviewer).then(() => setPlan(null))}
                                    >
                                      Cancel Plan
                                    </button>
                                  )}
                                </div>
                              </div>
                            )}
                            {plan.error_message && (
                              <p className="state-note warn" style={{ marginTop: 8 }}>Overrides were preserved. Re-comparison can be retried: {plan.error_message}</p>
                            )}
                          </div>
                        )}

                        {/* 3. COMPLETE 7 CANONICAL FIELDS TABLE TOGGLE (Matching Figure 2) */}
                        <div className="detail-section" style={{ marginTop: "16px" }}>
                          <button
                            type="button"
                            className="toggle-all-fields-btn"
                            onClick={() => setShowAllFields((prev) => !prev)}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                              width: "100%",
                              padding: "10px 14px",
                              background: "var(--color-grey-100)",
                              border: "1px solid var(--color-grey-300)",
                              borderRadius: "var(--radius-md)",
                              fontSize: "12.5px",
                              fontWeight: 650,
                              color: "var(--color-black)",
                              cursor: "pointer",
                            }}
                          >
                            <span style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                              <FileCheck2 size={15} />
                              {showAllFields ? "Hide Complete 7-Field Table" : "Show All 7 Canonical Comparison Fields"}
                            </span>
                            {showAllFields ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                          </button>

                          <div
                            className={cx(!showAllFields && "sub-tab-panel-hidden")}
                            id="fields-table-section"
                            style={{ marginTop: "10px" }}
                          >
                            <div className="section-heading-row" style={{ marginTop: "12px", marginBottom: "8px" }}>
                              <div>
                                <h3 style={{ margin: 0, fontSize: "14px" }}>Seven reviewed fields</h3>
                                <p style={{ margin: "2px 0 0", fontSize: "12px", color: "var(--color-grey-600)" }}>
                                  Original extraction remains immutable. Reviewed values are applied only during recomparison.
                                </p>
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
                                  {sortedFields.map((name) => {
                                    const compared = selected.comparison?.fields.find((item) => item.field === name);
                                    const siOverride = activeOverrides.find((item) => item.field === name && item.document_side === "SI");
                                    const blOverride = activeOverrides.find((item) => item.field === name && item.document_side === "BL");
                                    const isEditingThisRow = editingField === name;
                                    const isMatched = compared?.status === "MATCH";

                                    return (
                                      <tr
                                        key={name}
                                        id={`row-${name}`}
                                        className={cx(
                                          compared?.status === "MISMATCH" && "field-mismatch",
                                          compared?.status === "UNRESOLVED" && "field-unresolved",
                                          isEditingThisRow && "row-is-editing"
                                        )}
                                      >
                                        <th>{labelForField(name)}</th>
                                        <td>
                                          {siOverride ? (
                                            <>
                                              <span className="value-label">Original SI</span>
                                              <span className="original-val-strike">{displayValue(compared?.si.raw)}</span>
                                              <span className="reviewed-value">
                                                <span>Reviewed SI</span>
                                                {displayValue(siOverride.corrected_value)}
                                              </span>
                                              <span className="effective-value">
                                                Effective: {displayValue(siOverride.corrected_value)}
                                              </span>
                                            </>
                                          ) : !isMatched ? (
                                            <>
                                              <span className="value-label">Original SI</span>
                                              {displayValue(compared?.si.raw)}
                                              <span className="effective-value">
                                                Effective: {displayValue(compared?.si.canonical ?? compared?.si.raw)}
                                              </span>
                                            </>
                                          ) : (
                                            <span>{displayValue(compared?.si.canonical ?? compared?.si.raw)}</span>
                                          )}
                                        </td>
                                        <td>
                                          {blOverride ? (
                                            <>
                                              <span className="value-label">Original BL</span>
                                              <span className="original-val-strike">{displayValue(compared?.bl.raw)}</span>
                                              <span className="reviewed-value">
                                                <span>Reviewed BL</span>
                                                {displayValue(blOverride.corrected_value)}
                                              </span>
                                              <span className="effective-value">
                                                Effective: {displayValue(blOverride.corrected_value)}
                                              </span>
                                            </>
                                          ) : !isMatched ? (
                                            <>
                                              <span className="value-label">Original BL</span>
                                              {displayValue(compared?.bl.raw)}
                                              <span className="effective-value">
                                                Effective: {displayValue(compared?.bl.canonical ?? compared?.bl.raw)}
                                              </span>
                                            </>
                                          ) : (
                                            <span>{displayValue(compared?.bl.canonical ?? compared?.bl.raw)}</span>
                                          )}
                                        </td>
                                        <td style={{ textAlign: "center", whiteSpace: "nowrap" }}>
                                          <StatusBadge value={compared?.status ?? "UNRESOLVED"} />
                                        </td>
                                        <td style={{ textAlign: "center" }}>
                                          {selected.case_origin === "ACTIVE" ? (
                                            isMatched ? (
                                              <span className="matched-verified-pill" title="Field matches between SI and BL">
                                                <CheckCircle2 size={13} style={{ color: "#16a34a", marginRight: 4, verticalAlign: "-2px" }} />
                                                <span style={{ color: "#15803d", fontSize: "11.5px", fontWeight: 600 }}>Verified</span>
                                              </span>
                                            ) : (
                                              <button
                                                type="button"
                                                className="row-edit-action-btn is-unresolved"
                                                title={`Quick edit ${labelForField(name)}`}
                                                onClick={() => {
                                                  if (isEditingThisRow) {
                                                    setEditingField(null);
                                                  } else {
                                                    setField(name);
                                                    setEditingField(name);
                                                    if (compared?.bl.raw == null && compared?.si.raw != null) {
                                                      setSide("BL");
                                                    } else if (compared?.si.raw == null && compared?.bl.raw != null) {
                                                      setSide("SI");
                                                    } else {
                                                      setSide("BL");
                                                    }
                                                    const el = document.getElementById("review-editor-box");
                                                    if (el) el.scrollIntoView({ behavior: "smooth" });
                                                  }
                                                }}
                                              >
                                                {isEditingThisRow ? "Close" : "Correct"}
                                              </button>
                                            )
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
                        </div>

                        {activeOverrides.length > 0 && (
                          <div className="staged-overrides-card" style={{ marginTop: 14, marginBottom: 16 }}>
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
                      </div>

                      {selected.case_origin === "ACTIVE" ? (
                        <div
                          className={cx(
                            "sub-tab-panel",
                            reviewSubTab !== "assistant" && reviewSubTab !== "actions" && "sub-tab-panel-hidden",
                            reviewSubTab === "assistant" && "sub-tab-assistant-active",
                            reviewSubTab === "actions" && "sub-tab-actions-active"
                          )}
                        >
                          <AIReviewPanel
                            review={selected}
                            reviewerName={selected.reviewer_name || reviewer}
                            plan={plan}
                            onPlanChanged={setPlan}
                            onCaseUpdated={(updated) => onCaseUpdated?.(updated)}
                          />
                        </div>
                      ) : null}

                      <div
                        className={cx("sub-tab-panel", reviewSubTab !== "resolve" && "sub-tab-panel-hidden")}
                        id="resolve-panel-section"
                      >
                        {selected.case_origin === "ACTIVE" ? (
                          <div className="bottom-resolve-bar" id="resolve-action-section" style={{ marginTop: 0 }}>
                            <div className="resolve-bar-content">
                              <div className="resolve-bar-info">
                                <strong>Ready to verify?</strong>
                                <p className="subtle" style={{ margin: "2px 0 0 0", fontSize: "12px" }}>Applying overrides and running recomparison against canonical shipping rules.</p>
                              </div>
                              <button
                                className="button-primary btn-dark-charcoal resolve-final-btn"
                                type="button"
                                aria-label="Confirm Resolve & Recompare"
                                disabled={actionState === "loading" || selected.status === "DISMISSED"}
                                onClick={() => void onResolve(reviewer, note)}
                              >
                                <CheckCircle2 size={16} />
                                {actionState === "loading" ? "Recomparing…" : "Resolve & Recompare"}
                              </button>
                            </div>
                          </div>
                        ) : null}

                        {selected.case_origin === "ACTIVE" ? (
                          <details className="collapsible-detail-card danger-zone-collapsible" id="danger-zone-section" style={{ marginTop: 14 }}>
                            <summary className="collapsible-summary danger-summary">
                              <div className="collapsible-summary-left">
                                <AlertTriangle size={15} className="text-danger" aria-hidden="true" />
                                <strong>Danger Zone</strong>
                                <span className="subtle">Dismiss review without resolving</span>
                              </div>
                              <span className="subtle" style={{ fontSize: "12px" }}>Click to expand/collapse</span>
                            </summary>
                            <div className="collapsible-content">
                              <div id="dismiss-zone-box" className="dismiss-zone" style={{ border: "none", padding: 0 }}>
                                <p className="dismiss-subtitle" style={{ marginTop: 0 }}>
                                  Dismiss records an audited decision. It does not mark the comparison completed.
                                </p>
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
                          </details>
                        ) : (
                          <div className="detail-section">
                            <div className="state-note">
                              <strong>Historical review record</strong>
                              <span>This record is retained for audit history and is read-only.</span>
                              <small>No correction, claim, resolve, or dismiss action is available.</small>
                            </div>
                          </div>
                        )}
                      </div>
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
                  <ReplyEmailSection detail={replyDetail} />
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
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [summary, setSummary] = useState<ProductSummary | null>(null);
  const [queue, setQueue] = useState<EmailQueuePage | null>(null);
  const [detail, setDetail] = useState<ProductEmailDetail | null>(null);
  const [reviews, setReviews] = useState<HumanReviewPage | null>(null);
  const [reviewAnalytics, setReviewAnalytics] = useState<HumanReviewAnalytics | null>(null);
  const [selectedReview, setSelectedReview] = useState<ProductReview | null>(null);

  // Discrepancy workspace state
  const [discrepancies, setDiscrepancies] = useState<DiscrepancyPage | null>(null);
  const [selectedDiscrepancy, setSelectedDiscrepancy] = useState<ProductDiscrepancyDetail | null>(null);
  const [discrepancyState, setDiscrepancyState] = useState<LoadState>("idle");
  const [discrepancyActionState, setDiscrepancyActionState] = useState<LoadState>("idle");
  const [discrepancyFilters, setDiscrepancyFilters] = useState<DiscrepancyQueueFilters>({
    status: "",
    search: "",
    skip: 0,
    limit: 20,
  });

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

  const selectDiscrepancyById = useCallback(async (discrepancyId: string, updateUrl = true) => {
    setPage("discrepancies");
    setDiscrepancyActionState("loading");
    try {
      const detail = await getDiscrepancyDetail(discrepancyId);
      setSelectedDiscrepancy(detail);
      setDiscrepancyActionState("ready");
      if (updateUrl) window.history.replaceState({}, "", `?discrepancy=${encodeURIComponent(discrepancyId)}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load discrepancy detail");
      setDiscrepancyActionState("error");
    }
  }, []);

  const loadDiscrepancies = useCallback(async () => {
    setDiscrepancyState("loading");
    try {
      const pageData = await getDiscrepancies(discrepancyFilters);
      setDiscrepancies(pageData);
      setDiscrepancyState("ready");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load discrepancies");
      setDiscrepancyState("error");
    }
  }, [discrepancyFilters, selectDiscrepancyById]);

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
    const discrepancyId = params.get("discrepancy");
    const emailId = params.get("email");
    if (reviewId) void selectReviewById(reviewId, false);
    else if (discrepancyId) void selectDiscrepancyById(discrepancyId, false);
    else if (emailId) void selectEmailById(emailId, false);
  }, [selectEmailById, selectReviewById, selectDiscrepancyById]);

  useEffect(() => {
    if (page === "review") {
      void loadReviews();
    }
  }, [loadReviews, page]);

  useEffect(() => {
    if (page === "discrepancies") {
      void loadDiscrepancies();
    }
  }, [loadDiscrepancies, page]);

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
    await Promise.all([loadReviews(), loadDashboard(), loadDiscrepancies()]);
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

  const handleAcknowledgeDiscrepancy = async (discrepancyId: string, operatorName?: string) => {
    setDiscrepancyActionState("loading");
    setError(null);
    try {
      await acknowledgeDiscrepancy(discrepancyId, operatorName);
      await Promise.all([loadDiscrepancies(), loadDashboard()]);
      const updated = await getDiscrepancyDetail(discrepancyId);
      setSelectedDiscrepancy(updated);
      setDiscrepancyActionState("ready");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to acknowledge discrepancy");
      setDiscrepancyActionState("error");
    }
  };

  const handleResolveDiscrepancy = async (discrepancyId: string, operatorName?: string, notes?: string) => {
    setDiscrepancyActionState("loading");
    setError(null);
    try {
      await resolveDiscrepancy(discrepancyId, operatorName, notes);
      await Promise.all([loadDiscrepancies(), loadDashboard()]);
      const updated = await getDiscrepancyDetail(discrepancyId);
      setSelectedDiscrepancy(updated);
      setDiscrepancyActionState("ready");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to resolve discrepancy");
      setDiscrepancyActionState("error");
    }
  };

  const handleOverrideAndRecompareDiscrepancy = async (
    discrepancyId: string,
    payload: {
      document_side: "SI" | "BL";
      field_name: string;
      corrected_value: unknown;
      reviewer_name?: string;
      note?: string;
    },
  ) => {
    setDiscrepancyActionState("loading");
    setError(null);
    try {
      await saveDiscrepancyOverride(discrepancyId, payload);
      const recompared = await recompareDiscrepancy(discrepancyId, payload.reviewer_name);
      await Promise.all([loadDiscrepancies(), loadDashboard()]);
      const updated = await getDiscrepancyDetail(recompared.discrepancy.id).catch(() => recompared);
      setSelectedDiscrepancy(updated || recompared);
      setDiscrepancyActionState("ready");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to save correction and recompare");
      setDiscrepancyActionState("error");
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

  const restoreEmail = async (emailId: string) => {
    setError(null);
    try {
      await reconcileOutlookLifecycle({
        email_id: emailId,
        lifecycle_status: "RESTORED",
        actor_name: "Dashboard operator",
      });
      await loadDashboard();
      setDetail(await getEmailDetail(emailId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Restore failed");
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
    setMobileMenuOpen(false);
    window.history.replaceState({}, "", window.location.pathname);
  };

  return (
    <div className="app-shell">
      {/* Mobile Drawer Backdrop */}
      {mobileMenuOpen && (
        <div
          className="mobile-sidebar-backdrop"
          onClick={() => setMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside className={cx("sidebar", mobileMenuOpen && "mobile-open")} aria-label="Primary navigation">
        <div className="brand">
          <img src="/holyship-logo.png" alt="HolyShip" className="brand-logo" />
          <button
            type="button"
            className="sidebar-close-btn"
            onClick={() => setMobileMenuOpen(false)}
            aria-label="Close navigation menu"
            title="Close navigation menu"
          >
            <X size={20} />
          </button>
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
          <button className={cx(page === "discrepancies" && "active")} onClick={() => navigate("discrepancies")} type="button">
            <AlertTriangle size={18} />
            Discrepancies
            {typeof summary?.mismatch_count === "number" && summary.mismatch_count > 0 ? (
              <span className="sidebar-badge" style={{ marginLeft: "auto", background: "var(--color-danger)", color: "#fff", fontSize: "10px", padding: "1px 6px", borderRadius: "10px", fontWeight: 700 }}>
                {summary.confirmed_discrepancies_count ?? summary.mismatch_count}
              </span>
            ) : null}
          </button>
          <button className={cx(page === "review" && "active")} onClick={() => navigate("review")} type="button">
            <ClipboardList size={18} />
            Human Review
            {typeof summary?.human_review_open_count === "number" && summary.human_review_open_count > 0 ? (
              <span className="sidebar-badge" style={{ marginLeft: "auto", background: "var(--color-warn)", color: "#fff", fontSize: "10px", padding: "1px 6px", borderRadius: "10px", fontWeight: 700 }}>
                {summary.human_review_open_count}
              </span>
            ) : null}
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
          onToggleMobileMenu={() => setMobileMenuOpen((open) => !open)}
        />

        {error ? <div className="error-banner" role="alert">{error}</div> : null}

        {page === "overview" ? (
          <OverviewPage
            summary={summary}
            queue={queue}
            state={loadState}
            onOpenQueue={() => {
              setPageIndex(0);
              setFilters({ limit: 20, skip: 0 });
              setPage("queue");
            }}
            onOpenQueueWithFilters={(newFilters) => {
              setPageIndex(0);
              setFilters({ limit: 20, skip: 0, ...newFilters });
              setPage("queue");
            }}
            onSelectEmail={(item) => void selectEmail(item)}
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
            onRestoreEmail={(emailId) => void restoreEmail(emailId)}
            onCloseDetail={() => setDetail(null)}
            onPage={movePage}
            onGoToPage={goToPage}
          />
        ) : null}

        {page === "discrepancies" ? (
          <ConfirmedDiscrepanciesPageView
            discrepancies={discrepancies}
            state={discrepancyState}
            selected={selectedDiscrepancy}
            actionState={discrepancyActionState}
            filters={discrepancyFilters}
            onFilterChange={(newFilters) => setDiscrepancyFilters(newFilters)}
            onSelect={(id) => void selectDiscrepancyById(id)}
            onAcknowledge={handleAcknowledgeDiscrepancy}
            onResolve={handleResolveDiscrepancy}
            onOverrideAndRecompare={handleOverrideAndRecompareDiscrepancy}
            onOpenEmailInQueue={(emailId) => void selectEmailById(emailId)}
            onRefresh={() => void loadDiscrepancies()}
            onDeselect={() => setSelectedDiscrepancy(null)}
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
            onDeselect={() => setSelectedReview(null)}
          />
        ) : null}
      </main>
    </div>
  );
}
