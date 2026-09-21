import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { TaskPane } from "../src/components/TaskPane";
import { FakeCurrentMailContextProvider } from "../src/office/FakeContextProvider";
import type { MailContextItem, MailContextProvider, MailContextResult } from "../src/types/context";
import type { ProductEmailDetail } from "../src/types/product";
import * as clientModule from "../src/api/client";
import { fixtures } from "./fixtures";

// Mock the identity adapter module
vi.mock("../src/office/IdentityAdapter", () => ({
  IdentityAdapter: vi.fn(),
}));

import { IdentityAdapter } from "../src/office/IdentityAdapter";
const MockAdapter = vi.mocked(IdentityAdapter);

type ResolveResult = {
  detail: ProductEmailDetail | null;
  strategy: string;
  confidence: "high" | "low" | "none";
  limitationNote: string | null;
};

function setupAdapter(result: ResolveResult): void {
  MockAdapter.mockImplementation(
    () => ({ resolve: vi.fn().mockResolvedValue(result) }) as unknown as InstanceType<typeof IdentityAdapter>,
  );
}

const provider = new FakeCurrentMailContextProvider();

class MutableMailContextProvider implements MailContextProvider {
  constructor(private item: MailContextItem) {}

  setItem(item: MailContextItem): void {
    this.item = item;
  }

  async getContext(): Promise<MailContextResult> {
    return { state: "ready", item: this.item, error: null };
  }
}

describe("TaskPane", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    const testGlobal = globalThis as unknown as { Office?: unknown };
    delete testGlobal.Office;
    setupAdapter({ detail: null, strategy: "not_resolved", confidence: "none", limitationNote: "Test: not found" });
  });

  it("shows loading state initially", () => {
    MockAdapter.mockImplementation(
      () => ({ resolve: vi.fn(() => new Promise(() => undefined)) }) as unknown as InstanceType<typeof IdentityAdapter>,
    );
    render(<TaskPane contextProvider={provider} />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.getByText(/checking holyship/i)).toBeInTheDocument();
  });

  it("shows not-found state when no case resolved", async () => {
    setupAdapter({ detail: null, strategy: "not_resolved", confidence: "none", limitationNote: null });
    render(<TaskPane contextProvider={provider} />);
    await waitFor(() => {
      expect(screen.getByText(/not in holyship/i)).toBeInTheDocument();
    });
  });

  it("does not repeat the HolyShip logo inside the Outlook app pane", async () => {
    setupAdapter({ detail: fixtures.cleanMatch, strategy: "internet_message_id", confidence: "high", limitationNote: null });
    render(<TaskPane contextProvider={provider} />);
    await waitFor(() => {
      expect(screen.getByText(/no mismatch detected/i)).toBeInTheDocument();
    });
    expect(screen.queryByAltText("HolyShip")).not.toBeInTheDocument();
  });

  it("re-resolves when Outlook reports that the selected email changed", async () => {
    const firstDetail = fixtures.cleanMatch;
    const secondDetail: ProductEmailDetail = {
      ...fixtures.newSiRequest,
      email: {
        ...fixtures.newSiRequest.email,
        id: "email-002",
        subject: "Please create SI for booking BKG-20240502",
        sender: "ops@example.com",
      },
    };
    const resolveMock = vi
      .fn()
      .mockResolvedValueOnce({
        detail: firstDetail,
        strategy: "internet_message_id",
        confidence: "high",
        limitationNote: null,
      })
      .mockResolvedValueOnce({
        detail: secondDetail,
        strategy: "internet_message_id",
        confidence: "high",
        limitationNote: null,
      });
    MockAdapter.mockImplementation(
      () => ({ resolve: resolveMock }) as unknown as InstanceType<typeof IdentityAdapter>,
    );

    let itemChangedHandler: (() => void) | null = null;
    const testGlobal = globalThis as unknown as { Office?: unknown };
    testGlobal.Office = {
      context: {
        mailbox: {
          addHandlerAsync: vi.fn((_event, handler, callback) => {
            itemChangedHandler = handler;
            callback({ status: "succeeded" });
          }),
          removeHandlerAsync: vi.fn(),
        },
      },
      EventType: { ItemChanged: "ItemChanged" },
      AsyncResultStatus: { Succeeded: "succeeded" },
    };

    const mutableProvider = new MutableMailContextProvider({
      holyshipCaseId: null,
      outlookItemId: "outlook-001",
      internetMessageId: "<msg-001@example.com>",
      sender: "shipper@acme.com",
      subject: "Draft BL for BKG-20240501 for checking",
    });

    render(<TaskPane contextProvider={mutableProvider} />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: firstDetail.email.subject })).toBeInTheDocument();
    });

    mutableProvider.setItem({
      holyshipCaseId: null,
      outlookItemId: "outlook-002",
      internetMessageId: "<msg-002@example.com>",
      sender: "ops@example.com",
      subject: "Please create SI for booking BKG-20240502",
    });

    expect(itemChangedHandler).not.toBeNull();
    act(() => {
      itemChangedHandler?.();
    });

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Please create SI for booking BKG-20240502" })).toBeInTheDocument();
    });
    expect(resolveMock).toHaveBeenCalledTimes(2);
  });

  it("shows limitation note in not-found state", async () => {
    setupAdapter({ detail: null, strategy: "not_resolved", confidence: "none", limitationNote: "Graph identity required for accurate matching." });
    render(<TaskPane contextProvider={provider} />);
    await waitFor(() => {
      expect(screen.getByText(/Graph identity required/i)).toBeInTheDocument();
    });
  });

  it("renders clean match state correctly", async () => {
    setupAdapter({ detail: fixtures.cleanMatch, strategy: "internet_message_id", confidence: "high", limitationNote: null });
    render(<TaskPane contextProvider={provider} />);
    await waitFor(() => {
      expect(screen.getByText(/no mismatch detected/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/all seven fields match/i)).toBeInTheDocument();
  });

  it("renders mismatch state with mismatch count", async () => {
    setupAdapter({ detail: fixtures.mismatchDetected, strategy: "internet_message_id", confidence: "high", limitationNote: null });
    render(<TaskPane contextProvider={provider} />);
    await waitFor(() => {
      expect(screen.getByText(/confirmed discrepancy/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/2 fields mismatched/i)).toBeInTheDocument();
  });

  it("renders comparison table for document_comparison", async () => {
    setupAdapter({ detail: fixtures.cleanMatch, strategy: "internet_message_id", confidence: "high", limitationNote: null });
    render(<TaskPane contextProvider={provider} />);
    await waitFor(() => {
      expect(screen.getByRole("list", { name: /SI vs BL field comparison/i })).toBeInTheDocument();
    });
    expect(screen.getByText("Shipper")).toBeInTheDocument();
    expect(screen.getByText("Consignee")).toBeInTheDocument();
    expect(screen.getByText("Port of Loading")).toBeInTheDocument();
    expect(screen.getByText("Port of Discharge")).toBeInTheDocument();
    expect(screen.getByText("Container Count")).toBeInTheDocument();
    expect(screen.getByText("Gross Weight")).toBeInTheDocument();
    expect(screen.getByText("Notify Party")).toBeInTheDocument();
  });

  it("shows MATCH badges for clean comparison", async () => {
    setupAdapter({ detail: fixtures.cleanMatch, strategy: "internet_message_id", confidence: "high", limitationNote: null });
    render(<TaskPane contextProvider={provider} />);
    await waitFor(() => {
      const comparison = screen.getByRole("list", { name: /SI vs BL field comparison/i });
      const matches = within(comparison).getAllByText("Match");
      expect(matches.length).toBe(7);
    });
  });

  it("shows MISMATCH and UNRESOLVED badges", async () => {
    setupAdapter({ detail: fixtures.mismatchDetected, strategy: "internet_message_id", confidence: "high", limitationNote: null });
    render(<TaskPane contextProvider={provider} />);
    await waitFor(() => {
      const mismatches = screen.getAllByText("Mismatch");
      expect(mismatches.length).toBeGreaterThan(0);
      const unresolved = screen.getAllByText("Unresolved");
      expect(unresolved.length).toBeGreaterThan(0);
    });
  });

  it("renders awaiting documents state", async () => {
    setupAdapter({ detail: fixtures.awaitingDocuments, strategy: "internet_message_id", confidence: "high", limitationNote: null });
    render(<TaskPane contextProvider={provider} />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /waiting for documents/i })).toBeInTheDocument();
    });
    expect(screen.queryByRole("list", { name: /SI vs BL/i })).not.toBeInTheDocument();
  });

  it("renders blocked/needs review state", async () => {
    setupAdapter({ detail: fixtures.blocked, strategy: "internet_message_id", confidence: "high", limitationNote: null });
    render(<TaskPane contextProvider={provider} />);
    await waitFor(() => {
      const heading = screen.getByRole("heading", { name: /needs review/i });
      expect(heading).toBeInTheDocument();
    });
    expect(screen.getAllByText(/one or more document fields could not be verified/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Jordan Lee/i)).toBeInTheDocument();
    expect(screen.getByText(/affected field/i)).toBeInTheDocument();
    expect(screen.getAllByText(/^notify party$/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/suggested action/i)).toBeInTheDocument();
    expect(screen.getByText(/confirm notify party/i)).toBeInTheDocument();
    expect(screen.queryByText(/0 affected field/i)).not.toBeInTheDocument();
    const reviewLink = screen.getByRole("link", { name: /open human review/i });
    expect(reviewLink.getAttribute("href")).toContain("review=review-001");
  });

  it("renders legacy review records as non-actionable context", async () => {
    setupAdapter({ detail: fixtures.historicalReview, strategy: "internet_message_id", confidence: "high", limitationNote: null });
    render(<TaskPane contextProvider={provider} />);
    await waitFor(() => {
      expect(screen.getByText(/historical review record/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/no action required/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /open human review/i })).not.toBeInTheDocument();
  });

  it("renders compact AI companion entry without applying suggestions", async () => {
    setupAdapter({ detail: fixtures.aiSuggestion, strategy: "internet_message_id", confidence: "high", limitationNote: null });
    render(<TaskPane contextProvider={provider} />);
    await waitFor(() => {
      expect(screen.getByText(/ai suggestion available/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/gross weight may contain an ocr error/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open ai review/i })).toBeInTheDocument();
  });

  it("renders failed state", async () => {
    setupAdapter({ detail: fixtures.failed, strategy: "internet_message_id", confidence: "high", limitationNote: null });
    render(<TaskPane contextProvider={provider} />);
    await waitFor(() => {
      const heading = screen.getByRole("heading", { name: /processing failed/i });
      expect(heading).toBeInTheDocument();
    });
  });

  it("renders processing/in-progress state", async () => {
    setupAdapter({ detail: fixtures.processing, strategy: "internet_message_id", confidence: "high", limitationNote: null });
    render(<TaskPane contextProvider={provider} />);
    await waitFor(() => {
      expect(screen.getByText(/processing email/i)).toBeInTheDocument();
    });
  });

  it("does not render comparison table for non-document-comparison category", async () => {
    setupAdapter({ detail: fixtures.newSiRequest, strategy: "internet_message_id", confidence: "high", limitationNote: null });
    render(<TaskPane contextProvider={provider} />);
    await waitFor(() => {
      // The h2 heading in the state card shows "Completed"
      expect(screen.getByRole("heading", { name: /^completed$/i })).toBeInTheDocument();
    });
    expect(screen.queryByRole("list", { name: /SI vs BL/i })).not.toBeInTheDocument();
  });

  it("shows 'Open in Dashboard' link when case is resolved", async () => {
    setupAdapter({ detail: fixtures.cleanMatch, strategy: "internet_message_id", confidence: "high", limitationNote: null });
    render(<TaskPane contextProvider={provider} />);
    // Wait for the state to be ready first
    await waitFor(() => {
      expect(screen.getByText(/no mismatch detected/i)).toBeInTheDocument();
    });
    // Link should be present with correct href
    const link = screen.getByText(/open in dashboard/i).closest("a");
    expect(link).toBeInTheDocument();
    expect(link?.getAttribute("href")).toContain("email-001");
  });

  it("does not show dashboard link when case not found", async () => {
    setupAdapter({ detail: null, strategy: "not_resolved", confidence: "none", limitationNote: null });
    render(<TaskPane contextProvider={provider} />);
    await waitFor(() => {
      expect(screen.getByText(/not in holyship/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/open in dashboard/i)).not.toBeInTheDocument();
  });

  it("shows low-confidence limitation note when case resolved with subject search", async () => {
    setupAdapter({ detail: fixtures.cleanMatch, strategy: "subject_search", confidence: "low", limitationNote: "Matched by subject text only." });
    render(<TaskPane contextProvider={provider} />);
    await waitFor(() => {
      expect(screen.getByText(/matched by subject text only/i)).toBeInTheDocument();
    });
  });

  describe("AI Review Assistant Companion", () => {
    it("renders AI Review Assistant section and chips when active review exists", async () => {
      setupAdapter({ detail: fixtures.blocked, strategy: "internet_message_id", confidence: "high", limitationNote: null });
      render(<TaskPane contextProvider={provider} />);

      await waitFor(() => {
        expect(screen.getByRole("region", { name: "AI Review Assistant Companion" })).toBeInTheDocument();
      });
      expect(screen.getByText("AI Review Assistant")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Why does this need review?" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Suggest field overrides" })).toBeInTheDocument();
    });

    it("queries AI assistant on chip click, displays explanation and actionable suggestion with deep link", async () => {
      const mockAsk = vi.spyOn(clientModule, "askAIAssistant").mockResolvedValue({
        message: "The container count in Draft BL differs from SI.",
        mode: "ACTIONABLE_SUGGESTION",
        suggestion_id: "sugg-out-1",
        provider_name: "test-provider",
        provider_model: "test-model",
        suggestion: {
          action: "FIELD_OVERRIDE",
          document_side: "BL",
          field: "container_count",
          current_value: "4",
          suggested_value: "2",
          confidence: 0.95,
          reason: "SI explicitly states 2 x 40'HC.",
          evidence_refs: ["SI Page 1: 2 x 40'HC"],
        },
      });

      const user = userEvent.setup();
      setupAdapter({ detail: fixtures.blocked, strategy: "internet_message_id", confidence: "high", limitationNote: null });
      render(<TaskPane contextProvider={provider} />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Suggest field overrides" })).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: "Suggest field overrides" }));

      expect(mockAsk).toHaveBeenCalledWith("review-001", "Suggest field overrides");

      expect(await screen.findByText("The container count in Draft BL differs from SI.")).toBeInTheDocument();
      expect(screen.getByText(/Proposed: BL · Container Count/i)).toBeInTheDocument();
      expect(screen.getByText("95%")).toBeInTheDocument();
      expect(screen.getByText("SI explicitly states 2 x 40'HC.")).toBeInTheDocument();
      expect(screen.getByText("SI Page 1: 2 x 40'HC")).toBeInTheDocument();

      const applyLink = screen.getByRole("link", { name: /Open Review & Apply in HolyShip/i });
      expect(applyLink).toBeInTheDocument();
      expect(applyLink.getAttribute("href")).toContain("review=review-001");
    });

    it("displays error notice gracefully when AI assistant call fails", async () => {
      vi.spyOn(clientModule, "askAIAssistant").mockRejectedValue(new Error("AI service timeout"));

      const user = userEvent.setup();
      setupAdapter({ detail: fixtures.blocked, strategy: "internet_message_id", confidence: "high", limitationNote: null });
      render(<TaskPane contextProvider={provider} />);

      await waitFor(() => {
        expect(screen.getByRole("button", { name: "Why does this need review?" })).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: "Why does this need review?" }));

      expect(await screen.findByRole("alert")).toHaveTextContent("AI service timeout");
    });
  });
});
