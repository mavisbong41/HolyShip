import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";
import { demoDetail, demoHumanReview, demoQueue, demoSummary } from "../src/lib/fixtures";
import type { ProductReview, AIAssistantResponse } from "../src/api/types";

function jsonResponse(payload: unknown, ok = true, status = 200): Response {
  return {
    ok,
    status,
    statusText: ok ? "OK" : "Error",
    json: async () => payload,
  } as Response;
}

const mockSuggestionResponse: AIAssistantResponse = {
  message: "The Draft BL container count appears to have a typographical error based on SI document evidence showing 3 containers.",
  mode: "ACTIONABLE_SUGGESTION",
  suggestion_id: "sugg-1111-2222-3333-444444444444",
  provider_name: "test-provider",
  provider_model: "test-model",
  suggestion: {
    action: "FIELD_OVERRIDE",
    document_side: "BL",
    field: "container_count",
    current_value: "4",
    suggested_value: "3",
    confidence: 0.95,
    reason: "SI explicitly states 3 containers in cargo description.",
    evidence_refs: ["SI Page 1: 3 x 40'HC containers"],
  },
};

function setupFetch(overrides?: Partial<Record<string, unknown>>) {
  const reviewDetail: ProductReview = (overrides?.reviewDetail as ProductReview) ?? {
    ...demoHumanReview.items[0],
    ai_suggestions: [],
  };

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";

    if (url.includes("/summary")) {
      return jsonResponse(overrides?.summary ?? demoSummary);
    }
    if (url.includes("/emails?")) {
      return jsonResponse(overrides?.queue ?? demoQueue);
    }
    if (url.includes("/emails/22222222-2222-4222-8222-222222222222")) {
      return jsonResponse(overrides?.detail ?? demoDetail);
    }
    if (url.endsWith("/ai/ask") && method === "POST") {
      return jsonResponse(overrides?.aiAskResponse ?? mockSuggestionResponse);
    }
    if (url.endsWith("/plans") && method === "GET") {
      return jsonResponse(overrides?.reviewPlans ?? []);
    }
    if (url.endsWith("/plans") && method === "POST") {
      const body = init?.body ? JSON.parse(String(init.body)) : {};
      return jsonResponse({
        id: "plan-1", review_case_id: reviewDetail.id, status: "DRAFT",
        created_by: body.created_by, confirmed_at: null, confirmed_by: null,
        applied_comparison_id: null, error_message: null,
        items: body.items.map((item: Record<string, unknown>, index: number) => ({
          id: `manual-${index}`, ai_suggestion_id: null, human_edited_value: null,
          action: "REPLACE", created_at: "2026-09-25T00:00:00Z", updated_at: "2026-09-25T00:00:00Z",
          ...item,
        })),
        created_at: "2026-09-25T00:00:00Z", updated_at: "2026-09-25T00:00:00Z",
      });
    }
    if (url.includes("/ai/suggestions/") && url.endsWith("/accept") && method === "POST") {
      const acceptedReview: ProductReview = {
        ...reviewDetail,
        status: "RESOLVED",
        ai_suggestions: [
          {
            id: "sugg-1111-2222-3333-444444444444",
            human_review_case_id: reviewDetail.id,
            mode: "ACTIONABLE_SUGGESTION",
            message: mockSuggestionResponse.message,
            document_side: "BL",
            field: "container_count",
            current_value: "4",
            suggested_value: "3",
            confidence: 0.95,
            reason: "SI explicitly states 3 containers in cargo description.",
            evidence_refs: ["SI Page 1: 3 x 40'HC containers"],
            provider_name: "test-provider",
            provider_model: "test-model",
            status: "ACCEPTED",
            created_at: "2026-09-21T10:30:00+08:00",
          },
        ],
        overrides: [
          {
            id: "ovr-1",
            document_side: "BL",
            field: "container_count",
            original_field_id: "",
            corrected_value: "3",
            corrected_canonical_value: 3,
            reviewer_name: "Captain Jack",
            note: "Accepted AI suggestion",
            active: true,
            supersedes_override_id: null,
            ai_suggestion_id: "sugg-1111-2222-3333-444444444444",
            created_at: "2026-09-21T10:31:00+08:00",
          },
        ],
      };
      return jsonResponse(acceptedReview);
    }
    if (url.includes("/ai/suggestions/") && url.endsWith("/apply-edited") && method === "POST") {
      const body = init?.body ? JSON.parse(String(init.body)) : {};
      const editedReview: ProductReview = {
        ...reviewDetail,
        status: "RESOLVED",
        ai_suggestions: [
          {
            id: "sugg-1111-2222-3333-444444444444",
            human_review_case_id: reviewDetail.id,
            mode: "ACTIONABLE_SUGGESTION",
            message: mockSuggestionResponse.message,
            document_side: "BL",
            field: "container_count",
            current_value: "4",
            suggested_value: body.value || "3",
            confidence: 0.95,
            reason: "SI explicitly states 3 containers in cargo description.",
            evidence_refs: ["SI Page 1: 3 x 40'HC containers"],
            provider_name: "test-provider",
            provider_model: "test-model",
            status: "EDITED_APPLIED",
            created_at: "2026-09-21T10:30:00+08:00",
          },
        ],
        overrides: [
          {
            id: "ovr-2",
            document_side: "BL",
            field: "container_count",
            original_field_id: "",
            corrected_value: body.value || "3",
            corrected_canonical_value: 3,
            reviewer_name: body.reviewer_label || "Captain Jack",
            note: body.note || "Edited AI suggestion",
            active: true,
            supersedes_override_id: null,
            ai_suggestion_id: "sugg-1111-2222-3333-444444444444",
            created_at: "2026-09-21T10:31:00+08:00",
          },
        ],
      };
      return jsonResponse(editedReview);
    }
    if (url.includes("/ai/suggestions/") && url.endsWith("/dismiss") && method === "POST") {
      const dismissedReview: ProductReview = {
        ...reviewDetail,
        ai_suggestions: [
          {
            id: "sugg-1111-2222-3333-444444444444",
            human_review_case_id: reviewDetail.id,
            mode: "ACTIONABLE_SUGGESTION",
            message: mockSuggestionResponse.message,
            document_side: "BL",
            field: "container_count",
            current_value: "4",
            suggested_value: "3",
            confidence: 0.95,
            reason: "SI explicitly states 3 containers in cargo description.",
            evidence_refs: ["SI Page 1: 3 x 40'HC containers"],
            provider_name: "test-provider",
            provider_model: "test-model",
            status: "DISMISSED",
            created_at: "2026-09-21T10:30:00+08:00",
          },
        ],
      };
      return jsonResponse(dismissedReview);
    }
    if (url.includes("/human-review/99999999-9999-4999-8999-999999999999")) {
      return jsonResponse(reviewDetail);
    }
    if (url.includes("/human-review")) {
      return jsonResponse(overrides?.humanReview ?? { ...demoHumanReview, items: [reviewDetail] });
    }
    if (url.includes("/events")) {
      return jsonResponse([]);
    }
    return jsonResponse({ detail: "Not found" }, false, 404);
  });

  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});

afterEach(() => {
  window.history.replaceState({}, "", "/");
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("AI Review Assistant Dashboard UI", () => {
  it("adds a reviewer-authored manual correction to the same confirmable plan", async () => {
    const fetchMock = setupFetch();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    window.history.replaceState({}, "", "/?review=99999999-9999-4999-8999-999999999999");
    render(<App />);

    await screen.findByRole("region", { name: "Structured Review Plan" });
    await user.click(screen.getByRole("button", { name: /add manual correction/i }));
    const form = screen.getByLabelText("Add Manual Correction");
    expect(within(form).getAllByRole("option")).toHaveLength(9); // 2 sides + exactly 7 canonical fields
    await user.type(within(form).getByLabelText("Proposed Corrected Value"), "Corrected Shipper Ltd");
    await user.type(within(form).getByLabelText("Reason / Note"), "Verified against signed SI");
    await user.click(within(form).getByRole("button", { name: "Add to Plan" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/human-review\/99999999-9999-4999-8999-999999999999\/plans$/),
      expect.objectContaining({ method: "POST" }),
    ));
    expect(await screen.findByText("Manual correction")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /confirm implementation/i })).toBeInTheDocument();
  });

  it("renders AI Review Assistant panel with suggested prompt chips", async () => {
    setupFetch();
    window.history.replaceState({}, "", "/?review=99999999-9999-4999-8999-999999999999");
    render(<App />);

    expect(await screen.findByRole("region", { name: "AI Review Assistant" })).toBeInTheDocument();
    expect(screen.getByText("AI Review Assistant")).toBeInTheDocument();
    expect(screen.getByText("Grounded case reasoning & field override proposals")).toBeInTheDocument();

    // Check suggested chips
    expect(screen.getByRole("button", { name: "Why does this need Human Review?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Which fields should I check first?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Summarize this case" })).toBeInTheDocument();
  });

  it("submits a suggested question, displays AI reasoning, and renders actionable suggestion card", async () => {
    const fetchMock = setupFetch();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    window.history.replaceState({}, "", "/?review=99999999-9999-4999-8999-999999999999");
    render(<App />);

    await screen.findByRole("region", { name: "AI Review Assistant" });

    // Click suggested chip
    await user.click(screen.getByRole("button", { name: "Why does this need Human Review?" }));

    // Verify POST /ai/ask was called with case scope
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/human-review/99999999-9999-4999-8999-999999999999/ai/ask"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ question: "Why does this need Human Review?" }),
        }),
      );
    });

    // Check explanation
    expect(await screen.findByText(/The Draft BL container count appears to have a typographical error/)).toBeInTheDocument();

    // Check suggestion card
    expect(screen.getByText(/AI Proposed Override: BL · Container Count/i)).toBeInTheDocument();
    expect(screen.getByText("95% confidence")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("SI Page 1: 3 x 40'HC containers")).toBeInTheDocument();

    // Verify action buttons
    expect(screen.getByRole("button", { name: /Accept & Recompare/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Edit Before Applying/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dismiss" })).toBeInTheDocument();
  });

  it("accepts an AI proposal and triggers case recomparison", async () => {
    const fetchMock = setupFetch();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    window.history.replaceState({}, "", "/?review=99999999-9999-4999-8999-999999999999");
    render(<App />);

    await screen.findByRole("region", { name: "AI Review Assistant" });
    await user.click(screen.getByRole("button", { name: "Why does this need Human Review?" }));
    await screen.findByText(/AI Proposed Override: BL · Container Count/i);

    // Click Accept Proposal
    await user.click(screen.getByRole("button", { name: /Accept & Recompare/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/human-review/99999999-9999-4999-8999-999999999999/ai/suggestions/sugg-1111-2222-3333-444444444444/accept"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ reviewer_label: "Captain Jack" }),
        }),
      );
    });
  });

  it("opens edit modal, edits value, and applies edited proposal", async () => {
    const fetchMock = setupFetch();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    window.history.replaceState({}, "", "/?review=99999999-9999-4999-8999-999999999999");
    render(<App />);

    await screen.findByRole("region", { name: "AI Review Assistant" });
    await user.click(screen.getByRole("button", { name: "Why does this need Human Review?" }));
    await screen.findByText(/AI Proposed Override: BL · Container Count/i);

    // Click Edit Proposal
    await user.click(screen.getByRole("button", { name: /Edit Before Applying/i }));

    // Verify dialog opens
    const dialog = screen.getByRole("dialog", { name: /Edit before applying/i });
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByText(/Edit before applying: BL · Container Count/i)).toBeInTheDocument();

    const valueInput = within(dialog).getByLabelText("Reviewer corrected value");
    expect(valueInput).toHaveValue("3");
    await user.clear(valueInput);
    await user.type(valueInput, "5");

    const noteInput = within(dialog).getByLabelText("Reviewer note");
    await user.type(noteInput, "Adjusted to 5 based on revised packing list");

    // Submit dialog
    await user.click(within(dialog).getByRole("button", { name: "Apply & Recompare" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/human-review/99999999-9999-4999-8999-999999999999/ai/suggestions/sugg-1111-2222-3333-444444444444/apply-edited"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            value: "5",
            reviewer_label: "Captain Jack",
            note: "Adjusted to 5 based on revised packing list",
          }),
        }),
      );
    });
  });

  it("dismisses an AI proposal with reason", async () => {
    const fetchMock = setupFetch();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    window.history.replaceState({}, "", "/?review=99999999-9999-4999-8999-999999999999");
    render(<App />);

    await screen.findByRole("region", { name: "AI Review Assistant" });
    await user.click(screen.getByRole("button", { name: "Why does this need Human Review?" }));
    await screen.findByText(/AI Proposed Override: BL · Container Count/i);

    // Click Dismiss on the AI card
    const card = screen.getByRole("article", { name: "AI Field Override Suggestion" });
    await user.click(within(card).getByRole("button", { name: "Dismiss" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/human-review/99999999-9999-4999-8999-999999999999/ai/suggestions/sugg-1111-2222-3333-444444444444/dismiss"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ reviewer_label: "Captain Jack" }),
        }),
      );
    });
  });

  it("handles AI provider error gracefully without blocking manual review controls", async () => {
    const fetchMock = setupFetch({
      aiAskResponse: { detail: "AI provider timeout" },
    });
    // Make /ai/ask fail
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/ai/ask")) {
          return jsonResponse({ detail: "AI service temporarily unavailable" }, false, 503);
        }
        return fetchMock(input, init);
      }),
    );

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    window.history.replaceState({}, "", "/?review=99999999-9999-4999-8999-999999999999");
    render(<App />);

    await screen.findByRole("region", { name: "AI Review Assistant" });
    await user.click(screen.getByRole("button", { name: "Why does this need Human Review?" }));

    // Error banner inside AI panel
    expect(await screen.findByRole("alert")).toHaveTextContent("AI service temporarily unavailable");

    // Manual review controls must remain functional and active
    expect(screen.getByRole("button", { name: "Save Correction" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resolve & Recompare" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dismiss Review" })).toBeInTheDocument();
  });
});
