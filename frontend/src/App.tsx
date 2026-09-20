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
  MailCheck,
  Maximize2,
  Minimize2,
  MoreHorizontal,
  RefreshCw,
  Search,
  ShieldAlert,
  ShipWheel,
  X,
} from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  getEmailDetail,
  getEmailQueue,
  getEvents,
  getHumanReviewQueue,
  getSummary,
} from "./api/client";
import type {
  EmailQueuePage,
  HumanReviewPage,
  ProcessingStatus,
  ProductCategory,
  ProductEmailDetail,
  ProductEmailSummary,
  ProductSummary,
  QueueFilters,
} from "./api/types";
import { canonicalFields } from "./api/types";
import {
  categoryLabels,
  displayValue,
  fieldStatusLabels,
  formatDate,
  labelForField,
  readinessLabels,
  statusLabels,
} from "./lib/labels";

type Page = "overview" | "queue" | "review";
type LoadState = "idle" | "loading" | "ready" | "error";

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

function cx(...items: Array<string | false | null | undefined>): string {
  return items.filter(Boolean).join(" ");
}

function metricFromStatus(summary: ProductSummary | null, status: ProcessingStatus): number {
  return summary?.status_counts[status] ?? 0;
}

function StatusBadge({
  value,
  tone,
}: {
  value: string | null | undefined;
  tone?: "neutral" | "good" | "warn" | "bad" | "attention";
}) {
  if (!value) return <span className="badge badge-muted">Not set</span>;
  const resolvedTone =
    tone ??
    (value === "FAILED"
      ? "bad"
      : value === "BLOCKED"
        ? "attention"
        : value === "AWAITING_DOCUMENTS" || value === "UNRESOLVED"
          ? "warn"
          : value === "COMPLETED" || value === "MATCH"
            ? "good"
            : "neutral");
  const label =
    value in statusLabels
      ? statusLabels[value as ProcessingStatus]
      : value in categoryLabels
        ? categoryLabels[value as ProductCategory]
        : value.replaceAll("_", " ");
  return <span className={`badge badge-${resolvedTone}`}>{label}</span>;
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="empty-state">
      <Archive aria-hidden="true" size={28} />
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
  if (!date) return "Just now";
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
}: {
  page: Page;
  state: LoadState;
  lastSyncedAt: Date | null;
  onRefresh?: () => void;
}) {
  const [syncTimeText, setSyncTimeText] = useState(() => formatRelativeTime(lastSyncedAt));

  useEffect(() => {
    setSyncTimeText(formatRelativeTime(lastSyncedAt));
    const interval = window.setInterval(() => {
      setSyncTimeText(formatRelativeTime(lastSyncedAt));
    }, 5000);
    return () => window.clearInterval(interval);
  }, [lastSyncedAt]);

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
          <span style={{ opacity: 0.65, marginLeft: 6, fontWeight: 400, fontSize: "11.5px" }}>
            Last synced {syncTimeText}
          </span>
        </span>
        <button
          className="icon-button"
          onClick={onRefresh}
          type="button"
          aria-label="Refresh overview"
          style={{ width: 34, height: 34, borderRadius: 8 }}
        >
          <RefreshCw size={15} />
        </button>
        <div className="avatar-badge">JD</div>
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
      <div className="metric-grid-wrap">
        <div className="metric-grid" aria-label="Operational summary">
          <MetricCard
            cardIndex={0}
            icon={<MailCheck size={18} color="var(--color-black)" />}
            label="Total Emails"
            value={summary?.total_emails ?? 0}
            trendText="+12% from yesterday"
            trend="up"
            tone="neutral"
          />
          <MetricCard
            cardIndex={1}
            icon={<CircleCheck size={18} color="var(--color-success)" />}
            label="Completed"
            value={completed}
            trendText={`${completionRate}% of total`}
            subTrendText="+8%"
            trend="up"
            tone="good"
          />
          <MetricCard
            cardIndex={2}
            icon={<ShieldAlert size={18} color="var(--color-warn)" />}
            label="Needs Review"
            value={summary?.needs_review_count ?? 0}
            trendText={`${summary && summary.total_emails > 0 ? Math.round(((summary.needs_review_count ?? 0) / summary.total_emails) * 100) : 0}% of total`}
            subTrendText="+5%"
            trend="up"
            tone="warn"
          />
          <MetricCard
            cardIndex={3}
            icon={<AlertTriangle size={18} color="var(--color-danger)" />}
            label="Mismatch"
            value={summary?.mismatch_count ?? 0}
            trendText={`${summary && summary.total_emails > 0 ? Math.round(((summary.mismatch_count ?? 0) / summary.total_emails) * 100) : 0}% of total`}
            subTrendText="-2%"
            trend="down"
            tone="bad"
          />
        </div>
      </div>

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
              {queue.items.slice(0, 6).map((item, idx) => {
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
                    <span className="activity-row-time">{idx === 0 ? "2 min ago" : idx === 1 ? "8 min ago" : `${(idx + 1) * 7} min ago`}</span>
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
                  <strong>BL vs SI mismatch</strong>
                  <p>Container no. or weight discrepancy</p>
                </div>
              </div>
              <div className="alert-row-right">
                <span>{summary?.mismatch_count ?? 8}</span>
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
                <span>{metricFromStatus(summary, "AWAITING_DOCUMENTS") || 15}</span>
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
                <span>{metricFromStatus(summary, "BLOCKED") || 11}</span>
                <ChevronRight size={14} color="var(--color-grey-500)" />
              </div>
            </div>

            <div className="alert-row-compact" onClick={onOpenQueue}>
              <div className="alert-row-left">
                <div className="activity-circle-icon neutral">
                  <AlertCircle size={13} />
                </div>
                <div className="alert-row-info">
                  <strong>Unresolved fields</strong>
                  <p>Requires manual review verification</p>
                </div>
              </div>
              <div className="alert-row-right">
                <span>{summary?.unresolved_count ?? 12}</span>
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
                <span>{metricFromStatus(summary, "FAILED") || 6}</span>
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

const CARD_VIEW_SLICES = [
  { x: 0, w: 291 },
  { x: 303, w: 291 },
  { x: 606, w: 291 },
  { x: 909, w: 291 },
];

function MetricCardWave({ index }: { index: number }) {
  const slice = CARD_VIEW_SLICES[index % CARD_VIEW_SLICES.length];
  const gradId = `cardWaveGrad_${index}`;
  const glowId = `cardWaveGlow_${index}`;
  const sheenId = `cardWaveSheen_${index}`;

  return (
    <svg
      className="card-ribbon-svg"
      viewBox={`${slice.x} 0 ${slice.w} 100`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#e39439" stopOpacity="0.24" />
          <stop offset="35%" stopColor="#f59e0b" stopOpacity="0.36" />
          <stop offset="70%" stopColor="#f97316" stopOpacity="0.30" />
          <stop offset="100%" stopColor="#e39439" stopOpacity="0.20" />
        </linearGradient>
        <linearGradient id={glowId} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#e39439" stopOpacity="0.08" />
          <stop offset="50%" stopColor="#f59e0b" stopOpacity="0.14" />
          <stop offset="100%" stopColor="#ea580c" stopOpacity="0.06" />
        </linearGradient>
        <linearGradient id={sheenId} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#ffffff" stopOpacity="0.32" />
          <stop offset="50%" stopColor="#fff7ed" stopOpacity="0.55" />
          <stop offset="100%" stopColor="#fed7aa" stopOpacity="0.22" />
        </linearGradient>
      </defs>
      <path
        d={MASTER_WAVE_MAIN}
        fill="none"
        stroke={`url(#${glowId})`}
        strokeWidth="18"
        strokeLinecap="round"
      />
      <path
        d={MASTER_WAVE_MAIN}
        fill="none"
        stroke={`url(#${gradId})`}
        strokeWidth="9"
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
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  trendText?: string;
  subTrendText?: string;
  trend?: "up" | "down";
  tone?: "neutral" | "good" | "warn" | "bad" | "attention";
  cardIndex?: number;
}) {
  return (
    <article className={`metric-card metric-${tone}`}>
      <MetricCardWave index={cardIndex} />
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
        <strong>{value.toLocaleString()}</strong>
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

function QueuePage({
  page,
  queue,
  detail,
  detailState,
  queueState,
  filters,
  onFilters,
  onSelect,
  onCloseDetail,
  onPage,
}: {
  page: number;
  queue: EmailQueuePage | null;
  detail: ProductEmailDetail | null;
  detailState: LoadState;
  queueState: LoadState;
  filters: QueueFilters;
  onFilters: (filters: QueueFilters) => void;
  onSelect: (email: ProductEmailSummary) => void;
  onCloseDetail?: () => void;
  onPage: (direction: "next" | "previous") => void;
}) {
  const [isFloating, setIsFloating] = useState(false);
  const tableWrapRef = useRef<HTMLDivElement>(null);

  const scrollTable = (direction: "left" | "right") => {
    if (tableWrapRef.current) {
      const scrollAmount = direction === "left" ? -300 : 300;
      tableWrapRef.current.scrollBy({ left: scrollAmount, behavior: "smooth" });
    }
  };

  const pageSize = filters.limit ?? 25;
  const canPrevious = page > 0;
  const canNext = queue ? queue.skip + pageSize < queue.total : false;

  return (
    <section className={cx("queue-layout", isFloating && "floating-layout")}>
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
                    <tr key={item.id} onClick={() => onSelect(item)}>
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
                        <span className={cx("badge", item.needs_review ? "badge-attention" : "badge-neutral")}>
                          {item.needs_review ? "Needs review" : "Clear"}
                        </span>
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
              <button
                className="pagination-btn-prev"
                disabled={!canPrevious}
                onClick={() => onPage("previous")}
                type="button"
              >
                <ChevronLeft size={16} /> Previous
              </button>
              <span>
                Page {page + 1} of {Math.max(1, Math.ceil(queue.total / pageSize))} ({queue.total} total)
              </span>
              <button
                className="pagination-btn-next"
                disabled={!canNext}
                onClick={() => onPage("next")}
                type="button"
              >
                Next <ChevronRight size={16} />
              </button>
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
              <EmailDetailContent detail={detail} onClose={onCloseDetail} />
            </div>
          </>
        ) : null
      ) : (
        <div className="surface-panel detail-panel">
          {detailState === "loading" ? (
            <LoadingRows />
          ) : detail ? (
            <EmailDetailContent detail={detail} onClose={onCloseDetail} />
          ) : (
            <EmptyState
              title="Select an email"
              body="Choose any message from the operational queue to view classification, attachments, timeline, and document comparison."
            />
          )}
        </div>
      )}
    </section>
  );
}

function EmailDetailContent({
  detail,
  onClose,
}: {
  detail: ProductEmailDetail;
  onClose?: () => void;
}) {
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
          From {detail.email.sender || "Unknown"} · Message ID: {detail.email.external_message_id}
        </p>
      </div>

      <div className="detail-section">
        <h3>Classification & State</h3>
        <div className="info-grid">
          <div className="info-item">
            <span>Category</span>
            <strong>{categoryLabels[detail.email.category ?? "general_message"]}</strong>
          </div>
          <div className="info-item">
            <span>Confidence</span>
            <strong>{Math.round((detail.email.classification_confidence ?? 0) * 100)}%</strong>
          </div>
          <div className="info-item">
            <span>Status</span>
            <strong>{statusLabels[detail.email.processing_status]}</strong>
          </div>
          <div className="info-item">
            <span>Readiness</span>
            <strong>{detail.email.comparison_readiness ? readinessLabels[detail.email.comparison_readiness] : "—"}</strong>
          </div>
        </div>
      </div>

      {detail.comparison ? (
        <div className="detail-section">
          <h3>Seven-Field Verification</h3>
          <div className="comparison-table-wrap">
            <table
              className="comparison-table"
              aria-label="Seven-field SI and Draft BL comparison"
            >
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
                    <tr
                      key={fieldKey}
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
                  );
                })}
              </tbody>
            </table>
          </div>
          {detail.comparison.mismatch_found ? (
            <p className="comparison-message mismatch">
              Mismatch detected across {detail.comparison.mismatched_fields.length} field(s).
            </p>
          ) : detail.comparison.unresolved_fields.length ? (
            <p className="comparison-message unresolved">
              {detail.comparison.unresolved_fields.length} field(s) require human review.
            </p>
          ) : (
            <p className="comparison-message match">No mismatch detected across all 7 fields.</p>
          )}
        </div>
      ) : detail.email.comparison_readiness === "AWAITING_DOCUMENTS" ? (
        <div className="detail-section">
          <h3>Comparison Status</h3>
          <div className="state-note awaiting">
            Draft BL is not yet available for this SI. The case is awaiting follow-up documents.
          </div>
        </div>
      ) : null}

      <div className="detail-section">
        <h3>Attachments ({detail.attachments.length})</h3>
        {detail.attachments.length ? (
          <div className="attachment-list">
            {detail.attachments.map((att) => (
              <div className="attachment-row" key={att.id}>
                <FileSearch size={16} />
                <div>
                  <strong>{att.filename}</strong>
                  <p>{att.content_type || "Document"} · {att.retrieval_status || "Retrieved"}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="subtle">No attachments found on this email.</p>
        )}
      </div>

      <div className="detail-section">
        <h3>Processing Timeline</h3>
        <div className="timeline">
          {detail.timeline.map((event) => (
            <div className="timeline-row" key={event.id}>
              <span />
              <div>
                <strong>{(statusLabels as Record<string, string>)[event.new_status] || event.new_status}</strong>
                <p>{event.reason_code} · {formatDate(event.created_at)}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function HumanReviewPageView({
  reviews,
  state,
  onSelect,
}: {
  reviews: HumanReviewPage | null;
  state: LoadState;
  onSelect: (email: ProductEmailSummary) => void;
}) {
  return (
    <section className="surface-panel">
      <div className="section-header">
        <div>
          <p className="eyebrow">Exception handling</p>
          <h2>Human Review</h2>
        </div>
        <span className="total-pill">{reviews?.total ?? 0} cases</span>
      </div>

      {state === "loading" ? (
        <LoadingRows />
      ) : reviews?.items.length ? (
        <div className="review-list">
          {reviews.items.map((review) => (
            <div className="review-card" key={review.id}>
              <div className="review-card-header">
                <div>
                  <h2>{review.email?.subject ?? "Unknown subject"}</h2>
                  <p>From {review.email?.sender || "Unknown"} · Reason: {review.reason_text || review.reason_code}</p>
                </div>
                {review.email ? (
                  <button
                    type="button"
                    onClick={() => onSelect(review.email!)}
                  >
                    View Case
                  </button>
                ) : null}
              </div>
              <div className="review-meta">
                <StatusBadge value={review.status} />
                <span className="subtle">{labelForField(review.field ?? "unknown")}</span>
                <span className="subtle">Confidence: {Math.round((review.confidence ?? 0) * 100)}%</span>
                <span className="subtle">{review.created_at ? formatDate(review.created_at) : ""}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          title="No review cases"
          body="All current cases are either completed cleanly or do not require manual exception handling."
        />
      )}
    </section>
  );
}

export default function App() {
  const [page, setPage] = useState<Page>("overview");
  const [summary, setSummary] = useState<ProductSummary | null>(null);
  const [queue, setQueue] = useState<EmailQueuePage | null>(null);
  const [detail, setDetail] = useState<ProductEmailDetail | null>(null);
  const [reviews, setReviews] = useState<HumanReviewPage | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [detailState, setDetailState] = useState<LoadState>("idle");
  const [reviewState, setReviewState] = useState<LoadState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [pageIndex, setPageIndex] = useState(0);
  const [filters, setFilters] = useState<QueueFilters>({ limit: 25, skip: 0 });
  const [lastEventAt, setLastEventAt] = useState<string | undefined>(undefined);
  const [lastSyncedAt, setLastSyncedAt] = useState<Date | null>(null);

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
      setReviews(await getHumanReviewQueue());
      setReviewState("ready");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load review queue");
      setReviewState("error");
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

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
    setPage("queue");
    setDetailState("loading");
    try {
      setDetail(await getEmailDetail(email.id));
      setDetailState("ready");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load email detail");
      setDetailState("error");
    }
  };

  const updateFilters = (nextFilters: QueueFilters) => {
    setPageIndex(0);
    setFilters({ ...nextFilters, skip: 0, limit: nextFilters.limit ?? 25 });
  };

  const movePage = (direction: "next" | "previous") => {
    const nextIndex = direction === "next" ? pageIndex + 1 : Math.max(0, pageIndex - 1);
    const limit = filters.limit ?? 25;
    setPageIndex(nextIndex);
    setFilters({ ...filters, skip: nextIndex * limit, limit });
  };

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="brand">
          <div className="brand-mark">h</div>
          <div>
            <strong>HolyShip</strong>
            <span>Shipping Document Verification</span>
          </div>
        </div>
        <nav>
          <button className={cx(page === "overview" && "active")} onClick={() => setPage("overview")} type="button">
            <ShipWheel size={18} />
            Overview
          </button>
          <button className={cx(page === "queue" && "active")} onClick={() => setPage("queue")} type="button">
            <Inbox size={18} />
            Email Queue
          </button>
          <button className={cx(page === "review" && "active")} onClick={() => setPage("review")} type="button">
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
        />

        {error ? <div className="error-banner" role="alert">{error}</div> : null}

        {page === "overview" ? (
          <OverviewPage
            summary={summary}
            queue={queue}
            state={loadState}
            onOpenQueue={() => setPage("queue")}
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
            onCloseDetail={() => setDetail(null)}
            onPage={movePage}
          />
        ) : null}

        {page === "review" ? (
          <HumanReviewPageView
            reviews={reviews}
            state={reviewState}
            onSelect={(item) => void selectEmail(item)}
          />
        ) : null}
      </main>
    </div>
  );
}
