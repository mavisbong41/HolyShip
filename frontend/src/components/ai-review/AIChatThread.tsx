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

function assistantLines(text: string): string[] {
  const normalized = text
    .replace(/\r\n/g, "\n")
    .replace(/\s+(?=(Status|Issue|BL evidence|Next action):)/gi, "\n")
    .trim();
  return normalized
    .split("\n")
    .map((line) => line.trim().replace(/^[-•*]\s*/, ""))
    .filter(Boolean)
    .slice(0, 5);
}

function renderAssistantLine(line: string, index: number): React.ReactNode {
  const match = line.match(/^(Status|Issue|BL evidence|Next action):\s*(.*)$/i);
  if (!match) return <li key={`${line}-${index}`}>{line}</li>;
  return (
    <li key={`${line}-${index}`}>
      <strong>{match[1]}:</strong>{match[2] ? ` ${match[2]}` : null}
    </li>
  );
}

export function AIChatThread({
  messages,
  onAcceptSuggestion,
  onOpenEditSuggestion,
  onDismissSuggestion,
  isActionLoading = false,
}: AIChatThreadProps): React.ReactElement {
  if (messages.length === 0) {
    return (
      <div className="ai-chat-empty">
        <Bot size={28} className="text-orange" aria-hidden="true" />
        <p className="empty-title">HolyShip AI Review Assistant</p>
        <span className="empty-sub">
          Ask questions grounded in this case’s persisted SI/BL evidence, readiness, and verified fields.
        </span>
      </div>
    );
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
              <ul className="message-text assistant-message-list">
                {assistantLines(msg.text).map(renderAssistantLine)}
              </ul>
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
