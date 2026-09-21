import {
  AlertCircle,
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock,
  ExternalLink,
  FileSearch,
  FileText,
  Info,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { askAIAssistant, reprocessEmail } from "../api/client";
import { dashboardEmailUrl, dashboardReviewUrl } from "../lib/config";
import { categoryLabels, displayLabel, formatDate, labelForField, reasonLabels, statusLabels } from "../lib/labels";
import type { MailContextProvider, MailContextResult } from "../types/context";
import type {
  AIAssistantResponse,
  ProductComparison,
  ProductEmailDetail,
  ProductEmailSummary,
  ProductReview,
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

function contextIdentityKey(context: MailContextResult): string {
  if (context.state !== "ready" || !context.item) {
    return "";
  }

  const { holyshipCaseId, internetMessageId, outlookItemId, sender, subject } = context.item;
  return [
    holyshipCaseId,
    internetMessageId,
    outlookItemId,
    sender?.trim().toLowerCase(),
    subject?.trim().toLowerCase(),
  ]
    .filter(Boolean)
    .join("|");
}

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
}: {
  reviewId: string;
  reviewUrl: string | null;
}): React.ReactElement {
  const [isAsking, setIsAsking] = useState(false);
  const [response, setResponse] = useState<AIAssistantResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastQuestion, setLastQuestion] = useState<string | null>(null);

  const handleAsk = async (question: string) => {
    setIsAsking(true);
    setError(null);
    setLastQuestion(question);
    try {
      const resp = await askAIAssistant(reviewId, question);
      setResponse(resp);
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI Assistant unavailable");
    } finally {
      setIsAsking(false);
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

  const resolve = useCallback(async () => {
    const generation = resolveGeneration.current + 1;
    resolveGeneration.current = generation;
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


  // Refresh: full page reload so Office.js re-initialises and binds to the
  // email that is currently open in the reading pane.  This is the most reliable
  // way to switch context in New Outlook where mailbox.item can lag.
  const refresh = useCallback(() => {
    window.location.reload();
  }, []);


  useEffect(() => {
    void resolve();

    let mounted = true;
    let lastContextKey: string | null = null;

    const checkForContextChange = async () => {
      try {
        const context = await contextProvider.getContext();
        if (!mounted) return;

        const currentKey = contextIdentityKey(context);
        if (!currentKey) return;

        if (lastContextKey === null) {
          // First read: record current key without triggering another resolve
          lastContextKey = currentKey;
          return;
        }

        if (currentKey !== lastContextKey) {
          // Email changed detected via polling — reload to pick up new context
          window.location.reload();
        }
      } catch {
        // ignore transient failures
      }
    };

    void checkForContextChange();

    // 1. Listen for Office.js ItemChanged events when user switches emails in Outlook.
    const mailbox = typeof Office !== "undefined" ? Office.context?.mailbox : undefined;
    let itemChangedRegistered = false;

    // When the user clicks a different email, reload the entire page.
    // This is the most reliable approach for New Outlook where mailbox.item and
    // getSelectedItemsAsync can both lag or return stale data.
    // After reload, Office.js re-initialises and binds to the currently open email.
    const onItemChanged = () => {
      window.location.reload();
    };

    if (mailbox?.addHandlerAsync && typeof Office !== "undefined" && Office.EventType?.ItemChanged) {
      try {
        mailbox.addHandlerAsync(Office.EventType.ItemChanged, onItemChanged, (asyncResult) => {
          if (asyncResult.status === Office.AsyncResultStatus.Succeeded) {
            itemChangedRegistered = true;
          }
        });
      } catch {
        // Office context not fully available or unsupported host
      }
    }

    // 2. Polling fallback: if ItemChanged doesn't fire (e.g. taskpane not pinned),
    //    detect the change via getSelectedItemsAsync / mailbox.item and reload.
    const interval = setInterval(() => {
      void checkForContextChange();
    }, 800);

    return () => {
      mounted = false;
      clearInterval(interval);
      if (itemChangedRegistered && mailbox?.removeHandlerAsync && typeof Office !== "undefined" && Office.EventType?.ItemChanged) {
        try {
          mailbox.removeHandlerAsync(Office.EventType.ItemChanged);
        } catch {
          // ignore
        }
      }
    };
  }, [resolve]);

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
      await refresh();
      setActionState("idle");
    } catch (err) {
      setActionState("error");
      setState({ type: "error", message: err instanceof Error ? err.message : "Retry failed" });
    }
  };

  return (
    <div className="pane-shell">
      {/* Header */}
      <header className="pane-header">
        <div className="pane-header-actions">
          <button
            className="pane-icon-btn"
            type="button"
            onClick={() => void refresh()}
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

        {state.type === "error" && <ErrorView message={state.message} onRetry={() => void resolve()} />}

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

            <section className="email-hero" aria-labelledby="current-email-heading">
              <p className="pane-section-label">Current email</p>
              <h1 id="current-email-heading">{state.detail.email.subject}</h1>
              <p>{state.detail.email.sender || "Unknown sender"} · {formatDate(state.detail.email.received_at ?? state.detail.email.created_at)}</p>
            </section>

            {/* Processing state card */}
            <ProcessingStateCard email={state.detail.email} />

            {/* Comparison summary chips */}
            <ComparisonSummaryStrip email={state.detail.email} comparison={state.detail.comparison} />

            {/* Email info */}
            <EmailInfoSection email={state.detail.email} />

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

                <AICompanionSection reviewId={activeReview.id} reviewUrl={reviewUrl} />
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
                onClick={() => void refresh()}
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
