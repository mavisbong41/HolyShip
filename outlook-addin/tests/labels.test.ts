import { describe, expect, it } from "vitest";
import {
  categoryLabels,
  statusLabels,
  fieldLabels,
  fieldStatusLabels,
  readinessLabels,
  labelForField,
  displayValue,
  formatDate,
} from "../src/lib/labels";
import { dashboardBaseUrl, dashboardEmailUrl } from "../src/lib/config";

describe("categoryLabels", () => {
  it("maps all five backend categories", () => {
    expect(categoryLabels.document_comparison).toBe("Document Comparison");
    expect(categoryLabels.new_si_request).toBe("New Shipping Instruction");
    expect(categoryLabels.invoice_query).toBe("Invoice Query");
    expect(categoryLabels.general_message).toBe("General Message");
    expect(categoryLabels.spam).toBe("Spam");
  });

  it("does not change backend enum values", () => {
    // Backend values are used as keys, not mutated
    expect(Object.keys(categoryLabels)).toEqual([
      "document_comparison",
      "new_si_request",
      "invoice_query",
      "general_message",
      "spam",
    ]);
  });
});

describe("statusLabels", () => {
  it("maps BLOCKED to the shared Needs Review label", () => {
    expect(statusLabels.BLOCKED).toBe("Needs Review");
  });
  it("maps AWAITING_DOCUMENTS correctly", () => {
    expect(statusLabels.AWAITING_DOCUMENTS).toBe("Awaiting Documents");
  });
  it("maps FAILED correctly", () => {
    expect(statusLabels.FAILED).toBe("Processing Failed");
  });
  it("maps all eleven statuses", () => {
    const keys = Object.keys(statusLabels);
    expect(keys).toContain("NEW");
    expect(keys).toContain("QUEUED");
    expect(keys).toContain("CLASSIFYING");
    expect(keys).toContain("CLASSIFIED");
    expect(keys).toContain("AWAITING_DOCUMENTS");
    expect(keys).toContain("RETRIEVING_ATTACHMENTS");
    expect(keys).toContain("EXTRACTING");
    expect(keys).toContain("COMPARING");
    expect(keys).toContain("COMPLETED");
    expect(keys).toContain("BLOCKED");
    expect(keys).toContain("FAILED");
  });
});

describe("fieldLabels", () => {
  it("maps all seven canonical fields", () => {
    expect(fieldLabels.shipper).toBe("Shipper");
    expect(fieldLabels.consignee).toBe("Consignee");
    expect(fieldLabels.notify_party).toBe("Notify Party");
    expect(fieldLabels.port_of_loading).toBe("Port of Loading");
    expect(fieldLabels.port_of_discharge).toBe("Port of Discharge");
    expect(fieldLabels.container_count).toBe("Container Count");
    expect(fieldLabels.gross_weight_kg).toBe("Gross Weight");
  });
});

describe("fieldStatusLabels", () => {
  it("maps MATCH", () => expect(fieldStatusLabels.MATCH).toBe("Match"));
  it("maps MISMATCH", () => expect(fieldStatusLabels.MISMATCH).toBe("Mismatch"));
  it("maps UNRESOLVED", () => expect(fieldStatusLabels.UNRESOLVED).toBe("Unresolved"));
});

describe("readinessLabels", () => {
  it("maps all three readiness states", () => {
    expect(readinessLabels.READY_FOR_COMPARISON).toBe("Ready for Comparison");
    expect(readinessLabels.AWAITING_DOCUMENTS).toBe("Awaiting Documents");
    expect(readinessLabels.UNRESOLVED).toBe("Readiness Unresolved");
  });
});

describe("labelForField", () => {
  it("returns human label for canonical field", () => {
    expect(labelForField("shipper")).toBe("Shipper");
    expect(labelForField("gross_weight_kg")).toBe("Gross Weight");
  });

  it("title-cases unknown fields", () => {
    expect(labelForField("some_field_name")).toBe("Some Field Name");
  });
});

describe("displayValue", () => {
  it("returns em dash for null", () => expect(displayValue(null)).toBe("—"));
  it("returns em dash for undefined", () => expect(displayValue(undefined)).toBe("—"));
  it("returns em dash for empty string", () => expect(displayValue("")).toBe("—"));
  it("returns string representation of number", () => expect(displayValue(22000)).toBe("22000"));
  it("returns string as-is", () => expect(displayValue("Port Klang")).toBe("Port Klang"));
});

describe("formatDate", () => {
  it("returns No timestamp for null", () => expect(formatDate(null)).toBe("No timestamp"));
  it("formats a valid ISO date", () => {
    const result = formatDate("2024-05-01T09:00:00Z");
    expect(result).not.toBe("No timestamp");
    expect(typeof result).toBe("string");
  });
});

describe("dashboardEmailUrl", () => {
  it("includes the email ID", () => {
    const url = dashboardEmailUrl("email-001");
    expect(url).toContain("email-001");
    expect(url).toContain("email=");
  });

  it("uses the base URL from config", () => {
    const url = dashboardEmailUrl("email-001");
    expect(url.startsWith(dashboardBaseUrl())).toBe(true);
  });

  it("encodes special characters in email ID", () => {
    const url = dashboardEmailUrl("email with spaces");
    expect(url).not.toContain(" ");
  });
});
