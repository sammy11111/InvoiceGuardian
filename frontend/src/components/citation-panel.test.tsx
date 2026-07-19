import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { CitationPanel } from "@/components/citation-panel";
import { loadScenarioDetail } from "@/test/fixtures";

describe("CitationPanel", () => {
  it("renders S1's rate-mismatch exhibit verbatim with source label and side-by-side rates", () => {
    const scenario = loadScenarioDetail("INV-2026-061");
    render(<CitationPanel scenario={scenario} selectedFinding={null} />);

    expect(
      screen.getByText(
        "“Senior Consultant services shall be billed at CAD $150.00 per hour.”",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/MSA-2026-014 §4\.1, p\.2/)).toBeInTheDocument();
    expect(screen.getByText(/deterministic check/i)).toBeInTheDocument();
    expect(screen.getByText("175.00")).toBeInTheDocument();
    expect(screen.getByText("150.00")).toBeInTheDocument();
  });

  it("renders S5's aggregate-cap exhibit with total, cap, and excess", () => {
    const scenario = loadScenarioDetail("INV-2026-065");
    render(<CitationPanel scenario={scenario} selectedFinding={null} />);

    expect(screen.getByText(/Aggregate fees invoiced/)).toBeInTheDocument();
    expect(screen.getByText(/MSA-2026-014 §4\.3, p\.2/)).toBeInTheDocument();
    expect(screen.getByText("25,750.00")).toBeInTheDocument();
    expect(screen.getByText("25,000.00")).toBeInTheDocument();
    expect(screen.getByText("750.00")).toBeInTheDocument();
  });

  it("renders a clean empty state when a scenario has zero findings", () => {
    const scenario = loadScenarioDetail("INV-2026-063");
    render(<CitationPanel scenario={scenario} selectedFinding={null} />);

    expect(screen.getByText("No exceptions on this invoice")).toBeInTheDocument();
  });

  it("never renders a confidence score or percentage anywhere", () => {
    for (const invoiceId of [
      "INV-2026-061",
      "INV-2026-062",
      "INV-2026-063",
      "INV-2026-064",
      "INV-2026-065",
      "INV-2026-066",
    ]) {
      const scenario = loadScenarioDetail(invoiceId);
      const { container, unmount } = render(
        <CitationPanel scenario={scenario} selectedFinding={null} />,
      );
      expect(container.textContent?.toLowerCase()).not.toContain("confidence");
      expect(container.textContent).not.toMatch(/\d+(\.\d+)?%/);
      unmount();
    }
  });

  it("labels an ESCALATE finding as human review required, not a confident exception", () => {
    const scenario = loadScenarioDetail("INV-2026-062");
    render(<CitationPanel scenario={scenario} selectedFinding={null} />);

    expect(screen.getByText(/human review required/i)).toBeInTheDocument();
    expect(
      screen.getByText(/cannot conclusively include or exclude it/),
    ).toBeInTheDocument();
  });
});
