import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { TaskPane } from "../src/components/TaskPane";
import { FakeCurrentMailContextProvider } from "../src/office/FakeContextProvider";
import type { MailContextItem, MailContextProvider, MailContextResult } from "../src/types/context";
import type { ProductEmailDetail, ProductReviewPlan } from "../src/types/product";
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

function reviewPlan(overrides: Partial<ProductReviewPlan> = {}): ProductReviewPlan {
  return {
    id: "plan-001",
    review_case_id: "review-001",
    status: "DRAFT",
    created_by: "Outlook reviewer",
    confirmed_at: null,
    confirmed_by: null,
    applied_comparison_id: null,
    error_message: null,
    items: [
      {
        id: "item-001",
        ai_suggestion_id: "suggestion-001",
        document_side: "BL",
        field: "gross_weight_kg",
        current_value: "24850",
        proposed_value: "22000",
        human_edited_value: null,
        reason: "SI states 22,000 KG.",
        confidence: 0.94,
        action: "FIELD_OVERRIDE",
        status: "PROPOSED",
        created_at: "2026-09-25T01:00:00Z",
        updated_at: "2026-09-25T01:00:00Z",
      },
    ],
    created_at: "2026-09-25T01:00:00Z",
    updated_at: "2026-09-25T01:00:00Z",
    ...overrides,
  };
}

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
    vi.spyOn(clientModule, "listReviewPlans").mockResolvedValue([]);
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
    expect(screen.getByRole("region", { name: "Outlook Review Plan" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add manual correction/i })).toBeInTheDocument();
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
      expect(mockSummary).toHaveBeenCalledWith("email-001", "Captain Jack");
    });

    await user.click(await screen.findByRole("button", { name: /generate draft/i }));
    await waitFor(() => {
      expect(mockGenerate).toHaveBeenCalledWith("email-001", ["Acknowledge discrepancy"], "Captain Jack");
    });

    await user.click(await screen.findByRole("button", { name: /confirm/i }));
    await waitFor(() => {
      expect(mockSend).toHaveBeenCalledWith("email-001", draftWorkflow.draft, "Captain Jack");
    });
  });

  describe("Outlook Review Plan", () => {
    it("offers one shared plan for all pending AI suggestions", async () => {
      setupAdapter({ detail: fixtures.aiSuggestion, strategy: "internet_message_id", confidence: "high", limitationNote: null });
      render(<TaskPane contextProvider={provider} />);

      expect(await screen.findByRole("region", { name: "Outlook Review Plan" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /create plan from 1 pending suggestion/i })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /add manual correction/i })).toBeInTheDocument();
    });

    it("creates and renders an AI-backed plan item", async () => {
      const plan = reviewPlan();
      const create = vi.spyOn(clientModule, "createReviewPlan").mockResolvedValue(plan);
      const user = userEvent.setup();
      setupAdapter({ detail: fixtures.aiSuggestion, strategy: "internet_message_id", confidence: "high", limitationNote: null });
      render(<TaskPane contextProvider={provider} />);

      await user.click(await screen.findByRole("button", { name: /create plan from 1 pending suggestion/i }));

      await waitFor(() => expect(create).toHaveBeenCalledWith(fixtures.aiSuggestion.review[0], "Jordan Lee"));
      expect(screen.getByText("Source: AI")).toBeInTheDocument();
      expect(screen.getByText("SI states 22,000 KG.")).toBeInTheDocument();
      expect(screen.getByText("94%")).toBeInTheDocument();
    });

    it("supports approve, edit, reject, then confirms the plan once", async () => {
      const base = reviewPlan();
      const plan = reviewPlan({
        items: [
          { ...base.items[0], id: "item-approve", field: "gross_weight_kg", status: "APPROVED" },
          { ...base.items[0], id: "item-edit", field: "container_count", status: "EDITED", human_edited_value: "2" },
          { ...base.items[0], id: "item-reject", field: "notify_party", status: "REJECTED" },
        ],
      });
      vi.mocked(clientModule.listReviewPlans).mockResolvedValue([plan]);
      const update = vi.spyOn(clientModule, "updateReviewPlanItem").mockResolvedValue(plan);
      const applied = reviewPlan({ ...plan, status: "APPLIED" });
      const confirm = vi.spyOn(clientModule, "confirmReviewPlan").mockResolvedValue(applied);
      const user = userEvent.setup();
      setupAdapter({ detail: fixtures.aiSuggestion, strategy: "internet_message_id", confidence: "high", limitationNote: null });
      render(<TaskPane contextProvider={provider} />);

      const articles = await screen.findAllByRole("article");
      await user.click(within(articles[0]).getByRole("button", { name: /approve/i }));
      await user.click(within(articles[2]).getByRole("button", { name: /reject/i }));
      await waitFor(() => expect(update).toHaveBeenCalledTimes(2));
      await user.click(screen.getByRole("button", { name: /confirm implementation/i }));
      await waitFor(() => expect(confirm).toHaveBeenCalledTimes(1));
      expect(confirm).toHaveBeenCalledWith("review-001", "plan-001", "Jordan Lee");
    });

    it("creates a manual plan item with the canonical correction fields", async () => {
      const manualPlan = reviewPlan({
        items: [{ ...reviewPlan().items[0], id: "manual-001", ai_suggestion_id: null, field: "shipper", proposed_value: "Correct Shipper", confidence: null }],
      });
      const createManual = vi.spyOn(clientModule, "createManualReviewPlan").mockResolvedValue(manualPlan);
      const user = userEvent.setup();
      setupAdapter({ detail: fixtures.blocked, strategy: "internet_message_id", confidence: "high", limitationNote: null });
      render(<TaskPane contextProvider={provider} />);

      await user.click(await screen.findByRole("button", { name: /add manual correction/i }));
      await user.clear(screen.getByLabelText("Current / Effective Value"));
      await user.type(screen.getByLabelText("Current / Effective Value"), "Old Shipper");
      await user.type(screen.getByLabelText("Proposed Corrected Value"), "Correct Shipper");
      await user.type(screen.getByLabelText("Reason / Note"), "Verified against signed SI.");
      await user.click(screen.getByRole("button", { name: /add to plan/i }));

      await waitFor(() => expect(createManual).toHaveBeenCalledWith(
        "review-001",
        "Jordan Lee",
        expect.objectContaining({ field: "shipper", current_value: "Old Shipper", proposed_value: "Correct Shipper" }),
      ));
      expect(screen.getByText("Source: Manual")).toBeInTheDocument();
    });

    it("shows a plan-loading failure without breaking the task pane", async () => {
      vi.mocked(clientModule.listReviewPlans).mockRejectedValue(new Error("Plan service timeout"));
      setupAdapter({ detail: fixtures.blocked, strategy: "internet_message_id", confidence: "high", limitationNote: null });
      render(<TaskPane contextProvider={provider} />);

      expect(await screen.findByRole("alert")).toHaveTextContent("Plan service timeout");
      expect(screen.getByRole("region", { name: "Outlook Review Plan" })).toBeInTheDocument();
    });

    it("handles active mismatches when review array has no active record without showing No Review Required", async () => {
      const detailWithoutReview: ProductEmailDetail = {
        ...fixtures.blocked,
        review: [],
      };
      setupAdapter({ detail: detailWithoutReview, strategy: "internet_message_id", confidence: "high", limitationNote: null });
      render(<TaskPane contextProvider={provider} />);

      expect(await screen.findByRole("button", { name: /review \d+ issues? →/i })).toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: /review \d+ issues? →/i }));

      expect(screen.queryByText(/no review required/i)).not.toBeInTheDocument();
      expect(screen.getByRole("region", { name: "Outlook Review Plan" })).toBeInTheDocument();
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
