"use client";

import { useMemo, useState } from "react";
import { ListTree, ShieldCheck } from "lucide-react";

import { CitationPanel } from "@/components/citation-panel";
import { InvoiceLinesPanel } from "@/components/invoice-lines-panel";
import { ScenarioRail } from "@/components/scenario-rail";
import { ScopeLine } from "@/components/scope-line";
import { TraceDrawer } from "@/components/trace-drawer";
import { Button } from "@/components/ui/button";
import type { ApprovalState, ExceptionFinding, ScenarioDetail } from "@/lib/types";

export function AppShell({ scenarios }: { scenarios: ScenarioDetail[] }) {
  const [selectedInvoiceId, setSelectedInvoiceId] = useState(scenarios[0]?.summary.invoice_id);
  const [selectedFinding, setSelectedFinding] = useState<ExceptionFinding | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [approvalStates, setApprovalStates] = useState<Record<string, ApprovalState>>(() =>
    Object.fromEntries(scenarios.map((s) => [s.summary.invoice_id, s.approval_state])),
  );

  const summaries = useMemo(() => scenarios.map((s) => s.summary), [scenarios]);
  const selectedScenario =
    scenarios.find((s) => s.summary.invoice_id === selectedInvoiceId) ?? scenarios[0];

  function handleSelectScenario(invoiceId: string) {
    setSelectedInvoiceId(invoiceId);
    setSelectedFinding(null);
  }

  if (!selectedScenario) {
    return null;
  }

  const approvalState = approvalStates[selectedScenario.summary.invoice_id];

  return (
    <div className="flex h-screen flex-col bg-background">
      <header className="flex shrink-0 items-center justify-between gap-4 border-b border-border bg-card px-5 py-2.5">
        <div className="flex items-center gap-2.5">
          <ShieldCheck className="size-5 text-foreground" strokeWidth={1.75} aria-hidden />
          <span className="font-display text-base font-semibold text-foreground">
            InvoiceGuardian
          </span>
          <span className="hidden font-mono-tight text-[11px] text-muted-foreground md:inline">
            Service Invoice Exception Review
          </span>
        </div>
        <Button size="sm" variant="outline" onClick={() => setDrawerOpen(true)}>
          <ListTree className="size-3.5" /> View trace &amp; approve
        </Button>
      </header>

      <div className="flex min-h-0 flex-1">
        <aside className="w-[248px] shrink-0 border-r border-sidebar-border bg-sidebar">
          <ScenarioRail
            scenarios={summaries}
            selectedInvoiceId={selectedScenario.summary.invoice_id}
            onSelect={handleSelectScenario}
          />
        </aside>

        <main className="min-w-0 flex-1 border-r border-border">
          <InvoiceLinesPanel
            scenario={selectedScenario}
            selectedFinding={selectedFinding}
            onSelectFinding={setSelectedFinding}
          />
        </main>

        <aside className="w-[440px] shrink-0 bg-card/60">
          <CitationPanel scenario={selectedScenario} selectedFinding={selectedFinding} />
        </aside>
      </div>

      <footer className="shrink-0 border-t border-border bg-card px-5 py-2">
        <ScopeLine />
      </footer>

      <TraceDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        scenario={selectedScenario}
        approvalState={approvalState}
        onApprovalChange={(state) =>
          setApprovalStates((prev) => ({
            ...prev,
            [selectedScenario.summary.invoice_id]: state,
          }))
        }
      />
    </div>
  );
}
