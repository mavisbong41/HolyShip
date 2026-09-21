import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";
import { demoDetail, demoHumanReview, demoQueue, demoSummary } from "../src/lib/fixtures";
import type { ProductEmailDetail } from "../src/api/types";

function jsonResponse(payload: unknown, ok = true, status = 200): Response {
  return {
    ok,
    status,
    statusText: ok ? "OK" : "Error",
    json: async () => payload,
  } as Response;
}

function setupFetch(overrides?: Partial<Record<string, unknown>>) {
  const reviewDetail = overrides?.reviewDetail ?? demoHumanReview.items[0];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.includes("/summary")) {
      return jsonResponse(overrides?.summary ?? demoSummary);
    }
    if (url.includes("/emails?")) {
      return jsonResponse(overrides?.queue ?? demoQueue);
    }
    if (url.includes("/emails/22222222-2222-4222-8222-222222222222")) {
      return jsonResponse(overrides?.detail ?? demoDetail);
    }
    if (url.includes("/human-review/99999999-9999-4999-8999-999999999999")) {
      return jsonResponse(reviewDetail);
    }
    if (url.includes("/human-review/88888888-8888-4888-8888-888888888888")) {
      return jsonResponse(reviewDetail);
    }
    if (url.includes("/human-review")) {
      return jsonResponse(overrides?.humanReview ?? demoHumanReview);
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

describe("HolyShip dashboard", () => {
  it("renders overview data from the product API", async () => {
    setupFetch();
    render(<App />);

    expect(await screen.findByText("Shipping document operations, at a glance.")).toBeInTheDocument();
    expect(screen.getByText("128")).toBeInTheDocument();
    expect(screen.getAllByText("25").length).toBeGreaterThan(0);
    expect(screen.getByText("Recent Activity")).toBeInTheDocument();
  });

  it("renders queue rows and sends supported filter params", async () => {
    const fetchMock = setupFetch();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<App />);

    await screen.findByText("Shipping document operations, at a glance.");
    await user.click(screen.getByRole("button", { name: "Email Queue" }));
    expect(await screen.findByText("Please verify draft BL details")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Filter by status"), "COMPLETED");

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("status=COMPLETED"),
        expect.anything(),
      );
    });
  });

  it("renders the seven backend comparison fields without local comparison decisions", async () => {
    setupFetch();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<App />);

    await screen.findByText("Shipping document operations, at a glance.");
    await user.click(screen.getByRole("button", { name: "Email Queue" }));
    await user.click(await screen.findByRole("button", { name: "Please verify draft BL details" }));

    const comparison = await screen.findByRole("table", {
      name: "Seven-field SI and Draft BL comparison",
    });
    expect(screen.getByText("Shipping Instruction")).toBeInTheDocument();
    expect(screen.getByText("Draft BL")).toBeInTheDocument();
    expect(screen.getByText("Container Count")).toBeInTheDocument();
    expect(screen.getByText("4 containers")).toBeInTheDocument();
    expect(screen.getByText("22,000 KG")).toBeInTheDocument();
    expect(within(comparison).getAllByText("Mismatch").length).toBeGreaterThan(0);
  });

  it("keeps unresolved distinct from mismatch", async () => {
    const unresolvedDetail: ProductEmailDetail = {
      ...demoDetail,
      comparison: {
        ...demoDetail.comparison!,
        mismatch_found: false,
        mismatched_fields: [],
        unresolved_fields: ["notify_party"],
        fields: demoDetail.comparison!.fields.map((field) =>
          field.field === "notify_party"
            ? { ...field, status: "UNRESOLVED", reason_code: "MISSING_BL_VALUE", bl: { raw: null, canonical: null, normalized: null } }
            : field,
        ),
      },
    };
    setupFetch({ detail: unresolvedDetail });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<App />);

    await screen.findByText("Shipping document operations, at a glance.");
    await user.click(screen.getByRole("button", { name: "Email Queue" }));
    await user.click(await screen.findByRole("button", { name: "Please verify draft BL details" }));

    expect(await screen.findByText("Unresolved")).toBeInTheDocument();
    expect(screen.getByText("Missing")).toBeInTheDocument();
  });

  it("renders Human Review empty state intentionally", async () => {
    setupFetch({ humanReview: { items: [], total: 0, skip: 0, limit: 50 } });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<App />);

    await screen.findByText("Shipping document operations, at a glance.");
    await user.click(screen.getByRole("button", { name: "Human Review" }));

    expect(await screen.findByText("No active review cases")).toBeInTheDocument();
  });

  it("opens a real email detail from an Outlook add-in deep link", async () => {
    const fetchMock = setupFetch();
    window.history.replaceState({}, "", "/?email=22222222-2222-4222-8222-222222222222");

    render(<App />);

    expect(await screen.findByRole("table", { name: "Seven-field SI and Draft BL comparison" })).toBeInTheDocument();
    expect(screen.getAllByText("Please verify draft BL details").length).toBeGreaterThan(0);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/emails/22222222-2222-4222-8222-222222222222"),
      expect.anything(),
    );
  });

  it("loads Human Review detail and sends reviewer corrections through the API", async () => {
    const fetchMock = setupFetch();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<App />);

    await screen.findByText("Shipping document operations, at a glance.");
    await user.click(screen.getByRole("button", { name: "Human Review" }));
    await user.click(await screen.findByRole("button", { name: "Open Review" }));
    expect(await screen.findByRole("table", { name: "Human Review seven-field comparison" })).toBeInTheDocument();

    await user.type(screen.getByLabelText("Corrected value"), "Same as consignee");
    await user.click(screen.getByRole("button", { name: "Save Correction" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/human-review/99999999-9999-4999-8999-999999999999/overrides"),
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("opens Human Review directly and keeps resolve and dismiss as distinct actions", async () => {
    const fetchMock = setupFetch();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    window.history.replaceState({}, "", "/?review=99999999-9999-4999-8999-999999999999");

    render(<App />);

    expect(await screen.findByRole("table", { name: "Human Review seven-field comparison" })).toBeInTheDocument();
    expect(screen.getByText(/original extraction remains immutable/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Resolve & Recompare" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/human-review/99999999-9999-4999-8999-999999999999/resolve"),
      expect.objectContaining({ method: "POST" }),
    ));

    await user.click(screen.getByRole("button", { name: "Dismiss Review" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/human-review/99999999-9999-4999-8999-999999999999/dismiss"),
      expect.objectContaining({ method: "POST" }),
    ));
  });

  it("presents Waiting for Documents without Human Review controls", async () => {
    const awaiting: ProductEmailDetail = {
      ...demoDetail,
      email: { ...demoDetail.email, processing_status: "AWAITING_DOCUMENTS", comparison_readiness: "AWAITING_DOCUMENTS", review_id: null },
      comparison: null,
      review: [],
    };
    setupFetch({ detail: awaiting });
    window.history.replaceState({}, "", "/?email=22222222-2222-4222-8222-222222222222");

    render(<App />);

    expect((await screen.findAllByText("Waiting for Documents", { selector: "strong" })).length).toBeGreaterThan(0);
    expect(screen.getByText(/required document has not arrived/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /open human review/i })).not.toBeInTheDocument();
  });

  it("presents technical failure with a real reprocess action", async () => {
    const failed: ProductEmailDetail = {
      ...demoDetail,
      email: { ...demoDetail.email, processing_status: "FAILED", review_id: null },
      comparison: null,
      review: [],
      timeline: [{ id: "failure", old_status: "EXTRACTING", new_status: "FAILED", reason_code: "DOCUMENT_FIELD_EXTRACTION_FAILED", created_at: "2026-09-21T10:25:00+08:00" }],
    };
    const fetchMock = setupFetch({ detail: failed });
    window.history.replaceState({}, "", "/?email=22222222-2222-4222-8222-222222222222");
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Retry / Reprocess" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/emails/22222222-2222-4222-8222-222222222222/reprocess"),
      expect.objectContaining({ method: "POST" }),
    ));
    expect(screen.queryByRole("button", { name: /open human review/i })).not.toBeInTheDocument();
  });

  it("shows the backend error for an invalid email deep link", async () => {
    setupFetch();
    window.history.replaceState({}, "", "/?email=not-a-real-email-id");

    render(<App />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Not found");
    expect(screen.queryByRole("table", { name: "Seven-field SI and Draft BL comparison" })).not.toBeInTheDocument();
  });

  it("shows API errors without fabricating data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "database unavailable" }, false, 503)),
    );
    render(<App />);
    expect(await screen.findByRole("alert")).toHaveTextContent("database unavailable");
  });

  it("renders HumanReviewPageView with segmented view switch, defaults to active-only, and switches to History", async () => {
    const fetchMock = setupFetch();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<App />);

    await screen.findByText("Shipping document operations, at a glance.");
    await user.click(screen.getByRole("button", { name: "Human Review" }));

    // Verify page renders without crash and shows review items
    expect(await screen.findByText("Human Review Queue")).toBeInTheDocument();
    const activeTab = screen.getByRole("tab", { name: "Active Reviews" });
    const historyTab = screen.getByRole("tab", { name: "History" });
    expect(activeTab).toBeInTheDocument();
    expect(historyTab).toBeInTheDocument();
    expect(activeTab).toHaveAttribute("aria-selected", "true");
    expect(historyTab).toHaveAttribute("aria-selected", "false");

    // Initial fetch should request active_only=true
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("active_only=true"),
        expect.anything(),
      );
    });

    // Check count in Active view
    expect(screen.getByText("1 active")).toBeInTheDocument();

    // Switch to "History"
    await user.click(historyTab);
    expect(historyTab).toHaveAttribute("aria-selected", "true");
    expect(activeTab).toHaveAttribute("aria-selected", "false");

    // Toggled fetch should request active_only=false
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("active_only=false"),
        expect.anything(),
      );
    });

    // Switch back to active-only
    await user.click(activeTab);
    expect(activeTab).toHaveAttribute("aria-selected", "true");
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("active_only=true"),
        expect.anything(),
      );
    });
  });

  it("renders empty states matching active vs history view modes", async () => {
    setupFetch({
      humanReview: {
        total: 0,
        skip: 0,
        limit: 50,
        items: [],
      },
    });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<App />);

    await screen.findByText("Shipping document operations, at a glance.");
    await user.click(screen.getByRole("button", { name: "Human Review" }));

    expect(await screen.findByText("No active review cases")).toBeInTheDocument();
    expect(screen.getByText("0 active")).toBeInTheDocument();

    // Switch to History
    await user.click(screen.getByRole("tab", { name: "History" }));
    expect(await screen.findByText("No review history")).toBeInTheDocument();
    expect(screen.getByText("0 historical")).toBeInTheDocument();
  });

  it("renders historical review record with non-actionable semantics and View History button", async () => {
    const legacyReview = {
      ...demoHumanReview.items[0],
      id: "88888888-8888-4888-8888-888888888888",
      case_origin: "LEGACY" as const,
      status: "OPEN",
    };
    setupFetch({
      humanReview: {
        total: 1,
        skip: 0,
        limit: 50,
        items: [legacyReview],
      },
      reviewDetail: legacyReview,
    });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    window.history.replaceState({}, "", "/?review=88888888-8888-4888-8888-888888888888");

    render(<App />);

    // Detail view for historical case automatically opens in History view mode
    expect(await screen.findByText(/This record is retained for audit history and is read-only/i)).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "History" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("1 historical")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "View History" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save Correction" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start / Claim" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Resolve & Recompare" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Dismiss Review" })).not.toBeInTheDocument();
  });

  it("ensures ACTIVE-origin RESOLVED and DISMISSED cases appear in History and not in Active Reviews", async () => {
    const activeResolved = {
      ...demoHumanReview.items[0],
      id: "77777777-7777-4777-8777-777777777777",
      case_origin: "ACTIVE" as const,
      status: "RESOLVED",
    };
    const activeDismissed = {
      ...demoHumanReview.items[0],
      id: "66666666-6666-4666-8666-666666666666",
      case_origin: "ACTIVE" as const,
      status: "DISMISSED",
    };
    setupFetch({
      humanReview: {
        total: 2,
        skip: 0,
        limit: 50,
        items: [activeResolved, activeDismissed],
      },
    });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<App />);

    await screen.findByText("Shipping document operations, at a glance.");
    await user.click(screen.getByRole("button", { name: "Human Review" }));

    // In Active view, 0 active cases should be visible
    expect(await screen.findByText("No active review cases")).toBeInTheDocument();
    expect(screen.getByText("0 active")).toBeInTheDocument();

    // Switch to History
    await user.click(screen.getByRole("tab", { name: "History" }));
    expect(await screen.findByText("2 historical")).toBeInTheDocument();
    expect(screen.queryByText("No review history")).not.toBeInTheDocument();
  });
});
