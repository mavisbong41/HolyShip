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
import { useCallback, useEffect, useRef, useState } from "react";
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
import { categoryLabels, displayLabel, formatDate, labelForField, reasonLabels, statusLabels } from "../lib/labels";
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
import { ComparisonTable } from "./ComparisonTable";
import { StatusBadge } from "./StatusBadge";
import { IdentityAdapter } from "../office/IdentityAdapter";

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

function NotFoundView({ note }: { note: string | null }): React.ReactElement {
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
            <h2>No mismatch detected</h2>
            <p>All seven fields match between SI and Draft BL.</p>
          </div>
        );
      }
      return (
        <div className="state-card">
          <div className="state-card-icon icon-bad" aria-hidden="true">
            <AlertTriangle size={18} />
          </div>
          <h2>Confirmed Discrepancy</h2>
          <p>
            {email.mismatch_count > 0 && `${email.mismatch_count} field${email.mismatch_count > 1 ? "s" : ""} mismatched. `}
            {email.unresolved_count > 0 && `${email.unresolved_count} field${email.unresolved_count > 1 ? "s" : ""} unresolved.`}
          </p>
        </div>
      );
    }
    return (
      <div className="state-card">
        <div className="state-card-icon icon-good" aria-hidden="true">
          <CheckCircle2 size={18} />
        </div>
        <h2>Completed</h2>
        <p>{email.category ? categoryLabels[email.category] : "Processed"}</p>
      </div>
    );
  }

  if (status === "AWAITING_DOCUMENTS") {
    return (
      <div className="state-card">
        <div className="state-card-icon icon-warn" aria-hidden="true">
          <Clock size={18} />
        </div>
        <h2>Waiting for Documents</h2>
        <p>
          This is a Document Comparison case. Required documents have not been
          received yet.
        </p>
      </div>
    );
  }

  if ((status === "BLOCKED" || email.needs_review) && status !== "FAILED") {
    return (
      <div className="state-card">
        <div className="state-card-icon icon-warn" aria-hidden="true">
          <AlertTriangle size={18} />
        </div>
        <h2>Needs Review</h2>
        <p>
          {email.review_reason
            ? reasonLabels[email.review_reason] || displayLabel(email.review_reason)
            : "Human Review is required for this case."}
        </p>
      </div>
    );
  }

  if (status === "FAILED") {
    return (
      <div className="state-card">
        <div className="state-card-icon icon-bad" aria-hidden="true">
          <AlertCircle size={18} />
        </div>
        <h2>Processing failed</h2>
        <p>A technical error occurred. Check the Dashboard for details.</p>
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
        <h2>Processing email</h2>
        <p>{progressMsg}</p>
      </div>
    );
  }

  return (
    <div className="state-card">
      <div className="state-card-icon icon-neutral" aria-hidden="true">
        <Info size={18} />
      </div>
      <h2>{statusLabels[email.processing_status] ?? email.processing_status}</h2>
      <p>See Dashboard for details.</p>
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

export function TaskPane({
  contextProvider,
}: {
  contextProvider: MailContextProvider;
}): React.ReactElement {
  const [state, setState] = useState<PaneState>({ type: "loading" });
  const [showComparison, setShowComparison] = useState(true);
  const [actionState, setActionState] = useState<"idle" | "loading" | "error">("idle");
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

    // Prevent redundant fetches when polling finds no change, unless force=true
    if (!force && currentKey && currentKey === lastItemIdRef.current) {
      return;
    }

    if (currentKey) {
      lastItemIdRef.current = currentKey;
    }

    const generation = resolveGeneration.current + 1;
    resolveGeneration.current = generation;

    // 1. Immediately wipe previous email state and show loading
    setState({ type: "loading" });

    try {
      const adapter = new IdentityAdapter(contextProvider);
      const result = await adapter.resolve();
      if (generation !== resolveGeneration.current) return;

      if (!result.detail) {
        setState({
          type: "not_found",
          note: result.limitationNote,
        });
        return;
      }

      if (currentItemForSync) {
        void reconcileOutlookLifecycle(result.detail.email.id, currentItemForSync).catch(() => {
          // Best-effort sync; the pane still renders backend truth and exposes manual refresh.
        });
      }

      setState({
        type: "ready",
        detail: result.detail,
        confidence: result.confidence,
        note: result.limitationNote,
      });
    } catch (err) {
      if (generation !== resolveGeneration.current) return;
      setState({
        type: "error",
        message: err instanceof Error ? err.message : "Unexpected error",
      });
    }
  }, [contextProvider]);

  useEffect(() => {
    let pollTimer: ReturnType<typeof setInterval> | undefined;
    let itemChangedRegistered = false;
    let selectedItemsChangedRegistered = false;

    // 1. Handler: triggers immediately when Outlook fires ItemChanged or SelectedItemsChanged
    const onItemChanged = () => {
      void refreshCurrentEmail(true);
    };

    // 2. Polling fallback: checks contextProvider (including getSelectedItemsAsync) every 700ms
    const checkPollingChange = async () => {
      try {
        const ctx = await contextProvider.getContext();
        if (ctx.state === "ready" && ctx.item) {
          const currentKey = [
            ctx.item.holyshipCaseId,
            ctx.item.internetMessageId,
            ctx.item.outlookItemId,
            ctx.item.sender?.trim().toLowerCase(),
            ctx.item.subject?.trim().toLowerCase(),
          ].filter(Boolean).join("|");

          if (!currentKey) return;

          if (lastItemIdRef.current === null) {
            lastItemIdRef.current = currentKey;
            return;
          }

          if (currentKey !== lastItemIdRef.current) {
            lastItemIdRef.current = currentKey;
            void refreshCurrentEmail(true);
          }
        }
      } catch {
        // ignore
      }
    };

    const register = () => {
      // First open / initial email
      void refreshCurrentEmail(true);

      const mailbox = typeof Office !== "undefined" ? Office.context?.mailbox : undefined;
      if (typeof mailbox?.addHandlerAsync === "function" && typeof Office !== "undefined") {
        if (Office.EventType?.ItemChanged) {
          try {
            mailbox.addHandlerAsync(Office.EventType.ItemChanged, onItemChanged, (asyncResult) => {
              if (asyncResult?.status === Office.AsyncResultStatus.Succeeded) {
                itemChangedRegistered = true;
              }
            });
          } catch {
            // host unsupported
          }
        }

        const selectedEvent = (Office.EventType as any)?.SelectedItemsChanged;
        if (selectedEvent) {
          try {
            mailbox.addHandlerAsync(selectedEvent, onItemChanged, (asyncResult: any) => {
              if (asyncResult?.status === Office.AsyncResultStatus.Succeeded) {
                selectedItemsChangedRegistered = true;
              }
            });
          } catch {
            // host unsupported
          }
        }
      }

      pollTimer = setInterval(() => {
        void checkPollingChange();
      }, 700);
    };

    if (typeof Office !== "undefined" && typeof Office.onReady === "function") {
      Office.onReady(() => {
        register();
      });
    } else {
      register();
    }

    return () => {
      if (pollTimer) {
        clearInterval(pollTimer);
      }
      const mailbox = typeof Office !== "undefined" ? Office.context?.mailbox : undefined;
      if (itemChangedRegistered) {
        try {
          if (mailbox?.removeHandlerAsync && typeof Office !== "undefined" && Office.EventType?.ItemChanged) {
            mailbox.removeHandlerAsync(Office.EventType.ItemChanged);
          }
        } catch {
          // ignore
        }
      }
      if (selectedItemsChangedRegistered) {
        try {
          const selectedEvent = (Office.EventType as any)?.SelectedItemsChanged;
          if (mailbox?.removeHandlerAsync && selectedEvent) {
            mailbox.removeHandlerAsync(selectedEvent);
          }
        } catch {
          // ignore
        }
      }
    };
  }, [contextProvider, refreshCurrentEmail]);

  const emailId = state.type === "ready" ? state.detail.email.id : null;
  const dashUrl = emailId ? dashboardEmailUrl(emailId) : null;
  const activeReview = state.type === "ready"
    ? state.detail.review.find((review) => ["OPEN", "IN_REVIEW"].includes(review.status) && review.case_origin !== "LEGACY")
    : null;
  const historicalReview = state.type === "ready"
    ? state.detail.review.find((review) => review.case_origin === "LEGACY")
    : null;
  const aiSuggestion = state.type === "ready"
    ? state.detail.resolutions.find((resolution) => resolution.attempted)
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
    setState({ type: "ready", detail, confidence: state.type === "ready" ? state.confidence : "high", note: state.type === "ready" ? state.note : null });
  };

  return (
    <div className="pane-shell">
      {/* Header */}
      <header className="pane-header">
        <div className="pane-header-actions">
          <button
            className="pane-icon-btn"
            type="button"
            onClick={() => void refreshCurrentEmail(true)}
            aria-label="Refresh"
            title="Refresh"
          >
            <RefreshCw size={13} aria-hidden="true" />
          </button>
        </div>
      </header>

      {/* Body */}
      <main className="pane-body">
        {state.type === "loading" && <LoadingView />}

        {state.type === "error" && <ErrorView message={state.message} onRetry={() => void refreshCurrentEmail(true)} />}

        {state.type === "not_found" && <NotFoundView note={state.note} />}

        {state.type === "ready" && (
          <>
            {/* Low-confidence identity note */}
            {state.note && (
              <div className="limitation-note" role="note">
                <Info size={12} style={{ flexShrink: 0, marginTop: 2 }} aria-hidden="true" />
                <span>{state.note}</span>
              </div>
            )}

            {getEmailLifecycle(state.detail.email).lifecycle_status !== "ACTIVE" && (
              <div className="lifecycle-alert" role="status">
                <Archive size={13} aria-hidden="true" />
                <strong>{displayLabel(getEmailLifecycle(state.detail.email).lifecycle_status)}</strong>
                <span>
                  {getEmailLifecycle(state.detail.email).lifecycle_status === "DELETED"
                    ? "Hidden from active queues; history and review evidence are preserved."
                    : "Mailbox location changed; backend case state remains available."}
                </span>
              </div>
            )}

            {getEmailLifecycle(state.detail.email).outlook_sync_error && (
              <div className="lifecycle-alert error" role="alert">
                <AlertCircle size={13} aria-hidden="true" />
                <strong>Sync issue</strong>
                <span>{getEmailLifecycle(state.detail.email).outlook_sync_error}</span>
              </div>
            )}

            <section className="email-hero" aria-labelledby="current-email-heading">
              <p className="pane-section-label">Current email</p>
              <h1 id="current-email-heading">{state.detail.email.subject}</h1>
              <p>{state.detail.email.sender || "Unknown sender"} · {formatDate(state.detail.email.received_at ?? state.detail.email.created_at)}</p>
            </section>

            <CaseStatusRail detail={state.detail} />

            {/* Processing state card */}
            <ProcessingStateCard email={state.detail.email} />

            {/* Comparison summary chips */}
            <ComparisonSummaryStrip email={state.detail.email} comparison={state.detail.comparison} />

            <div className="operational-grid" aria-label="Outlook operational workflow">
              <section className="ops-panel">
                <EmailInfoSection email={state.detail.email} />
              </section>
              <CategoryCorrectionSection email={state.detail.email} onUpdated={replaceReadyDetail} />
              <ReplyWorkflowSection
                email={state.detail.email}
                initialWorkflow={state.detail.outlook_workflow}
                onActionComplete={refreshAfterMutation}
              />
            </div>

            {/* Comparison table for document_comparison */}
            {state.detail.email.category === "document_comparison" &&
              state.detail.comparison && (
                <>
                  <div className="pane-divider" />
                  <button
                    className="collapsible-header"
                    type="button"
                    onClick={() => setShowComparison((v) => !v)}
                    aria-expanded={showComparison}
                    aria-controls="comparison-section"
                  >
                    <p className="pane-section-label" style={{ margin: 0 }}>
                      SI vs Draft BL Comparison
                    </p>
                    <span aria-hidden="true">{showComparison ? "▲" : "▼"}</span>
                  </button>
                  {showComparison && (
                    <div id="comparison-section">
                      <ComparisonTable comparison={state.detail.comparison} />
                    </div>
                  )}
                </>
              )}

            {/* Review info */}
            {activeReview && (
              <>
                <div className="pane-divider" />
                <p className="pane-section-label">Human Review</p>
                <section className="review-card-compact">
                  <div className="review-card-heading"><StatusBadge value={activeReview.status} /><span>{activeReview.reviewer_name || "Unassigned"}</span></div>
                  <strong>{reasonLabels[activeReview.reason_code] || displayLabel(activeReview.reason_code)}</strong>
                  <p>{activeReview.reason_text}</p>
                  <dl className="review-card-facts">
                    <div>
                      <dt>{activeReview.field ? "Affected field" : "Affected area"}</dt>
                      <dd>{reviewAffectedText(activeReview, state.detail.email)}</dd>
                    </div>
                    <div>
                      <dt>Suggested action</dt>
                      <dd>{reviewSuggestedAction(activeReview)}</dd>
                    </div>
                  </dl>
                  {reviewUrl ? <a className="btn-primary" href={reviewUrl} target="_blank" rel="noopener noreferrer"><ExternalLink size={12} aria-hidden="true" />Open Human Review</a> : null}
                </section>

                <AICompanionSection
                  reviewId={activeReview.id}
                  reviewUrl={reviewUrl}
                  onActionComplete={refreshAfterMutation}
                />
                <ExistingSuggestionsSection
                  review={activeReview}
                  onActionComplete={refreshAfterMutation}
                />
                <DirectReviewActions
                  review={activeReview}
                  comparison={state.detail.comparison}
                  onActionComplete={refreshAfterMutation}
                />
                <ReviewHistorySection review={activeReview} />
              </>
            )}

            {!activeReview && historicalReview && (
              <>
                <div className="pane-divider" />
                <p className="pane-section-label">Human Review</p>
                <section className="review-card-compact">
                  <div className="review-card-heading"><StatusBadge value={historicalReview.status} /><span>No action required</span></div>
                  <strong>Historical review record</strong>
                  <p>This completed case has an older review record. It is shown for context only.</p>
                  <dl className="review-card-facts">
                    <div>
                      <dt>Affected area</dt>
                      <dd>{reviewAffectedText(historicalReview, state.detail.email)}</dd>
                    </div>
                  </dl>
                  <ReviewHistorySection review={historicalReview} />
                </section>
              </>
            )}

            {aiSuggestion && activeReview && reviewUrl && (
              <>
                <div className="pane-divider" />
                <p className="pane-section-label">AI Companion</p>
                <section className="review-card-compact">
                  <div className="review-card-heading"><StatusBadge value="info" tone="info" /><span>AI explanation available</span></div>
                  <strong>AI suggestion available</strong>
                  <p>{aiSuggestion.reason || "HolyShip AI has context for this review case."}</p>
                  <a className="btn-secondary" href={reviewUrl} target="_blank" rel="noopener noreferrer"><ExternalLink size={12} aria-hidden="true" />Open AI Review</a>
                </section>
              </>
            )}

            {/* Actions */}
            <div className="pane-divider" />
            <div className="pane-action-row">
              {dashUrl && (
                <a
                  href={dashUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-primary"
                  aria-label="Open this case in the HolyShip Dashboard"
                >
                  <ExternalLink size={12} aria-hidden="true" />
                  Open in Dashboard
                </a>
              )}
              {state.detail.email.processing_status === "FAILED" ? (
                <button className="btn-primary" type="button" disabled={actionState === "loading"} onClick={() => void retryProcessing()}>
                  <RefreshCw size={12} aria-hidden="true" />
                  {actionState === "loading" ? "Retrying…" : "Retry / Reprocess"}
                </button>
              ) : null}
              <button
                type="button"
                className="btn-secondary"
                onClick={() => void refreshCurrentEmail(true)}
                aria-label="Refresh case data"
              >
                <RefreshCw size={12} aria-hidden="true" />
                Refresh
              </button>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
