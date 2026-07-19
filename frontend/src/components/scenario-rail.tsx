"use client";

import type { ScenarioSummary } from "@/lib/types";
import { cn } from "@/lib/utils";
import { DispositionBadge } from "./status-badge";

function formatCurrency(amount: string, currency: string): string {
  const value = Number.parseFloat(amount);
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  }).format(value);
}

export function ScenarioRail({
  scenarios,
  selectedInvoiceId,
  onSelect,
}: {
  scenarios: ScenarioSummary[];
  selectedInvoiceId: string;
  onSelect: (invoiceId: string) => void;
}) {
  return (
    <nav aria-label="Scenario selector" className="flex h-full flex-col gap-1.5 overflow-y-auto p-2.5">
      <p className="px-1.5 pt-0.5 pb-1 font-mono-tight text-[11px] tracking-widest text-sidebar-foreground/50 uppercase">
        Invoices — 6
      </p>
      {scenarios.map((scenario) => {
        const isSelected = scenario.invoice_id === selectedInvoiceId;
        return (
          <button
            key={scenario.invoice_id}
            type="button"
            onClick={() => onSelect(scenario.invoice_id)}
            aria-pressed={isSelected}
            className={cn(
              "group relative flex flex-col gap-1 rounded-md border px-3 py-2 text-left transition-colors",
              isSelected
                ? "border-sidebar-accent bg-sidebar-accent"
                : "border-transparent hover:bg-sidebar-accent/50",
            )}
          >
            <span
              className={cn(
                "absolute top-0 left-0 h-full w-0.5 rounded-full bg-sidebar-foreground transition-opacity",
                isSelected ? "opacity-100" : "opacity-0",
              )}
              aria-hidden
            />
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono-tight text-[10px] font-medium text-sidebar-foreground/55">
                {scenario.scenario_label} · {scenario.invoice_date}
              </span>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-display text-sm font-medium text-sidebar-foreground">
                {scenario.invoice_id}
              </span>
              <span className="tabular-figures font-mono-tight text-[11px] text-sidebar-foreground/75">
                {formatCurrency(scenario.invoice_total_cad, scenario.currency)}
              </span>
            </div>
            <DispositionBadge disposition={scenario.disposition} className="w-fit" />
          </button>
        );
      })}
    </nav>
  );
}
