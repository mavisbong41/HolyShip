import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";
import type { DiscrepancyPage, ProductDiscrepancyDetail } from "../src/api/types";
import { demoDetail, demoHumanReview, demoQueue, demoSummary } from "../src/lib/fixtures";

const mockDiscrepancySummary = {
  id: "d1111111-1111-4111-8111-111111111111",
  email_id: "e1111111-1111-4111-8111-111111111111",
  external_message_id: "MSG-MISMATCH-001",
  subject: "Draft BL for Verification - Ref 9901",
  sender: "shipper@globalforwarding.com",
  received_at: "2026-09-21T10:00:00Z",
  created_at: "2026-09-21T10:00:00Z",
  mismatch_count: 1,
  mismatched_fields: ["consignee"],
  resolution_status: "OPEN" as const,
  acknowledged_at: null,
  acknowledged_by: null,
  resolved_at: null,
  resolved_by: null,
  resolution_notes: null,
  comparison_state: "COMPLETED",
};

const mockDiscrepancyPage: DiscrepancyPage = {
  items: [mockDiscrepancySummary],
  total: 1,
  open_count: 1,
  acknowledged_count: 0,
  resolved_count: 0,
  skip: 0,
  limit: 20,
};

const mockDiscrepancyDetail: ProductDiscrepancyDetail = {
  discrepancy: mockDiscrepancySummary,
  email: {
    id: "e1111111-1111-4111-8111-111111111111",
    external_message_id: "MSG-MISMATCH-001",
    source_type: "STATIC_BUNDLE",
    sender: "shipper@globalforwarding.com",
    subject: "Draft BL for Verification - Ref 9901",
    received_at: "2026-09-21T10:00:00Z",
    created_at: "2026-09-21T10:00:00Z",
    processing_status: "COMPLETED",
    attachment_count: 2,
    category: "document_comparison",
    classification_confidence: 0.95,
    comparison_readiness: "READY_FOR_COMPARISON",
    comparison_state: "COMPLETED",
    mismatch_count: 1,
    unresolved_count: 0,
    needs_review: false,
    review_status: null,
    review_reason: null,
  },
  email_body: "Please check the attached draft BL against our SI.",
  comparison: {
    state: "COMPLETED",
    mismatch_found: true,
    mismatched_fields: ["consignee"],
    unresolved_fields: [],
    reason_code: "L1_ENTITY_DIFFERENCE",
    message: "Discrepancy detected in consignee",
    fields: [
      {
        field: "shipper",
        si: { raw: "Alpha Logistics", canonical: "Alpha Logistics", normalized: "Alpha Logistics" },
        bl: { raw: "Alpha Logistics", canonical: "Alpha Logistics", normalized: "Alpha Logistics" },
        status: "MATCH",
        reason_code: "L0_EXACT_MATCH",
        evidence: [],
      },
      {
        field: "consignee",
        si: { raw: "Beta Imports Corp", canonical: "Beta Imports Corp", normalized: "Beta Imports Corp" },
        bl: { raw: "Gamma Overseas Ltd", canonical: "Gamma Overseas Ltd", normalized: "Gamma Overseas Ltd" },
        status: "MISMATCH",
        reason_code: "L1_ENTITY_DIFFERENCE",
        evidence: [],
      },
      {
        field: "notify_party",
        si: { raw: "Same As Consignee", canonical: "Beta Imports Corp", normalized: "Beta Imports Corp" },
        bl: { raw: "Same As Consignee", canonical: "Beta Imports Corp", normalized: "Beta Imports Corp" },
        status: "MATCH",
        reason_code: "L0_EXACT_MATCH",
        evidence: [],
      },
      {
        field: "port_of_loading",
        si: { raw: "Port Klang", canonical: "Port Klang", normalized: "Port Klang" },
        bl: { raw: "Port Klang", canonical: "Port Klang", normalized: "Port Klang" },
        status: "MATCH",
        reason_code: "L0_EXACT_MATCH",
        evidence: [],
      },
      {
        field: "port_of_discharge",
        si: { raw: "Singapore", canonical: "Singapore", normalized: "Singapore" },
        bl: { raw: "Singapore", canonical: "Singapore", normalized: "Singapore" },
        status: "MATCH",
        reason_code: "L0_EXACT_MATCH",
        evidence: [],
      },
      {
        field: "container_count",
        si: { raw: "3", canonical: 3, normalized: 3 },
        bl: { raw: "3", canonical: 3, normalized: 3 },
        status: "MATCH",
        reason_code: "L1_NUMERIC_EQUAL",
        evidence: [],
      },
      {
        field: "gross_weight_kg",
        si: { raw: "15,000 KG", canonical: 15000, normalized: 15000 },
        bl: { raw: "15,000 KG", canonical: 15000, normalized: 15000 },
        status: "MATCH",
        reason_code: "L1_NUMERIC_EQUAL",
        evidence: [],
      },
    ],
  },
  mismatched_fields_detail: [
    {
      field: "consignee",
      si: { raw: "Beta Imports Corp", canonical: "Beta Imports Corp", normalized: "Beta Imports Corp" },
      bl: { raw: "Gamma Overseas Ltd", canonical: "Gamma Overseas Ltd", normalized: "Gamma Overseas Ltd" },
      status: "MISMATCH",
      reason_code: "L1_ENTITY_DIFFERENCE",
      evidence: [],
    },
  ],
  attachments: [
    {
      id: "att-1",
      filename: "SI_9901.pdf",
      content_type: "application/pdf",
      external_attachment_id: "ext-1",
      retrieval_status: "RETRIEVED",
      retrieval_reason_code: null,
      content_sha256: "abc111",
    },
  ],
  documents: [
    {
      id: "doc-1",
      attachment_id: "att-1",
      filename: "SI_9901.pdf",
      role: "SI",
      format: "PDF",
      source_reference: "att-1",
      routing_outcome: "SI_FOUND",
      role_confidence: 1.0,
      role_evidence: {},
      validation_outcome: "VALID",
      read_status: "READ",
      reader_used: "PdfReader",
      extraction_quality: 1.0,
      failure_reason: null,
      fields: [],
    },
  ],
  overrides: [],
  timeline: [],
};

function jsonResponse(payload: unknown, ok = true, status = 200): Response {
  return {
    ok,
    status,
    statusText: ok ? "OK" : "Error",
    json: async () => payload,
  } as Response;
}

function setupDiscrepancyFetch() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";

    if (url.includes("/summary")) {
      return jsonResponse({
        ...demoSummary,
        mismatch_count: 1,
        confirmed_discrepancies_count: 1,
      });
    }
    if (url.includes("/emails?")) {
      return jsonResponse(demoQueue);
    }
    if (url.includes("/discrepancies?")) {
      return jsonResponse(mockDiscrepancyPage);
    }
    if (url.includes("/discrepancies/d1111111-1111-4111-8111-111111111111/acknowledge") && method === "POST") {
      return jsonResponse({
        ...mockDiscrepancyDetail,
        discrepancy: {
          ...mockDiscrepancySummary,
          resolution_status: "ACKNOWLEDGED",
          acknowledged_by: "Test Operator",
          acknowledged_at: "2026-09-21T11:00:00Z",
        },
      });
    }
    if (url.includes("/discrepancies/d1111111-1111-4111-8111-111111111111/resolve") && method === "POST") {
      return jsonResponse({
        ...mockDiscrepancyDetail,
        discrepancy: {
          ...mockDiscrepancySummary,
          resolution_status: "RESOLVED",
          resolved_by: "Test Operator",
          resolved_at: "2026-09-21T11:05:00Z",
          resolution_notes: "Checked with shipper",
        },
      });
    }
    if (url.includes("/discrepancies/d1111111-1111-4111-8111-111111111111/override") && method === "POST") {
      return jsonResponse({
        ...mockDiscrepancyDetail,
        overrides: [
          {
            id: "ov-1",
            comparison_result_id: mockDiscrepancySummary.id,
            document_side: "BL",
            field_name: "consignee",
            original_field_id: "f-1",
            corrected_value: "Beta Imports Corp",
            corrected_canonical_value: "Beta Imports Corp",
            reviewer_name: "Test Reviewer",
            note: "Corrected typo",
            active: true,
            created_at: "2026-09-21T11:10:00Z",
          },
        ],
      });
    }
    if (url.includes("/discrepancies/d1111111-1111-4111-8111-111111111111/recompare") && method === "POST") {
      return jsonResponse({
        discrepancy: { ...mockDiscrepancySummary, resolution_status: null },
        comparison: { ...mockDiscrepancyDetail.comparison, mismatch_found: false, mismatched_fields: [] },
      });
    }
    if (url.includes("/discrepancies/d1111111-1111-4111-8111-111111111111")) {
      return jsonResponse(mockDiscrepancyDetail);
    }
    if (url.includes("/human-review")) {
      return jsonResponse(demoHumanReview);
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

describe("Confirmed Discrepancies Workspace", () => {
  it("navigates to Discrepancies workspace and renders confirmed differences", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    setupDiscrepancyFetch();
    render(<App />);

    // Click Discrepancies in sidebar navigation
    const navBtn = await screen.findByRole("button", { name: /Discrepancies/i });
    await user.click(navBtn);

    // Verify left list shows the mismatch item
    expect(await screen.findByText("MSG-MISMATCH-001")).toBeInTheDocument();
    const subjects = await screen.findAllByText("Draft BL for Verification - Ref 9901");
    expect(subjects.length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText(/Confirmed Differences/i)).not.toBeInTheDocument();

    await user.click(await screen.findByRole("button", { name: "Open Review" }));

    // Verify right pane differences-first card
    expect(await screen.findByText(/Confirmed Differences/i)).toBeInTheDocument();
    expect(await screen.findByText("Beta Imports Corp")).toBeInTheDocument();
    expect(await screen.findByText("Gamma Overseas Ltd")).toBeInTheDocument();
    expect(await screen.findByText("SI (Reference Document)")).toBeInTheDocument();
    expect(await screen.findByText("Draft BL (Document Checked)")).toBeInTheDocument();
  });

  it("acknowledges an open discrepancy", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const fetchMock = setupDiscrepancyFetch();
    render(<App />);

    const navBtn = await screen.findByRole("button", { name: /Discrepancies/i });
    await user.click(navBtn);

    await user.click(await screen.findByRole("button", { name: "Open Review" }));

    // Wait for detail pane to load
    expect(await screen.findByText("Draft BL (Document Checked)")).toBeInTheDocument();

    // Click Acknowledge button
    const ackBtn = await screen.findByRole("button", { name: /^Acknowledge$/i });
    await user.click(ackBtn);

    // Verify API call
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/discrepancies/d1111111-1111-4111-8111-111111111111/acknowledge"),
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("toggles the complete 7-field canonical table", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    setupDiscrepancyFetch();
    render(<App />);

    const navBtn = await screen.findByRole("button", { name: /Discrepancies/i });
    await user.click(navBtn);

    await user.click(await screen.findByRole("button", { name: "Open Review" }));

    // Wait for detail pane to load
    expect(await screen.findByText("Draft BL (Document Checked)")).toBeInTheDocument();

    // Click toggle button
    const toggleBtn = await screen.findByRole("button", { name: /Show All 7 Canonical Comparison Fields/i });
    await user.click(toggleBtn);

    // Verify 7 canonical fields appear in the table
    const ports = await screen.findAllByText("Port Klang");
    expect(ports.length).toBeGreaterThanOrEqual(1);
    const discharge = await screen.findAllByText("Singapore");
    expect(discharge.length).toBeGreaterThanOrEqual(1);
    expect((await screen.findAllByText("Gross Weight")).length).toBeGreaterThanOrEqual(2);
  });
});
