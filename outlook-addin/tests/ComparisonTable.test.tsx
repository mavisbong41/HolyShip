import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ComparisonTable } from "../src/components/ComparisonTable";
import { fixtures } from "./fixtures";

describe("ComparisonTable", () => {
  it("renders all seven canonical field rows", () => {
    render(<ComparisonTable comparison={fixtures.cleanMatch.comparison!} />);
    expect(screen.getByText("Shipper")).toBeInTheDocument();
    expect(screen.getByText("Consignee")).toBeInTheDocument();
    expect(screen.getByText("Notify Party")).toBeInTheDocument();
    expect(screen.getByText("Port of Loading")).toBeInTheDocument();
    expect(screen.getByText("Port of Discharge")).toBeInTheDocument();
    expect(screen.getByText("Container Count")).toBeInTheDocument();
    expect(screen.getByText("Gross Weight")).toBeInTheDocument();
  });

  it("renders MATCH badges for all clean fields", () => {
    render(<ComparisonTable comparison={fixtures.cleanMatch.comparison!} />);
    const matches = screen.getAllByText("Match");
    expect(matches).toHaveLength(7);
  });

  it("renders MISMATCH badge for mismatched fields", () => {
    render(<ComparisonTable comparison={fixtures.mismatchDetected.comparison!} />);
    const mismatches = screen.getAllByText("Mismatch");
    expect(mismatches.length).toBeGreaterThanOrEqual(2);
  });

  it("renders UNRESOLVED badge for unresolved fields", () => {
    render(<ComparisonTable comparison={fixtures.mismatchDetected.comparison!} />);
    const unresolved = screen.getAllByText("Unresolved");
    expect(unresolved.length).toBeGreaterThanOrEqual(1);
  });

  it("shows SI and BL column headers", () => {
    render(<ComparisonTable comparison={fixtures.cleanMatch.comparison!} />);
    expect(screen.getByText("SI")).toBeInTheDocument();
    expect(screen.getByText("Draft BL")).toBeInTheDocument();
  });

  it("displays SI and BL values from backend, does not compare locally", () => {
    render(<ComparisonTable comparison={fixtures.mismatchDetected.comparison!} />);
    // The gross_weight_kg mismatch values
    expect(screen.getByText("22,000 KG")).toBeInTheDocument();
    expect(screen.getByText("24,500 KG")).toBeInTheDocument();
  });

  it("renders em dash for missing values safely", () => {
    render(<ComparisonTable comparison={fixtures.mismatchDetected.comparison!} />);
    // notify_party BL is null — should show em dash, not throw
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThan(0);
  });

  it("has accessible table with aria-label", () => {
    render(<ComparisonTable comparison={fixtures.cleanMatch.comparison!} />);
    expect(
      screen.getByRole("table", { name: /SI vs BL field comparison/i }),
    ).toBeInTheDocument();
  });

  it("has scope='col' on all column headers", () => {
    const { container } = render(<ComparisonTable comparison={fixtures.cleanMatch.comparison!} />);
    const ths = container.querySelectorAll("th[scope='col']");
    expect(ths.length).toBe(4); // Field, SI, Draft BL, Status
  });
});
