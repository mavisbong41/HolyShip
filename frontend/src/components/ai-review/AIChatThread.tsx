import React from "react";
import { Bot, User, AlertCircle, Info, Sparkles } from "lucide-react";
import type { AIAssistantResponse, ProductAISuggestion, AISuggestionPayload } from "../../api/types";
import { AISuggestionCard } from "./AISuggestionCard";

export interface ChatMessage {
  id: string;
  sender: "user" | "ai";
  text: string;
  mode?: "EXPLANATION_ONLY" | "ACTIONABLE_SUGGESTION" | "INSUFFICIENT_EVIDENCE";
  suggestion?: ProductAISuggestion | AISuggestionPayload | null;
  suggestionId?: string;
  providerModel?: string;
  timestamp: string;
}

interface AIChatThreadProps {
  messages: ChatMessage[];
  onAcceptSuggestion: (suggestionId: string) => void;
  onOpenEditSuggestion: (suggestion: ProductAISuggestion | AISuggestionPayload, suggestionId?: string) => void;
  onDismissSuggestion: (suggestionId: string) => void;
  isActionLoading?: boolean;
}

type AssistantSection = { label: string; value: string };

function assistantSections(text: string): AssistantSection[] {
  const labels = /\b(Status|Issue|BL evidence|Next action):/gi;
  const matches = [...text.matchAll(labels)];
  if (matches.length === 0) return [{ label: "", value: text.trim() }];

  return matches.slice(0, 5).map((match, index) => ({
    label: match[1],
    value: text.slice(
      (match.index ?? 0) + match[0].length,
      matches[index + 1]?.index,
    ).replace(/^[\s•*-]+|[\s•*-]+$/g, "").trim(),
  }));
}

function renderAssistantSection(section: AssistantSection, index: number): React.ReactNode {
  if (!section.label) return <div key={`section-${index}`}>{section.value}</div>;
  return (
    <div className="assistant-message-section" key={`${section.label}-${index}`}>
      <div className="assistant-message-heading"><span aria-hidden="true">•</span><strong>{section.label === "Status" ? "Status:" : section.label}</strong></div>
      {section.value && <div className="assistant-message-value">{section.value}</div>}
    </div>
  );
}

export function AIChatThread({
  messages,
  onAcceptSuggestion,
  onOpenEditSuggestion,
  onDismissSuggestion,
  isActionLoading = false,
}: AIChatThreadProps): React.ReactElement | null {
  if (messages.length === 0) {
    return null;
  }

  return (
    <div className="ai-chat-thread" role="log" aria-live="polite" aria-label="AI Review Assistant Thread">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`chat-bubble-wrap ${msg.sender === "user" ? "user-wrap" : "ai-wrap"}`}
        >
          <div className="chat-bubble-header">
            <span className="sender-tag">
              {msg.sender === "user" ? (
                <>
                  <User size={12} aria-hidden="true" /> You
                </>
              ) : (
                <>
                  <Bot size={12} aria-hidden="true" /> AI Review Assistant
                </>
              )}
            </span>
            {msg.mode && (
              <span className={`badge badge-${msg.mode === "ACTIONABLE_SUGGESTION" ? "attention" : msg.mode === "EXPLANATION_ONLY" ? "good" : "warn"}`}>
                {msg.mode === "ACTIONABLE_SUGGESTION"
                  ? "Actionable Suggestion"
                  : msg.mode === "EXPLANATION_ONLY"
                    ? "Explanation"
                    : "Insufficient Evidence"}
              </span>
            )}
            <span className="bubble-time">{msg.timestamp}</span>
          </div>

          <div className="chat-bubble-content">
            {msg.sender === "ai" ? (
              <div className="message-text assistant-message-list">
                {assistantSections(msg.text).map(renderAssistantSection)}
              </div>
            ) : <p className="message-text">{msg.text}</p>}
            {msg.suggestion && msg.suggestion.field && msg.suggestion.suggested_value != null && msg.suggestionId && (
              <AISuggestionCard
                suggestion={msg.suggestion}
                suggestionId={msg.suggestionId}
                onAccept={onAcceptSuggestion}
                onOpenEdit={onOpenEditSuggestion}
                onDismiss={onDismissSuggestion}
                isActionLoading={isActionLoading}
              />
            )}
          </div>

          {msg.providerModel && (
            <div className="chat-bubble-footer">
              <small className="technical-code">model: {msg.providerModel}</small>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
