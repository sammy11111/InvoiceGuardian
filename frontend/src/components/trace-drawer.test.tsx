import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { TraceDrawer } from "@/components/trace-drawer";
import { loadScenarioDetail } from "@/test/fixtures";

describe("TraceDrawer", () => {
  it("renders the structured trace (documents, versions, rules, model calls, disposition)", () => {
    const scenario = loadScenarioDetail("INV-2026-061");
    render(
      <TraceDrawer
        open
        onOpenChange={() => {}}
        scenario={scenario}
        approvalState={scenario.approval_state}
        onApprovalChange={() => {}}
      />,
    );

    expect(screen.getByText("Operational trace")).toBeInTheDocument();
    expect(screen.getByText("MSA-2026-014")).toBeInTheDocument();
    expect(screen.getByText("SOW-2026-03")).toBeInTheDocument();
    expect(screen.getByText(/dataset v1\.3-2026-07-15/)).toBeInTheDocument();
    expect(screen.getByText(/Extracted facts \(\d+\)/)).toBeInTheDocument();
    expect(screen.getByText(/RATE_MISMATCH_CHECK · L1/)).toBeInTheDocument();
    expect(screen.getByText("MSA_EXTRACTION")).toBeInTheDocument();
    expect(screen.getAllByText("schema-valid").length).toBe(scenario.trace.model_calls.length);
  });

  it("surfaces the draft / no-communication-sent language from DraftedAction", () => {
    const scenario = loadScenarioDetail("INV-2026-061");
    render(
      <TraceDrawer
        open
        onOpenChange={() => {}}
        scenario={scenario}
        approvalState={scenario.approval_state}
        onApprovalChange={() => {}}
      />,
    );

    expect(screen.getByText(/no communication has been sent/i)).toBeInTheDocument();
  });

  it("clicking Approve/Reject updates local state only, via the callback", async () => {
    const user = userEvent.setup();
    const scenario = loadScenarioDetail("INV-2026-061");
    const onApprovalChange = vi.fn();

    render(
      <TraceDrawer
        open
        onOpenChange={() => {}}
        scenario={scenario}
        approvalState="AWAITING_REVIEW"
        onApprovalChange={onApprovalChange}
      />,
    );

    await user.click(screen.getByRole("button", { name: /approve/i }));
    expect(onApprovalChange).toHaveBeenCalledWith("APPROVED");

    await user.click(screen.getByRole("button", { name: /reject/i }));
    expect(onApprovalChange).toHaveBeenCalledWith("REJECTED");
  });

  it("shows 'no action required' for a clean scenario with no drafted action", () => {
    const scenario = loadScenarioDetail("INV-2026-063");
    render(
      <TraceDrawer
        open
        onOpenChange={() => {}}
        scenario={scenario}
        approvalState={scenario.approval_state}
        onApprovalChange={() => {}}
      />,
    );

    expect(screen.getByText(/no action required/i)).toBeInTheDocument();
  });
});
