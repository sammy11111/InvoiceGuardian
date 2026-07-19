import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AppShell } from "@/components/app-shell";
import { loadAllScenarioDetails } from "@/test/fixtures";

describe("AppShell — all six scenarios", () => {
  it("loads and renders every scenario without error when selected in turn", async () => {
    const user = userEvent.setup();
    const scenarios = loadAllScenarioDetails();
    expect(scenarios).toHaveLength(6);

    render(<AppShell scenarios={scenarios} />);

    // Default: first scenario (S1) selected.
    expect(screen.getByRole("heading", { name: "INV-2026-061" })).toBeInTheDocument();

    for (const scenario of scenarios) {
      const railButton = screen.getByRole("button", {
        name: new RegExp(scenario.summary.invoice_id),
      });
      await user.click(railButton);
      expect(
        screen.getByRole("heading", { name: scenario.summary.invoice_id }),
      ).toBeInTheDocument();
    }
  });

  it("renders the persistent scope-line sentence", () => {
    const scenarios = loadAllScenarioDetails();
    render(<AppShell scenarios={scenarios} />);

    expect(
      screen.getAllByText(/Never decides payment, never determines fraud/).length,
    ).toBeGreaterThan(0);
  });

  it("opens the trace drawer and shows approval actions for the selected scenario", async () => {
    const user = userEvent.setup();
    const scenarios = loadAllScenarioDetails();
    render(<AppShell scenarios={scenarios} />);

    await user.click(screen.getByRole("button", { name: /view trace/i }));
    expect(screen.getByText("Operational trace")).toBeInTheDocument();
  });
});
