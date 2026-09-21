import React from "react";
import { HelpCircle } from "lucide-react";

interface SuggestedQuestionsProps {
  onSelectQuestion: (question: string) => void;
  disabled?: boolean;
}

const DEFAULT_QUESTIONS = [
  "Why is this case blocked?",
  "Why does this need Human Review?",
  "Which fields should I check first?",
  "Explain the gross weight mismatch",
  "Where did this value come from?",
  "Summarize this case",
];

export function SuggestedQuestions({
  onSelectQuestion,
  disabled = false,
}: SuggestedQuestionsProps): React.ReactElement {
  return (
    <div className="suggested-questions-wrap">
      <div className="suggested-questions-label">
        <HelpCircle size={13} aria-hidden="true" />
        <span>Suggested questions:</span>
      </div>
      <div className="suggested-chips-list" role="group" aria-label="Suggested questions">
        {DEFAULT_QUESTIONS.map((q) => (
          <button
            key={q}
            type="button"
            className="chip-btn"
            disabled={disabled}
            onClick={() => onSelectQuestion(q)}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
