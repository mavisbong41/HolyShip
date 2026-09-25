import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";
import { demoDetail, demoHumanReview, demoQueue, demoSummary } from "../src/lib/fixtures";
import type { ProductReview, AIAssistantResponse, ProductReviewPlan } from "../src/api/types";

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
  const defaultReview: ProductReview = {
    ...demoHumanReview.items[0],
    ai_suggestions: [
      {
        id: "sugg-1111-2222-3333-444444444444",
        human_review_case_id: demoHumanReview.items[0].id,
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
        status: "PENDING",
        created_at: "2026-09-25T10:30:00+08:00",
      },
    ],
  };

  const reviewDetail: ProductReview = (overrides?.reviewDetail as ProductReview) ?? defaultReview;
  let plans: ProductReviewPlan[] = (overrides?.reviewPlans as ProductReviewPlan[]) ?? [];

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
      return jsonResponse(plans);
    }
    if (url.endsWith("/plans") && method === "POST") {
      const body = init?.body ? JSON.parse(String(init.body)) : {};
      const newPlan: ProductReviewPlan = {
        id: "plan-1",
        review_case_id: reviewDetail.id,
        status: "DRAFT",
        created_by: body.created_by,
        confirmed_at: null,
        confirmed_by: null,
        applied_comparison_id: null,
        error_message: null,
        items: body.items.map((item: Record<string, unknown>, index: number) => ({
          id: `item-${index + 1}`,
          ai_suggestion_id: item.ai_suggestion_id ?? null,
          human_edited_value: null,
          action: "REPLACE",
          created_at: "2026-09-25T00:00:00Z",
          updated_at: "2026-09-25T00:00:00Z",
          ...item,
        })),
        created_at: "2026-09-25T00:00:00Z",
        updated_at: "2026-09-25T00:00:00Z",
      };
      plans = [newPlan, ...plans.filter((p) => p.id !== "plan-1")];
      return jsonResponse(newPlan);
    }
    if (url.includes("/plans/") && url.includes("/items") && method === "POST") {
      const body = init?.body ? JSON.parse(String(init.body)) : {};
      const targetPlan = plans.find((p) => p.id === "plan-1") ?? plans[0];
      const newItem = {
        id: `item-${targetPlan.items.length + 1}`,
        ai_suggestion_id: body.ai_suggestion_id ?? null,
        human_edited_value: null,
        action: "REPLACE",
        created_at: "2026-09-25T00:00:00Z",
        updated_at: "2026-09-25T00:00:00Z",
        ...body,
      };
      targetPlan.items.push(newItem);
      return jsonResponse(targetPlan);
    }
    if (url.includes("/plans/") && url.endsWith("/confirm") && method === "POST") {
      const body = init?.body ? JSON.parse(String(init.body)) : {};
      const targetPlan = plans.find((p) => p.id === "plan-1") ?? plans[0];
      targetPlan.status = "APPLIED";
      targetPlan.confirmed_at = "2026-09-25T12:00:00Z";
      targetPlan.confirmed_by = body.confirmed_by;

      // Update reviewDetail on recomparison
      if (overrides?.recompareResult === "MISMATCH") {
        reviewDetail.status = "OPEN";
      } else {
        reviewDetail.status = "RESOLVED";
        if (reviewDetail.comparison) {
          reviewDetail.comparison = {
            ...reviewDetail.comparison,
            state: "COMPLETED",
            mismatch_found: false,
            mismatched_fields: [],
            unresolved_fields: [],
            fields: reviewDetail.comparison.fields.map((f) => ({
              ...f,
              status: "MATCH",
              reason_code: "L0_MATCH",
            })),
          };
        }
      }
      return jsonResponse(targetPlan);
    }
    if (url.includes("/plans/") && url.includes("/items/") && method === "PATCH") {
      const body = init?.body ? JSON.parse(String(init.body)) : {};
      const targetPlan = plans.find((p) => p.id === "plan-1") ?? plans[0];
      const itemId = url.split("/items/")[1];
      const item = targetPlan.items.find((i) => i.id === itemId);
      if (item) {
        item.status = body.status;
        if (body.status === "EDITED") item.human_edited_value = body.edited_value;
      }
      return jsonResponse(targetPlan);
    }
    if (url.includes("/plans/") && url.includes("/items/") && method === "DELETE") {
      const targetPlan = plans.find((p) => p.id === "plan-1") ?? plans[0];
      const itemId = url.split("/items/")[1].split("?")[0];
      targetPlan.items = targetPlan.items.filter((i) => i.id !== itemId);
      return jsonResponse(targetPlan);
    }
    if (url.includes("/plans/") && url.endsWith("/cancel") && method === "POST") {
      const targetPlan = plans.find((p) => p.id === "plan-1") ?? plans[0];
      targetPlan.status = "CANCELLED";
      return jsonResponse(targetPlan);
    }
    if (url.includes("/ai/suggestions/") && url.endsWith("/dismiss") && method === "POST") {
      const dismissedReview: ProductReview = {
        ...reviewDetail,
        ai_suggestions: (reviewDetail.ai_suggestions ?? []).map((s) => ({
          ...s,
          status: "DISMISSED",
        })),
      };
      return jsonResponse(dismissedReview);
    }
    if (url.includes("/human-review/99999999-9999-4999-8999-999999999999/overrides") && method === "POST") {
      return jsonResponse(reviewDetail);
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

describe("AI Review Assistant Dashboard UI & Review Plan Workflow", () => {
  it("A, B, C, D: displays MISMATCH, prefills editable AI proposal without applying override, and reflects reviewer edits", async () => {
    const fetchMock = setupFetch();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    window.history.replaceState({}, "", "/?review=99999999-9999-4999-8999-999999999999");
    render(<App />);

    // Switch to compare tab
    await user.click(await screen.findByRole("button", { name: /Compare Fields/i }));

    // A: MISMATCH appears under Confirmed Differences
    expect(await screen.findByText("Confirmed Differences (1)")).toBeInTheDocument();
    expect(screen.getAllByText("Container Count").length).toBeGreaterThan(0);

    // B: Existing AI proposal prefills Proposed Corrected Value
    const input = screen.getByLabelText("Corrected value") as HTMLInputElement;
    expect(input).toBeInTheDocument();
    expect(input.value).toBe("3");
    expect(input.className).toContain("input-ai-suggested");
    expect(screen.getByText(/✦ AI suggested · 95% confidence/i)).toBeInTheDocument();

    // D: Showing the AI value does NOT apply an override or resolve case
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("/overrides"),
      expect.anything(),
    );
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("/confirm"),
      expect.anything(),
    );

    // C: Prefilled value is editable by the human reviewer
    await user.clear(input);
    await user.type(input, "5");
    expect(input.value).toBe("5");

    // H: Shows "Edited by reviewer" label
    expect(screen.getByText(/✎ Edited by reviewer/i)).toBeInTheDocument();
  });

  it("E, F, G: Approve stages AI proposal into Review Plan and allows adding manual correction to the same plan", async () => {
    const fetchMock = setupFetch();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    window.history.replaceState({}, "", "/?review=99999999-9999-4999-8999-999999999999");
    render(<App />);

    const compareTabBtn = await screen.findByRole("button", { name: /Compare Fields/i });
    fireEvent.click(compareTabBtn);

    // Click Approve Suggestion
    const approveBtn = await screen.findByRole("button", { name: "Approve Suggestion" });
    await user.click(approveBtn);

    // E: Proposal staged into Review Plan via POST /plans
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringMatching(/\/human-review\/99999999-9999-4999-8999-999999999999\/plans$/),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"field":"container_count"'),
        }),
      );
    });

    // Review Plan region is rendered with staged AI item
    const planRegion = await screen.findByRole("region", { name: "Review Plan" });
    expect(planRegion).toBeInTheDocument();
    expect(within(planRegion).getByText("Container Count")).toBeInTheDocument();
    expect(within(planRegion).getByText("AI Suggested")).toBeInTheDocument();
    expect(within(planRegion).getByText("Approved")).toBeInTheDocument();

    // F & G: Add a manual correction to the EXISTING plan
    // Select a different field (port_of_loading)
    await user.selectOptions(screen.getByLabelText("Override field"), "port_of_loading");
    const input = screen.getByLabelText("Corrected value");
    await user.clear(input);
    await user.type(input, "SINGAPORE (SGSIN)");
    await user.click(screen.getByRole("button", { name: "Add to Plan" }));

    // Staged to the existing plan via POST /plans/plan-1/items
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/plans/plan-1/items"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"field":"port_of_loading"'),
        }),
      );
    });

    // Both AI and Manual items live in the SAME Review Plan
    expect(within(planRegion).getByText("Port of Loading")).toBeInTheDocument();
    expect(within(planRegion).getByText("Manual")).toBeInTheDocument();
    expect(within(planRegion).getByText(/2 approved changes ready/i)).toBeInTheDocument();
  });

  it("I: Rejecting AI proposal clears suggestion and does NOT resolve the mismatch", async () => {
    setupFetch();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    window.history.replaceState({}, "", "/?review=99999999-9999-4999-8999-999999999999");
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /Compare Fields/i }));

    const rejectBtn = await screen.findByRole("button", { name: "Reject" });
    await user.click(rejectBtn);

    // Input is cleared for manual correction
    const input = screen.getByLabelText("Corrected value") as HTMLInputElement;
    expect(input.value).toBe("");

    // Mismatch remains present and active
    expect(screen.getByText("Confirmed Differences (1)")).toBeInTheDocument();
    expect(screen.getByText("Draft BL (Document Checked)")).toBeInTheDocument();

    // "Add to Plan" is now available for manual correction
    expect(screen.getByRole("button", { name: "Add to Plan" })).toBeInTheDocument();
  });

  it("J, K, L: Confirm Implementation applies approved overrides and re-compares", async () => {
    const fetchMock = setupFetch();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    window.history.replaceState({}, "", "/?review=99999999-9999-4999-8999-999999999999");
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /Compare Fields/i }));
    await user.click(await screen.findByRole("button", { name: "Approve Suggestion" }));

    const planRegion = await screen.findByRole("region", { name: "Review Plan" });
    const confirmBtn = within(planRegion).getByRole("button", { name: /confirm implementation/i });
    expect(confirmBtn).toBeInTheDocument();

    // J & K: Confirm Implementation commits overrides and re-compares
    await user.click(confirmBtn);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/plans/plan-1/confirm"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ confirmed_by: "Captain Jack" }),
        }),
      );
    });

    // Case is refreshed after re-comparison
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/human-review/99999999-9999-4999-8999-999999999999"),
        expect.anything(),
      );
    });
  });

  it("L: Re-comparison may remain MISMATCH if differences persist", async () => {
    const fetchMock = setupFetch({
      recompareResult: "MISMATCH",
    });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    window.history.replaceState({}, "", "/?review=99999999-9999-4999-8999-999999999999");
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /Compare Fields/i }));
    await user.click(await screen.findByRole("button", { name: "Approve Suggestion" }));

    const planRegion = await screen.findByRole("region", { name: "Review Plan" });
    await user.click(within(planRegion).getByRole("button", { name: /confirm implementation/i }));

    // Confirm was executed
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/plans/plan-1/confirm"),
        expect.anything(),
      );
    });
  });

  it("M: AI unavailable still allows Manual Correction", async () => {
    const fetchMock = setupFetch({
      reviewDetail: {
        ...demoHumanReview.items[0],
        ai_suggestions: [],
      },
      aiAskResponse: { detail: "AI service offline" },
    });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    window.history.replaceState({}, "", "/?review=99999999-9999-4999-8999-999999999999");
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /Compare Fields/i }));

    // Manual input is operational
    const input = screen.getByLabelText("Corrected value");
    await user.clear(input);
    await user.type(input, "4 containers");

    const addBtn = screen.getByRole("button", { name: "Add to Plan" });
    expect(addBtn).toBeInTheDocument();
    await user.click(addBtn);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringMatching(/\/plans$/),
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("N: Preserves original source and extracted evidence", async () => {
    setupFetch();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    window.history.replaceState({}, "", "/?review=99999999-9999-4999-8999-999999999999");
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /Compare Fields/i }));

    // Original SI and BL values remain rendered and intact
    expect(screen.getByText("SI (Reference Document)")).toBeInTheDocument();
    expect(screen.getByText("Draft BL (Document Checked)")).toBeInTheDocument();
  });

  it("O: UNRESOLVED field is kept distinct from MISMATCH", async () => {
    const unresolvedReview: ProductReview = {
      ...demoHumanReview.items[0],
      comparison: {
        ...demoHumanReview.items[0].comparison!,
        fields: [
          {
            field: "port_of_loading",
            status: "UNRESOLVED",
            reason_code: "AMBIGUOUS_EXTRACTION",
            si: { raw: "SINGAPORE", normalized: "SINGAPORE", canonical: "SINGAPORE" },
            bl: { raw: null, normalized: null, canonical: null },
            evidence: [],
          },
        ],
      },
    };
    setupFetch({ reviewDetail: unresolvedReview });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    window.history.replaceState({}, "", "/?review=99999999-9999-4999-8999-999999999999");
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /Compare Fields/i }));

    // Unresolved field is displayed with UNRESOLVED reason, not as a false MATCH
    expect(screen.getAllByText("Port of Loading").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Ambiguous Extraction|UNRESOLVED/i).length).toBeGreaterThan(0);
  });

  it("P: Active review case without review plan or suggestions does not claim No Review Required", async () => {
    const plainReview: ProductReview = {
      ...demoHumanReview.items[0],
      ai_suggestions: [],
    };
    setupFetch({ reviewDetail: plainReview, reviewPlans: [] });
    window.history.replaceState({}, "", "/?review=99999999-9999-4999-8999-999999999999");
    render(<App />);

    // The review header and details are rendered
    expect((await screen.findAllByText(/Review case|Human Review/i)).length).toBeGreaterThan(0);
    expect(screen.queryByText("No Review Required")).not.toBeInTheDocument();
  });

  it("AI Review Assistant chat thread approves suggestion into Review Plan rather than direct override", async () => {
    const fetchMock = setupFetch();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    window.history.replaceState({}, "", "/?review=99999999-9999-4999-8999-999999999999");
    render(<App />);

    // Switch to AI Assistant tab
    await user.click((await screen.findAllByRole("button", { name: /AI Assistant/i }))[0]);

    // Find the suggestion card and approve to plan
    const approveBtn = await screen.findByRole("button", { name: /Approve Suggestion \(Accept & Implement\)/i });
    await user.click(approveBtn);

    // Stages into review plan, DOES NOT call direct /accept
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringMatching(/\/plans$/),
        expect.objectContaining({ method: "POST" }),
      );
    });
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("/ai/suggestions/sugg-1111-2222-3333-444444444444/accept"),
      expect.anything(),
    );
  });
});
