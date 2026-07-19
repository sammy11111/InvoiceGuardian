"use client";

import { AlertTriangle } from "lucide-react";

import type { ExceptionFinding, ScenarioDetail } from "@/lib/types";
import { cn } from "@/lib/utils";
import { LineStatusChip } from "./status-badge";

function formatMoney(amount: string): string {
  return new Intl.NumberFormat("en-CA", { minimumFractionDigits: 2 }).format(
    Number.parseFloat(amount),
  );
}

export function InvoiceLinesPanel({
  scenario,
  selectedFinding,
  onSelectFinding,
}: {
  scenario: ScenarioDetail;
  selectedFinding: ExceptionFinding | null;
  onSelectFinding: (finding: ExceptionFinding | null) => void;
}) {
  const { summary, lines, invoice_level_findings } = scenario;

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-5">
      <header className="flex flex-col gap-1 border-b border-border pb-4">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="font-display text-xl font-medium text-foreground">
            {summary.invoice_id}
          </h2>
          <span className="font-mono-tight text-xs text-muted-foreground">
            {summary.scenario_label}
          </span>
        </div>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 pt-2 text-xs text-muted-foreground">
          <div className="flex justify-between gap-2">
            <dt>Invoice date</dt>
            <dd className="tabular-figures font-mono-tight text-foreground">
              {summary.invoice_date}
            </dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt>SOW reference</dt>
            <dd className="font-mono-tight text-foreground">{summary.sow_reference}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt>Service period</dt>
            <dd className="tabular-figures font-mono-tight text-foreground">
              {summary.service_period_start} – {summary.service_period_end}
            </dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt>Total</dt>
            <dd className="tabular-figures font-mono-tight text-foreground">
              {formatMoney(summary.invoice_total_cad)} {summary.currency}
            </dd>
          </div>
        </dl>
      </header>

      {invoice_level_findings.map((finding) => (
        <button
          key={finding.finding_type}
          type="button"
          onClick={() => onSelectFinding(finding)}
          className={cn(
            "flex items-start gap-3 rounded-md border px-4 py-3 text-left transition-colors",
            "border-status-exception/30 bg-status-exception-bg",
            selectedFinding === finding && "ring-2 ring-status-exception ring-offset-1",
          )}
        >
          <AlertTriangle
            className="mt-0.5 size-4 shrink-0 text-status-exception"
            strokeWidth={2.25}
            aria-hidden
          />
          <div className="flex flex-col gap-0.5">
            <p className="text-sm font-medium text-status-exception">
              Invoice-level exception — {finding.finding_type.replaceAll("_", " ").toLowerCase()}
            </p>
            <p className="text-xs text-muted-foreground">
              Every line is individually valid; the aggregate total breaches the contract cap.
            </p>
          </div>
        </button>
      ))}

      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border text-left text-[11px] tracking-wide text-muted-foreground uppercase">
            <th className="py-2 pr-2 font-medium">Line</th>
            <th className="py-2 pr-2 font-medium">Description</th>
            <th className="py-2 pr-2 text-right font-medium">Hours</th>
            <th className="py-2 pr-2 text-right font-medium">Rate</th>
            <th className="py-2 pr-2 text-right font-medium">Amount</th>
            <th className="py-2 pl-2 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {lines.map((line) => {
            const finding = scenario.findings.find((f) => f.invoice_line_id === line.line_id);
            const isSelected = finding !== undefined && finding === selectedFinding;
            return (
              <tr
                key={line.line_id}
                onClick={() => finding && onSelectFinding(finding)}
                className={cn(
                  "border-b border-border/60 last:border-0",
                  finding && "cursor-pointer hover:bg-muted/60",
                  isSelected && "bg-muted",
                )}
              >
                <td className="py-2.5 pr-2 font-mono-tight text-xs text-muted-foreground">
                  {line.line_id}
                </td>
                <td className="py-2.5 pr-2 text-foreground">{line.description}</td>
                <td className="tabular-figures py-2.5 pr-2 text-right font-mono-tight text-foreground">
                  {line.hours}
                </td>
                <td className="tabular-figures py-2.5 pr-2 text-right font-mono-tight text-foreground">
                  {formatMoney(line.rate_cad)}
                </td>
                <td className="tabular-figures py-2.5 pr-2 text-right font-mono-tight text-foreground">
                  {formatMoney(line.amount_cad)}
                </td>
                <td className="py-2.5 pl-2">
                  <LineStatusChip status={line.status} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
