import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AIChatThread } from "./AIChatThread";

describe("AIChatThread", () => {
  const baseProps = {
    onAcceptSuggestion: vi.fn(),
    onOpenEditSuggestion: vi.fn(),
    onDismissSuggestion: vi.fn(),
  };

  it("renders concise explanation responses as labelled bullets", () => {
    render(
      <AIChatThread
        {...baseProps}
        messages={[{
          id: "explanation",
          sender: "ai",
          mode: "EXPLANATION_ONLY",
          text: "Status: BLOCKED\n- Issue: Shipper Count missing in SI\n- BL evidence: Container Count: 3 × 20'FCL\n- Next action: Manually review these fields",
          timestamp: "05:34 PM",
        }]}
      />,
    );

    expect(screen.getByText("Status:")).toBeInTheDocument();
    expect(screen.getByText(/Shipper Count missing in SI/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Accept & Implement/i })).not.toBeInTheDocument();
  });

  it("shows implementation controls only for concrete structured suggestions", () => {
    render(
      <AIChatThread
        {...baseProps}
        messages={[{
          id: "suggestion",
          sender: "ai",
          mode: "ACTIONABLE_SUGGESTION",
          text: "Update the BL container count.",
          suggestionId: "suggestion-1",
          suggestion: {
            action: "FIELD_OVERRIDE",
            document_side: "BL",
            field: "container_count",
            current_value: "3",
            suggested_value: "4",
            confidence: 0.99,
            reason: "The BL evidence shows four containers.",
            evidence_refs: ["BL page 1"],
          },
          timestamp: "05:35 PM",
        }]}
      />,
    );

    expect(screen.getByRole("button", { name: /Accept & Implement/i })).toBeInTheDocument();
  });
});
