import React from "react";
import { Check, Edit3, X, AlertTriangle, ShieldCheck, FileText } from "lucide-react";
import type { ProductAISuggestion, AISuggestionPayload } from "../../api/types";
import { labelForField } from "../../lib/labels";

interface AISuggestionCardProps {
  suggestion: ProductAISuggestion | AISuggestionPayload;
  suggestionId?: string;
  onAccept: (suggestionId: string) => void;
  onOpenEdit: (suggestion: ProductAISuggestion | AISuggestionPayload, suggestionId?: string) => void;
  onDismiss: (suggestionId: string) => void;
  isActionLoading?: boolean;
}

export function AISuggestionCard({
  suggestion,
  suggestionId,
  onAccept,
  onOpenEdit,
  onDismiss,
  isActionLoading = false,
}: AISuggestionCardProps): React.ReactElement {
  const sid = suggestionId || ("id" in suggestion ? (suggestion as ProductAISuggestion).id : "");
  const status = "status" in suggestion ? (suggestion as ProductAISuggestion).status : "PENDING";
  const fieldName = suggestion.field ? labelForField(suggestion.field) : "Field";
  const side = suggestion.document_side || "BL";
  const confidencePct = suggestion.confidence != null ? Math.round(suggestion.confidence * 100) : null;

  return (
    <article className="ai-suggestion-card" aria-label="AI Field Override Suggestion">
      <div className="suggestion-header">
        <div className="suggestion-target">
          <ShieldCheck size={16} className="text-orange" aria-hidden="true" />
          <strong>AI Proposed Override: {side} · {fieldName}</strong>
        </div>
        {confidencePct != null && (
          <span className="badge badge-info">{confidencePct}% confidence</span>
        )}
      </div>

      <div className="suggestion-values-grid">
        <div className="suggestion-val-box">
          <span className="val-caption">Current {side} value</span>
          <code className="val-code">{suggestion.current_value || "—"}</code>
        </div>
        <div className="suggestion-val-box proposed">
          <span className="val-caption">AI Suggested value</span>
          <code className="val-code highlight">{suggestion.suggested_value || "—"}</code>
        </div>
      </div>

      {suggestion.reason && (
        <p className="suggestion-reason">
          <strong>Reason:</strong> {suggestion.reason}
        </p>
      )}

      {suggestion.evidence_refs && suggestion.evidence_refs.length > 0 && (
        <div className="suggestion-evidence-list">
          <span className="val-caption">Grounding Evidence:</span>
          <ul>
            {suggestion.evidence_refs.map((refText, i) => (
              <li key={i}>
                <FileText size={12} aria-hidden="true" />
                <span>{refText}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="suggestion-notice">
        <AlertTriangle size={14} aria-hidden="true" />
        <span>
          Original extraction is preserved. Approving stages this proposal into the Review Plan for confirmation and re-comparison.
        </span>
      </div>

      {status === "PENDING" ? (
        <div className="suggestion-actions">
          <button
            type="button"
            className="button-primary btn-sm"
            aria-label="Approve Suggestion (Accept & Implement)"
            disabled={isActionLoading || !sid}
            onClick={() => onAccept(sid)}
          >
            <Check size={14} aria-hidden="true" />
            Approve Suggestion (Accept & Implement)
          </button>
          <button
            type="button"
            className="button-secondary btn-sm"
            aria-label="Edit Before Applying"
            disabled={isActionLoading}
            onClick={() => onOpenEdit(suggestion, sid)}
          >
            <Edit3 size={14} aria-hidden="true" />
            Edit Before Applying
          </button>
          <button
            type="button"
            className="button-danger-secondary btn-sm"
            aria-label="Dismiss"
            disabled={isActionLoading || !sid}
            onClick={() => onDismiss(sid)}
          >
            <X size={14} aria-hidden="true" />
            Dismiss
          </button>
        </div>
      ) : (
        <div className="suggestion-resolved-status">
          <span className={`badge badge-${status === "ACCEPTED" ? "good" : status === "EDITED_APPLIED" ? "info" : "muted"}`}>
            {status === "ACCEPTED" ? "Accepted & Implemented" : status === "EDITED_APPLIED" ? "Edited & Implemented" : "Dismissed"}
          </span>
        </div>
      )}
    </article>
  );
}
