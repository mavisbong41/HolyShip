import React, { useState } from "react";
import { X, CheckCircle2 } from "lucide-react";
import type { ProductAISuggestion, AISuggestionPayload } from "../../api/types";
import { labelForField } from "../../lib/labels";

interface AIEditSuggestionDialogProps {
  suggestion: ProductAISuggestion | AISuggestionPayload;
  suggestionId: string;
  defaultReviewer: string;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (suggestionId: string, value: string, reviewerLabel: string, note?: string) => Promise<void>;
  isLoading?: boolean;
}

export function AIEditSuggestionDialog({
  suggestion,
  suggestionId,
  defaultReviewer,
  isOpen,
  onClose,
  onSubmit,
  isLoading = false,
}: AIEditSuggestionDialogProps): React.ReactElement | null {
  const [value, setValue] = useState(suggestion.suggested_value || "");
  const [reviewer, setReviewer] = useState(defaultReviewer || "Reviewer");
  const [note, setNote] = useState("");

  if (!isOpen) return null;

  const fieldName = suggestion.field ? labelForField(suggestion.field) : "Field";
  const side = suggestion.document_side || "BL";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim() || !reviewer.trim()) return;
    await onSubmit(suggestionId, value.trim(), reviewer.trim(), note.trim() || undefined);
    onClose();
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="edit-dialog-title">
      <div className="modal-dialog">
        <div className="modal-header">
          <div>
            <p className="eyebrow" style={{ margin: 0 }}>Human Review · Edit AI Proposal</p>
            <h3 id="edit-dialog-title">Edit before applying: {side} · {fieldName}</h3>
          </div>
          <button
            type="button"
            className="icon-button"
            onClick={onClose}
            aria-label="Close dialog"
          >
            <X size={16} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="modal-body form-grid">
          <div className="form-info-box">
            <span>AI-Proposed Value:</span>
            <code>{suggestion.suggested_value}</code>
          </div>

          <label className="form-span">
            Reviewer corrected value
            <input
              type="text"
              aria-label="Reviewer corrected value"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              required
              autoFocus
            />
          </label>

          <label className="form-span">
            Reviewer label / signature
            <input
              type="text"
              aria-label="Reviewer signature"
              value={reviewer}
              onChange={(e) => setReviewer(e.target.value)}
              required
            />
          </label>

          <label className="form-span">
            Reviewer note (optional)
            <textarea
              aria-label="Reviewer note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Provide context or explanation for the edited correction"
              rows={3}
            />
          </label>

          <div className="modal-footer">
            <button
              type="button"
              className="button-secondary"
              onClick={onClose}
              disabled={isLoading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="button-primary"
              disabled={isLoading || !value.trim() || !reviewer.trim()}
            >
              {isLoading ? "Applying…" : "Apply & Recompare"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
