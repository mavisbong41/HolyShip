import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { TaskPane } from "../src/components/TaskPane";
import { FakeCurrentMailContextProvider } from "../src/office/FakeContextProvider";
import type { ProductEmailDetail } from "../src/types/product";
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

describe("TaskPane", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupAdapter({ detail: null, strategy: "not_resolved", confidence: "none", limitationNote: "Test: not found" });
  });

  it("shows loading state initially", () => {
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
      expect(screen.getByText(/mismatch detected/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/2 fields mismatched/i)).toBeInTheDocument();
  });

  it("renders comparison table for document_comparison", async () => {
    setupAdapter({ detail: fixtures.cleanMatch, strategy: "internet_message_id", confidence: "high", limitationNote: null });
    render(<TaskPane contextProvider={provider} />);
    await waitFor(() => {
      expect(screen.getByRole("table", { name: /SI vs BL field comparison/i })).toBeInTheDocument();
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
      const matches = screen.getAllByText("Match");
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
      expect(screen.getByText(/waiting for documents/i)).toBeInTheDocument();
    });
    expect(screen.queryByRole("table", { name: /SI vs BL/i })).not.toBeInTheDocument();
  });

  it("renders blocked/needs attention state", async () => {
    setupAdapter({ detail: fixtures.blocked, strategy: "internet_message_id", confidence: "high", limitationNote: null });
    render(<TaskPane contextProvider={provider} />);
    await waitFor(() => {
      // The state card h2 should say "Needs attention"
      const heading = screen.getByRole("heading", { name: /needs attention/i });
      expect(heading).toBeInTheDocument();
    });
    expect(screen.getByText(/COMPARISON UNRESOLVED/i)).toBeInTheDocument();
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
    expect(screen.queryByRole("table", { name: /SI vs BL/i })).not.toBeInTheDocument();
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
});
