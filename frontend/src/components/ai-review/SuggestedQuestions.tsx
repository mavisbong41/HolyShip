import React, { useState } from "react";
import { HelpCircle, ChevronDown, ChevronUp } from "lucide-react";

interface SuggestedQuestionsProps {
  onSelectQuestion: (question: string) => void;
  disabled?: boolean;
}

const PRIMARY_QUESTIONS = [
  "Why does this need Human Review?",
  "Which fields should I check first?",
];

const MORE_QUESTIONS = [
  "Why is this case blocked?",
  "Explain the gross weight mismatch",
  "Where did this value come from?",
  "Summarize this case",
];

export function SuggestedQuestions({
  onSelectQuestion,
  disabled = false,
}: SuggestedQuestionsProps): React.ReactElement {
  const [showMore, setShowMore] = useState(false);

  return (
    <div className="suggested-questions-wrap">
      <div className="suggested-questions-label">
        <HelpCircle size={13} aria-hidden="true" />
        <span>Suggested:</span>
      </div>
      <div className="suggested-chips-list" role="group" aria-label="Suggested questions">
        {PRIMARY_QUESTIONS.map((q) => (
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
        {MORE_QUESTIONS.map((q) => (
          <button
            key={q}
            type="button"
            className={showMore ? "chip-btn" : "chip-btn chip-btn-collapsed"}
            disabled={disabled}
            onClick={() => onSelectQuestion(q)}
          >
            {q}
          </button>
        ))}
        <button
          type="button"
          className="chip-btn chip-btn-toggle"
          disabled={disabled}
          onClick={() => setShowMore((prev) => !prev)}
          aria-expanded={showMore}
        >
          {showMore ? (
            <>
              Less <ChevronUp size={11} aria-hidden="true" style={{ display: "inline", verticalAlign: "middle" }} />
            </>
          ) : (
            <>
              More <ChevronDown size={11} aria-hidden="true" style={{ display: "inline", verticalAlign: "middle" }} />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
