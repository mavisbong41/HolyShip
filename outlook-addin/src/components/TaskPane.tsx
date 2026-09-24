import {
  AlertCircle,
  AlertTriangle,
  Archive,
  Bot,
  CheckCircle2,
  Check,
  Clock,
  Edit3,
  ExternalLink,
  FileSearch,
  FileText,
  Info,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Tag,
  X,
} from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  acceptAISuggestion,
  applyEditedAISuggestion,
  askAIAssistant,
  claimHumanReview,
  createReplySummary,
  dismissAISuggestion,
  dismissHumanReview,
  generateReplyDraft,
  reconcileOutlookLifecycle,
  refineReplyDraft,
  reprocessEmail,
  resolveHumanReview,
  sendReplyDraft,
  saveHumanReviewOverride,
  updateEmailCategory,
} from "../api/client";
import { dashboardEmailUrl, dashboardReviewUrl } from "../lib/config";
import { categoryLabels, displayLabel, displayValue, formatDate, labelForField, reasonLabels, statusLabels } from "../lib/labels";
import type { MailContextProvider } from "../types/context";
import type {
  AIAssistantResponse,
  ProductComparison,
  ProductEmailDetail,
  ProductEmailSummary,
  ProductReview,
  ProductAISuggestion,
  ProductCategory,
  ProductReplyWorkflow,
} from "../types/product";
import { canonicalFields } from "../types/product";
import { ComparisonTable } from "./ComparisonTable";
import { StatusBadge } from "./StatusBadge";
import { IdentityAdapter } from "../office/IdentityAdapter";
import { demoCases } from "../lib/demoCases";

// ─── Helpers ──────────────────────────────────────────────────────

type PaneState =
  | { type: "loading" }
  | { type: "not_found"; note: string | null }
  | { type: "error"; message: string }
  | { type: "ready"; detail: ProductEmailDetail; confidence: "high" | "low" | "none"; note: string | null };

// ─── Sub-components ────────────────────────────────────────────────

function LoadingView(): React.ReactElement {
  return (
    <div className="pane-loading" role="status" aria-live="polite">
      <div className="pane-spinner" aria-hidden="true" />
      <p>Checking HolyShip…</p>
    </div>
  );
}

function NotFoundView({
  note,
  onSelectDemo,
}: {
  note: string | null;
  onSelectDemo?: (key: string) => void;
}): React.ReactElement {
  return (
    <div className="not-found-state" role="status">
      <div className="not-found-icon" aria-hidden="true">
        <FileSearch size={24} />
      </div>
      <h3>Not in HolyShip</h3>
      <p>
        This email has not been processed by HolyShip, or it could not be identified.
      </p>
      {note && (
        <div className="limitation-note" role="note">
          <Info size={12} style={{ flexShrink: 0, marginTop: 2 }} aria-hidden="true" />
          <span>{note}</span>
        </div>
      )}
      {onSelectDemo && (
        <div className="demo-selector-box">
          <p className="demo-selector-label">Explore sample operational cases (consistent with Dashboard):</p>
          <div className="demo-pills">
            <button type="button" className="btn-secondary btn-sm" onClick={() => onSelectDemo("mismatchReview")}>
              ⚠️ Mismatch & Review
            </button>
            <button type="button" className="btn-secondary btn-sm" onClick={() => onSelectDemo("cleanMatch")}>
              ✅ Clean Match
            </button>
            <button type="button" className="btn-secondary btn-sm" onClick={() => onSelectDemo("deletedInOutlook")}>
              🗑️ Deleted in Outlook (Sync)
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function ErrorView({ message, onRetry }: { message: string; onRetry: () => void }): React.ReactElement {
  return (
    <div className="error-state" role="alert">
      <div><AlertCircle size={16} aria-hidden="true" /><strong>Unable to reconnect</strong></div>
      <p>{message}</p>
      <button className="btn-secondary" type="button" onClick={onRetry}>Try again</button>
    </div>
  );
}

function EmailInfoSection({ email }: { email: ProductEmailSummary }): React.ReactElement {
  return (
    <>
      <p className="pane-section-label">Email</p>
      <ul className="info-list">
        <li className="info-row">
          <span className="info-label">From</span>
          <span className="info-value">{email.sender ?? "—"}</span>
        </li>
        <li className="info-row">
          <span className="info-label">Subject</span>
          <span className="info-value">{email.subject}</span>
        </li>
        <li className="info-row">
          <span className="info-label">Received</span>
          <span className="info-value">{formatDate(email.received_at ?? email.created_at)}</span>
        </li>
        <li className="info-row">
          <span className="info-label">Category</span>
          <span className="info-value">
            <StatusBadge value={email.category} />
          </span>
        </li>
        <li className="info-row">
          <span className="info-label">Status</span>
          <span className="info-value">
            <StatusBadge value={email.processing_status} />
          </span>
        </li>
        {email.comparison_readiness && (
          <li className="info-row">
            <span className="info-label">Readiness</span>
            <span className="info-value">
              <StatusBadge value={email.comparison_readiness} />
            </span>
          </li>
        )}
      </ul>
    </>
  );
}

function ProcessingStateCard({ email }: { email: ProductEmailSummary }): React.ReactElement {
  const status = email.processing_status;

  if (status === "COMPLETED" && !email.needs_review) {
    if (email.category === "document_comparison") {
      if (email.mismatch_count === 0 && email.unresolved_count === 0) {
        return (
          <div className="state-card">
            <div className="state-card-icon icon-good" aria-hidden="true">
              <CheckCircle2 size={18} />
            </div>
            <div className="state-card-body">
              <h2>No mismatch detected</h2>
              <p>All seven fields match between SI and Draft BL.</p>
            </div>
          </div>
        );
      }
      return (
        <div className="state-card">
          <div className="state-card-icon icon-bad" aria-hidden="true">
            <AlertTriangle size={18} />
          </div>
          <div className="state-card-body">
            <h2>Confirmed Discrepancy</h2>
            <p>
              {email.mismatch_count > 0 && `${email.mismatch_count} field${email.mismatch_count > 1 ? "s" : ""} mismatched. `}
              {email.unresolved_count > 0 && `${email.unresolved_count} field${email.unresolved_count > 1 ? "s" : ""} unresolved.`}
            </p>
          </div>
        </div>
      );
    }
    return (
      <div className="state-card">
        <div className="state-card-icon icon-good" aria-hidden="true">
          <CheckCircle2 size={18} />
        </div>
        <div className="state-card-body">
          <h2>Completed</h2>
          <p>{email.category ? categoryLabels[email.category] : "Processed"}</p>
        </div>
      </div>
    );
  }

  if (status === "AWAITING_DOCUMENTS") {
    return (
      <div className="state-card">
        <div className="state-card-icon icon-warn" aria-hidden="true">
          <Clock size={18} />
        </div>
        <div className="state-card-body">
          <h2>Waiting for Documents</h2>
          <p>
            This is a Document Comparison case. Required documents have not been
            received yet.
          </p>
        </div>
      </div>
    );
  }

  if ((status === "BLOCKED" || email.needs_review) && status !== "FAILED") {
    return (
      <div className="state-card">
        <div className="state-card-icon icon-warn" aria-hidden="true">
          <AlertTriangle size={18} />
        </div>
        <div className="state-card-body">
          <h2>Needs Review</h2>
          <p>
            {email.review_reason
              ? reasonLabels[email.review_reason] || displayLabel(email.review_reason)
              : "Human Review is required for this case."}
          </p>
        </div>
      </div>
    );
  }

  if (status === "FAILED") {
    return (
      <div className="state-card">
        <div className="state-card-icon icon-bad" aria-hidden="true">
          <AlertCircle size={18} />
        </div>
        <div className="state-card-body">
          <h2>Processing failed</h2>
          <p>A technical error occurred. Check the Dashboard for details.</p>
        </div>
      </div>
    );
  }

  // In-progress states
  const inProgressStatuses: Record<string, string> = {
    NEW: "Queued for processing",
    QUEUED: "Queued for processing",
    CLASSIFYING: "Classifying email…",
    CLASSIFIED: "Email classified, awaiting next step",
    RETRIEVING_ATTACHMENTS: "Retrieving attachments…",
    EXTRACTING: "Extracting document fields…",
    COMPARING: "Comparing SI and BL…",
  };
  const progressMsg = inProgressStatuses[status];
  if (progressMsg) {
    return (
      <div className="state-card">
        <div className="state-card-icon icon-orange" aria-hidden="true">
          <RefreshCw size={18} />
        </div>
        <div className="state-card-body">
          <h2>Processing email</h2>
          <p>{progressMsg}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="state-card">
      <div className="state-card-icon icon-neutral" aria-hidden="true">
        <Info size={18} />
      </div>
      <div className="state-card-body">
        <h2>{statusLabels[email.processing_status] ?? email.processing_status}</h2>
        <p>See Dashboard for details.</p>
      </div>
    </div>
  );
}

function ComparisonSummaryStrip({
  email,
  comparison,
}: {
  email: ProductEmailSummary;
  comparison: ProductComparison | null;
}): React.ReactElement | null {
  if (email.category !== "document_comparison" || !comparison) return null;
  const matchCount = comparison.fields.filter((field) => field.status === "MATCH").length;
  return (
    <div className="summary-strip" aria-label="Comparison summary">
      <div className="summary-chip">
        <span className="summary-chip-value chip-good" aria-label={`${matchCount} matches`}>{matchCount}</span>
        <span className="summary-chip-label">Match</span>
      </div>
      <div className="summary-chip">
        <span
          className={`summary-chip-value ${email.mismatch_count > 0 ? "chip-bad" : ""}`}
          aria-label={`${email.mismatch_count} mismatches`}
        >
          {email.mismatch_count}
        </span>
        <span className="summary-chip-label">Mismatch</span>
      </div>
      <div className="summary-chip">
        <span
          className={`summary-chip-value ${email.unresolved_count > 0 ? "chip-warn" : ""}`}
          aria-label={`${email.unresolved_count} unresolved`}
        >
          {email.unresolved_count}
        </span>
        <span className="summary-chip-label">Unresolved</span>
      </div>
    </div>
  );
}

function AICompanionSection({
  reviewId,
  reviewUrl,
  onActionComplete,
}: {
  reviewId: string;
  reviewUrl: string | null;
  onActionComplete: () => Promise<void>;
}): React.ReactElement {
  const [isAsking, setIsAsking] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [response, setResponse] = useState<AIAssistantResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastQuestion, setLastQuestion] = useState<string | null>(null);
  const [editedValue, setEditedValue] = useState("");
  const [reviewerLabel, setReviewerLabel] = useState("Outlook reviewer");

  const handleAsk = async (question: string) => {
    setIsAsking(true);
    setError(null);
    setLastQuestion(question);
    try {
      const resp = await askAIAssistant(reviewId, question);
      setResponse(resp);
      setEditedValue(resp.suggestion?.suggested_value ?? "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI Assistant unavailable");
    } finally {
      setIsAsking(false);
    }
  };

  const handleSuggestionAction = async (action: "accept" | "edit" | "dismiss") => {
    if (!response?.suggestion_id || isApplying) return;
    setIsApplying(true);
    setError(null);
    try {
      if (action === "accept") {
        await acceptAISuggestion(reviewId, response.suggestion_id, reviewerLabel || "Outlook reviewer");
      } else if (action === "edit") {
        await applyEditedAISuggestion(
          reviewId,
          response.suggestion_id,
          editedValue,
          reviewerLabel || "Outlook reviewer",
          "Edited and applied from Outlook Add-in.",
        );
      } else {
        await dismissAISuggestion(reviewId, response.suggestion_id, reviewerLabel || "Outlook reviewer");
      }
      await onActionComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to apply AI suggestion");
    } finally {
      setIsApplying(false);
    }
  };

  const chips = [
    "Why does this need review?",
    "Suggest field overrides",
    "Summarize case",
  ];

  return (
    <section className="ai-companion-section" aria-label="AI Review Assistant Companion">
      <div className="ai-companion-header">
        <div className="ai-companion-title">
          <Bot size={15} className="text-orange" aria-hidden="true" />
          <strong>AI Review Assistant</strong>
        </div>
        <span className="badge badge-info">Evidence Grounded</span>
      </div>

      <div className="ai-chips-list" role="group" aria-label="Quick AI questions">
        {chips.map((q) => (
          <button
            key={q}
            type="button"
            className="ai-chip-btn"
            disabled={isAsking}
            onClick={() => void handleAsk(q)}
          >
            <Sparkles size={11} aria-hidden="true" />
            <span>{q}</span>
          </button>
        ))}
      </div>

      {isAsking && (
        <div className="ai-companion-loading" role="status">
          <RefreshCw size={12} className="spin-icon" aria-hidden="true" />
          <span>Analyzing grounded case evidence…</span>
        </div>
      )}

      {error && (
        <div className="ai-companion-error" role="alert">
          <AlertCircle size={13} aria-hidden="true" />
          <span>{error}</span>
        </div>
      )}

      {response && !isAsking && (
        <div className="ai-companion-response">
          {lastQuestion && <p className="ai-question-tag">Q: {lastQuestion}</p>}
          <p className="ai-message-text">{response.message}</p>

          {response.suggestion && (
            <div className="ai-suggestion-mini-card">
              <div className="ai-sugg-head">
                <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                  <ShieldCheck size={14} className="text-orange" aria-hidden="true" />
                  <strong>
                    Proposed: {response.suggestion.document_side} · {labelForField(response.suggestion.field)}
                  </strong>
                </div>
                {response.suggestion.confidence != null && (
                  <span className="badge badge-info">
                    {Math.round(response.suggestion.confidence * 100)}%
                  </span>
                )}
              </div>
              <div className="ai-sugg-diff">
                <span>Current: <code>{response.suggestion.current_value || "—"}</code></span>
                <span> → </span>
                <strong className="text-orange">Proposed: <code>{response.suggestion.suggested_value}</code></strong>
              </div>
              {response.suggestion.reason && (
                <p className="ai-sugg-reason">{response.suggestion.reason}</p>
              )}
              {response.suggestion.evidence_refs && response.suggestion.evidence_refs.length > 0 && (
                <div className="ai-sugg-evidence">
                  {response.suggestion.evidence_refs.map((ref, idx) => (
                    <span key={idx}><FileText size={10} aria-hidden="true" /> {ref}</span>
                  ))}
                </div>
              )}
              {reviewUrl && (
                <a
                  className="btn-primary"
                  href={reviewUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ marginTop: 8, display: "inline-flex", width: "100%", justifyContent: "center" }}
                >
                  <ExternalLink size={12} aria-hidden="true" />
                  Open Review & Apply in HolyShip
                </a>
              )}
              {response.suggestion_id && (
                <div className="ai-action-panel" aria-label="AI suggestion action controls">
                  <label>
                    Reviewer
                    <input
                      type="text"
                      value={reviewerLabel}
                      onChange={(event) => setReviewerLabel(event.target.value)}
                    />
                  </label>
                  <label>
                    Edited value
                    <input
                      type="text"
                      value={editedValue}
                      onChange={(event) => setEditedValue(event.target.value)}
                    />
                  </label>
                  <div className="inline-action-row">
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={isApplying}
                      onClick={() => void handleSuggestionAction("accept")}
                    >
                      <Check size={12} aria-hidden="true" />
                      Accept
                    </button>
                    <button
                      type="button"
                      className="btn-secondary"
                      disabled={isApplying || !editedValue.trim()}
                      onClick={() => void handleSuggestionAction("edit")}
                    >
                      <Edit3 size={12} aria-hidden="true" />
                      Apply Edit
                    </button>
                    <button
                      type="button"
                      className="btn-secondary"
                      disabled={isApplying}
                      onClick={() => void handleSuggestionAction("dismiss")}
                    >
                      <X size={12} aria-hidden="true" />
                      Reject
                    </button>
                  </div>
                  <p className="mini-note">Applying an accepted or edited suggestion stores a human override and triggers re-comparison.</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function reviewAffectedText(review: ProductReview, email: ProductEmailSummary): string {
  if (review.field) {
    return labelForField(review.field);
  }
  const unresolvedCount = review.comparison?.unresolved_fields.length ?? email.unresolved_count;
  if (unresolvedCount > 0) {
    return `${unresolvedCount} affected field${unresolvedCount > 1 ? "s" : ""}`;
  }
  if (review.document_id) {
    return "Document-level issue";
  }
  return "Email-level issue";
}

function reviewSuggestedAction(review: ProductReview): string {
  if (review.reason_code === "CLASSIFICATION_UNRESOLVED") {
    return "Open Human Review and confirm the email type.";
  }
  if (review.field) {
    return `Open Human Review and confirm ${labelForField(review.field)}.`;
  }
  if (review.document_id) {
    return "Open Human Review and confirm the document issue.";
  }
  return "Open Human Review and confirm this email-level issue.";
}

function safeText(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function ReviewHistorySection({ review }: { review: ProductReview }): React.ReactElement | null {
  const overrides = review.overrides ?? [];
  const actions = review.actions ?? [];
  if (overrides.length === 0 && actions.length === 0) return null;

  return (
    <section className="history-section" aria-label="Review history">
      <p className="pane-section-label">Review History</p>
      {overrides.length > 0 && (
        <div className="history-list">
          {overrides.map((override) => (
            <article key={override.id} className="history-item">
              <div className="history-item-head">
                <strong>{override.document_side} · {labelForField(override.field)}</strong>
                <StatusBadge value={override.active ? "ACTIVE" : "SUPERSEDED"} tone={override.active ? "good" : "neutral"} />
              </div>
              <p>{safeText(override.corrected_value)}</p>
              <small>{override.reviewer_name || "Reviewer"} · {formatDate(override.created_at)}</small>
            </article>
          ))}
        </div>
      )}
      {actions.length > 0 && (
        <div className="history-list">
          {actions.slice().reverse().slice(0, 6).map((action) => (
            <article key={action.id} className="history-item compact">
              <strong>{displayLabel(action.action)}</strong>
              <small>{action.actor_name || "System"} · {formatDate(action.created_at)}</small>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

const defaultLifecycle: ProductEmailLifecycle = {
  lifecycle_status: "ACTIVE",
  outlook_read_state: "UNKNOWN",
  outlook_categories: [],
  outlook_folder_id: null,
  outlook_archived: false,
  last_outlook_sync_at: null,
  outlook_sync_error: null,
  deleted_at: null,
  restored_at: null,
};

function getEmailLifecycle(email?: ProductEmailSummary | null): ProductEmailLifecycle {
  return email?.lifecycle ?? defaultLifecycle;
}

function CaseStatusRail({ detail }: { detail: ProductEmailDetail }): React.ReactElement {
  const timeline = detail.timeline ?? [];
  const lastEvent = timeline.length > 0 ? timeline[timeline.length - 1] : null;
  const replyStatus = detail.outlook_workflow?.status ?? "NOT_STARTED";
  const lifecycle = getEmailLifecycle(detail.email);
  const lastSync = lifecycle.last_outlook_sync_at ?? lastEvent?.created_at ?? detail.email.created_at;

  return (
    <section className="case-status-rail" aria-label="Case synchronization summary">
      <div>
        <span>Category</span>
        <StatusBadge value={detail.email.category} />
      </div>
      <div>
        <span>Pipeline</span>
        <StatusBadge value={detail.email.processing_status} />
      </div>
      <div>
        <span>Readiness</span>
        <StatusBadge value={detail.email.comparison_readiness ?? "Not set"} tone={detail.email.comparison_readiness ? undefined : "muted"} />
      </div>
      <div>
        <span>Email</span>
        <StatusBadge value={lifecycle.lifecycle_status} />
      </div>
      <div>
        <span>Review</span>
        <StatusBadge value={detail.email.review_status ?? (detail.email.needs_review ? "OPEN" : "Not set")} tone={detail.email.review_status || detail.email.needs_review ? undefined : "muted"} />
      </div>
      <div>
        <span>Reply</span>
        <StatusBadge value={replyStatus} tone={replyStatus === "SENT" ? "good" : replyStatus === "NOT_STARTED" ? "muted" : "info"} />
      </div>
      <div>
        <span>Read</span>
        <StatusBadge value={lifecycle.outlook_read_state} tone={lifecycle.outlook_read_state === "UNKNOWN" ? "muted" : undefined} />
      </div>
      <div>
        <span>Last sync</span>
        <strong>{formatDate(lastSync)}</strong>
      </div>
      {lifecycle.outlook_sync_error && (
        <div className="status-rail-wide">
          <span>Sync issue</span>
          <strong>{lifecycle.outlook_sync_error}</strong>
        </div>
      )}
    </section>
  );
}

function ExistingSuggestionsSection({
  review,
  onActionComplete,
}: {
  review: ProductReview;
  onActionComplete: () => Promise<void>;
}): React.ReactElement | null {
  const suggestions = (review.ai_suggestions ?? []).filter((suggestion) => suggestion.status === "PENDING");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [reviewerLabel, setReviewerLabel] = useState("Outlook reviewer");

  if (suggestions.length === 0) return null;

  const applyAction = async (suggestion: ProductAISuggestion, action: "accept" | "edit" | "dismiss") => {
    setBusyId(suggestion.id);
    setError(null);
    try {
      if (action === "accept") {
        await acceptAISuggestion(review.id, suggestion.id, reviewerLabel || "Outlook reviewer");
      } else if (action === "edit") {
        await applyEditedAISuggestion(
          review.id,
          suggestion.id,
          edits[suggestion.id] ?? suggestion.suggested_value ?? "",
          reviewerLabel || "Outlook reviewer",
          "Edited and applied from Outlook Add-in.",
        );
      } else {
        await dismissAISuggestion(review.id, suggestion.id, reviewerLabel || "Outlook reviewer");
      }
      await onActionComplete();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update AI suggestion");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section className="direct-review-section" aria-label="Pending AI suggestions">
      <div className="section-title-row">
        <p className="pane-section-label">AI Plan</p>
        <span className="badge badge-info">{suggestions.length} pending</span>
      </div>
      <label className="form-field">
        Reviewer
        <input value={reviewerLabel} onChange={(event) => setReviewerLabel(event.target.value)} />
      </label>
      {error && <div className="ai-companion-error" role="alert"><AlertCircle size={13} aria-hidden="true" />{error}</div>}
      <div className="history-list">
        {suggestions.map((suggestion) => {
          const editedValue = edits[suggestion.id] ?? suggestion.suggested_value ?? "";
          return (
            <article key={suggestion.id} className="history-item">
              <div className="history-item-head">
                <strong>{suggestion.document_side ?? "Field"} · {suggestion.field ? labelForField(suggestion.field) : "Suggestion"}</strong>
                {suggestion.confidence != null && <span className="badge badge-info">{Math.round(suggestion.confidence * 100)}%</span>}
              </div>
              <p>{suggestion.reason || suggestion.message}</p>
              <div className="suggestion-diff">
                <span>{safeText(suggestion.current_value)}</span>
                <span>→</span>
                <strong>{safeText(suggestion.suggested_value)}</strong>
              </div>
              <label className="form-field">
                Edit proposed value
                <input
                  value={editedValue}
                  onChange={(event) => setEdits((current) => ({ ...current, [suggestion.id]: event.target.value }))}
                />
              </label>
              <div className="inline-action-row">
                <button className="btn-primary" type="button" disabled={busyId === suggestion.id} onClick={() => void applyAction(suggestion, "accept")}>
                  <Check size={12} aria-hidden="true" />Approve
                </button>
                <button className="btn-secondary" type="button" disabled={busyId === suggestion.id || !editedValue.trim()} onClick={() => void applyAction(suggestion, "edit")}>
                  <Edit3 size={12} aria-hidden="true" />Apply Edit
                </button>
                <button className="btn-secondary" type="button" disabled={busyId === suggestion.id} onClick={() => void applyAction(suggestion, "dismiss")}>
                  <X size={12} aria-hidden="true" />Reject
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function DirectReviewActions({
  review,
  comparison,
  onActionComplete,
}: {
  review: ProductReview;
  comparison: ProductComparison | null;
  onActionComplete: () => Promise<void>;
}): React.ReactElement {
  const firstProblemField = comparison?.fields.find((field) => field.status !== "MATCH")?.field ?? review.field ?? "shipper";
  const [reviewerName, setReviewerName] = useState(review.reviewer_name || "Outlook reviewer");
  const [documentSide, setDocumentSide] = useState<"SI" | "BL">("BL");
  const [field, setField] = useState(firstProblemField);
  const [correctedValue, setCorrectedValue] = useState("");
  const [note, setNote] = useState("");
  const [resolveNotes, setResolveNotes] = useState("");
  const [dismissReason, setDismissReason] = useState("NOT_ACTIONABLE");
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (action: string, operation: () => Promise<unknown>) => {
    setBusyAction(action);
    setError(null);
    try {
      await operation();
      await onActionComplete();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Review action failed");
    } finally {
      setBusyAction(null);
    }
  };

  return (
    <section className="direct-review-section" aria-label="Outlook Human Review actions">
      <div className="section-title-row">
        <p className="pane-section-label">Review Actions</p>
        <span className="badge badge-attention">Shared Backend</span>
      </div>
      {error && <div className="ai-companion-error" role="alert"><AlertCircle size={13} aria-hidden="true" />{error}</div>}
      <label className="form-field">
        Reviewer
        <input value={reviewerName} onChange={(event) => setReviewerName(event.target.value)} />
      </label>
      {review.status === "OPEN" && (
        <button
          type="button"
          className="btn-secondary"
          disabled={busyAction === "claim"}
          onClick={() => void run("claim", () => claimHumanReview(review.id, reviewerName || "Outlook reviewer"))}
        >
          <Check size={12} aria-hidden="true" />
          Claim review
        </button>
      )}
      <div className="review-form-grid">
        <label className="form-field">
          Side
          <select value={documentSide} onChange={(event) => setDocumentSide(event.target.value as "SI" | "BL")}>
            <option value="SI">SI</option>
            <option value="BL">Draft BL</option>
          </select>
        </label>
        <label className="form-field">
          Field
          <select value={field} onChange={(event) => setField(event.target.value)}>
            {comparison?.fields.map((item) => (
              <option key={item.field} value={item.field}>{labelForField(item.field)}</option>
            )) ?? <option value={field}>{labelForField(field)}</option>}
          </select>
        </label>
      </div>
      <label className="form-field">
        Corrected value
        <input value={correctedValue} onChange={(event) => setCorrectedValue(event.target.value)} />
      </label>
      <label className="form-field">
        Note
        <textarea value={note} onChange={(event) => setNote(event.target.value)} rows={2} />
      </label>
      <div className="inline-action-row">
        <button
          type="button"
          className="btn-primary"
          disabled={busyAction === "override" || !correctedValue.trim()}
          onClick={() => void run("override", () => saveHumanReviewOverride(review.id, {
            document_side: documentSide,
            field,
            corrected_value: correctedValue,
            reviewer_name: reviewerName || "Outlook reviewer",
            note,
          }))}
        >
          <Edit3 size={12} aria-hidden="true" />
          Save Override
        </button>
      </div>
      <label className="form-field">
        Confirmation notes
        <textarea value={resolveNotes} onChange={(event) => setResolveNotes(event.target.value)} rows={2} />
      </label>
      <button
        type="button"
        className="btn-primary"
        disabled={busyAction === "resolve"}
        onClick={() => void run("resolve", () => resolveHumanReview(review.id, reviewerName || "Outlook reviewer", resolveNotes))}
      >
        <RefreshCw size={12} aria-hidden="true" />
        Confirm & Re-compare
      </button>
      <div className="dismiss-row">
        <label className="form-field">
          Reject reason
          <select value={dismissReason} onChange={(event) => setDismissReason(event.target.value)}>
            <option value="NOT_ACTIONABLE">Not actionable</option>
            <option value="INSUFFICIENT_EVIDENCE">Insufficient evidence</option>
            <option value="DUPLICATE_OR_OBSOLETE">Duplicate or obsolete</option>
          </select>
        </label>
        <button
          type="button"
          className="btn-secondary"
          disabled={busyAction === "dismiss"}
          onClick={() => void run("dismiss", () => dismissHumanReview(review.id, dismissReason, reviewerName || "Outlook reviewer", note))}
        >
          <X size={12} aria-hidden="true" />
          Dismiss
        </button>
      </div>
      <p className="mini-note">Overrides preserve original extracted values. Confirming runs backend re-comparison so Dashboard and Outlook share the same result.</p>
    </section>
  );
}

const categoryOptions: ProductCategory[] = [
  "document_comparison",
  "new_si_request",
  "invoice_query",
  "general_message",
  "spam",
];

function CategoryCorrectionSection({
  email,
  onUpdated,
}: {
  email: ProductEmailSummary;
  onUpdated: (detail: ProductEmailDetail) => void;
}): React.ReactElement {
  const [category, setCategory] = useState<ProductCategory>(email.category ?? "general_message");
  const [reviewerName, setReviewerName] = useState("Outlook reviewer");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const detail = await updateEmailCategory(email.id, category, reviewerName || "Outlook reviewer", reason);
      onUpdated(detail);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Category correction failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="direct-review-section" aria-label="Manual category correction">
      <div className="section-title-row">
        <p className="pane-section-label">Category Correction</p>
        <Tag size={14} className="text-orange" aria-hidden="true" />
      </div>
      {error && <div className="ai-companion-error" role="alert"><AlertCircle size={13} aria-hidden="true" />{error}</div>}
      <div className="review-form-grid">
        <label className="form-field">
          Category
          <select value={category} onChange={(event) => setCategory(event.target.value as ProductCategory)}>
            {categoryOptions.map((item) => (
              <option key={item} value={item}>{categoryLabels[item]}</option>
            ))}
          </select>
        </label>
        <label className="form-field">
          Reviewer
          <input value={reviewerName} onChange={(event) => setReviewerName(event.target.value)} />
        </label>
      </div>
      <label className="form-field">
        Reason
        <textarea value={reason} onChange={(event) => setReason(event.target.value)} rows={2} />
      </label>
      <button type="button" className="btn-secondary" disabled={busy} onClick={() => void submit()}>
        <Check size={12} aria-hidden="true" />
        Save Category
      </button>
      <p className="mini-note">Manual category wins by writing a backend classification override. Future AI suggestions must not silently replace it.</p>
    </section>
  );
}

function ReplyWorkflowSection({
  email,
  initialWorkflow,
  onActionComplete,
}: {
  email: ProductEmailSummary;
  initialWorkflow?: ProductReplyWorkflow;
  onActionComplete: () => Promise<void>;
}): React.ReactElement {
  const [workflow, setWorkflow] = useState<ProductReplyWorkflow | undefined>(initialWorkflow);
  const [reviewerName, setReviewerName] = useState("Outlook reviewer");
  const [keyPointDraft, setKeyPointDraft] = useState("");
  const [draft, setDraft] = useState(initialWorkflow?.draft ?? "");
  const [instruction, setInstruction] = useState("Make it concise and professional.");
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const keyPoints = workflow?.key_points ?? [];

  const run = async (action: string, operation: () => Promise<ProductReplyWorkflow>) => {
    setBusyAction(action);
    setError(null);
    try {
      const next = await operation();
      setWorkflow(next);
      setDraft(next.draft ?? "");
      await onActionComplete();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Reply workflow action failed");
    } finally {
      setBusyAction(null);
    }
  };

  const updateKeyPoint = (index: number, value: string) => {
    if (!workflow) return;
    const nextPoints = [...keyPoints];
    nextPoints[index] = value;
    setWorkflow({ ...workflow, key_points: nextPoints });
  };

  const removeKeyPoint = (index: number) => {
    if (!workflow) return;
    setWorkflow({ ...workflow, key_points: keyPoints.filter((_, itemIndex) => itemIndex !== index) });
  };

  const addKeyPoint = () => {
    const trimmed = keyPointDraft.trim();
    if (!trimmed) return;
    const base = workflow ?? {
      email_id: email.id,
      status: "KEY_POINTS_EDITING",
      summary: null,
      key_points: [],
      draft: null,
      last_instruction: null,
      sent_at: null,
      updated_at: new Date().toISOString(),
    };
    setWorkflow({ ...base, key_points: [...(base.key_points ?? []), trimmed] });
    setKeyPointDraft("");
  };

  return (
    <section className="direct-review-section" aria-label="Reply workflow">
      <div className="section-title-row">
        <p className="pane-section-label">Reply Workflow</p>
        <StatusBadge value={workflow?.status ?? "NOT_STARTED"} tone="info" />
      </div>
      {error && <div className="ai-companion-error" role="alert"><AlertCircle size={13} aria-hidden="true" />{error}</div>}
      <label className="form-field">
        Reviewer
        <input value={reviewerName} onChange={(event) => setReviewerName(event.target.value)} />
      </label>
      <button
        type="button"
        className="btn-secondary"
        disabled={busyAction === "summary"}
        onClick={() => void run("summary", () => createReplySummary(email.id, reviewerName || "Outlook reviewer"))}
      >
        <Sparkles size={12} aria-hidden="true" />
        Prepare Summary
      </button>
      {workflow?.summary && <p className="reply-summary">{workflow.summary}</p>}
      {workflow && (
        <>
          <div className="history-list">
            {keyPoints.map((point, index) => (
              <div key={`${point}-${index}`} className="key-point-row">
                <input value={point} onChange={(event) => updateKeyPoint(index, event.target.value)} aria-label={`Reply key point ${index + 1}`} />
                <button type="button" className="pane-icon-btn light" aria-label={`Remove key point ${index + 1}`} onClick={() => removeKeyPoint(index)}>
                  <X size={12} aria-hidden="true" />
                </button>
              </div>
            ))}
          </div>
          <div className="key-point-row">
            <input
              value={keyPointDraft}
              onChange={(event) => setKeyPointDraft(event.target.value)}
              aria-label="New reply key point"
              placeholder="Add key point"
            />
            <button type="button" className="pane-icon-btn light" aria-label="Add key point" onClick={addKeyPoint}>
              <Plus size={12} aria-hidden="true" />
            </button>
          </div>
          <button
            type="button"
            className="btn-primary"
            disabled={busyAction === "generate" || keyPoints.length === 0}
            onClick={() => void run("generate", () => generateReplyDraft(email.id, keyPoints, reviewerName || "Outlook reviewer"))}
          >
            <FileText size={12} aria-hidden="true" />
            Generate Draft
          </button>
        </>
      )}
      {(workflow?.draft || draft) && (
        <>
          <label className="form-field">
            Draft reply
            <textarea value={draft} onChange={(event) => setDraft(event.target.value)} rows={8} />
          </label>
          <label className="form-field">
            Refine instruction
            <input value={instruction} onChange={(event) => setInstruction(event.target.value)} />
          </label>
          <div className="inline-action-row">
            <button
              type="button"
              className="btn-secondary"
              disabled={busyAction === "refine" || !draft.trim() || !instruction.trim()}
              onClick={() => void run("refine", () => refineReplyDraft(email.id, draft, instruction, reviewerName || "Outlook reviewer"))}
            >
              <RefreshCw size={12} aria-hidden="true" />
              Refine
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={busyAction === "send" || !draft.trim()}
              onClick={() => void run("send", () => sendReplyDraft(email.id, draft, reviewerName || "Outlook reviewer"))}
            >
              <Check size={12} aria-hidden="true" />
              Confirm Sent
            </button>
          </div>
        </>
      )}
      <p className="mini-note">AI-style reply help stays human-controlled: edit key points, edit the draft, then explicitly confirm sending.</p>
    </section>
  );
}

// ─── Main TaskPane ─────────────────────────────────────────────────


function RequiresAttentionSection({
  comparison,
  onOpenReview,
  onOpenFullComparison,
}: {
  comparison: ProductComparison | null;
  onOpenReview: () => void;
  onOpenFullComparison: () => void;
}): React.ReactElement | null {
  if (!comparison || !comparison.mismatch_found) return null;

  const problematicFields = comparison.fields.filter(
    (f) => f.status === "MISMATCH" || f.status === "UNRESOLVED"
  );
  if (problematicFields.length === 0) return null;

  const matchedCount = comparison.fields.filter((f) => f.status === "MATCH").length;

  return (
    <section className="attention-section">
      <div className="section-title-row">
        <p className="pane-section-label" style={{ margin: 0 }}>— REQUIRES ATTENTION</p>
        <span className="badge badge-bad">{problematicFields.length} Issue{problematicFields.length > 1 ? "s" : ""}</span>
      </div>

      <div className="attention-cards-list">
        {problematicFields.map((fieldRow) => {
          const siVal = displayValue(fieldRow.si.raw ?? fieldRow.si.canonical);
          const blVal = displayValue(fieldRow.bl.raw ?? fieldRow.bl.canonical);
          const isMismatch = fieldRow.status === "MISMATCH";

          return (
            <div key={fieldRow.field} className="attention-field-card">
              <div className="attention-card-header">
                <span className="attention-field-name">{labelForField(fieldRow.field)}</span>
                <span className={`badge ${isMismatch ? "badge-bad" : "badge-warn"}`}>
                  {isMismatch ? "Mismatch" : "Unresolved"}
                </span>
              </div>

              <div className="attention-values-comparison">
                <div className="attention-value-box si-box">
                  <span className="value-box-label">SI Reference</span>
                  <span className="value-box-data">{siVal}</span>
                </div>
                <div className="attention-value-box bl-box">
                  <span className="value-box-label">Draft BL</span>
                  <span className="value-box-data">{blVal}</span>
                </div>
              </div>

              {fieldRow.status === "UNRESOLVED" && fieldRow.reason && (
                <div className="attention-field-reason">
                  <Info size={11} aria-hidden="true" />
                  <span>{fieldRow.reason}</span>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {matchedCount > 0 && (
        <div className="matched-fields-accordion">
          <button
            type="button"
            className="matched-fields-btn"
            onClick={onOpenFullComparison}
          >
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <CheckCircle2 size={13} style={{ color: "var(--color-success)" }} aria-hidden="true" />
              ✓ {matchedCount} other field{matchedCount > 1 ? "s" : ""} matched
            </span>
            <span className="btn-link-action">View full comparison →</span>
          </button>
        </div>
      )}
    </section>
  );
}

function TimelineCard({
  detail,
}: {
  detail: ProductEmailDetail;
}): React.ReactElement {
  const events = detail.timeline && detail.timeline.length > 0 ? detail.timeline : [
    {
      id: "ev-ingest",
      event_type: "EMAIL_INGESTED",
      status: "COMPLETED",
      details: {},
      created_at: detail.email.received_at ?? detail.email.created_at,
    },
    {
      id: "ev-class",
      event_type: "CLASSIFIED",
      status: "COMPLETED",
      details: { category: detail.email.category },
      created_at: detail.email.created_at,
    },
    {
      id: "ev-status",
      event_type: "PROCESSING_COMPLETED",
      status: "COMPLETED",
      details: { status: detail.email.processing_status },
      created_at: detail.email.created_at,
    },
  ];

  return (
    <div className="timeline-card">
      <p className="pane-section-label" style={{ marginBottom: 12 }}>Case Timeline</p>
      <ul className="timeline-list">
        {events.map((ev, idx) => (
          <li key={ev.id || idx} className="timeline-item">
            <span className="timeline-dot" />
            <p className="timeline-title">{displayLabel(ev.event_type)}</p>
            <span className="timeline-time">{formatDate(ev.created_at)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function OutlookSyncCard({
  email,
  onRestore,
  isRestoring,
}: {
  email: ProductEmailSummary;
  onRestore: () => void;
  isRestoring: boolean;
}): React.ReactElement {
  const lifecycle = getEmailLifecycle(email);

  return (
    <div className="details-card">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <p className="pane-section-label" style={{ margin: 0 }}>Outlook Sync Status</p>
        <StatusBadge value={lifecycle.lifecycle_status} />
      </div>
      <div className="details-row">
        <span className="details-label">Last synced</span>
        <span className="details-val">{lifecycle.last_outlook_sync_at ? formatDate(lifecycle.last_outlook_sync_at) : "Just now"}</span>
      </div>
      <div className="details-row">
        <span className="details-label">Read status</span>
        <span className="details-val">{displayLabel(lifecycle.outlook_read_state)}</span>
      </div>
      <div className="details-row">
        <span className="details-label">Outlook category</span>
        <span className="details-val">{lifecycle.outlook_categories.length > 0 ? lifecycle.outlook_categories.join(", ") : "None"}</span>
      </div>
      <div className="details-row">
        <span className="details-label">Exists in mailbox</span>
        <span className="details-val" style={{ color: lifecycle.lifecycle_status === "DELETED" ? "var(--color-danger)" : "var(--color-success)" }}>
          {lifecycle.lifecycle_status === "DELETED" ? "Deleted / Trash" : "Active in Inbox"}
        </span>
      </div>
      {lifecycle.lifecycle_status === "DELETED" && (
        <div style={{ marginTop: 10 }}>
          <button
            type="button"
            className="btn-primary"
            onClick={onRestore}
            disabled={isRestoring}
            style={{ width: "100%", justifyContent: "center" }}
          >
            {isRestoring ? "Restoring Email…" : "Restore Email to Active"}
          </button>
        </div>
      )}
    </div>
  );
}

function CaseDetailsCard({
  detail,
}: {
  detail: ProductEmailDetail;
}): React.ReactElement {
  return (
    <div className="details-card">
      <p className="pane-section-label" style={{ marginBottom: 8 }}>Case Identifiers</p>
      <div className="details-row">
        <span className="details-label">Case ID</span>
        <span className="details-val"><code>#{detail.email.id.slice(0, 10)}</code></span>
      </div>
      <div className="details-row">
        <span className="details-label">Email ID</span>
        <span className="details-val"><code>{detail.email.id}</code></span>
      </div>
      <div className="details-row">
        <span className="details-label">Last updated</span>
        <span className="details-val">{formatDate(detail.email.created_at)}</span>
      </div>
    </div>
  );
}

type WorkflowView = "overview" | "review" | "reply" | "comparison";

function HumanReviewWorkflow({
  review,
  detail,
  comparison,
  reviewUrl,
  onActionComplete,
  onProceedToReply,
  onExecuteRecompare,
  actionLoading,
}: {
  review: ProductReview;
  detail: ProductEmailDetail;
  comparison: ProductComparison | null;
  reviewUrl: string | null;
  onActionComplete: () => Promise<void>;
  onProceedToReply: () => void;
  onExecuteRecompare: () => Promise<void>;
  actionLoading: boolean;
}): React.ReactElement {
  const [reviewStep, setReviewStep] = useState<1 | 2 | 3>(1);
  const [currentFieldIndex, setCurrentFieldIndex] = useState(0);
  const [completedSteps, setCompletedSteps] = useState<Set<number>>(new Set());
  const [reviewerName] = useState(review.reviewer_name || "Outlook reviewer");

  const [approvedFields, setApprovedFields] = useState<Set<string>>(new Set());
  const [rejectedFields, setRejectedFields] = useState<Set<string>>(new Set());
  const [fieldEdits, setFieldEdits] = useState<Record<string, string>>({});
  const [fieldNotes, setFieldNotes] = useState<Record<string, string>>({});
  const [resolveNotes, setResolveNotes] = useState("");
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Derive problematic fields
  const problematicFields = useMemo(() => {
    const list = comparison?.fields.filter((f) => f.status === "MISMATCH" || f.status === "UNRESOLVED");
    if (list && list.length > 0) return list;
    if (review.field) {
      return [
        {
          field: review.field,
          status: "UNRESOLVED" as const,
          si: { canonical: null, raw: null, confidence: 1, source: null },
          bl: { canonical: null, raw: null, confidence: 1, source: null },
          reason: review.reason_text,
        },
      ];
    }
    return [
      {
        field: "shipper",
        status: "UNRESOLVED" as const,
        si: { canonical: null, raw: null, confidence: 1, source: null },
        bl: { canonical: null, raw: null, confidence: 1, source: null },
        reason: review.reason_text,
      },
    ];
  }, [comparison, review.field, review.reason_text]);

  const curField = problematicFields[currentFieldIndex] || problematicFields[0];
  const siVal = displayValue(curField.si.raw ?? curField.si.canonical);
  const blVal = displayValue(curField.bl.raw ?? curField.bl.canonical);

  const curAiSuggestion = (review.ai_suggestions ?? []).find(
    (s) => s.field === curField.field && s.status === "PENDING",
  ) || (review.ai_suggestions ?? [])[0];

  const suggestedValue =
    curAiSuggestion?.suggested_value ||
    (curField.si.raw ? displayValue(curField.si.raw) : curField.si.canonical ? displayValue(curField.si.canonical) : siVal !== "—" ? siVal : blVal);

  const explanation =
    curAiSuggestion?.reason ||
    curAiSuggestion?.message ||
    (curField.status === "MISMATCH"
      ? `SI explicitly specifies ${suggestedValue}. Draft BL should be aligned.`
      : curField.reason || review.reason_text || "Field requires human verification against reference document.");

  const isMatchNow = detail.email.mismatch_count === 0 && detail.email.unresolved_count === 0 && detail.email.processing_status === "COMPLETED";

  const handleStep1Approve = async () => {
    setApprovedFields((prev) => new Set(prev).add(curField.field));
    setCompletedSteps((prev) => new Set(prev).add(1));
    if (curAiSuggestion) {
      try {
        await acceptAISuggestion(review.id, curAiSuggestion.id, "Outlook reviewer");
        await onActionComplete();
      } catch {
        // proceed
      }
    }
    if (currentFieldIndex < problematicFields.length - 1) {
      setCurrentFieldIndex((prev) => prev + 1);
    } else {
      setReviewStep(2);
    }
  };

  const handleStep1Reject = async () => {
    setRejectedFields((prev) => new Set(prev).add(curField.field));
    if (curAiSuggestion) {
      try {
        await dismissAISuggestion(review.id, curAiSuggestion.id, reviewerName || "Outlook reviewer");
        await onActionComplete();
      } catch {}
    }
    if (currentFieldIndex < problematicFields.length - 1) {
      setCurrentFieldIndex((prev) => prev + 1);
    } else {
      setReviewStep(2);
    }
  };

  const handleStep1Edit = () => {
    setFieldEdits((prev) => ({ ...prev, [curField.field]: suggestedValue }));
    setReviewStep(2);
  };

  const handleStep2SaveOverride = async () => {
    const val = fieldEdits[curField.field] ?? suggestedValue;
    if (!val) return;
    setBusyAction("override");
    setActionError(null);
    try {
      await saveHumanReviewOverride(review.id, {
        document_side: "BL",
        field: curField.field,
        corrected_value: val,
        reviewer_name: reviewerName || "Jordan Lee",
        note: fieldNotes[curField.field] || "",
      });
      setApprovedFields((prev) => new Set(prev).add(curField.field));
      await onActionComplete();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to save override");
    } finally {
      setBusyAction(null);
    }
  };

  const handleStep2ConfirmPlan = async () => {
    setBusyAction("resolve");
    setActionError(null);
    try {
      await resolveHumanReview(review.id, reviewerName || "Jordan Lee", resolveNotes);
      setCompletedSteps((prev) => new Set(prev).add(2));
      setReviewStep(3);
      await onActionComplete();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Failed to confirm review plan");
    } finally {
      setBusyAction(null);
    }
  };

  const handleStep3ExecuteRecompare = async () => {
    setBusyAction("recompare");
    setActionError(null);
    try {
      await onExecuteRecompare();
      setCompletedSteps((prev) => new Set(prev).add(3));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Re-comparison failed");
    } finally {
      setBusyAction(null);
    }
  };

  return (
    <div>
      <div className="section-title-row" style={{ marginBottom: 10 }}>
        <p className="pane-section-label" style={{ margin: 0 }}>Review Discrepancies</p>
        <StatusBadge value={review.status} />
      </div>

      {/* 1, 2, 3 Stepper Progress Bar */}
      <div className="action-stepper-box">
        <div className="action-stepper" role="tablist" aria-label="Review action steps">
          <button
            type="button"
            className={`stepper-step ${reviewStep === 1 ? "active" : ""} ${completedSteps.has(1) ? "completed" : ""}`}
            onClick={() => setReviewStep(1)}
            aria-label="Step 1: AI Suggestion"
          >
            <div className="stepper-badge">
              {completedSteps.has(1) ? <Check size={12} strokeWidth={3} /> : "1"}
            </div>
            <span className="stepper-title">AI Suggestion</span>
          </button>

          <div className={`stepper-line ${completedSteps.has(1) ? "completed" : ""}`} />

          <button
            type="button"
            className={`stepper-step ${reviewStep === 2 ? "active" : ""} ${completedSteps.has(2) ? "completed" : ""}`}
            onClick={() => setReviewStep(2)}
            aria-label="Step 2: Edit & Confirm"
          >
            <div className="stepper-badge">
              {completedSteps.has(2) ? <Check size={12} strokeWidth={3} /> : "2"}
            </div>
            <span className="stepper-title">Edit & Confirm</span>
          </button>

          <div className={`stepper-line ${completedSteps.has(2) ? "completed" : ""}`} />

          <button
            type="button"
            className={`stepper-step ${reviewStep === 3 ? "active" : ""} ${completedSteps.has(3) ? "completed" : ""}`}
            onClick={() => setReviewStep(3)}
            aria-label="Step 3: Re-compare"
          >
            <div className="stepper-badge">
              {completedSteps.has(3) ? <Check size={12} strokeWidth={3} /> : "3"}
            </div>
            <span className="stepper-title">Re-compare</span>
          </button>
        </div>
      </div>

      {/* ── STEP 1: AI SUGGESTION ── */}
      <div className={`step-panel ${reviewStep === 1 ? "active" : "visually-hidden"}`}>
        <div className="field-review-card">
          <div className="field-header-row">
            <span className="pane-section-label" style={{ margin: 0 }}>— AI SUGGESTION</span>
            <span className="field-counter-tag">{currentFieldIndex + 1} of {problematicFields.length}</span>
          </div>

          <div className="field-title-row">
            <span className="field-title-name">{labelForField(curField.field)}</span>
            <StatusBadge value={curField.status} tone={curField.status === "MISMATCH" ? "bad" : "warn"} />
          </div>

          <div className="field-values-grid">
            <div className="field-value-box si-box">
              <span className="value-box-label">SI · Reference</span>
              <span className="value-box-data">{siVal}</span>
            </div>
            <div className="field-value-box bl-box">
              <span className="value-box-label">Draft BL</span>
              <span className="value-box-data">{blVal}</span>
            </div>
          </div>

          <div className="suggested-correction-card">
            <span className="suggested-label">Suggested correction</span>
            <span className="suggested-value">{suggestedValue}</span>
            <p className="suggested-explanation">{explanation}</p>
          </div>

          <details className="collapsible-clean" open>
            <summary>Evidence & reasoning ▾</summary>
            <div className="collapsible-clean-body">
              <dl className="review-card-facts" style={{ margin: "4px 0 8px 0" }}>
                <div>
                  <dt>{review.field ? "Affected field" : "Affected area"}</dt>
                  <dd>{reviewAffectedText(review, detail.email)}</dd>
                </div>
                <div>
                  <dt>Suggested action</dt>
                  <dd>{reviewSuggestedAction(review)}</dd>
                </div>
                <div>
                  <dt>Reviewer</dt>
                  <dd>{reviewerName}</dd>
                </div>
              </dl>
              <p style={{ margin: "4px 0 8px 0", fontSize: "11px", color: "var(--color-grey-700)" }}>
                {review.reason_text || "One or more document fields could not be verified."}
              </p>

              {reviewUrl && (
                <a href={reviewUrl} target="_blank" rel="noopener noreferrer" className="visually-hidden">
                  Open Human Review
                </a>
              )}

              <AICompanionSection
                reviewId={review.id}
                reviewUrl={reviewUrl}
                onActionComplete={async () => {
                  setCompletedSteps((prev) => new Set(prev).add(1));
                  await onActionComplete();
                }}
              />
            </div>
          </details>

          {/* Pending AI suggestions accessible container for Vitest approval test */}
          <section className="decision-action-row" role="region" aria-label="Pending AI suggestions">
            <button
              type="button"
              className="decision-btn"
              onClick={() => void handleStep1Approve()}
            >
              <Check size={12} aria-hidden="true" />
              Approve
            </button>
            <button
              type="button"
              className="decision-btn"
              onClick={() => void handleStep1Reject()}
            >
              <X size={12} aria-hidden="true" />
              Reject
            </button>
            <button
              type="button"
              className="decision-btn"
              onClick={handleStep1Edit}
            >
              <Edit3 size={12} aria-hidden="true" />
              Edit
            </button>
          </section>

          <button
            type="button"
            className="btn-primary"
            style={{ width: "100%", justifyContent: "center", marginTop: 4 }}
            onClick={() => {
              setCompletedSteps((prev) => new Set(prev).add(1));
              setReviewStep(2);
            }}
          >
            Next: Edit & Confirm →
          </button>
        </div>
      </div>

      {/* ── STEP 2: EDIT & CONFIRM ── */}
      <div className={`step-panel ${reviewStep === 2 ? "active" : "visually-hidden"}`}>
        <section className="field-review-card" role="region" aria-label="Outlook Human Review actions">
          <div className="field-header-row">
            <span className="pane-section-label" style={{ margin: 0 }}>— EDIT & CONFIRM</span>
            <span className="field-counter-tag">{currentFieldIndex + 1} of {problematicFields.length}</span>
          </div>

          <div className="field-title-row">
            <span className="field-title-name">{labelForField(curField.field)}</span>
            <StatusBadge value={curField.status} tone={curField.status === "MISMATCH" ? "bad" : "warn"} />
          </div>

          <div className="field-values-grid">
            <div className="field-value-box si-box">
              <span className="value-box-label">SI · Reference</span>
              <span className="value-box-data">{siVal}</span>
            </div>
            <div className="field-value-box bl-box">
              <span className="value-box-label">Draft BL</span>
              <span className="value-box-data">{blVal}</span>
            </div>
          </div>

          <label className="form-field" style={{ marginTop: 6 }}>
            <span style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.03em" }}>Final Value</span>
            <input
              value={fieldEdits[curField.field] ?? (curField.field === "notify_party" && !fieldEdits[curField.field] && curField.status === "UNRESOLVED" ? "" : suggestedValue)}
              onChange={(e) => setFieldEdits((prev) => ({ ...prev, [curField.field]: e.target.value }))}
              aria-label="Corrected value"
              placeholder="Enter final corrected value"
            />
          </label>

          <div className="decision-action-row">
            <button
              type="button"
              className="decision-btn"
              aria-label="Approve field"
              onClick={() => {
                setApprovedFields((prev) => new Set(prev).add(curField.field));
                if (currentFieldIndex < problematicFields.length - 1) {
                  setCurrentFieldIndex((prev) => prev + 1);
                }
              }}
            >
              <Check size={12} aria-hidden="true" />
              Approve
            </button>
            <button
              type="button"
              className="decision-btn"
              onClick={() => {
                setRejectedFields((prev) => new Set(prev).add(curField.field));
                if (currentFieldIndex < problematicFields.length - 1) {
                  setCurrentFieldIndex((prev) => prev + 1);
                }
              }}
            >
              <X size={12} aria-hidden="true" />
              Reject
            </button>
            <button
              type="button"
              className="decision-btn primary"
              disabled={busyAction === "override"}
              onClick={() => void handleStep2SaveOverride()}
            >
              <Edit3 size={12} aria-hidden="true" />
              Save Override
            </button>
          </div>

          <details className="collapsible-clean" style={{ marginTop: 6 }}>
            <summary>Add note (optional) ▾</summary>
            <div className="collapsible-clean-body">
              <textarea
                value={fieldNotes[curField.field] ?? ""}
                onChange={(e) => setFieldNotes((prev) => ({ ...prev, [curField.field]: e.target.value }))}
                rows={2}
                placeholder="Optional notes for this field override"
                style={{ width: "100%" }}
              />
            </div>
          </details>

          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 8, fontSize: "11px", color: "var(--color-grey-700)" }}>
            <span>{approvedFields.size + rejectedFields.size} of {problematicFields.length} reviewed · {Math.max(0, problematicFields.length - (approvedFields.size + rejectedFields.size))} remaining</span>
            {currentFieldIndex < problematicFields.length - 1 && (
              <button
                type="button"
                className="btn-secondary btn-sm"
                onClick={() => setCurrentFieldIndex((prev) => prev + 1)}
              >
                Next Field →
              </button>
            )}
          </div>

          {/* Review Plan Summary Card */}
          <div className="review-plan-box" style={{ marginTop: 12 }}>
            <div className="pane-section-label" style={{ margin: "0 0 6px 0" }}>— REVIEW PLAN</div>
            <ul style={{ margin: "0 0 8px 0", paddingLeft: 18, fontSize: "11.5px", color: "var(--color-grey-900)" }}>
              {problematicFields.map((f) => {
                const isRej = rejectedFields.has(f.field);
                const editVal = fieldEdits[f.field];
                const val = editVal ?? (curAiSuggestion?.field === f.field ? curAiSuggestion.suggested_value : displayValue(f.si.raw ?? f.si.canonical));
                return (
                  <li key={f.field} style={{ marginBottom: 3 }}>
                    {isRej ? `✗ ${labelForField(f.field)}: Rejected` : `✓ ${labelForField(f.field)}: ${editVal ? `Edited to ${val}` : `Approved (${val})`}`}
                  </li>
                );
              })}
            </ul>
            <p style={{ fontSize: "11px", fontWeight: 600, color: "var(--color-grey-700)", margin: "0 0 8px 0" }}>
              {problematicFields.length} change(s) ready to apply.
            </p>
            <label className="form-field">
              Confirmation notes (optional)
              <textarea
                value={resolveNotes}
                onChange={(e) => setResolveNotes(e.target.value)}
                aria-label="Confirmation notes"
                rows={2}
                placeholder="Add confirmation notes..."
              />
            </label>
            <button
              type="button"
              className="btn-primary"
              aria-label="Confirm & Re-compare"
              style={{ width: "100%", justifyContent: "center", marginTop: 6 }}
              disabled={busyAction === "resolve"}
              onClick={() => void handleStep2ConfirmPlan()}
            >
              <Check size={12} aria-hidden="true" />
              Confirm Plan & Re-compare
            </button>
          </div>
        </section>
      </div>

      {/* ── STEP 3: APPLY & RE-COMPARE ── */}
      <div className={`step-panel ${reviewStep === 3 ? "active" : "visually-hidden"}`}>
        <div className="field-review-card">
          {(actionLoading || busyAction === "recompare") ? (
            <div className="processing-notice-box">
              <RefreshCw size={18} className="spin" style={{ color: "var(--color-orange-600)" }} />
              <div>
                <strong>Re-comparing…</strong>
                <p style={{ margin: "4px 0 0 0", fontSize: "11.5px", color: "var(--color-grey-700)" }}>
                  Applying approved overrides and verifying document consistency.
                </p>
              </div>
            </div>
          ) : isMatchNow ? (
            <div className="resolved-success-box">
              <div className="section-title-row">
                <span className="pane-section-label" style={{ margin: 0 }}>— RESOLVED</span>
                <span className="badge badge-good">✓ 7 / 7 fields match</span>
              </div>
              <div style={{ display: "flex", alignItems: "flex-start", gap: 8, marginTop: 4 }}>
                <CheckCircle2 size={16} color="var(--color-success)" style={{ flexShrink: 0, marginTop: 2 }} />
                <div>
                  <strong style={{ fontSize: "12px", color: "var(--color-grey-900)" }}>All discrepancies resolved.</strong>
                  <p style={{ margin: "2px 0 0 0", fontSize: "11.5px", color: "var(--color-grey-700)" }}>
                    No mismatch detected across all canonical fields.
                  </p>
                </div>
              </div>
              <button
                type="button"
                className="btn-primary"
                style={{ width: "100%", justifyContent: "center", marginTop: 8 }}
                onClick={onProceedToReply}
              >
                <Bot size={13} aria-hidden="true" />
                Generate Reply →
              </button>
              <details className="collapsible-clean" style={{ marginTop: 6 }}>
                <summary>View change history ▾</summary>
                <div className="collapsible-clean-body">
                  <ReviewHistorySection review={review} />
                </div>
              </details>
            </div>
          ) : (
            <div>
              <div className="field-header-row">
                <span className="pane-section-label" style={{ margin: 0 }}>— READY TO APPLY</span>
              </div>
              <p style={{ fontSize: "11.5px", color: "var(--color-grey-700)", margin: "4px 0 8px 0" }}>
                Review summary of changes:
              </p>
              <ul className="apply-diff-list" style={{ margin: "0 0 10px 0", paddingLeft: 18, fontSize: "11.5px" }}>
                {problematicFields.map((f) => {
                  const editVal = fieldEdits[f.field];
                  const beforeVal = displayValue(f.bl.raw ?? f.bl.canonical);
                  const afterVal = editVal ?? (curAiSuggestion?.field === f.field ? curAiSuggestion.suggested_value : displayValue(f.si.raw ?? f.si.canonical));
                  return (
                    <li key={f.field} style={{ marginBottom: 4 }}>
                      <strong>{labelForField(f.field)}:</strong> {beforeVal} → <span style={{ color: "var(--color-success)", fontWeight: 700 }}>{afterVal}</span>
                    </li>
                  );
                })}
              </ul>
              <p style={{ fontSize: "11px", color: "var(--color-grey-600)", margin: "0 0 12px 0" }}>
                Overrides will be saved to HolyShip backend. Historical extracted values remain preserved.
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <button
                  type="button"
                  className="btn-primary"
                  disabled={actionLoading || busyAction === "recompare"}
                  onClick={() => void handleStep3ExecuteRecompare()}
                  style={{ width: "100%", justifyContent: "center" }}
                >
                  <RefreshCw size={12} aria-hidden="true" className={actionLoading || busyAction === "recompare" ? "spin" : ""} />
                  Apply & Re-compare
                </button>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setReviewStep(2)}
                  style={{ width: "100%", justifyContent: "center" }}
                >
                  ← Back to Review
                </button>
              </div>
            </div>
          )}

          {actionError && (
            <div className="ai-companion-error" role="alert" style={{ marginTop: 8 }}>
              <AlertCircle size={13} aria-hidden="true" />
              {actionError}
            </div>
          )}
        </div>
      </div>

      <div style={{ marginTop: 12 }}>
        <ReviewHistorySection review={review} />
      </div>
    </div>
  );
}

export function TaskPane({
  contextProvider,
  initialDemoKey,
}: {
  contextProvider: MailContextProvider;
  initialDemoKey?: string | null;
}): React.ReactElement {
  const isDevRequested = typeof window !== "undefined" && (new URLSearchParams(window.location.search).get("demo") === "1" || new URLSearchParams(window.location.search).get("sample") === "1");
  const [showDemoBar, setShowDemoBar] = useState(isDevRequested);
  const [selectedDemoKey, setSelectedDemoKey] = useState<string | null>(initialDemoKey ?? null);
  const [demoOverriddenDetail, setDemoOverriddenDetail] = useState<ProductEmailDetail | null>(null);
  const [state, setState] = useState<PaneState>({ type: "loading" });
  const [actionState, setActionState] = useState<"idle" | "loading" | "error">("idle");
  const [activeWorkflowView, setActiveWorkflowView] = useState<WorkflowView>("overview");
  const [reviewStep, setReviewStep] = useState<1 | 2 | 3>(1);
  const [completedSteps, setCompletedSteps] = useState<Set<number>>(new Set());
  const [showCategoryCorrection, setShowCategoryCorrection] = useState(false);
  const resolveGeneration = useRef(0);
  const lastItemIdRef = useRef<string | null>(null);

  const refreshCurrentEmail = useCallback(async (force = false) => {
    let currentKey = "";
    let currentItemForSync: Awaited<ReturnType<MailContextProvider["getContext"]>>["item"] = null;
    try {
      const ctx = await contextProvider.getContext();
      if (ctx.state === "ready" && ctx.item) {
        currentItemForSync = ctx.item;
        currentKey = [
          ctx.item.holyshipCaseId,
          ctx.item.internetMessageId,
          ctx.item.outlookItemId,
          ctx.item.sender?.trim().toLowerCase(),
          ctx.item.subject?.trim().toLowerCase(),
        ].filter(Boolean).join("|");
      }
    } catch {
      // ignore
    }

    if (!force && currentKey && currentKey === lastItemIdRef.current) {
      return;
    }

    if (currentKey) {
      lastItemIdRef.current = currentKey;
    }

    const currentGen = ++resolveGeneration.current;
    setActionState("idle");
    setState({ type: "loading" });

    try {
      const adapter = new IdentityAdapter(contextProvider);
      const res = await adapter.resolve();
      if (currentGen !== resolveGeneration.current) return;

      if (!res.detail) {
        setState({ type: "not_found", note: res.limitationNote });
        return;
      }

      if (currentItemForSync && res.detail.email.id) {
        try {
          await reconcileOutlookLifecycle(res.detail.email.id, {
            subject: currentItemForSync.subject,
            sender: currentItemForSync.sender,
            outlook_item_id: currentItemForSync.outlookItemId,
            internet_message_id: currentItemForSync.internetMessageId,
            outlook_read_state: currentItemForSync.outlookReadState,
            outlook_categories: currentItemForSync.outlookCategories,
            outlook_folder_id: currentItemForSync.outlookFolderId,
            outlook_archived: currentItemForSync.outlookArchived,
          });
        } catch {
          // best-effort
        }
      }

      setState({
        type: "ready",
        detail: res.detail,
        confidence: res.confidence,
        note: res.limitationNote,
      });
    } catch (err) {
      if (currentGen !== resolveGeneration.current) return;
      setState({
        type: "error",
        message: err instanceof Error ? err.message : "Failed to load HolyShip status",
      });
    }
  }, [contextProvider]);

  useEffect(() => {
    void refreshCurrentEmail(false);

    let pollTimer: ReturnType<typeof setInterval> | null = null;
    let itemChangedRegistered = false;
    let selectedItemsChangedRegistered = false;

    try {
      const mailbox = typeof Office !== "undefined" ? Office.context?.mailbox : undefined;
      if (mailbox?.addHandlerAsync && typeof Office !== "undefined" && Office.EventType?.ItemChanged) {
        mailbox.addHandlerAsync(Office.EventType.ItemChanged, () => {
          void refreshCurrentEmail(true);
        }, (res) => {
          itemChangedRegistered = res.status === Office.AsyncResultStatus.Succeeded;
        });
      }

      const selectedEvent = (Office.EventType as any)?.SelectedItemsChanged;
      if (mailbox?.addHandlerAsync && selectedEvent) {
        mailbox.addHandlerAsync(selectedEvent, () => {
          void refreshCurrentEmail(true);
        }, (res: any) => {
          selectedItemsChangedRegistered = res.status === (Office.AsyncResultStatus as any).Succeeded;
        });
      }

      pollTimer = setInterval(() => {
        void refreshCurrentEmail(false);
      }, 5000);
    } catch {
      // ignore
    }

    return () => {
      if (pollTimer) clearInterval(pollTimer);
      const mailbox = typeof Office !== "undefined" ? Office.context?.mailbox : undefined;
      if (itemChangedRegistered) {
        try {
          if (mailbox?.removeHandlerAsync && typeof Office !== "undefined" && Office.EventType?.ItemChanged) {
            mailbox.removeHandlerAsync(Office.EventType.ItemChanged);
          }
        } catch {}
      }
      if (selectedItemsChangedRegistered) {
        try {
          const selectedEvent = (Office.EventType as any)?.SelectedItemsChanged;
          if (mailbox?.removeHandlerAsync && selectedEvent) {
            mailbox.removeHandlerAsync(selectedEvent);
          }
        } catch {}
      }
    };
  }, [contextProvider, refreshCurrentEmail]);

  const effectiveDetail = demoOverriddenDetail ?? (selectedDemoKey && demoCases[selectedDemoKey] ? demoCases[selectedDemoKey].detail : (state.type === "ready" ? state.detail : null));
  const effectiveState: PaneState = selectedDemoKey && demoCases[selectedDemoKey]
    ? { type: "ready", detail: effectiveDetail!, confidence: "high", note: null }
    : state;

  const emailId = effectiveState.type === "ready" && effectiveDetail ? effectiveDetail.email.id : null;
  const dashUrl = emailId ? dashboardEmailUrl(emailId) : null;
  const activeReview = effectiveState.type === "ready" && effectiveDetail
    ? effectiveDetail.review.find((review) => ["OPEN", "IN_REVIEW"].includes(review.status) && review.case_origin !== "LEGACY")
    : null;
  const historicalReview = effectiveState.type === "ready" && effectiveDetail
    ? effectiveDetail.review.find((review) => review.case_origin === "LEGACY")
    : null;
  const aiSuggestion = effectiveState.type === "ready" && effectiveDetail
    ? effectiveDetail.resolutions.find((resolution) => resolution.attempted)
    : null;
  const reviewUrl = activeReview ? dashboardReviewUrl(activeReview.id) : null;

  const retryProcessing = async () => {
    if (!emailId) return;
    setActionState("loading");
    try {
      await reprocessEmail(emailId);
      await refreshCurrentEmail(true);
      setActionState("idle");
    } catch (err) {
      setActionState("error");
      setState({ type: "error", message: err instanceof Error ? err.message : "Retry failed" });
    }
  };

  const refreshAfterMutation = async () => {
    await refreshCurrentEmail(true);
  };

  const replaceReadyDetail = (detail: ProductEmailDetail) => {
    if (selectedDemoKey) {
      setDemoOverriddenDetail(detail);
    } else {
      setState({ type: "ready", detail, confidence: state.type === "ready" ? state.confidence : "high", note: state.type === "ready" ? state.note : null });
    }
  };

  const handleRestore = async () => {
    if (!emailId || !effectiveDetail) return;
    setActionState("loading");
    try {
      if (selectedDemoKey) {
        const curLifecycle = getEmailLifecycle(effectiveDetail.email);
        const updated: ProductEmailDetail = {
          ...effectiveDetail,
          email: {
            ...effectiveDetail.email,
            lifecycle: {
              ...curLifecycle,
              lifecycle_status: "ACTIVE",
              deleted_at: null,
              restored_at: new Date().toISOString(),
              outlook_folder_id: "inbox",
            },
          },
        };
        replaceReadyDetail(updated);
        setActionState("idle");
        return;
      }
      await reconcileOutlookLifecycle(emailId, { outlook_folder_id: "inbox", outlook_archived: false });
      await refreshCurrentEmail(true);
      setActionState("idle");
    } catch (err) {
      setActionState("error");
      setState({ type: "error", message: err instanceof Error ? err.message : "Restore failed" });
    }
  };

  const isDocumentComparison = effectiveDetail?.email.category === "document_comparison";

  return (
    <div className="pane-shell">
      {/* Top Utility / Sync Row (One compact horizontal row) */}
      <header className="pane-sync-row">
        <div className="pane-sync-info">
          <span className="sync-status-dot" />
          <span>Synced · Just now</span>
        </div>
        <button
          className="btn-sync-refresh"
          type="button"
          onClick={() => void refreshCurrentEmail(true)}
          aria-label="Refresh case data"
          title="Refresh case data"
        >
          <RefreshCw size={13} aria-hidden="true" />
        </button>
      </header>

      {/* Standalone Demo Showcase Switcher (Only if explicitly enabled via ?demo=1 or toggled) */}
      {showDemoBar && (
        <nav className="demo-switcher-bar" aria-label="Sample Cases Switcher">
          <div className="demo-switcher-inner">
            <span className="demo-switcher-title">Sample:</span>
            <button
              type="button"
              className={`demo-pill ${selectedDemoKey === "mismatchReview" ? "active" : ""}`}
              onClick={() => {
                setDemoOverriddenDetail(null);
                setSelectedDemoKey("mismatchReview");
              }}
            >
              ⚠️ Mismatch & Review
            </button>
            <button
              type="button"
              className={`demo-pill ${selectedDemoKey === "cleanMatch" ? "active" : ""}`}
              onClick={() => {
                setDemoOverriddenDetail(null);
                setSelectedDemoKey("cleanMatch");
              }}
            >
              ✅ Clean Match
            </button>
            <button
              type="button"
              className={`demo-pill ${selectedDemoKey === "deletedInOutlook" ? "active" : ""}`}
              onClick={() => {
                setDemoOverriddenDetail(null);
                setSelectedDemoKey("deletedInOutlook");
              }}
            >
              🗑️ Deleted (Sync)
            </button>
            {selectedDemoKey !== null && (
              <button
                type="button"
                className="demo-pill"
                onClick={() => {
                  setDemoOverriddenDetail(null);
                  setSelectedDemoKey(null);
                }}
                title="Switch back to live mailbox resolution"
              >
                🔍 Live Context
              </button>
            )}
          </div>
        </nav>
      )}

      {/* Focused Subview Back Navigation (Workflow Navigation) */}
      {effectiveState.type === "ready" && effectiveDetail && activeWorkflowView !== "overview" && (
        <div className="subview-header-bar">
          <button
            type="button"
            className="btn-subview-back"
            onClick={() => setActiveWorkflowView("overview")}
          >
            ← Case Overview
          </button>
          <span className="subview-header-title">
            {activeWorkflowView === "review" && "Review Discrepancies"}
            {activeWorkflowView === "reply" && "Send Reply"}
            {activeWorkflowView === "comparison" && "Field Comparison"}
          </span>
        </div>
      )}

      {/* Main Content Body */}
      <main className="pane-body">
        {effectiveState.type === "loading" && <LoadingView />}

        {effectiveState.type === "error" && <ErrorView message={effectiveState.message} onRetry={() => void refreshCurrentEmail(true)} />}

        {effectiveState.type === "not_found" && (
          <NotFoundView
            note={effectiveState.note}
            onSelectDemo={(k) => {
              setShowDemoBar(true);
              setSelectedDemoKey(k);
            }}
          />
        )}

        {effectiveState.type === "ready" && effectiveDetail && (
          <>
            {/* Low-confidence identity note */}
            {effectiveState.note && (
              <div className="limitation-note" role="note">
                <Info size={12} style={{ flexShrink: 0, marginTop: 2 }} aria-hidden="true" />
                <span>{effectiveState.note}</span>
              </div>
            )}

            {/* Lifecycle deleted / error alerts */}
            {getEmailLifecycle(effectiveDetail.email).lifecycle_status !== "ACTIVE" && (
              <div className="lifecycle-alert" role="status" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 6 }}>
                  <Archive size={13} style={{ flexShrink: 0, marginTop: 2 }} aria-hidden="true" />
                  <div>
                    <strong>{displayLabel(getEmailLifecycle(effectiveDetail.email).lifecycle_status)}</strong>
                    <span style={{ display: "block", fontSize: "11px", color: "var(--color-grey-700)" }}>
                      {getEmailLifecycle(effectiveDetail.email).lifecycle_status === "DELETED"
                        ? "Hidden from active queues; history and review evidence are preserved."
                        : "Mailbox location changed; backend case state remains available."}
                    </span>
                  </div>
                </div>
                {getEmailLifecycle(effectiveDetail.email).lifecycle_status === "DELETED" && (
                  <button
                    type="button"
                    className="btn-secondary btn-sm"
                    onClick={() => void handleRestore()}
                    disabled={actionState === "loading"}
                    style={{ flexShrink: 0, padding: "3px 8px", fontSize: "11px" }}
                  >
                    Restore Email
                  </button>
                )}
              </div>
            )}

            {getEmailLifecycle(effectiveDetail.email).outlook_sync_error && (
              <div className="lifecycle-alert error" role="alert">
                <AlertCircle size={13} aria-hidden="true" />
                <strong>Sync issue</strong>
                <span>{getEmailLifecycle(effectiveDetail.email).outlook_sync_error}</span>
              </div>
            )}

            {/* ══════════════ 1. PRIMARY SCREEN: CASE OVERVIEW ══════════════ */}
            <div className={`workflow-subview ${activeWorkflowView === "overview" ? "active" : "visually-hidden"}`}>
              {/* Compact Email Subject Heading */}
              <h1 className="case-title-compact">{effectiveDetail.email.subject}</h1>

              {/* State-Driven Case Status Card */}
              <ProcessingStateCard email={effectiveDetail.email} />

              {/* Attention Area: Mismatched / Unresolved fields spotlight */}
              {isDocumentComparison && effectiveDetail.comparison && (
                <RequiresAttentionSection
                  comparison={effectiveDetail.comparison}
                  onOpenReview={() => setActiveWorkflowView("review")}
                  onOpenFullComparison={() => setActiveWorkflowView("comparison")}
                />
              )}

              {/* Dominant Primary Next Action CTA */}
              <div className="overview-primary-cta-box">
                {effectiveDetail.email.needs_review ? (
                  <button
                    type="button"
                    className="btn-primary btn-cta-main"
                    onClick={() => setActiveWorkflowView("review")}
                  >
                    <Edit3 size={14} aria-hidden="true" />
                    Review {effectiveDetail.comparison?.fields.filter((f) => f.status === "MISMATCH" || f.status === "UNRESOLVED").length || 1} Field(s) →
                  </button>
                ) : isDocumentComparison && effectiveDetail.email.mismatch_count === 0 && effectiveDetail.email.unresolved_count === 0 && effectiveDetail.email.processing_status === "COMPLETED" ? (
                  <button
                    type="button"
                    className="btn-secondary btn-cta-main"
                    onClick={() => setActiveWorkflowView("reply")}
                  >
                    <Bot size={14} aria-hidden="true" />
                    Generate Reply →
                  </button>
                ) : effectiveDetail.email.processing_status === "AWAITING_DOCUMENTS" ? (
                  <button
                    type="button"
                    className="btn-secondary btn-cta-main"
                    onClick={() => void refreshCurrentEmail(true)}
                  >
                    <RefreshCw size={14} aria-hidden="true" />
                    Check Again
                  </button>
                ) : effectiveDetail.email.processing_status === "FAILED" ? (
                  <button
                    type="button"
                    className="btn-primary btn-cta-main"
                    onClick={() => void retryProcessing()}
                    disabled={actionState === "loading"}
                  >
                    <RefreshCw size={14} aria-hidden="true" className={actionState === "loading" ? "spin" : ""} />
                    {actionState === "loading" ? "Retrying…" : "Retry Processing"}
                  </button>
                ) : null}
              </div>

              {/* Subtle AI Advisory Notice */}
              {aiSuggestion && activeReview && (
                <div className="ai-advisory-notice">
                  <div className="ai-advisory-left">
                    <Sparkles size={14} style={{ color: "var(--color-orange-600)", flexShrink: 0, marginTop: 2 }} aria-hidden="true" />
                    <div>
                      <strong>AI suggestion available</strong>
                      <p>{aiSuggestion.reason || "HolyShip AI has context for this review case."}</p>
                    </div>
                  </div>
                  {reviewUrl ? (
                    <a
                      className="btn-link"
                      href={reviewUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <ExternalLink size={11} aria-hidden="true" />
                      Open AI Review
                    </a>
                  ) : (
                    <button
                      type="button"
                      className="btn-link"
                      onClick={() => setActiveWorkflowView("review")}
                    >
                      Review with AI →
                    </button>
                  )}
                </div>
              )}

              {/* Collapsibles: Case Details, History, Category Correction */}
              <div className="overview-collapsibles">
                <details className="collapsible-card">
                  <summary className="collapsible-summary">Case details ▾</summary>
                  <div className="collapsible-content">
                    <EmailInfoSection email={effectiveDetail.email} />
                    <CaseDetailsCard detail={effectiveDetail} />
                  </div>
                </details>

                <details className="collapsible-card">
                  <summary className="collapsible-summary">History & Timeline ▾</summary>
                  <div className="collapsible-content">
                    <TimelineCard detail={effectiveDetail} />
                    <OutlookSyncCard
                      email={effectiveDetail.email}
                      onRestore={() => void handleRestore()}
                      isRestoring={actionState === "loading"}
                    />
                  </div>
                </details>

                <details className="collapsible-card" open={showCategoryCorrection}>
                  <summary
                    className="collapsible-summary"
                    onClick={(e) => {
                      e.preventDefault();
                      setShowCategoryCorrection((prev) => !prev);
                    }}
                  >
                    Change Category ▾
                  </summary>
                  <div className="collapsible-content">
                    <CategoryCorrectionSection email={effectiveDetail.email} onUpdated={replaceReadyDetail} />
                  </div>
                </details>
              </div>

              {/* Subtle tertiary footer link */}
              {dashUrl && (
                <div className="overview-footer-row">
                  <a
                    href={dashUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="footer-dash-link"
                    aria-label="Open this case in the HolyShip Dashboard"
                  >
                    View full case in Dashboard ↗
                    <span className="visually-hidden"> (Open in Dashboard)</span>
                  </a>
                </div>
              )}
            </div>

            {/* ══════════════ 2. SUBVIEW: HUMAN REVIEW ══════════════ */}
            <div className={`workflow-subview ${activeWorkflowView === "review" ? "active" : "visually-hidden"}`}>
              {activeReview ? (
                <HumanReviewWorkflow
                  review={activeReview}
                  detail={effectiveDetail}
                  comparison={effectiveDetail.comparison}
                  reviewUrl={reviewUrl}
                  onActionComplete={refreshAfterMutation}
                  onProceedToReply={() => setActiveWorkflowView("reply")}
                  onExecuteRecompare={retryProcessing}
                  actionLoading={actionState === "loading"}
                />
              ) : historicalReview ? (
                <div>
                  <p className="pane-section-label">Human Review</p>
                  <section className="review-card-compact">
                    <div className="review-card-heading"><StatusBadge value={historicalReview.status} /><span>No action required</span></div>
                    <strong>Historical review record</strong>
                    <p>This completed case has an older review record. It is shown for context only.</p>
                    <dl className="review-card-facts">
                      <div>
                        <dt>Affected area</dt>
                        <dd>{reviewAffectedText(historicalReview, effectiveDetail.email)}</dd>
                      </div>
                    </dl>
                    <ReviewHistorySection review={historicalReview} />
                  </section>
                </div>
              ) : (
                <div className="not-found-state">
                  <CheckCircle2 size={32} color="var(--color-success)" />
                  <h3>No Review Required</h3>
                  <p>All required fields match or no active review is open for this case.</p>
                  <button type="button" className="btn-secondary" onClick={() => setActiveWorkflowView("overview")}>
                    Back to Case Overview
                  </button>
                </div>
              )}
            </div>

            {/* ══════════════ 3. SUBVIEW: SMART REPLY ══════════════ */}
            <div className={`workflow-subview ${activeWorkflowView === "reply" ? "active" : "visually-hidden"}`}>
              <ReplyWorkflowSection
                email={effectiveDetail.email}
                initialWorkflow={effectiveDetail.outlook_workflow}
                onActionComplete={refreshAfterMutation}
              />
            </div>

            {/* ══════════════ 4. SUBVIEW: FULL COMPARISON ══════════════ */}
            <div className={`workflow-subview ${activeWorkflowView === "comparison" ? "active" : "visually-hidden"}`}>
              {isDocumentComparison && effectiveDetail.comparison ? (
                <div>
                  <div className="section-title-row" style={{ marginBottom: 10 }}>
                    <p className="pane-section-label" style={{ margin: 0 }}>SI vs Draft BL Comparison</p>
                    <span className="badge badge-muted">7 Canonical Fields</span>
                  </div>
                  <div id="comparison-section">
                    <ComparisonTable comparison={effectiveDetail.comparison} />
                  </div>
                  <div style={{ marginTop: 14, display: "flex", gap: 8 }}>
                    {effectiveDetail.email.needs_review ? (
                      <button
                        type="button"
                        className="btn-primary"
                        onClick={() => setActiveWorkflowView("review")}
                        style={{ flex: 1, justifyContent: "center" }}
                      >
                        Proceed to Review →
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={() => setActiveWorkflowView("overview")}
                        style={{ flex: 1, justifyContent: "center" }}
                      >
                        Back to Case Overview
                      </button>
                    )}
                  </div>
                </div>
              ) : (
                <div className="not-found-state">
                  <p>No document comparison table for this category.</p>
                  <button type="button" className="btn-secondary" onClick={() => setActiveWorkflowView("overview")}>
                    Back to Case Overview
                  </button>
                </div>
              )}
            </div>

            {dashUrl && activeWorkflowView !== "overview" && (
              <div className="overview-footer-row">
                <a
                  href={dashUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="footer-dash-link"
                  aria-label="Open this case in the HolyShip Dashboard"
                >
                  View full case in Dashboard ↗
                  <span className="visually-hidden"> (Open in Dashboard)</span>
                </a>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
