import React, { useState, useMemo } from "react";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Clock,
  ExternalLink,
  FileCheck2,
  FileEdit,
  FileText,
  RefreshCw,
  Search,
  ShieldAlert,
  X,
} from "lucide-react";
import type {
  CanonicalField,
  DiscrepancyPage,
  DiscrepancyQueueFilters,
  DiscrepancyStatus,
  LoadState,
  ProductDiscrepancyDetail,
  ProductDiscrepancySummary,
} from "../../api/types";
import { canonicalFields } from "../../api/types";
import {
  displayLabel,
  displayValue,
  fieldStatusLabels,
  formatDate,
  labelForField,
  reasonLabels,
} from "../../lib/labels";
import { EmptyState, MetricCard } from "../common/MetricCard";

function cx(...items: Array<string | false | null | undefined>): string {
  return items.filter(Boolean).join(" ");
}

interface ConfirmedDiscrepanciesPageViewProps {
  discrepancies: DiscrepancyPage | null;
  state: LoadState;
  selected: ProductDiscrepancyDetail | null;
  actionState: LoadState;
  filters: DiscrepancyQueueFilters;
  onFilterChange: (filters: DiscrepancyQueueFilters) => void;
  onSelect: (discrepancyId: string) => void;
  onAcknowledge: (discrepancyId: string, operatorName?: string) => Promise<void>;
  onResolve: (discrepancyId: string, operatorName?: string, notes?: string) => Promise<void>;
  onOverrideAndRecompare: (
    discrepancyId: string,
    payload: {
      document_side: "SI" | "BL";
      field_name: string;
      corrected_value: unknown;
      reviewer_name?: string;
      note?: string;
    },
  ) => Promise<void>;
  onOpenEmailInQueue: (emailId: string) => void;
  onRefresh: () => void;
  onDeselect?: () => void;
}

export function ConfirmedDiscrepanciesPageView({
  discrepancies,
  state,
  selected,
  actionState,
  filters,
  onFilterChange,
  onSelect,
  onAcknowledge,
  onResolve,
  onOverrideAndRecompare,
  onOpenEmailInQueue,
  onRefresh,
  onDeselect,
}: ConfirmedDiscrepanciesPageViewProps) {
  const [operatorName, setOperatorName] = useState("Captain Jack");
  const [showAllFields, setShowAllFields] = useState(false);
  const [activeTab, setActiveTab] = useState<"differences" | "documents" | "history">("differences");
  const [fieldFilter, setFieldFilter] = useState<string>("");
  const [sortFilter, setSortFilter] = useState<"newest" | "oldest" | "mismatches">("newest");

  // Correction Modal State
  const [overrideModalOpen, setOverrideModalOpen] = useState(false);
  const [overrideSide, setOverrideSide] = useState<"SI" | "BL">("BL");
  const [overrideField, setOverrideField] = useState<string>("consignee");
  const [overrideValue, setOverrideValue] = useState<string>("");
  const [overrideNote, setOverrideNote] = useState<string>("");

  // Resolve Modal State
  const [resolveModalOpen, setResolveModalOpen] = useState(false);
  const [resolveNotes, setResolveNotes] = useState<string>("");

  const rawItems = discrepancies?.items ?? [];
  const total = discrepancies?.total ?? 0;
  const openCount = discrepancies?.open_count ?? 0;
  const acknowledgedCount = discrepancies?.acknowledged_count ?? 0;
  const resolvedCount = discrepancies?.resolved_count ?? 0;

  // Filter and sort items
  const filteredItems = useMemo(() => {
    let result = [...rawItems];
    if (fieldFilter) {
      result = result.filter((item) =>
        item.mismatched_fields.includes(fieldFilter as CanonicalField)
      );
    }
    result.sort((a, b) => {
      if (sortFilter === "mismatches") {
        return b.mismatch_count - a.mismatch_count;
      }
      const timeA = new Date(a.received_at || a.created_at).getTime();
      const timeB = new Date(b.received_at || b.created_at).getTime();
      return sortFilter === "oldest" ? timeA - timeB : timeB - timeA;
    });
    return result;
  }, [rawItems, fieldFilter, sortFilter]);

  // Client pagination for left list
  const [pageIndex, setPageIndex] = useState(0);
  const pageSize = 10;
  const totalPages = Math.max(1, Math.ceil(filteredItems.length / pageSize));
  const safePage = Math.min(pageIndex, totalPages - 1);
  const pagedItems = useMemo(
    () => filteredItems.slice(safePage * pageSize, (safePage + 1) * pageSize),
    [filteredItems, safePage, pageSize]
  );

  // Compute top mismatched field for metrics
  const topMismatchedField = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const item of rawItems) {
      for (const f of item.mismatched_fields) {
        counts[f] = (counts[f] ?? 0) + 1;
      }
    }
    const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    return sorted[0] ? labelForField(sorted[0][0]) : "Gross Weight";
  }, [rawItems]);

  const openCorrectionModal = (side: "SI" | "BL", fieldName: string, initialVal?: string) => {
    setOverrideSide(side);
    setOverrideField(fieldName);
    setOverrideValue(initialVal ?? "");
    setOverrideNote("");
    setOverrideModalOpen(true);
  };

  const handleOverrideSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected) return;
    await onOverrideAndRecompare(selected.discrepancy.id, {
      document_side: overrideSide,
      field_name: overrideField,
      corrected_value: overrideValue,
      reviewer_name: operatorName,
      note: overrideNote,
    });
    setOverrideModalOpen(false);
  };

  const handleResolveSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected) return;
    await onResolve(selected.discrepancy.id, operatorName, resolveNotes);
    setResolveModalOpen(false);
    setResolveNotes("");
  };

  const countLabel =
    filteredItems.length === total
      ? `${total} cases`
      : `${filteredItems.length} shown · ${total} total`;

  return (
    <section className="page-grid discrepancies-page-grid">
      {/* 1. TOP METRIC SUMMARY CARDS (Matching Image 3 Human Review & Overview) */}
      <section className={cx("overview-summary-panel", selected && "mobile-hide-when-detail-open")} aria-label="Discrepancy Analytics">
        <div className="metric-grid human-review-metric-grid" aria-label="Discrepancy analytics cards">
          <MetricCard
            cardIndex={0}
            totalCards={5}
            icon={<AlertTriangle size={18} color="var(--color-review)" />}
            label="Open"
            value={openCount}
            trendText="Active confirmed mismatches"
            tone="attention"
          />
          <MetricCard
            cardIndex={1}
            totalCards={5}
            icon={<Clock size={18} color="var(--color-warn)" />}
            label="Acknowledged"
            value={acknowledgedCount}
            trendText="In review / handling"
            tone="neutral"
          />
          <MetricCard
            cardIndex={2}
            totalCards={5}
            icon={<CheckCircle2 size={18} color="var(--color-success)" />}
            label="Resolved"
            value={resolvedCount}
            trendText="Settled discrepancies"
            tone="good"
          />
          <MetricCard
            cardIndex={3}
            totalCards={5}
            icon={<AlertCircle size={18} color="var(--color-grey-700)" />}
            label="Total Queue"
            value={total}
            trendText="All mismatch cases"
            tone="neutral"
          />
          <MetricCard
            cardIndex={4}
            totalCards={5}
            icon={<FileEdit size={18} color="var(--color-grey-700)" />}
            label="Top Mismatch"
            value={topMismatchedField}
            trendText="Highest frequency field"
            tone="neutral"
          />
        </div>
      </section>

      {/* 2. MAIN SPLIT QUEUE & DETAIL WORKSPACE */}
      <section className={cx("queue-layout", !selected && "queue-layout-empty")}>
        {/* LEFT COLUMN: Queue Panel */}
        <div className={cx("surface-panel queue-panel", selected && "mobile-hide-when-detail-open")}>
          {/* Header */}
          <div className="section-header">
            <div>
              <p className="eyebrow">DISCREPANCY RESOLUTION</p>
              <h2>Confirmed Discrepancies</h2>
            </div>
            <div className="queue-header-right" style={{ flexDirection: "row", alignItems: "center", gap: "8px" }}>
              <button
                className="icon-button"
                onClick={onRefresh}
                type="button"
                aria-label="Refresh discrepancies"
                title="Refresh discrepancies list"
                style={{ width: "32px", height: "32px" }}
              >
                <RefreshCw size={13} />
              </button>
              <span className="total-pill">{countLabel}</span>
            </div>
          </div>

          {/* Filters Toolbar */}
          <div className="review-filters" aria-label="Discrepancy filters">
            <div className="review-filters-row-1">
              <label>
                <Search size={16} />
                <input
                  aria-label="Search discrepancies"
                  placeholder="Search subject, sender, ID…"
                  value={filters.search || ""}
                  onChange={(e) => onFilterChange({ ...filters, search: e.target.value, skip: 0 })}
                />
                {filters.search && (
                  <button
                    type="button"
                    className="search-clear-btn"
                    onClick={() => onFilterChange({ ...filters, search: "", skip: 0 })}
                    style={{ border: 0, background: "transparent", cursor: "pointer", color: "var(--color-grey-500)", padding: 0 }}
                    aria-label="Clear search"
                  >
                    <X size={13} />
                  </button>
                )}
              </label>

              {/* Status Segmented Pill Tabs */}
              <div className="review-view-switch" role="tablist" aria-label="Status filter">
                {[
                  { label: "All", value: "" },
                  { label: "Open", value: "OPEN", count: openCount },
                  { label: "Acknowledged", value: "ACKNOWLEDGED", count: acknowledgedCount },
                  { label: "Resolved", value: "RESOLVED", count: resolvedCount },
                ].map((pill) => (
                  <button
                    key={pill.value}
                    type="button"
                    role="tab"
                    aria-selected={(filters.status || "") === pill.value}
                    className={cx((filters.status || "") === pill.value && "active")}
                    onClick={() =>
                      onFilterChange({
                        ...filters,
                        status: pill.value as DiscrepancyStatus | "",
                        skip: 0,
                      })
                    }
                  >
                    {pill.label}
                    {typeof pill.count === "number" && pill.count > 0 ? (
                      <span className="filter-pill-count" style={{ marginLeft: "4px", fontSize: "10px", opacity: 0.85 }}>
                        ({pill.count})
                      </span>
                    ) : null}
                  </button>
                ))}
              </div>
            </div>

            {/* Sub Filters Row */}
            <div className="review-filters-row">
              <select
                aria-label="Filter by mismatched field"
                value={fieldFilter}
                onChange={(e) => {
                  setFieldFilter(e.target.value);
                  setPageIndex(0);
                }}
              >
                <option value="">All Mismatched Fields</option>
                {canonicalFields.map((f) => (
                  <option key={f} value={f}>
                    {labelForField(f)}
                  </option>
                ))}
              </select>

              <select
                aria-label="Sort queue"
                value={sortFilter}
                onChange={(e) => setSortFilter(e.target.value as "newest" | "oldest" | "mismatches")}
              >
                <option value="newest">Newest first</option>
                <option value="oldest">Oldest first</option>
                <option value="mismatches">Most mismatches</option>
              </select>
            </div>
          </div>

          {/* List of Discrepancies */}
          {state === "loading" && !rawItems.length ? (
            <div className="skeleton-stack" aria-label="Loading discrepancy cases">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="skeleton-row" />
              ))}
            </div>
          ) : filteredItems.length === 0 ? (
            <EmptyState
              title="No discrepancies match"
              body="All checked shipping documents match reference SI or no cases match your active filter."
            />
          ) : (
            <div className="review-list" role="list">
              {pagedItems.map((item) => {
                const isSelected = selected?.discrepancy.id === item.id;
                const statusTone =
                  item.resolution_status === "OPEN"
                    ? "badge-attention"
                    : item.resolution_status === "ACKNOWLEDGED"
                    ? "badge-warn"
                    : "badge-good";

                return (
                  <article
                    key={item.id}
                    className={cx("review-card discrepancy-review-card", isSelected && "selected")}
                    onClick={() => onSelect(item.id)}
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") onSelect(item.id);
                    }}
                    role="listitem"
                  >
                    <div className="review-card-header">
                      <div>
                        <h2>{item.subject}</h2>
                        <p>{item.sender || "Unknown sender"}</p>
                        <strong className="review-reason">
                          {item.mismatched_fields.map(labelForField).join(", ")} Mismatch
                        </strong>
                        <p className="human-explanation">
                          SI is reference; Draft BL value differs for{" "}
                          <strong>{item.mismatched_fields.map(labelForField).join(", ")}</strong>.
                        </p>
                        <p className="affected-fields-summary">
                          Mismatched fields: {item.mismatched_fields.map(labelForField).join(", ")}
                        </p>
                        <p className="suggested-action-summary">
                          Next action: Inspect extraction evidence, correct field or resolve
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelect(item.id);
                        }}
                      >
                        Open Review
                      </button>
                    </div>

                    <div className="review-meta">
                      <span className="badge badge-attention" style={{ fontWeight: 700 }}>
                        {item.mismatch_count} Mismatch{item.mismatch_count > 1 ? "es" : ""}
                      </span>
                      <span className={cx("badge", statusTone)}>
                        {displayLabel(item.resolution_status)}
                      </span>
                      <span className="badge badge-neutral" style={{ fontFamily: "monospace", fontSize: "10.5px" }}>
                        {item.external_message_id}
                      </span>
                      <span className="subtle" style={{ fontSize: "11px", marginLeft: "auto" }}>
                        {formatDate(item.received_at || item.created_at)}
                      </span>
                    </div>
                  </article>
                );
              })}
            </div>
          )}

          {/* Left List Pagination */}
          {filteredItems.length > pageSize && (
            <div className="pagination" style={{ marginTop: "16px" }}>
              <span className="pagination-info">
                Showing {safePage * pageSize + 1}–{Math.min(filteredItems.length, (safePage + 1) * pageSize)} of {filteredItems.length}
              </span>
              <div className="pagination-nav">
                <button
                  className="pagination-btn pagination-btn-nav"
                  disabled={safePage === 0}
                  onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
                  type="button"
                >
                  ‹ Previous
                </button>
                <span className="pagination-ellipsis" style={{ padding: "0 8px", fontSize: "12px" }}>
                  Page {safePage + 1} of {totalPages}
                </span>
                <button
                  className="pagination-btn pagination-btn-nav"
                  disabled={safePage >= totalPages - 1}
                  onClick={() => setPageIndex((p) => Math.min(totalPages - 1, p + 1))}
                  type="button"
                >
                  Next ›
                </button>
              </div>
            </div>
          )}
        </div>

        {/* RIGHT COLUMN: Discrepancy Detail Workspace */}
        <div className={cx("detail-panel-wrapper", !selected && "mobile-hide-when-no-detail")}>
          <div className={cx("surface-panel detail-panel", !selected && "detail-panel-empty")}>
            {!selected ? (
              <EmptyState
                title="Select a discrepancy"
                body="Open a confirmed discrepancy case to inspect field differences, review extraction evidence, acknowledge, or apply corrections."
              />
            ) : (
              <div className="discrepancy-detail-inner">
                {/* Mobile Back to List Button */}
                <div className="mobile-detail-nav-row">
                  <button
                    type="button"
                    className="mobile-back-to-list-btn"
                    onClick={() => {
                      if (onDeselect) onDeselect();
                    }}
                  >
                    ‹ Back to Discrepancies Queue
                  </button>
                </div>

                {/* Detail Header */}
                <div className="detail-title">
                  <div className="detail-header-top">
                    <p className="eyebrow" style={{ margin: 0 }}>DISCREPANCY INSPECTOR</p>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      {onDeselect && (
                        <button
                          type="button"
                          className="close-detail-btn"
                          onClick={onDeselect}
                          aria-label="Close discrepancy inspector"
                          title="Close discrepancy inspector"
                        >
                          <X size={15} />
                        </button>
                      )}
                    </div>
                  </div>

                  <h2>{selected.discrepancy.subject}</h2>
                  <p>
                    <strong>From:</strong> {selected.discrepancy.sender || "Unknown sender"} · <strong>Received:</strong> {formatDate(selected.discrepancy.received_at || selected.discrepancy.created_at)}
                  </p>

                  <div className="detail-badge-row">
                    <span className="badge badge-neutral" style={{ fontFamily: "monospace", fontSize: "11px" }}>
                      {selected.discrepancy.external_message_id}
                    </span>
                    <span
                      className={cx(
                        "badge",
                        selected.discrepancy.resolution_status === "OPEN"
                          ? "badge-attention"
                          : selected.discrepancy.resolution_status === "ACKNOWLEDGED"
                          ? "badge-warn"
                          : "badge-good"
                      )}
                      style={{ fontWeight: 700 }}
                    >
                      {displayLabel(selected.discrepancy.resolution_status)}
                    </span>
                    <span className="badge badge-attention" style={{ fontWeight: 700 }}>
                      {selected.discrepancy.mismatch_count} Mismatched Field{selected.discrepancy.mismatch_count > 1 ? "s" : ""}
                    </span>
                  </div>

                  {/* Primary Action Buttons */}
                  <div className="detail-actions" style={{ marginTop: "12px" }}>
                    {selected.discrepancy.resolution_status === "OPEN" && (
                      <button
                        type="button"
                        className="button-primary"
                        disabled={actionState === "loading"}
                        onClick={() => onAcknowledge(selected.discrepancy.id, operatorName)}
                        title="Acknowledge this discrepancy for operational handling"
                      >
                        <Check size={13} style={{ marginRight: "4px" }} />
                        Acknowledge
                      </button>
                    )}

                    {selected.discrepancy.resolution_status !== "RESOLVED" && (
                      <button
                        type="button"
                        className="button-primary"
                        style={{ background: "var(--color-success)", borderColor: "var(--color-success)" }}
                        disabled={actionState === "loading"}
                        onClick={() => setResolveModalOpen(true)}
                        title="Mark this discrepancy as resolved"
                      >
                        <CheckCircle2 size={13} style={{ marginRight: "4px" }} />
                        Resolve
                      </button>
                    )}

                    <button
                      type="button"
                      className="button-secondary"
                      disabled={actionState === "loading"}
                      onClick={() =>
                        openCorrectionModal("BL", selected.discrepancy.mismatched_fields[0] || "consignee")
                      }
                      title="Correct field extraction and re-run comparison"
                    >
                      <FileEdit size={13} style={{ marginRight: "4px" }} />
                      Correct Field
                    </button>

                    <button
                      type="button"
                      className="button-secondary"
                      onClick={() => onOpenEmailInQueue(selected.email.id)}
                      title="View in Email Queue"
                      aria-label="View in Email Queue"
                    >
                      <ExternalLink size={13} style={{ marginRight: "4px" }} />
                      Email Queue
                    </button>
                  </div>
                </div>

                {/* Sub-nav Tab Buttons */}
                <div
                  className="detail-tabs-row"
                  style={{
                    display: "flex",
                    gap: "6px",
                    marginTop: "16px",
                    borderBottom: "1px solid var(--color-grey-200)",
                    paddingBottom: "0",
                  }}
                >
                  <button
                    type="button"
                    className={cx("detail-tab-btn", activeTab === "differences" && "active")}
                    onClick={() => setActiveTab("differences")}
                  >
                    Differences & Comparison
                  </button>
                  <button
                    type="button"
                    className={cx("detail-tab-btn", activeTab === "documents" && "active")}
                    onClick={() => setActiveTab("documents")}
                  >
                    Attachments & Docs ({selected.documents?.length || selected.attachments?.length || 0})
                  </button>
                  <button
                    type="button"
                    className={cx("detail-tab-btn", activeTab === "history" && "active")}
                    onClick={() => setActiveTab("history")}
                  >
                    Audit Trail ({selected.overrides?.length || 0})
                  </button>
                </div>

                {/* TAB 1: DIFFERENCES & COMPARISON */}
                {activeTab === "differences" && (
                  <div className="discrepancy-tab-pane" style={{ marginTop: "14px" }}>
                    {/* Confirmed Differences */}
                    <div className="detail-section">
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                        <div>
                          <h3 style={{ fontSize: "14.5px", fontWeight: 700, margin: 0, display: "flex", alignItems: "center", gap: "6px" }}>
                            <AlertTriangle size={16} color="var(--color-review)" />
                            Confirmed Differences ({selected.mismatched_fields_detail.length})
                          </h3>
                          <p style={{ fontSize: "11.5px", color: "var(--color-grey-500)", margin: "2px 0 0" }}>
                            SI is authoritative reference document; BL values differ.
                          </p>
                        </div>
                      </div>

                      <div className="discrepancy-diff-grid" style={{ display: "grid", gap: "10px" }}>
                        {selected.mismatched_fields_detail.map((diff) => (
                          <div
                            key={diff.field}
                            className="discrepancy-diff-card is-mismatch"
                          >
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px", flexWrap: "wrap", gap: "6px" }}>
                              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                                <strong style={{ fontSize: "13.5px", color: "var(--color-black)" }}>
                                  {labelForField(diff.field)}
                                </strong>
                                <span className="badge badge-attention" style={{ fontSize: "10px" }}>
                                  {reasonLabels[diff.reason_code] || displayLabel(diff.reason_code)}
                                </span>
                              </div>
                              <div style={{ display: "flex", gap: "6px" }}>
                                <button
                                  type="button"
                                  className="button-secondary"
                                  style={{ fontSize: "11px", padding: "3px 8px" }}
                                  onClick={() =>
                                    openCorrectionModal("BL", String(diff.field), String(diff.bl.canonical ?? diff.bl.raw ?? ""))
                                  }
                                >
                                  Correct BL
                                </button>
                                <button
                                  type="button"
                                  className="button-secondary"
                                  style={{ fontSize: "11px", padding: "3px 8px" }}
                                  onClick={() =>
                                    openCorrectionModal("SI", String(diff.field), String(diff.si.canonical ?? diff.si.raw ?? ""))
                                  }
                                >
                                  Correct SI
                                </button>
                              </div>
                            </div>

                            {/* Side by side comparison cards */}
                            <div className="diff-side-by-side">
                              {/* SI Box */}
                              <div className="diff-box si-side">
                                <div className="diff-box-label">
                                  SI (Reference Document)
                                </div>
                                <div className="diff-box-value">
                                  {displayValue(diff.si.canonical ?? diff.si.normalized ?? diff.si.raw)}
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
                                  {displayValue(diff.bl.canonical ?? diff.bl.normalized ?? diff.bl.raw)}
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
                    </div>

                    {/* Complete 7 Canonical Fields Table Toggle */}
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

                      {showAllFields && (
                        <div style={{ marginTop: "10px", overflowX: "auto" }}>
                          <table className="review-fields-table" style={{ width: "100%", fontSize: "12px", borderCollapse: "collapse" }}>
                            <thead>
                              <tr style={{ background: "var(--color-grey-100)", textAlign: "left" }}>
                                <th style={{ padding: "8px 10px" }}>Canonical Field</th>
                                <th style={{ padding: "8px 10px" }}>Status</th>
                                <th style={{ padding: "8px 10px" }}>SI Value (Ref)</th>
                                <th style={{ padding: "8px 10px" }}>BL Value</th>
                                <th style={{ padding: "8px 10px" }}>Reason / Mapping</th>
                              </tr>
                            </thead>
                            <tbody>
                              {selected.comparison.fields.map((f) => (
                                <tr
                                  key={f.field}
                                  style={{
                                    borderBottom: "1px solid var(--color-grey-200)",
                                    background:
                                      f.status === "MISMATCH"
                                        ? "rgba(227, 148, 57, 0.08)"
                                        : f.status === "MATCH"
                                        ? "rgba(34, 197, 94, 0.02)"
                                        : "transparent",
                                  }}
                                >
                                  <td style={{ padding: "8px 10px", fontWeight: 650 }}>{labelForField(f.field)}</td>
                                  <td style={{ padding: "8px 10px" }}>
                                    <span
                                      className={cx(
                                        "badge",
                                        f.status === "MATCH"
                                          ? "badge-good"
                                          : f.status === "MISMATCH"
                                          ? "badge-attention"
                                          : "badge-warn"
                                      )}
                                      style={{ fontSize: "10px" }}
                                    >
                                      {fieldStatusLabels[f.status] || f.status}
                                    </span>
                                  </td>
                                  <td style={{ padding: "8px 10px" }}>{displayValue(f.si.canonical ?? f.si.raw)}</td>
                                  <td style={{ padding: "8px 10px" }}>{displayValue(f.bl.canonical ?? f.bl.raw)}</td>
                                  <td style={{ padding: "8px 10px", color: "var(--color-grey-600)" }}>
                                    {reasonLabels[f.reason_code] || displayLabel(f.reason_code)}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* TAB 2: ATTACHMENTS & SOURCE DOCUMENTS */}
                {activeTab === "documents" && (
                  <div className="discrepancy-tab-pane" style={{ marginTop: "14px" }}>
                    <div className="detail-section">
                      <h3 style={{ fontSize: "14px", fontWeight: 700, marginBottom: "10px" }}>
                        Source Documents ({selected.documents?.length || 0})
                      </h3>
                      {selected.documents?.length ? (
                        <div className="documents-card-list" style={{ display: "grid", gap: "8px" }}>
                          {selected.documents.map((doc) => (
                            <div
                              key={doc.id}
                              className="attachment-row document-card"
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "10px",
                                padding: "10px 12px",
                                border: "1px solid var(--color-grey-300)",
                                borderRadius: "var(--radius-md)",
                                background: "var(--color-white)",
                              }}
                            >
                              <FileText size={18} className="doc-icon" />
                              <div className="doc-info" style={{ flex: 1, minWidth: 0 }}>
                                <strong className="doc-name" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                  {doc.filename}
                                </strong>
                                <div className="doc-badges" style={{ display: "flex", gap: "6px", marginTop: "4px", flexWrap: "wrap" }}>
                                  <span className="badge badge-info">Role: {doc.role}</span>
                                  <span
                                    className={cx(
                                      "badge",
                                      doc.validation_outcome === "VALID" ? "badge-good" : "badge-warn"
                                    )}
                                  >
                                    {displayLabel(doc.validation_outcome)}
                                  </span>
                                  {doc.reader_used && (
                                    <span className="badge badge-neutral">Reader: {doc.reader_used}</span>
                                  )}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p style={{ color: "var(--color-grey-500)", fontSize: "12px" }}>No document records available.</p>
                      )}
                    </div>

                    {/* Email Body Excerpt */}
                    <div className="detail-section" style={{ marginTop: "16px" }}>
                      <h3 style={{ fontSize: "14px", fontWeight: 700, marginBottom: "8px" }}>Original Email Body</h3>
                      <div
                        style={{
                          background: "var(--color-grey-100)",
                          border: "1px solid var(--color-grey-300)",
                          borderRadius: "var(--radius-md)",
                          padding: "12px 14px",
                          fontSize: "12px",
                          lineHeight: "1.5",
                          whiteSpace: "pre-wrap",
                          fontFamily: "var(--font-mono, monospace)",
                          maxHeight: "260px",
                          overflowY: "auto",
                        }}
                      >
                        {selected.email_body || "No email body text available."}
                      </div>
                    </div>
                  </div>
                )}

                {/* TAB 3: AUDIT TRAIL & OVERRIDES */}
                {activeTab === "history" && (
                  <div className="discrepancy-tab-pane" style={{ marginTop: "14px" }}>
                    <div className="detail-section">
                      <h3 style={{ fontSize: "14px", fontWeight: 700, marginBottom: "8px" }}>
                        Field Extraction Overrides ({selected.overrides?.length || 0})
                      </h3>
                      {selected.overrides?.length ? (
                        <div style={{ display: "grid", gap: "8px" }}>
                          {selected.overrides.map((ov) => (
                            <div
                              key={ov.id}
                              style={{
                                border: "1px solid var(--color-grey-300)",
                                borderRadius: "var(--radius-md)",
                                padding: "10px 12px",
                                background: "var(--color-white)",
                              }}
                            >
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "6px" }}>
                                <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                                  <span className="badge badge-info">{ov.document_side}</span>
                                  <strong>{labelForField(ov.field_name)}</strong>
                                  <ArrowRight size={12} color="var(--color-grey-400)" />
                                  <span style={{ fontWeight: 600, color: "var(--color-success)" }}>
                                    {displayValue(ov.corrected_value)}
                                  </span>
                                </div>
                                <span style={{ fontSize: "11px", color: "var(--color-grey-500)" }}>
                                  {formatDate(ov.created_at)}
                                </span>
                              </div>
                              {ov.note && (
                                <div style={{ fontSize: "11px", color: "var(--color-grey-600)", marginTop: "4px" }}>
                                  <strong>Note:</strong> {ov.note}
                                </div>
                              )}
                              {ov.reviewer_name && (
                                <div style={{ fontSize: "10.5px", color: "var(--color-grey-500)", marginTop: "2px" }}>
                                  By: {ov.reviewer_name}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p style={{ color: "var(--color-grey-500)", fontSize: "12px" }}>
                          No overrides have been applied to this discrepancy.
                        </p>
                      )}
                    </div>

                    <div className="detail-section" style={{ marginTop: "16px" }}>
                      <h3 style={{ fontSize: "14px", fontWeight: 700, marginBottom: "8px" }}>Operational State</h3>
                      <div
                        style={{
                          border: "1px solid var(--color-grey-300)",
                          borderRadius: "var(--radius-md)",
                          padding: "12px 14px",
                          background: "var(--color-white)",
                          fontSize: "12px",
                          lineHeight: "1.6",
                        }}
                      >
                        <div>
                          <strong>Resolution Status:</strong>{" "}
                          <span className="badge badge-neutral">{displayLabel(selected.discrepancy.resolution_status)}</span>
                        </div>
                        {selected.discrepancy.acknowledged_at && (
                          <div>
                            <strong>Acknowledged:</strong> {formatDate(selected.discrepancy.acknowledged_at)} by{" "}
                            <code>{selected.discrepancy.acknowledged_by || "Operator"}</code>
                          </div>
                        )}
                        {selected.discrepancy.resolved_at && (
                          <div>
                            <strong>Resolved:</strong> {formatDate(selected.discrepancy.resolved_at)} by{" "}
                            <code>{selected.discrepancy.resolved_by || "Operator"}</code>
                          </div>
                        )}
                        {selected.discrepancy.resolution_notes && (
                          <div style={{ marginTop: "4px" }}>
                            <strong>Resolution Note:</strong> {selected.discrepancy.resolution_notes}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </section>

      {/* 3. FIELD CORRECTION MODAL */}
      {overrideModalOpen && (
        <div className="modal-backdrop" onClick={() => setOverrideModalOpen(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <p className="eyebrow" style={{ margin: 0 }}>DOCUMENT FIELD OVERRIDE</p>
                <h3>Correct Field Extraction & Recompare</h3>
              </div>
              <button
                type="button"
                className="close-detail-btn"
                onClick={() => setOverrideModalOpen(false)}
                aria-label="Close modal"
              >
                <X size={15} />
              </button>
            </div>

            <form onSubmit={handleOverrideSubmit}>
              <div className="modal-body" style={{ display: "grid", gap: "12px" }}>
                <div className="form-info-box">
                  <AlertCircle size={15} color="var(--color-orange-600)" />
                  <span>
                    Overrides will update the field value for comparison and re-run verification deterministically.
                  </span>
                </div>

                <div className="modal-two-col">
                  <div>
                    <label style={{ display: "block", fontSize: "11.5px", fontWeight: 650, marginBottom: "4px" }}>
                      Document Side
                    </label>
                    <select
                      value={overrideSide}
                      onChange={(e) => setOverrideSide(e.target.value as "SI" | "BL")}
                      style={{ width: "100%", padding: "6px 8px", fontSize: "12px" }}
                    >
                      <option value="BL">Draft BL (Checked Doc)</option>
                      <option value="SI">SI (Reference)</option>
                    </select>
                  </div>

                  <div>
                    <label style={{ display: "block", fontSize: "11.5px", fontWeight: 650, marginBottom: "4px" }}>
                      Canonical Field
                    </label>
                    <select
                      value={overrideField}
                      onChange={(e) => setOverrideField(e.target.value)}
                      style={{ width: "100%", padding: "6px 8px", fontSize: "12px" }}
                    >
                      {canonicalFields.map((f) => (
                        <option key={f} value={f}>
                          {labelForField(f)}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "11.5px", fontWeight: 650, marginBottom: "4px" }}>
                    Corrected Value
                  </label>
                  <input
                    type="text"
                    required
                    value={overrideValue}
                    onChange={(e) => setOverrideValue(e.target.value)}
                    placeholder="Enter correct field value as shown in document"
                    style={{ width: "100%", padding: "7px 10px", fontSize: "12px" }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "11.5px", fontWeight: 650, marginBottom: "4px" }}>
                    Operator / Reviewer Name
                  </label>
                  <input
                    type="text"
                    value={operatorName}
                    onChange={(e) => setOperatorName(e.target.value)}
                    style={{ width: "100%", padding: "7px 10px", fontSize: "12px" }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "11.5px", fontWeight: 650, marginBottom: "4px" }}>
                    Audit Note (Optional)
                  </label>
                  <textarea
                    rows={2}
                    value={overrideNote}
                    onChange={(e) => setOverrideNote(e.target.value)}
                    placeholder="e.g. OCR misread letter O as 0"
                    style={{ width: "100%", padding: "7px 10px", fontSize: "12px", fontFamily: "inherit" }}
                  />
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="button-secondary"
                  onClick={() => setOverrideModalOpen(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="button-primary"
                  disabled={actionState === "loading" || !overrideValue.trim()}
                >
                  {actionState === "loading" ? "Saving & Recomparing…" : "Apply & Recompare"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 4. RESOLVE DISCREPANCY MODAL */}
      {resolveModalOpen && (
        <div className="modal-backdrop" onClick={() => setResolveModalOpen(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <p className="eyebrow" style={{ margin: 0 }}>RESOLVE DISCREPANCY</p>
                <h3>Mark Case as Resolved</h3>
              </div>
              <button
                type="button"
                className="close-detail-btn"
                onClick={() => setResolveModalOpen(false)}
                aria-label="Close modal"
              >
                <X size={15} />
              </button>
            </div>

            <form onSubmit={handleResolveSubmit}>
              <div className="modal-body" style={{ display: "grid", gap: "12px" }}>
                <p style={{ fontSize: "12.5px", color: "var(--color-grey-700)", margin: 0 }}>
                  Marking this discrepancy as <strong>RESOLVED</strong> confirms that differences have been settled,
                  revised documents received, or commercial approval granted.
                </p>

                <div>
                  <label style={{ display: "block", fontSize: "11.5px", fontWeight: 650, marginBottom: "4px" }}>
                    Operator Name
                  </label>
                  <input
                    type="text"
                    value={operatorName}
                    onChange={(e) => setOperatorName(e.target.value)}
                    style={{ width: "100%", padding: "7px 10px", fontSize: "12px" }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "11.5px", fontWeight: 650, marginBottom: "4px" }}>
                    Resolution Notes (Optional)
                  </label>
                  <textarea
                    rows={3}
                    value={resolveNotes}
                    onChange={(e) => setResolveNotes(e.target.value)}
                    placeholder="e.g. Carrier confirmed revised draft BL matches SI specifications"
                    style={{ width: "100%", padding: "7px 10px", fontSize: "12px", fontFamily: "inherit" }}
                  />
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="button-secondary"
                  onClick={() => setResolveModalOpen(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="button-primary"
                  style={{ background: "var(--color-success)", borderColor: "var(--color-success)" }}
                  disabled={actionState === "loading"}
                >
                  {actionState === "loading" ? "Resolving…" : "Confirm Resolution"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </section>
  );
}
