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
  Eye,
  FileCheck2,
  FileEdit,
  FileText,
  Filter,
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
  ProductFieldComparison,
} from "../../api/types";
import { canonicalFields } from "../../api/types";
import {
  categoryLabels,
  displayLabel,
  displayValue,
  fieldStatusLabels,
  formatDate,
  labelForField,
  reasonLabels,
  semanticTone,
} from "../../lib/labels";

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
}: ConfirmedDiscrepanciesPageViewProps) {
  const [operatorName, setOperatorName] = useState("Demo Reviewer");
  const [showAllFields, setShowAllFields] = useState(false);
  const [activeTab, setActiveTab] = useState<"differences" | "documents" | "history">("differences");

  // Correction Modal State
  const [overrideModalOpen, setOverrideModalOpen] = useState(false);
  const [overrideSide, setOverrideSide] = useState<"SI" | "BL">("BL");
  const [overrideField, setOverrideField] = useState<string>("consignee");
  const [overrideValue, setOverrideValue] = useState<string>("");
  const [overrideNote, setOverrideNote] = useState<string>("");

  // Resolve Modal State
  const [resolveModalOpen, setResolveModalOpen] = useState(false);
  const [resolveNotes, setResolveNotes] = useState<string>("");

  const items = discrepancies?.items ?? [];
  const total = discrepancies?.total ?? 0;
  const skip = filters.skip ?? 0;
  const limit = filters.limit ?? 20;

  // Pagination for left list (5 items per page in view)
  const [pageIndex, setPageIndex] = useState(0);
  const pageSize = 5;
  const totalPages = Math.ceil(items.length / pageSize) || 1;
  const pagedItems = useMemo(
    () => items.slice(pageIndex * pageSize, (pageIndex + 1) * pageSize),
    [items, pageIndex],
  );

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

  return (
    <div className="review-layout discrepancies-layout">
      {/* LEFT COLUMN: Discrepancy Queue List */}
      <div className="review-left-pane">
        <div className="review-list-header">
          <div className="review-list-title-row">
            <div>
              <p className="eyebrow" style={{ margin: 0 }}>CONFIRMED MISMATCHES</p>
              <h2 className="section-title" style={{ margin: "2px 0 0", fontSize: "16px" }}>
                Discrepancies
              </h2>
            </div>
            <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
              <span className="badge badge-bad" style={{ fontWeight: 700 }}>
                {total} cases
              </span>
              <button
                className="icon-button"
                onClick={onRefresh}
                type="button"
                aria-label="Refresh discrepancies"
                title="Refresh discrepancies"
              >
                <RefreshCw size={13} />
              </button>
            </div>
          </div>

          {/* Search */}
          <div className="search-bar" style={{ marginTop: "10px" }}>
            <Search size={14} className="search-icon" />
            <input
              type="text"
              placeholder="Search subject, sender, ID…"
              value={filters.search || ""}
              onChange={(e) => onFilterChange({ ...filters, search: e.target.value, skip: 0 })}
            />
            {filters.search && (
              <button
                type="button"
                className="search-clear-btn"
                onClick={() => onFilterChange({ ...filters, search: "", skip: 0 })}
              >
                <X size={12} />
              </button>
            )}
          </div>

          {/* Status Filter Pills */}
          <div className="filter-pill-row" style={{ marginTop: "8px", display: "flex", gap: "4px", flexWrap: "wrap" }}>
            {[
              { label: "All", value: "" },
              { label: "Open", value: "OPEN", count: discrepancies?.open_count },
              { label: "Acknowledged", value: "ACKNOWLEDGED", count: discrepancies?.acknowledged_count },
              { label: "Resolved", value: "RESOLVED", count: discrepancies?.resolved_count },
            ].map((pill) => (
              <button
                key={pill.value}
                type="button"
                className={cx(
                  "filter-pill",
                  (filters.status || "") === pill.value && "active",
                )}
                onClick={() =>
                  onFilterChange({
                    ...filters,
                    status: pill.value as DiscrepancyStatus | "",
                    skip: 0,
                  })
                }
                style={{ fontSize: "11px", padding: "3px 8px" }}
              >
                {pill.label}
                {typeof pill.count === "number" && pill.count > 0 ? (
                  <span className="filter-pill-count">{pill.count}</span>
                ) : null}
              </button>
            ))}
          </div>
        </div>

        {/* List Items */}
        <div className="review-list" role="list">
          {state === "loading" && !items.length ? (
            <div className="loading-state" style={{ padding: "30px 16px", textAlign: "center" }}>
              <RefreshCw size={18} className="spin" style={{ margin: "0 auto 8px" }} />
              <p>Loading discrepancy cases…</p>
            </div>
          ) : items.length === 0 ? (
            <div className="empty-state" style={{ padding: "32px 16px", textAlign: "center" }}>
              <CheckCircle2 size={24} color="var(--color-success)" style={{ margin: "0 auto 8px" }} />
              <strong>No discrepancies match</strong>
              <p style={{ fontSize: "12px", color: "var(--color-grey-500)", marginTop: "4px" }}>
                All checked documents match or no cases match your filter.
              </p>
            </div>
          ) : (
            pagedItems.map((item) => {
              const isSelected = selected?.discrepancy.id === item.id;
              const statusTone =
                item.resolution_status === "OPEN"
                  ? "badge-bad"
                  : item.resolution_status === "ACKNOWLEDGED"
                    ? "badge-info"
                    : "badge-good";

              return (
                <div
                  key={item.id}
                  role="listitem"
                  className={cx(
                    "review-list-item",
                    isSelected && "selected",
                  )}
                  onClick={() => onSelect(item.id)}
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") onSelect(item.id);
                  }}
                >
                  <div className="review-item-header">
                    <span className="review-item-ref">{item.external_message_id}</span>
                    <span className={cx("badge", statusTone)} style={{ fontSize: "10px" }}>
                      {displayLabel(item.resolution_status)}
                    </span>
                  </div>

                  <strong className="review-item-subject" title={item.subject}>
                    {item.subject}
                  </strong>

                  <div className="review-item-sender" title={item.sender || ""}>
                    {item.sender || "Unknown sender"}
                  </div>

                  <div className="review-item-footer" style={{ marginTop: "6px" }}>
                    <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                      {item.mismatched_fields.map((f) => (
                        <span key={f} className="badge badge-bad" style={{ fontSize: "10px", padding: "1px 5px" }}>
                          {labelForField(f)}
                        </span>
                      ))}
                    </div>
                    <span className="review-item-date">{formatDate(item.received_at || item.created_at)}</span>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Left List Pagination */}
        {items.length > pageSize && (
          <div className="review-list-pagination" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 12px", borderTop: "1px solid var(--color-grey-200)" }}>
            <span style={{ fontSize: "11px", color: "var(--color-grey-500)" }}>
              Page {pageIndex + 1} of {totalPages}
            </span>
            <div style={{ display: "flex", gap: "4px" }}>
              <button
                type="button"
                className="icon-button"
                disabled={pageIndex === 0}
                onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
                aria-label="Previous discrepancy page"
              >
                <ChevronLeft size={14} />
              </button>
              <button
                type="button"
                className="icon-button"
                disabled={pageIndex >= totalPages - 1}
                onClick={() => setPageIndex((p) => Math.min(totalPages - 1, p + 1))}
                aria-label="Next discrepancy page"
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* RIGHT COLUMN: Discrepancy Detail Workspace */}
      <div className="review-right-pane">
        {!selected ? (
          <div className="review-empty-detail" style={{ padding: "60px 20px", textAlign: "center" }}>
            <AlertTriangle size={36} color="var(--color-grey-400)" style={{ margin: "0 auto 12px" }} />
            <h3>Select a discrepancy case</h3>
            <p style={{ color: "var(--color-grey-500)", maxWidth: "360px", margin: "6px auto 0" }}>
              Choose a case from the list on the left to review differences, inspect extraction evidence, acknowledge, or apply corrections.
            </p>
          </div>
        ) : (
          <div className="review-detail-content">
            {/* Detail Top Header */}
            <div className="review-detail-header-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "12px" }}>
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap", marginBottom: "4px" }}>
                    <span className="badge badge-neutral" style={{ fontFamily: "monospace", fontSize: "11px" }}>
                      {selected.discrepancy.external_message_id}
                    </span>
                    <span
                      className={cx(
                        "badge",
                        selected.discrepancy.resolution_status === "OPEN"
                          ? "badge-bad"
                          : selected.discrepancy.resolution_status === "ACKNOWLEDGED"
                            ? "badge-info"
                            : "badge-good",
                      )}
                      style={{ fontWeight: 650 }}
                    >
                      {displayLabel(selected.discrepancy.resolution_status)}
                    </span>
                    <span className="badge badge-bad">
                      {selected.discrepancy.mismatch_count} Mismatched Field{selected.discrepancy.mismatch_count > 1 ? "s" : ""}
                    </span>
                  </div>
                  <h2 style={{ fontSize: "18px", fontWeight: 700, margin: "4px 0 6px", color: "var(--color-black)" }}>
                    {selected.discrepancy.subject}
                  </h2>
                  <div style={{ fontSize: "12px", color: "var(--color-grey-600)", display: "flex", gap: "16px", flexWrap: "wrap" }}>
                    <span><strong>From:</strong> {selected.discrepancy.sender || "Unknown sender"}</span>
                    <span><strong>Received:</strong> {formatDate(selected.discrepancy.received_at || selected.discrepancy.created_at)}</span>
                  </div>
                </div>

                {/* Primary Action Buttons */}
                <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", alignItems: "center" }}>
                  {selected.discrepancy.resolution_status === "OPEN" && (
                    <button
                      type="button"
                      className="button-primary"
                      style={{ background: "#2563eb", borderColor: "#2563eb", fontSize: "12px", padding: "6px 12px" }}
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
                      style={{ background: "var(--color-success)", borderColor: "var(--color-success)", fontSize: "12px", padding: "6px 12px" }}
                      disabled={actionState === "loading"}
                      onClick={() => setResolveModalOpen(true)}
                      title="Mark this confirmed discrepancy as resolved"
                    >
                      <CheckCircle2 size={13} style={{ marginRight: "4px" }} />
                      Resolve
                    </button>
                  )}

                  <button
                    type="button"
                    className="button-secondary"
                    style={{ fontSize: "12px", padding: "6px 12px" }}
                    disabled={actionState === "loading"}
                    onClick={() => openCorrectionModal("BL", selected.discrepancy.mismatched_fields[0] || "consignee")}
                    title="Correct field extraction and re-run comparison"
                  >
                    <FileEdit size={13} style={{ marginRight: "4px" }} />
                    Correct Field
                  </button>

                  <button
                    type="button"
                    className="icon-button"
                    style={{ padding: "6px" }}
                    onClick={() => onOpenEmailInQueue(selected.email.id)}
                    title="View in Email Queue"
                    aria-label="View in Email Queue"
                  >
                    <ExternalLink size={14} />
                  </button>
                </div>
              </div>

              {/* Sub-nav tabs */}
              <div className="detail-tabs-row" style={{ display: "flex", gap: "8px", marginTop: "16px", borderBottom: "1px solid var(--color-grey-200)", paddingBottom: "0" }}>
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
                  Attachments & Documents ({selected.documents?.length || selected.attachments?.length || 0})
                </button>
                <button
                  type="button"
                  className={cx("detail-tab-btn", activeTab === "history" && "active")}
                  onClick={() => setActiveTab("history")}
                >
                  Audit Trail & Overrides ({selected.overrides?.length || 0})
                </button>
              </div>
            </div>

            {/* TAB 1: DIFFERENCES & COMPARISON */}
            {activeTab === "differences" && (
              <div className="discrepancy-tab-pane">
                {/* SECTION 1: DIFFERENCES-FIRST SUMMARY CARDS */}
                <div className="detail-section" style={{ marginTop: "16px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                    <div>
                      <h3 style={{ fontSize: "15px", fontWeight: 700, margin: 0, display: "flex", alignItems: "center", gap: "6px" }}>
                        <AlertTriangle size={16} color="var(--color-danger)" />
                        Confirmed Differences ({selected.mismatched_fields_detail.length})
                      </h3>
                      <p style={{ fontSize: "12px", color: "var(--color-grey-500)", margin: "2px 0 0" }}>
                        SI is authoritative reference; BL values differ from SI.
                      </p>
                    </div>
                  </div>

                  <div className="discrepancy-diff-grid" style={{ display: "grid", gap: "12px" }}>
                    {selected.mismatched_fields_detail.map((diff) => (
                      <div
                        key={diff.field}
                        className="discrepancy-diff-card"
                        style={{
                          border: "1px solid var(--color-grey-300)",
                          borderRadius: "var(--radius-md)",
                          background: "var(--color-white)",
                          padding: "14px 16px",
                          boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <strong style={{ fontSize: "14px", color: "var(--color-black)" }}>
                              {labelForField(diff.field)}
                            </strong>
                            <span className="badge badge-bad" style={{ fontSize: "10px" }}>
                              {reasonLabels[diff.reason_code] || displayLabel(diff.reason_code)}
                            </span>
                          </div>
                          <div style={{ display: "flex", gap: "6px" }}>
                            <button
                              type="button"
                              className="button-secondary"
                              style={{ fontSize: "11px", padding: "3px 8px" }}
                              onClick={() => openCorrectionModal("BL", String(diff.field), String(diff.bl.canonical ?? diff.bl.raw ?? ""))}
                            >
                              Correct BL
                            </button>
                            <button
                              type="button"
                              className="button-secondary"
                              style={{ fontSize: "11px", padding: "3px 8px" }}
                              onClick={() => openCorrectionModal("SI", String(diff.field), String(diff.si.canonical ?? diff.si.raw ?? ""))}
                            >
                              Correct SI
                            </button>
                          </div>
                        </div>

                        {/* Side by side comparison */}
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                          {/* SI Box */}
                          <div
                            style={{
                              background: "#f0fdf4",
                              border: "1px solid #bbf7d0",
                              borderRadius: "var(--radius-sm)",
                              padding: "10px 12px",
                            }}
                          >
                            <div style={{ fontSize: "10px", fontWeight: 700, color: "#166534", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "4px" }}>
                              SI (Reference)
                            </div>
                            <div style={{ fontSize: "14px", fontWeight: 600, color: "#14532d", wordBreak: "break-word" }}>
                              {displayValue(diff.si.canonical ?? diff.si.normalized ?? diff.si.raw)}
                            </div>
                            {diff.si.raw !== undefined && diff.si.raw !== diff.si.canonical && (
                              <div style={{ fontSize: "11px", color: "#166534", marginTop: "4px", opacity: 0.8 }}>
                                Raw: <code>{displayValue(diff.si.raw)}</code>
                              </div>
                            )}
                          </div>

                          {/* BL Box */}
                          <div
                            style={{
                              background: "#fef2f2",
                              border: "1px solid #fecaca",
                              borderRadius: "var(--radius-sm)",
                              padding: "10px 12px",
                            }}
                          >
                            <div style={{ fontSize: "10px", fontWeight: 700, color: "#991b1b", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: "4px" }}>
                              Draft BL (Document Checked)
                            </div>
                            <div style={{ fontSize: "14px", fontWeight: 600, color: "#7f1d1d", wordBreak: "break-word" }}>
                              {displayValue(diff.bl.canonical ?? diff.bl.normalized ?? diff.bl.raw)}
                            </div>
                            {diff.bl.raw !== undefined && diff.bl.raw !== diff.bl.canonical && (
                              <div style={{ fontSize: "11px", color: "#991b1b", marginTop: "4px", opacity: 0.8 }}>
                                Raw: <code>{displayValue(diff.bl.raw)}</code>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* SECTION 2: SHOW ALL 7 CANONICAL FIELDS TOGGLE */}
                <div className="detail-section" style={{ marginTop: "20px" }}>
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
                      fontSize: "13px",
                      fontWeight: 600,
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
                    <div style={{ marginTop: "12px", overflowX: "auto" }}>
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
                                    ? "rgba(239, 68, 68, 0.04)"
                                    : f.status === "MATCH"
                                      ? "rgba(34, 197, 94, 0.02)"
                                      : "transparent",
                              }}
                            >
                              <td style={{ padding: "8px 10px", fontWeight: 600 }}>{labelForField(f.field)}</td>
                              <td style={{ padding: "8px 10px" }}>
                                <span
                                  className={cx(
                                    "badge",
                                    f.status === "MATCH"
                                      ? "badge-good"
                                      : f.status === "MISMATCH"
                                        ? "badge-bad"
                                        : "badge-warn",
                                  )}
                                  style={{ fontSize: "10px" }}
                                >
                                  {fieldStatusLabels[f.status] || f.status}
                                </span>
                              </td>
                              <td style={{ padding: "8px 10px" }}>
                                <div>{displayValue(f.si.canonical ?? f.si.raw)}</div>
                              </td>
                              <td style={{ padding: "8px 10px" }}>
                                <div>{displayValue(f.bl.canonical ?? f.bl.raw)}</div>
                              </td>
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
              <div className="discrepancy-tab-pane" style={{ marginTop: "16px" }}>
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
                          <FileText size={20} className="doc-icon" />
                          <div className="doc-info" style={{ flex: 1 }}>
                            <strong className="doc-name">{doc.filename}</strong>
                            <div className="doc-badges" style={{ display: "flex", gap: "6px", marginTop: "4px" }}>
                              <span className="badge badge-info">Role: {doc.role}</span>
                              <span
                                className={cx(
                                  "badge",
                                  doc.validation_outcome === "VALID" ? "badge-good" : "badge-warn",
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
                    }}
                  >
                    {selected.email_body || "No email body text available."}
                  </div>
                </div>
              </div>
            )}

            {/* TAB 3: AUDIT TRAIL & OVERRIDES */}
            {activeTab === "history" && (
              <div className="discrepancy-tab-pane" style={{ marginTop: "16px" }}>
                {/* Active Overrides */}
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
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
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
                            <div style={{ fontSize: "10px", color: "var(--color-grey-500)", marginTop: "2px" }}>
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

                {/* Resolution Status History */}
                <div className="detail-section" style={{ marginTop: "16px" }}>
                  <h3 style={{ fontSize: "14px", fontWeight: 700, marginBottom: "8px" }}>Operational State</h3>
                  <div
                    style={{
                      border: "1px solid var(--color-grey-300)",
                      borderRadius: "var(--radius-md)",
                      padding: "12px 14px",
                      background: "var(--color-white)",
                      fontSize: "12px",
                    }}
                  >
                    <div style={{ marginBottom: "6px" }}>
                      <strong>Status:</strong>{" "}
                      <span className="badge badge-neutral">{displayLabel(selected.discrepancy.resolution_status)}</span>
                    </div>
                    {selected.discrepancy.acknowledged_at && (
                      <div style={{ marginBottom: "4px" }}>
                        <strong>Acknowledged:</strong> {formatDate(selected.discrepancy.acknowledged_at)} by{" "}
                        <code>{selected.discrepancy.acknowledged_by || "Operator"}</code>
                      </div>
                    )}
                    {selected.discrepancy.resolved_at && (
                      <div style={{ marginBottom: "4px" }}>
                        <strong>Resolved:</strong> {formatDate(selected.discrepancy.resolved_at)} by{" "}
                        <code>{selected.discrepancy.resolved_by || "Operator"}</code>
                      </div>
                    )}
                    {selected.discrepancy.resolution_notes && (
                      <div style={{ marginTop: "6px" }}>
                        <strong>Resolution Notes:</strong>
                        <p style={{ margin: "2px 0 0", color: "var(--color-grey-700)" }}>
                          {selected.discrepancy.resolution_notes}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* MODAL 1: Field Extraction Correction Modal */}
      {overrideModalOpen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="modal-override-title">
          <div className="modal-card" style={{ maxWidth: "480px" }}>
            <div className="modal-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <h3 id="modal-override-title" style={{ fontSize: "16px", fontWeight: 700, margin: 0 }}>
                Correct Field & Recompute
              </h3>
              <button
                type="button"
                className="icon-button"
                onClick={() => setOverrideModalOpen(false)}
                aria-label="Close modal"
              >
                <X size={14} />
              </button>
            </div>

            <form onSubmit={handleOverrideSubmit}>
              <div style={{ display: "grid", gap: "10px", fontSize: "13px" }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                  <label>
                    <span style={{ fontWeight: 600, display: "block", marginBottom: "4px" }}>Document Side</span>
                    <select
                      value={overrideSide}
                      onChange={(e) => setOverrideSide(e.target.value as "SI" | "BL")}
                      style={{ width: "100%", padding: "6px 8px", borderRadius: "var(--radius-sm)", border: "1px solid var(--color-grey-300)" }}
                    >
                      <option value="BL">BL (Document Checked)</option>
                      <option value="SI">SI (Reference)</option>
                    </select>
                  </label>

                  <label>
                    <span style={{ fontWeight: 600, display: "block", marginBottom: "4px" }}>Canonical Field</span>
                    <select
                      value={overrideField}
                      onChange={(e) => setOverrideField(e.target.value)}
                      style={{ width: "100%", padding: "6px 8px", borderRadius: "var(--radius-sm)", border: "1px solid var(--color-grey-300)" }}
                    >
                      {canonicalFields.map((f) => (
                        <option key={f} value={f}>{labelForField(f)}</option>
                      ))}
                    </select>
                  </label>
                </div>

                <label>
                  <span style={{ fontWeight: 600, display: "block", marginBottom: "4px" }}>Corrected Value</span>
                  <input
                    type="text"
                    required
                    value={overrideValue}
                    onChange={(e) => setOverrideValue(e.target.value)}
                    placeholder="Enter verified correct value"
                    style={{ width: "100%", padding: "6px 8px", borderRadius: "var(--radius-sm)", border: "1px solid var(--color-grey-300)" }}
                  />
                </label>

                <label>
                  <span style={{ fontWeight: 600, display: "block", marginBottom: "4px" }}>Reviewer Name</span>
                  <input
                    type="text"
                    value={operatorName}
                    onChange={(e) => setOperatorName(e.target.value)}
                    style={{ width: "100%", padding: "6px 8px", borderRadius: "var(--radius-sm)", border: "1px solid var(--color-grey-300)" }}
                  />
                </label>

                <label>
                  <span style={{ fontWeight: 600, display: "block", marginBottom: "4px" }}>Correction Note (Evidence)</span>
                  <textarea
                    rows={2}
                    value={overrideNote}
                    onChange={(e) => setOverrideNote(e.target.value)}
                    placeholder="e.g. OCR misread consignee name on page 1"
                    style={{ width: "100%", padding: "6px 8px", borderRadius: "var(--radius-sm)", border: "1px solid var(--color-grey-300)", resize: "vertical" }}
                  />
                </label>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "16px" }}>
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
                  {actionState === "loading" ? "Recomputing…" : "Save & Recompute"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: Resolve Discrepancy Modal */}
      {resolveModalOpen && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="modal-resolve-title">
          <div className="modal-card" style={{ maxWidth: "460px" }}>
            <div className="modal-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
              <h3 id="modal-resolve-title" style={{ fontSize: "16px", fontWeight: 700, margin: 0 }}>
                Resolve Confirmed Discrepancy
              </h3>
              <button
                type="button"
                className="icon-button"
                onClick={() => setResolveModalOpen(false)}
                aria-label="Close modal"
              >
                <X size={14} />
              </button>
            </div>

            <form onSubmit={handleResolveSubmit}>
              <p style={{ fontSize: "12px", color: "var(--color-grey-600)", margin: "0 0 12px" }}>
                Marking this discrepancy as resolved acknowledges that the mismatch has been reviewed and handled operationally with the shipper or carrier.
              </p>

              <div style={{ display: "grid", gap: "10px", fontSize: "13px" }}>
                <label>
                  <span style={{ fontWeight: 600, display: "block", marginBottom: "4px" }}>Operator Name</span>
                  <input
                    type="text"
                    value={operatorName}
                    onChange={(e) => setOperatorName(e.target.value)}
                    style={{ width: "100%", padding: "6px 8px", borderRadius: "var(--radius-sm)", border: "1px solid var(--color-grey-300)" }}
                  />
                </label>

                <label>
                  <span style={{ fontWeight: 600, display: "block", marginBottom: "4px" }}>Resolution Notes</span>
                  <textarea
                    rows={3}
                    value={resolveNotes}
                    onChange={(e) => setResolveNotes(e.target.value)}
                    placeholder="e.g. Verified with shipper via email, BL amendment draft requested."
                    style={{ width: "100%", padding: "6px 8px", borderRadius: "var(--radius-sm)", border: "1px solid var(--color-grey-300)", resize: "vertical" }}
                  />
                </label>
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "16px" }}>
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
    </div>
  );
}
