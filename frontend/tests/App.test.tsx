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
});
