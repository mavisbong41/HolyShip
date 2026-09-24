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
    if (url.includes("/human-review/") && !url.includes("/human-review?")) {
      return jsonResponse(reviewDetail);
    }
    if (url.includes("/human-review")) {
      return jsonResponse(overrides?.humanReview ?? demoHumanReview);
    }
    if (url.includes("/events")) {
      return jsonResponse([]);
    }
    if (url.includes("/outlook/reconcile")) {
      return jsonResponse({ email_id: "22222222-2222-4222-8222-222222222222", action: "OUTLOOK_EMAIL_RESTORED" });
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

  it("filters queue by lifecycle status", async () => {
    const fetchMock = setupFetch();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<App />);

    await screen.findByText("Shipping document operations, at a glance.");
    await user.click(screen.getByRole("button", { name: "Email Queue" }));
    expect(await screen.findByText("Please verify draft BL details")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Filter by lifecycle"), "DELETED");

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("lifecycle_status=DELETED"),
        expect.anything(),
      );
    });
  });

  it("renders deleted lifecycle banner and restores email from case inspector", async () => {
    const deletedDetail: ProductEmailDetail = {
      ...demoDetail,
      email: {
        ...demoDetail.email,
        lifecycle: {
          lifecycle_status: "DELETED",
          outlook_read_state: "READ",
          outlook_categories: ["BL_COMPARISON"],
          outlook_folder_id: "trash",
          outlook_archived: false,
          last_outlook_sync_at: "2026-09-21T10:23:00+08:00",
          outlook_sync_error: null,
          deleted_at: "2026-09-21T10:23:00+08:00",
          restored_at: null,
        },
      },
    };
    const fetchMock = setupFetch({ detail: deletedDetail });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<App />);

    await screen.findByText("Shipping document operations, at a glance.");
    await user.click(screen.getByRole("button", { name: "Email Queue" }));
    await user.click(await screen.findByRole("button", { name: "Please verify draft BL details" }));

    expect(await screen.findByText("Mailbox item deleted")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /restore email/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /restore email/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/outlook/reconcile"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining('"lifecycle_status":"RESTORED"'),
        }),
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

  it("renders Document Exception panel without 7-field table or field editor for non-field reviews", async () => {
    const wrongDocReview = {
      ...demoHumanReview.items[0],
      id: "55555555-5555-4555-8555-555555555555",
      reason_code: "WRONG_DOCUMENT_TYPE",
      reason_text: "Wrong Document Type",
      presentation_title: "Wrong document type",
      canonical_reason: "Wrong Document Type",
      human_explanation: "The attached file does not appear to be the required shipping document.",
      affected_fields: [],
      affected_area: "Documents",
      suggested_action: "Confirm the attached document",
      comparison: null,
      documents: [
        {
          id: "11111111-1111-4111-8111-111111111111",
          attachment_id: "att-1",
          filename: "email_503_SI.txt",
          role: "SI",
          format: "PLAIN_TEXT",
          validation_outcome: "VALID",
          routing_outcome: "SI_FOUND",
        },
        {
          id: "22222222-2222-4222-8222-222222222222",
          attachment_id: "att-2",
          filename: "email_503_BL.txt",
          role: "OTHER",
          format: "PLAIN_TEXT",
          validation_outcome: "WRONG_DOCUMENT_TYPE",
          routing_outcome: "WRONG_DOCUMENT_TYPE",
          role_evidence: {
            summary: "Conflicting business-document marker(s): CERTIFICATE OF ORIGIN",
          },
        },
      ],
    };

    setupFetch({
      humanReview: {
        total: 1,
        skip: 0,
        limit: 50,
        items: [wrongDocReview],
      },
      reviewDetail: wrongDocReview,
    });
    window.history.replaceState({}, "", "/?review=55555555-5555-4555-8555-555555555555");

    render(<App />);

    // Tab should say Document Exception
    expect(await screen.findByRole("tab", { name: /Document Exception/i })).toBeInTheDocument();

    // Should NOT render the 7-field comparison table or field editor
    expect(screen.queryByRole("table", { name: "Human Review seven-field comparison" })).not.toBeInTheDocument();
    expect(screen.queryByText("Seven reviewed fields")).not.toBeInTheDocument();
    expect(screen.queryByText("Save a correction")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Corrected value")).not.toBeInTheDocument();
    expect(screen.queryByText("Resolve & Recompare")).not.toBeInTheDocument();

    // Top action button should be Dismiss Review
    expect(screen.getAllByRole("button", { name: "Dismiss Review" }).length).toBeGreaterThan(0);

    // Document Exception panel should be visible
    expect(screen.getByText("Document role & validation exception")).toBeInTheDocument();
    expect(screen.getByText("Standard Operational Procedure (SOP):")).toBeInTheDocument();
    expect(screen.getByText(/Confirm the invalid attachment:/i)).toBeInTheDocument();
    expect(screen.getByText(/Determine the operational next step:/i)).toBeInTheDocument();
    expect(screen.getByText("email_503_BL.txt")).toBeInTheDocument();
    expect(screen.getByText("Conflicting business-document marker(s): CERTIFICATE OF ORIGIN")).toBeInTheDocument();
    expect(screen.getByText("Document Resolution")).toBeInTheDocument();
    expect(screen.getByText(/Obtain the correct Shipping Instruction or Draft Bill of Lading/i)).toBeInTheDocument();
    expect(screen.getByText("Quick presets:")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "NOT_ACTIONABLE" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "WRONG_DOCUMENT_TYPE" })).not.toBeInTheDocument();

    // Dismiss Review is secondary
    const dismissButtons = screen.getAllByRole("button", { name: "Dismiss Review" });
    expect(dismissButtons.length).toBeGreaterThan(0);
    dismissButtons.forEach((btn) => {
      expect(btn.className).toContain("button-secondary");
    });
  });

  it("renders field-level workspace with Seven Reviewed Fields and non-mutating overrides for Missing Required Value", async () => {
    const missingValueReview = {
      ...demoHumanReview.items[0],
      id: "77777777-7777-4777-8777-777777777777",
      reason_code: "MISSING_REQUIRED_VALUE",
      reason_text: "Gross weight is missing from Draft BL.",
      presentation_title: "Missing Required Value",
      canonical_reason: "Missing Required Value",
      human_explanation: "The SI and BL evidence was not sufficient to determine one or more required field values confidently.",
      affected_fields: ["gross_weight_kg"],
      affected_area: "Document fields",
      suggested_action: "Review unresolved fields",
      comparison: {
        ...demoDetail.comparison!,
        mismatch_found: false,
        mismatched_fields: [],
        unresolved_fields: ["gross_weight_kg"],
        fields: demoDetail.comparison!.fields.map((f) =>
          f.field === "gross_weight_kg"
            ? { ...f, status: "UNRESOLVED" as const, bl: { raw: null, canonical: null, normalized: null } }
            : { ...f, status: "MATCH" as const }
        ),
      },
    };

    setupFetch({
      humanReview: {
        total: 1,
        skip: 0,
        limit: 50,
        items: [missingValueReview],
      },
      reviewDetail: missingValueReview,
    });
    window.history.replaceState({}, "", "/?review=77777777-7777-4777-8777-777777777777");

    render(<App />);

    // Renders Comparison & Overrides tab
    expect(await screen.findByRole("tab", { name: /Comparison & Overrides/i })).toBeInTheDocument();

    // Renders Header Title & Description
    expect(screen.getAllByText("Missing Required Value").length).toBeGreaterThan(0);
    expect(screen.getAllByText("The SI and BL evidence was not sufficient to determine one or more required field values confidently.").length).toBeGreaterThan(0);

    // Renders Seven Reviewed Fields table
    expect(screen.getByText("Seven reviewed fields")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Human Review seven-field comparison" })).toBeInTheDocument();

    // Shows only actually affected field chip (gross_weight_kg), NOT matched fields (e.g. shipper)
    expect(screen.getByRole("button", { name: "Gross Weight" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Shipper" })).not.toBeInTheDocument();

    // Shows unresolved count
    expect(screen.getByText("1 unresolved")).toBeInTheDocument();

    // Preserves original and effective values
    expect(screen.getAllByText("Original SI").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Original BL").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Effective:/).length).toBeGreaterThan(0);

    // Save correction section
    expect(screen.getByText("Save a correction")).toBeInTheDocument();
    expect(screen.getByText("The saved correction is stored as a review override and used as the effective value during Resolve & Recompare. The original extraction remains unchanged.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save Correction" })).toBeInTheDocument();

    // Primary action is Resolve & Recompare
    expect(screen.getByRole("button", { name: "Resolve & Recompare" })).toBeInTheDocument();

    // Dismissal remains in Danger Zone / secondary
    expect(screen.getByText("Danger Zone")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "NOT_ACTIONABLE" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "MISSING_REQUIRED_VALUE" })).not.toBeInTheDocument();
  });

  it("renders Document Exception workspace with technical OCR evidence and dedicated SOP for Unreadable Document", async () => {
    const unreadableDocReview = {
      ...demoHumanReview.items[0],
      id: "88888888-8888-4888-8888-888888888888",
      reason_code: "UNREADABLE_ATTACHMENT",
      reason_text: "Unreadable Document",
      presentation_title: "Unreadable Document",
      canonical_reason: "Unreadable Document",
      human_explanation: "The attached document could not be read reliably.",
      affected_fields: [],
      affected_area: "Documents",
      suggested_action: "Inspect document readability",
      comparison: null,
      documents: [
        {
          id: "44444444-4444-4444-8444-444444444444",
          attachment_id: "att-514",
          filename: "email_514_SI.pdf",
          role: "UNKNOWN",
          format: "PDF",
          validation_outcome: "INCONCLUSIVE",
          routing_outcome: "UNREADABLE_ATTACHMENT",
          failure_reason: "OCR engine (tesseract) is not installed or not found in PATH",
        },
      ],
    };

    setupFetch({
      humanReview: {
        total: 1,
        skip: 0,
        limit: 50,
        items: [unreadableDocReview],
      },
      reviewDetail: unreadableDocReview,
    });
    window.history.replaceState({}, "", "/?review=88888888-8888-4888-8888-888888888888");

    render(<App />);

    // Renders Document Exception tab
    expect(await screen.findByRole("tab", { name: /Document Exception/i })).toBeInTheDocument();

    // Does NOT render 7-field table or field correction form
    expect(screen.queryByRole("table", { name: "Human Review seven-field comparison" })).not.toBeInTheDocument();
    expect(screen.queryByText("Seven reviewed fields")).not.toBeInTheDocument();
    expect(screen.queryByText("Save a correction")).not.toBeInTheDocument();
    expect(screen.queryByText("Resolve & Recompare")).not.toBeInTheDocument();

    // Header title and description
    expect(screen.getAllByText("Unreadable Document").length).toBeGreaterThan(0);
    expect(screen.getAllByText("The attached document could not be read reliably.").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Affected area:\s*Documents/i).length).toBeGreaterThan(0);

    // Displays actual OCR/parser evidence separated into user-facing summary and technical detail
    expect(screen.getByText("email_514_SI.pdf")).toBeInTheDocument();
    expect(screen.getByText("Document content could not be extracted reliably.")).toBeInTheDocument();
    expect(screen.getByText("OCR engine (tesseract) is not installed or not found in PATH")).toBeInTheDocument();

    // Renders readability-specific SOP
    expect(screen.getByText(/Inspect the affected document:/i)).toBeInTheDocument();
    expect(screen.getByText(/Review processing evidence:/i)).toBeInTheDocument();
    expect(screen.getByText(/Determine the next step:/i)).toBeInTheDocument();

    // Readability resolution area with Retry/Reprocess action
    expect(screen.getByText("Document Readability Resolution")).toBeInTheDocument();
    expect(screen.getByText(/Obtain a clearer, machine-readable digital document/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry / Reprocess Email" })).toBeInTheDocument();

    // Dismiss Review is secondary with standard presets (no UNREADABLE_DOCUMENT preset)
    expect(screen.getByRole("button", { name: "NOT_ACTIONABLE" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "UNREADABLE_ATTACHMENT" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "UNREADABLE_DOCUMENT" })).not.toBeInTheDocument();
    const dismissButtons = screen.getAllByRole("button", { name: "Dismiss Review" });
    expect(dismissButtons.length).toBeGreaterThan(0);
    dismissButtons.forEach((btn) => {
      expect(btn.className).toContain("button-secondary");
    });
  });

  it("renders Document Exception workspace with Missing Document Resolution for MISSING_REQUIRED_ATTACHMENT", async () => {
    const missingDocReview = {
      ...demoHumanReview.items[0],
      id: "66666666-6666-4666-8666-666666666666",
      reason_code: "MISSING_REQUIRED_ATTACHMENT",
      reason_text: "Missing Attachment",
      presentation_title: "Missing Attachment",
      canonical_reason: "Missing Attachment",
      human_explanation: "A required shipping document is not available for comparison.",
      affected_fields: [],
      affected_area: "Documents",
      suggested_action: "Request or provide the missing document",
      comparison: null,
      documents: [
        {
          id: "33333333-3333-4333-8333-333333333333",
          attachment_id: "att-509",
          filename: "email_509_SI.txt",
          role: "SI",
          format: "PLAIN_TEXT",
          validation_outcome: "VALID",
          routing_outcome: "SI_FOUND",
        },
      ],
    };

    setupFetch({
      humanReview: {
        total: 1,
        skip: 0,
        limit: 50,
        items: [missingDocReview],
      },
      reviewDetail: missingDocReview,
    });
    window.history.replaceState({}, "", "/?review=66666666-6666-4666-8666-666666666666");

    render(<App />);

    // Document Exception workspace is rendered
    expect(await screen.findByRole("tab", { name: /Document Exception/i })).toBeInTheDocument();
    expect(screen.getByText("Missing required document exception")).toBeInTheDocument();

    // Seven Reviewed Fields is not rendered
    expect(screen.queryByRole("table", { name: "Human Review seven-field comparison" })).not.toBeInTheDocument();
    expect(screen.queryByText("Seven reviewed fields")).not.toBeInTheDocument();
    expect(screen.queryByText("Save a correction")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Corrected value")).not.toBeInTheDocument();

    // Resolve & Recompare is not shown
    expect(screen.queryByText("Resolve & Recompare")).not.toBeInTheDocument();

    // review reason is Missing Attachment
    expect(screen.getAllByText("Missing Attachment").length).toBeGreaterThan(0);
    expect(screen.getAllByText("A required shipping document is not available for comparison.").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Affected area:\s*Documents/i).length).toBeGreaterThan(0);

    // existing attachment evidence remains visible
    expect(screen.getByText("email_509_SI.txt")).toBeInTheDocument();
    expect(screen.getByText("Role: SI")).toBeInTheDocument();
    expect(screen.getByText("Validation: VALID")).toBeInTheDocument();
    expect(screen.getByText("Router: SI FOUND")).toBeInTheDocument();

    // missing Draft BL clearly identified as unresolved document requirement
    expect(screen.getByText(/Unresolved Requirement: Draft BL/i)).toBeInTheDocument();

    // guidance tells the reviewer to obtain the missing required document
    expect(screen.getByText("Missing Document Resolution")).toBeInTheDocument();
    expect(screen.getByText(/Recommended Action:/i)).toBeInTheDocument();
    expect(screen.getByText("Request or provide the missing document")).toBeInTheDocument();
    expect(screen.getByText(/Obtain the missing Draft BL from the sender/i)).toBeInTheDocument();

    // SOP wording updated
    expect(screen.getByText(/Confirm that the required SI or Draft BL is genuinely missing/i)).toBeInTheDocument();
    expect(screen.getByText(/Obtain the missing shipping document before comparison can continue/i)).toBeInTheDocument();

    // unsupported automatic follow-up behavior is not promised
    expect(screen.queryByText(/new verification case will be created automatically/i)).not.toBeInTheDocument();

    // MISSING_ATTACHMENT is not offered as a dismiss reason preset
    expect(screen.queryByRole("button", { name: "MISSING_ATTACHMENT" })).not.toBeInTheDocument();

    // Dismiss Review is secondary
    const dismissButtons = screen.getAllByRole("button", { name: "Dismiss Review" });
    expect(dismissButtons.length).toBeGreaterThan(0);
    dismissButtons.forEach((btn) => {
      expect(btn.className).toContain("button-secondary");
    });
  });
});

