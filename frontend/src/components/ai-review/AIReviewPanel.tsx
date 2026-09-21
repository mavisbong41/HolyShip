import React, { useState, useEffect } from "react";
import { Send, Bot, AlertCircle, RefreshCw, Sparkles } from "lucide-react";
import type { ProductReview, ProductAISuggestion, AISuggestionPayload } from "../../api/types";
import {
  askAIAssistant,
  acceptAISuggestion,
  applyEditedAISuggestion,
  dismissAISuggestion,
} from "../../api/aiReview";
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
  }, [review.id]);

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

  return (
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
          className="button-primary btn-sm"
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
  );
}
