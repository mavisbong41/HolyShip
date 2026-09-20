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
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
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

    expect(await screen.findByText("No review cases")).toBeInTheDocument();
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
