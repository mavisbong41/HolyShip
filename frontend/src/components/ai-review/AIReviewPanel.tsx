import React, { useState, useEffect } from "react";
import { Send, Bot, AlertCircle, RefreshCw, Sparkles, Plus, Trash2, X } from "lucide-react";
import type { ProductReview, ProductAISuggestion, AISuggestionPayload, ProductReviewPlan } from "../../api/types";
import {
  askAIAssistant,
  acceptAISuggestion,
  applyEditedAISuggestion,
  dismissAISuggestion,
  listReviewPlans,
  createReviewPlan,
  updateReviewPlanItem,
  confirmReviewPlan,
  createManualReviewPlan,
  addManualReviewPlanItem,
  removeManualReviewPlanItem,
  cancelReviewPlan,
} from "../../api/aiReview";
import { getHumanReviewDetail } from "../../api/client";
import { SuggestedQuestions } from "./SuggestedQuestions";
import { AIChatThread, ChatMessage } from "./AIChatThread";
import { AIEditSuggestionDialog } from "./AIEditSuggestionDialog";

interface AIReviewPanelProps {
  review: ProductReview;
  reviewerName: string;
  onCaseUpdated: (updated: ProductReview) => void;
}

export function AIReviewPanel({
  review,
  reviewerName,
  onCaseUpdated,
}: AIReviewPanelProps): React.ReactElement {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputQuestion, setInputQuestion] = useState("");
  const [isAsking, setIsAsking] = useState(false);
  const [isActionLoading, setIsActionLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [plan, setPlan] = useState<ProductReviewPlan | null>(null);
  const [showManualForm, setShowManualForm] = useState(false);
  const [manualSide, setManualSide] = useState<"SI" | "BL">("BL");
  const [manualField, setManualField] = useState("shipper");
  const [manualCurrentValue, setManualCurrentValue] = useState("");
  const [manualProposedValue, setManualProposedValue] = useState("");
  const [manualReason, setManualReason] = useState("");

  // Edit dialog state
  const [editingSuggestion, setEditingSuggestion] = useState<{
    suggestion: ProductAISuggestion | AISuggestionPayload;
    suggestionId: string;
  } | null>(null);

  // Load existing suggestions from review object when review changes
  useEffect(() => {
    if (review.ai_suggestions && review.ai_suggestions.length > 0) {
      const initialMsgs: ChatMessage[] = review.ai_suggestions.map((s) => ({
        id: s.id,
        sender: "ai",
        text: s.message,
        mode: s.mode,
        suggestion: s,
        suggestionId: s.id,
        providerModel: s.provider_model,
        timestamp: new Date(s.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      }));
      setMessages(initialMsgs);
    } else {
      setMessages([]);
    }
    setErrorMessage(null);
    void listReviewPlans(review.id).then((plans) => setPlan(plans.find((item) => item.status !== "CANCELLED") ?? null)).catch(() => setPlan(null));
  }, [review.id]);

  const canonicalFields = [
    "shipper", "consignee", "notify_party", "port_of_loading",
    "port_of_discharge", "container_count", "gross_weight_kg",
  ];

  const beginManualCorrection = () => {
    const comparisonField = review.comparison?.fields.find((item) => item.field === manualField);
    const value = manualSide === "SI" ? comparisonField?.si : comparisonField?.bl;
    setManualCurrentValue(String(value?.canonical ?? value?.raw ?? ""));
    setShowManualForm(true);
  };

  const saveManualCorrection = async () => {
    if (!manualProposedValue.trim() || !manualReason.trim()) return;
    setIsActionLoading(true);
    setErrorMessage(null);
    try {
      const item = {
        document_side: manualSide, field: manualField,
        current_value: manualCurrentValue, proposed_value: manualProposedValue,
        reason: manualReason,
      };
      const updated = plan
        ? await addManualReviewPlanItem(review.id, plan.id, reviewerName || "Reviewer", item)
        : await createManualReviewPlan(review.id, reviewerName || "Reviewer", item);
      setPlan(updated);
      setShowManualForm(false);
      setManualProposedValue("");
      setManualReason("");
    } catch (caught) {
      setErrorMessage(caught instanceof Error ? caught.message : "Could not add manual correction");
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleAsk = async (question: string) => {
    const qTrim = question.trim();
    if (!qTrim || isAsking) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: "user",
      text: qTrim,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputQuestion("");
    setIsAsking(true);
    setErrorMessage(null);

    try {
      const resp = await askAIAssistant(review.id, qTrim);
      const aiMsg: ChatMessage = {
        id: resp.suggestion_id || `ai-${Date.now()}`,
        sender: "ai",
        text: resp.message,
        mode: resp.mode,
        suggestion: resp.suggestion,
        suggestionId: resp.suggestion_id || undefined,
        providerModel: resp.provider_model,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (caught) {
      setErrorMessage(
        caught instanceof Error ? caught.message : "AI Assistant is currently unavailable. Manual review is fully operational.",
      );
    } finally {
      setIsAsking(false);
    }
  };

  const handleAcceptSuggestion = async (suggestionId: string) => {
    if (!suggestionId || isActionLoading) return;
    setIsActionLoading(true);
    setErrorMessage(null);
    try {
      const updatedReview = await acceptAISuggestion(review.id, suggestionId, reviewerName || "Reviewer");
      setMessages((current) => current.map((message) => {
        if (message.suggestionId !== suggestionId) return message;
        const updatedSuggestion = updatedReview.ai_suggestions?.find((item) => item.id === suggestionId);
        return updatedSuggestion ? { ...message, suggestion: updatedSuggestion } : message;
      }));
      onCaseUpdated(updatedReview);
    } catch (caught) {
      setErrorMessage(caught instanceof Error ? caught.message : "Failed to accept AI suggestion");
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleOpenEdit = (
    suggestion: ProductAISuggestion | AISuggestionPayload,
    suggestionId?: string,
  ) => {
    const sid = suggestionId || ("id" in suggestion ? (suggestion as ProductAISuggestion).id : "");
    if (!sid) return;
    setEditingSuggestion({ suggestion, suggestionId: sid });
  };

  const handleApplyEdited = async (
    suggestionId: string,
    value: string,
    reviewerLabel: string,
    note?: string,
  ) => {
    setIsActionLoading(true);
    setErrorMessage(null);
    try {
      const updatedReview = await applyEditedAISuggestion(
        review.id,
        suggestionId,
        value,
        reviewerLabel,
        note,
      );
      setMessages((current) => current.map((message) => {
        if (message.suggestionId !== suggestionId) return message;
        const updatedSuggestion = updatedReview.ai_suggestions?.find((item) => item.id === suggestionId);
        return updatedSuggestion ? { ...message, suggestion: updatedSuggestion } : message;
      }));
      onCaseUpdated(updatedReview);
    } catch (caught) {
      setErrorMessage(caught instanceof Error ? caught.message : "Failed to apply edited suggestion");
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleDismissSuggestion = async (suggestionId: string) => {
    if (!suggestionId || isActionLoading) return;
    setIsActionLoading(true);
    setErrorMessage(null);
    try {
      const updatedReview = await dismissAISuggestion(review.id, suggestionId, reviewerName || "Reviewer");
      onCaseUpdated(updatedReview);
    } catch (caught) {
      setErrorMessage(caught instanceof Error ? caught.message : "Failed to dismiss AI suggestion");
    } finally {
      setIsActionLoading(false);
    }
  };

  const unresolvedCount = review.comparison?.fields.filter((f) => f.status === "UNRESOLVED").length ?? 0;
  const pendingSuggestionsCount = (review.ai_suggestions ?? []).filter((s) => s.status === "PENDING").length;
  const [reviewActionsOpen, setReviewActionsOpen] = useState(false);

  return (
    <div className="ai-review-wrapper" id="ai-review-assistant-section">
      <section className="detail-section ai-review-container" role="region" aria-label="AI Review Assistant">
        <div className="ai-panel-header">
          <div className="ai-panel-title">
            <Bot size={18} className="text-orange" aria-hidden="true" />
            <div>
              <h3>AI Review Assistant</h3>
              <p className="subtle">Grounded case reasoning &amp; field override proposals</p>
            </div>
          </div>
          <span className="badge badge-info">Evidence Grounded</span>
        </div>

        <SuggestedQuestions
          onSelectQuestion={(q) => void handleAsk(q)}
          disabled={isAsking}
        />

        <AIChatThread
          messages={messages}
          onAcceptSuggestion={handleAcceptSuggestion}
          onOpenEditSuggestion={handleOpenEdit}
          onDismissSuggestion={handleDismissSuggestion}
          isActionLoading={isActionLoading}
        />

        {isAsking && (
          <div className="ai-asking-indicator" role="status">
            <RefreshCw size={14} className="spin-icon" aria-hidden="true" />
            <span>Analyzing evidence and formulating response…</span>
          </div>
        )}

        {errorMessage && (
          <div className="state-note warn" role="alert" style={{ marginTop: 12 }}>
            <AlertCircle size={14} aria-hidden="true" />
            <div>
              <strong>AI Assistant Notice</strong>
              <span>{errorMessage}</span>
            </div>
          </div>
        )}

        <form
          className="ai-chat-input-row"
          onSubmit={(e) => {
            e.preventDefault();
            void handleAsk(inputQuestion);
          }}
        >
          <input
            type="text"
            className="ai-input"
            placeholder="Ask a question about this case's documents or discrepancy…"
            value={inputQuestion}
            onChange={(e) => setInputQuestion(e.target.value)}
            disabled={isAsking}
            aria-label="Ask AI Assistant"
          />
          <button
            type="submit"
            className="button-primary btn-sm btn-dark-charcoal"
            disabled={isAsking || !inputQuestion.trim()}
            aria-label="Send question to AI Assistant"
          >
            <Send size={14} aria-hidden="true" />
            Ask AI
          </button>
        </form>

        {editingSuggestion && (
          <AIEditSuggestionDialog
            suggestion={editingSuggestion.suggestion}
            suggestionId={editingSuggestion.suggestionId}
            defaultReviewer={reviewerName}
            isOpen={true}
            onClose={() => setEditingSuggestion(null)}
            onSubmit={handleApplyEdited}
            isLoading={isActionLoading}
          />
        )}
      </section>

      <section
        className="detail-section review-actions-collapsible"
        role="region"
        aria-label="Structured Review Plan"
        id="review-actions-section"
      >
        <div
          className="review-actions-header"
          role="button"
          tabIndex={0}
          onClick={() => setReviewActionsOpen((prev) => !prev)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              setReviewActionsOpen((prev) => !prev);
            }
          }}
          aria-expanded={reviewActionsOpen || Boolean(plan) || showManualForm}
        >
          <div className="review-actions-title-row">
            <span className="section-chevron">{reviewActionsOpen || Boolean(plan) || showManualForm ? "▾" : "▸"}</span>
            <strong>Review Actions</strong>
            <span className="review-actions-summary subtle">
              {unresolvedCount} unresolved {unresolvedCount === 1 ? "field" : "fields"} · {pendingSuggestionsCount} pending {pendingSuggestionsCount === 1 ? "suggestion" : "suggestions"}
            </span>
          </div>
          {plan && <span className="badge badge-info">{plan.status}</span>}
        </div>

        {reviewActionsOpen || Boolean(plan) || showManualForm ? (
          <div className="review-actions-body" style={{ marginTop: 12 }}>
            {!plan ? (
              <div className="review-actions-empty-row">
                {pendingSuggestionsCount > 0 ? (
                  <button
                    type="button"
                    className="button-secondary btn-sm"
                    disabled={isActionLoading}
                    onClick={() => {
                      setIsActionLoading(true);
                      void createReviewPlan(review, reviewerName || "Reviewer")
                        .then(setPlan)
                        .catch((error) => setErrorMessage(error instanceof Error ? error.message : "Could not create review plan"))
                        .finally(() => setIsActionLoading(false));
                    }}
                  >
                    Create Plan from Pending Suggestions
                  </button>
                ) : (
                  <span className="subtle">No pending suggestions.</span>
                )}
                <button
                  type="button"
                  className="button-secondary btn-sm"
                  style={{ marginLeft: 8 }}
                  onClick={beginManualCorrection}
                >
                  <Plus size={12} /> Add Manual Correction
                </button>
              </div>
            ) : (
              <>
                {plan.items.map((item) => (
                  <article key={item.id} className="suggestion-val-box" style={{ marginTop: 8 }}>
                    <div className="suggestion-header">
                      <strong>{item.document_side} · {item.field}</strong>
                      <span className="badge badge-info">{item.ai_suggestion_id ? "AI proposal" : "Manual correction"}</span>
                    </div>
                    <small>Current / effective value: {String(item.current_value ?? "—")}</small>
                    <p>{item.reason || "No note supplied"}</p>
                    <input
                      aria-label={`Proposed value for ${item.field}`}
                      defaultValue={String(item.human_edited_value ?? item.proposed_value ?? "")}
                      disabled={plan.status !== "DRAFT"}
                      onBlur={(event) => {
                        if (event.target.value !== String(item.proposed_value ?? "")) {
                          void updateReviewPlanItem(review.id, plan.id, item.id, "EDITED", event.target.value).then(setPlan);
                        }
                      }}
                    />
                    {plan.status === "DRAFT" && (
                      <div className="suggestion-actions">
                        <button type="button" className="button-primary btn-sm" onClick={() => void updateReviewPlanItem(review.id, plan.id, item.id, "APPROVED").then(setPlan)}>Approve</button>
                        <button type="button" className="button-danger-secondary btn-sm" onClick={() => void updateReviewPlanItem(review.id, plan.id, item.id, "REJECTED").then(setPlan)}>Reject</button>
                        {!item.ai_suggestion_id && (
                          <button
                            type="button"
                            className="button-danger-secondary btn-sm"
                            aria-label={`Remove manual correction ${item.field}`}
                            onClick={() => void removeManualReviewPlanItem(review.id, plan.id, item.id, reviewerName || "Reviewer").then(setPlan)}
                          >
                            <Trash2 size={12} /> Remove
                          </button>
                        )}
                      </div>
                    )}
                  </article>
                ))}
                {(plan.status === "DRAFT" || plan.status === "APPLY_FAILED") && (
                  <div style={{ marginTop: 12, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    {plan.status === "DRAFT" && (
                      <button type="button" className="button-secondary btn-sm" onClick={beginManualCorrection}>
                        <Plus size={12} /> Add Manual Correction
                      </button>
                    )}
                    <button
                      type="button"
                      className="button-primary btn-sm btn-dark-charcoal"
                      disabled={plan.status === "DRAFT" && !plan.items.some((item) => item.status === "APPROVED" || item.status === "EDITED")}
                      onClick={() =>
                        void confirmReviewPlan(review.id, plan.id, reviewerName || "Reviewer")
                          .then(async (updated) => {
                            setPlan(updated);
                            onCaseUpdated(await getHumanReviewDetail(review.id));
                          })
                          .catch((error) => setErrorMessage(error instanceof Error ? error.message : "Plan application failed"))
                      }
                    >
                      {plan.status === "APPLY_FAILED" ? "Retry Re-comparison" : "Confirm Implementation & Recompare"}
                    </button>
                    {plan.status === "DRAFT" && (
                      <button
                        type="button"
                        className="button-secondary btn-sm"
                        onClick={() => void cancelReviewPlan(review.id, plan.id, reviewerName || "Reviewer").then(() => setPlan(null))}
                      >
                        <X size={12} /> Cancel / Back
                      </button>
                    )}
                  </div>
                )}
                {plan.error_message && (
                  <p className="state-note warn">Overrides were preserved. Re-comparison can be retried: {plan.error_message}</p>
                )}
              </>
            )}

            {showManualForm && (
              <div className="suggestion-val-box manual-correction-card" style={{ marginTop: 12 }} aria-label="Add Manual Correction">
                <div className="manual-correction-title">
                  <Plus size={14} className="text-orange" aria-hidden="true" />
                  <strong>Manual correction</strong>
                </div>

                <div className="manual-form-grid">
                  <div className="manual-field-group">
                    <label className="manual-field-label" htmlFor="manual-side-select">Document side</label>
                    <select
                      id="manual-side-select"
                      className="manual-field-select"
                      value={manualSide}
                      onChange={(event) => setManualSide(event.target.value as "SI" | "BL")}
                    >
                      <option value="SI">SI</option>
                      <option value="BL">Draft BL</option>
                    </select>
                  </div>

                  <div className="manual-field-group">
                    <label className="manual-field-label" htmlFor="manual-field-select">Field</label>
                    <select
                      id="manual-field-select"
                      className="manual-field-select"
                      value={manualField}
                      onChange={(event) => {
                        setManualField(event.target.value);
                        setManualCurrentValue("");
                      }}
                    >
                      {canonicalFields.map((field) => (
                        <option key={field} value={field}>{field}</option>
                      ))}
                    </select>
                  </div>

                  <div className="manual-field-group manual-form-row-full">
                    <label className="manual-field-label" htmlFor="manual-current-val">Current / Effective Value</label>
                    <input
                      id="manual-current-val"
                      className="manual-field-input"
                      value={manualCurrentValue}
                      onChange={(event) => setManualCurrentValue(event.target.value)}
                      placeholder="e.g. Current extracted value"
                    />
                  </div>

                  <div className="manual-field-group manual-form-row-full">
                    <label className="manual-field-label" htmlFor="manual-proposed-val">Proposed Corrected Value</label>
                    <input
                      id="manual-proposed-val"
                      className="manual-field-input"
                      aria-label="Proposed Corrected Value"
                      value={manualProposedValue}
                      onChange={(event) => setManualProposedValue(event.target.value)}
                      placeholder="Enter proposed corrected value"
                    />
                  </div>

                  <div className="manual-field-group manual-form-row-full">
                    <label className="manual-field-label" htmlFor="manual-reason">Reason / Note</label>
                    <textarea
                      id="manual-reason"
                      className="manual-field-textarea"
                      aria-label="Reason / Note"
                      value={manualReason}
                      onChange={(event) => setManualReason(event.target.value)}
                      placeholder="Explain the rationale for this manual correction..."
                    />
                  </div>
                </div>

                <div className="manual-form-actions">
                  <button
                    type="button"
                    className="button-primary btn-sm btn-dark-charcoal"
                    disabled={isActionLoading || !manualProposedValue.trim() || !manualReason.trim()}
                    onClick={() => void saveManualCorrection()}
                  >
                    Add to Plan
                  </button>
                  <button type="button" className="button-secondary btn-sm" onClick={() => setShowManualForm(false)}>
                    Back
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="review-actions-collapsed-strip" style={{ marginTop: 8, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span className="subtle" style={{ fontSize: "12px" }}>No pending suggestions.</span>
            <button
              type="button"
              className="button-secondary btn-sm"
              onClick={beginManualCorrection}
            >
              <Plus size={12} /> Add Manual Correction
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
