"use client";

import { Check, CircleSlash, MessageSquareWarning, ShieldAlert } from "lucide-react";

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import type { ApprovalState, ScenarioDetail } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Deterministic rate/cap checks genuinely pass or fail. The semantic
 * comparison check isn't pass/fail in that sense — a non-EQUIVALENT outcome
 * means the system caught something worth review, not that anything broke.
 */
function ruleOutcomeLabel(rule: { rule_name: string; passed: boolean }): string {
  if (rule.passed) return "passed";
  return rule.rule_name === "SEMANTIC_COMPARISON_CHECK" ? "flagged" : "failed";
}

function TraceSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="font-mono-tight text-[11px] tracking-widest text-muted-foreground uppercase">
        {title}
      </h3>
      {children}
    </section>
  );
}

function ApprovalActions({
  scenario,
  approvalState,
  onApprovalChange,
}: {
  scenario: ScenarioDetail;
  approvalState: ApprovalState;
  onApprovalChange: (state: ApprovalState) => void;
}) {
  const draft = scenario.drafted_action;

  if (!draft) {
    return (
      <p className="rounded-md border border-status-clean/30 bg-status-clean-bg px-3 py-2.5 text-sm text-status-clean">
        No action required — this invoice has no findings to review.
      </p>
    );
  }

  const actionLabel =
    draft.action_type === "HUMAN_REVIEW" ? "Route to human review" : "Request clarification";

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant={approvalState === "APPROVED" ? "default" : "outline"}
          onClick={() => onApprovalChange("APPROVED")}
        >
          <Check className="size-3.5" /> Approve
        </Button>
        <Button
          size="sm"
          variant={approvalState === "REJECTED" ? "destructive" : "outline"}
          onClick={() => onApprovalChange("REJECTED")}
        >
          <CircleSlash className="size-3.5" /> Reject
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => onApprovalChange("APPROVED")}
        >
          {draft.action_type === "HUMAN_REVIEW" ? (
            <ShieldAlert className="size-3.5" />
          ) : (
            <MessageSquareWarning className="size-3.5" />
          )}
          {actionLabel}
        </Button>
      </div>
      <div className="rounded-md border border-border bg-secondary/50 px-3 py-2.5 text-xs text-muted-foreground">
        <span className="font-medium text-foreground">Draft only.</span> {draft.summary}
      </div>
      <p className="font-mono-tight text-[11px] text-muted-foreground">
        Local review state: <span className="text-foreground">{approvalState}</span>
      </p>
    </div>
  );
}

export function TraceDrawer({
  open,
  onOpenChange,
  scenario,
  approvalState,
  onApprovalChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  scenario: ScenarioDetail;
  approvalState: ApprovalState;
  onApprovalChange: (state: ApprovalState) => void;
}) {
  const { trace } = scenario;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="h-[75vh] max-h-[75vh] overflow-y-auto px-6 pb-6">
        <SheetHeader className="px-0">
          <SheetTitle className="font-display text-lg">Operational trace</SheetTitle>
          <SheetDescription>
            A structured render of pipeline state — inputs, extracted facts, rule results, model
            calls, evidence, and decision state. Never chain-of-thought.
          </SheetDescription>
        </SheetHeader>

        <div className="flex flex-col gap-5">
          <TraceSection title="Approval">
            <ApprovalActions
              scenario={scenario}
              approvalState={approvalState}
              onApprovalChange={onApprovalChange}
            />
          </TraceSection>

          <Separator />

          <TraceSection title="Input documents & versions">
            <div className="flex flex-wrap gap-1.5">
              {trace.input_document_ids.map((id) => (
                <span
                  key={id}
                  className="rounded border border-border bg-card px-2 py-0.5 font-mono-tight text-xs text-foreground"
                >
                  {id}
                </span>
              ))}
            </div>
            <p className="font-mono-tight text-xs text-muted-foreground">
              dataset {trace.versions.dataset_version} · answer-key schema{" "}
              {trace.versions.schema_version} · prompt {trace.versions.prompt_version}
            </p>
          </TraceSection>

          <TraceSection title={`Extracted facts (${trace.extracted_facts.length})`}>
            <p className="text-sm text-muted-foreground">
              Typed facts with provenance, extracted from the MSA, SOW, and this invoice.
            </p>
          </TraceSection>

          <TraceSection title="Deterministic rules">
            <ul className="flex flex-col divide-y divide-border rounded-md border border-border">
              {trace.deterministic_rules.map((rule, i) => (
                <li
                  key={`${rule.rule_name}-${rule.invoice_line_id}-${i}`}
                  className="flex items-center justify-between gap-3 px-3 py-2 text-sm"
                >
                  <span className="font-mono-tight text-xs text-foreground">
                    {rule.rule_name}
                    {rule.invoice_line_id ? ` · ${rule.invoice_line_id}` : " · invoice"}
                  </span>
                  <span
                    className={cn(
                      "font-mono-tight text-xs font-medium",
                      rule.passed ? "text-status-clean" : "text-status-exception",
                    )}
                  >
                    {ruleOutcomeLabel(rule)}
                  </span>
                </li>
              ))}
            </ul>
          </TraceSection>

          <TraceSection title="Model calls">
            <ul className="flex flex-col divide-y divide-border rounded-md border border-border">
              {trace.model_calls.map((call, i) => (
                <li
                  key={`${call.purpose}-${i}`}
                  className="flex items-center justify-between gap-3 px-3 py-2 text-sm"
                >
                  <div className="flex flex-col">
                    <span className="text-foreground">{call.purpose}</span>
                    <span className="font-mono-tight text-xs text-muted-foreground">
                      {call.model_id}
                    </span>
                  </div>
                  <span
                    className={cn(
                      "font-mono-tight text-xs font-medium",
                      call.schema_valid ? "text-status-clean" : "text-status-exception",
                    )}
                  >
                    {call.schema_valid ? "schema-valid" : "schema-invalid"}
                  </span>
                </li>
              ))}
            </ul>
          </TraceSection>

          <TraceSection title="Disposition & approval state">
            <p className="font-mono-tight text-sm text-foreground">
              {trace.disposition} · {trace.approval_state}
            </p>
          </TraceSection>
        </div>
      </SheetContent>
    </Sheet>
  );
}
