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
    vi.restoreAllMocks();
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

  it("re-resolves when user clicks Refresh button", async () => {
    const detail = fixtures.cleanMatch;
    const resolveMock = vi.fn().mockResolvedValue({
      detail,
      strategy: "internet_message_id",
      confidence: "high",
      limitationNote: null,
    });
    MockAdapter.mockImplementation(
      () => ({ resolve: resolveMock }) as unknown as InstanceType<typeof IdentityAdapter>,
    );

    render(<TaskPane contextProvider={provider} />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: detail.email.subject })).toBeInTheDocument();
    });
    expect(resolveMock).toHaveBeenCalledTimes(1);

    const refreshBtn = screen.getByRole("button", { name: "Refresh case data" });
    const user = userEvent.setup();
    await user.click(refreshBtn);

    await waitFor(() => {
      expect(resolveMock).toHaveBeenCalledTimes(2);
    });
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

  it("saves manual category correction from Outlook", async () => {
    const updatedDetail: ProductEmailDetail = {
      ...fixtures.cleanMatch,
      email: {
        ...fixtures.cleanMatch.email,
        category: "invoice_query",
      },
    };
    const mockCategory = vi.spyOn(clientModule, "updateEmailCategory").mockResolvedValue(updatedDetail);
    const user = userEvent.setup();
    setupAdapter({ detail: fixtures.cleanMatch, strategy: "internet_message_id", confidence: "high", limitationNote: null });
    render(<TaskPane contextProvider={provider} />);

    await waitFor(() => {
      expect(screen.getByRole("region", { name: "Manual category correction" })).toBeInTheDocument();
    });

    await user.selectOptions(screen.getByLabelText("Category"), "invoice_query");
    await user.type(screen.getByLabelText("Reason"), "Customer is asking about invoice charges.");
    await user.click(screen.getByRole("button", { name: /save category/i }));

    await waitFor(() => {
      expect(mockCategory).toHaveBeenCalledWith(
        "email-001",
        "invoice_query",
        "Outlook reviewer",
        "Customer is asking about invoice charges.",
      );
    });
  });

  it("runs reply summary and draft workflow from Outlook", async () => {
    const summaryWorkflow = {
      email_id: "email-001",
      status: "KEY_POINTS_READY",
      summary: "Draft BL case needs a reply.",
      key_points: ["Acknowledge discrepancy"],
      draft: null,
      last_instruction: null,
      sent_at: null,
      updated_at: "2024-05-01T09:05:00Z",
    };
    const draftWorkflow = {
      ...summaryWorkflow,
      status: "DRAFT_READY",
      draft: "Dear Customer,\n\n- Acknowledge discrepancy\n\nBest regards,\nHolyShip Operations",
    };
    const sentWorkflow = {
      ...draftWorkflow,
      status: "SENT",
      sent_at: "2024-05-01T09:07:00Z",
    };
    const mockSummary = vi.spyOn(clientModule, "createReplySummary").mockResolvedValue(summaryWorkflow);
    const mockGenerate = vi.spyOn(clientModule, "generateReplyDraft").mockResolvedValue(draftWorkflow);
    const mockSend = vi.spyOn(clientModule, "sendReplyDraft").mockResolvedValue(sentWorkflow);
    const user = userEvent.setup();
    setupAdapter({ detail: fixtures.cleanMatch, strategy: "internet_message_id", confidence: "high", limitationNote: null });
    render(<TaskPane contextProvider={provider} />);

    await waitFor(() => {
      expect(screen.getByRole("region", { name: "Reply workflow" })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /prepare summary/i }));
    await waitFor(() => {
      expect(mockSummary).toHaveBeenCalledWith("email-001", "Outlook reviewer");
    });

    await user.click(await screen.findByRole("button", { name: /generate draft/i }));
    await waitFor(() => {
      expect(mockGenerate).toHaveBeenCalledWith("email-001", ["Acknowledge discrepancy"], "Outlook reviewer");
    });

    await user.click(await screen.findByRole("button", { name: /confirm sent/i }));
    await waitFor(() => {
      expect(mockSend).toHaveBeenCalledWith("email-001", draftWorkflow.draft, "Outlook reviewer");
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

    it("accepts an AI suggestion directly from Outlook and refreshes the case", async () => {
      const mockAccept = vi.spyOn(clientModule, "acceptAISuggestion").mockResolvedValue(fixtures.aiSuggestion.review[0]);
      const user = userEvent.setup();
      setupAdapter({ detail: fixtures.aiSuggestion, strategy: "internet_message_id", confidence: "high", limitationNote: null });
      render(<TaskPane contextProvider={provider} />);

      await waitFor(() => {
        expect(screen.getByRole("region", { name: "Pending AI suggestions" })).toBeInTheDocument();
      });

      await user.click(screen.getByRole("button", { name: /^Approve$/i }));

      await waitFor(() => {
        expect(mockAccept).toHaveBeenCalledWith("review-001", "suggestion-001", "Outlook reviewer");
      });
      expect(MockAdapter).toHaveBeenCalledTimes(2);
    });

    it("saves a manual override and confirms backend recomparison from Outlook", async () => {
      const mockOverride = vi.spyOn(clientModule, "saveHumanReviewOverride").mockResolvedValue(fixtures.blocked.review[0]);
      const mockResolve = vi.spyOn(clientModule, "resolveHumanReview").mockResolvedValue(fixtures.blocked.review[0]);
      const user = userEvent.setup();
      setupAdapter({ detail: fixtures.blocked, strategy: "internet_message_id", confidence: "high", limitationNote: null });
      render(<TaskPane contextProvider={provider} />);

      await waitFor(() => {
        expect(screen.getByRole("region", { name: "Outlook Human Review actions" })).toBeInTheDocument();
      });

      await user.clear(screen.getByLabelText("Corrected value"));
      await user.type(screen.getByLabelText("Corrected value"), "Same as consignee");
      await user.click(screen.getByRole("button", { name: /save override/i }));

      await waitFor(() => {
        expect(mockOverride).toHaveBeenCalledWith("review-001", expect.objectContaining({
          document_side: "BL",
          field: "notify_party",
          corrected_value: "Same as consignee",
          reviewer_name: "Jordan Lee",
        }));
      });

      await user.type(screen.getByLabelText("Confirmation notes"), "Confirmed in Outlook.");
      await user.click(screen.getByRole("button", { name: /confirm & re-compare/i }));

      await waitFor(() => {
        expect(mockResolve).toHaveBeenCalledWith("review-001", "Jordan Lee", "Confirmed in Outlook.");
      });
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

    it("renders deleted lifecycle banner and sync rail status", async () => {
      const deletedDetail = {
        ...fixtures.cleanMatch,
        email: {
          ...fixtures.cleanMatch.email,
          lifecycle: {
            lifecycle_status: "DELETED",
            outlook_read_state: "READ",
            outlook_categories: ["BL_COMPARISON"],
            outlook_folder_id: "trash",
            outlook_archived: false,
            last_outlook_sync_at: "2024-05-01T12:00:00Z",
            outlook_sync_error: null,
            deleted_at: "2024-05-01T12:00:00Z",
            restored_at: null,
          },
        },
      };
      setupAdapter({ detail: deletedDetail as any, strategy: "internet_message_id", confidence: "high", limitationNote: null });
      render(<TaskPane contextProvider={provider} />);
      await waitFor(() => {
        expect(screen.getByRole("status")).toHaveTextContent("Hidden from active queues; history and review evidence are preserved.");
      });
      expect(screen.getAllByText("Deleted").length).toBeGreaterThanOrEqual(2);
    });

    it("triggers best-effort lifecycle reconciliation on email resolution", async () => {
      const mockReconcile = vi.spyOn(clientModule, "reconcileOutlookLifecycle").mockResolvedValue(undefined);
      setupAdapter({ detail: fixtures.cleanMatch, strategy: "internet_message_id", confidence: "high", limitationNote: null });
      render(<TaskPane contextProvider={provider} />);
      await waitFor(() => {
        expect(mockReconcile).toHaveBeenCalledWith("email-001", expect.objectContaining({
          subject: expect.stringContaining("Draft BL"),
        }));
      });
    });

    it("restores email with explicit RESTORED lifecycle status", async () => {
      const mockReconcile = vi.spyOn(clientModule, "reconcileOutlookLifecycle").mockResolvedValue(undefined);
      const user = userEvent.setup();
      const deletedDetail = {
        ...fixtures.cleanMatch,
        email: {
          ...fixtures.cleanMatch.email,
          lifecycle: {
            lifecycle_status: "DELETED",
            outlook_read_state: "READ",
            outlook_categories: [],
            outlook_folder_id: "trash",
            outlook_archived: false,
            last_outlook_sync_at: "2024-05-01T12:00:00Z",
            outlook_sync_error: null,
            deleted_at: "2024-05-01T12:00:00Z",
            restored_at: null,
          },
        },
      };
      setupAdapter({ detail: deletedDetail as any, strategy: "internet_message_id", confidence: "high", limitationNote: null });
      render(<TaskPane contextProvider={provider} />);

      await waitFor(() => {
        expect(screen.getByText("Restore Email")).toBeInTheDocument();
      });

      const restoreBtn = screen.getByRole("button", { name: "Restore Email" });
      await user.click(restoreBtn);

      await waitFor(() => {
        expect(mockReconcile).toHaveBeenCalledWith("email-001", expect.objectContaining({
          lifecycle_status: "RESTORED",
          outlook_folder_id: "inbox",
        }));
      });
      mockReconcile.mockRestore();
    });

    it("renders lifecycle audit events in timeline card", async () => {
      const detailWithLifecycleAudit = {
        ...fixtures.cleanMatch,
        timeline: [
          {
            id: "ev-1",
            old_status: "NEW",
            new_status: "COMPLETED",
            reason_code: "OUTLOOK_EMAIL_DELETED",
            created_at: "2024-05-01T12:00:00Z",
          },
          {
            id: "ev-2",
            old_status: "COMPLETED",
            new_status: "COMPLETED",
            reason_code: "OUTLOOK_EMAIL_RESTORED",
            created_at: "2024-05-01T12:05:00Z",
          },
        ],
      };
      setupAdapter({ detail: detailWithLifecycleAudit as any, strategy: "internet_message_id", confidence: "high", limitationNote: null });
      render(<TaskPane contextProvider={provider} />);

      await waitFor(() => {
        expect(screen.getByText("Mailbox item deleted")).toBeInTheDocument();
        expect(screen.getByText("Mailbox item restored")).toBeInTheDocument();
      });
    });

    it("detects deleted items folder in reconcileOutlookLifecycle", async () => {
      const fetchSpy = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ email_id: "email-001", action: "OUTLOOK_EMAIL_DELETED", lifecycle: {} }),
      });
      vi.stubGlobal("fetch", fetchSpy);

      await clientModule.reconcileOutlookLifecycle("email-001", {
        outlookFolderId: "DeletedItems",
      } as any);

      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining("/outlook/reconcile"),
        expect.objectContaining({
          body: expect.stringContaining('"lifecycle_status":"DELETED"'),
        }),
      );
      vi.unstubAllGlobals();
    });
  });
});
