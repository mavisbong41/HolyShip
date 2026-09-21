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
            <p className="message-text">{msg.text}</p>
            {msg.suggestion && (
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
