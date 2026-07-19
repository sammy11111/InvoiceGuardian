import { CheckCircle2, Cog, Scale, UserCheck } from "lucide-react";

import type {
  AbsenceOfAuthorizationEvidence,
  ComputedTotalEvidence,
  DecisionMode,
  ExceptionFinding,
  ScenarioDetail,
  SupportingQuoteEvidence,
} from "@/lib/types";
import { cn } from "@/lib/utils";

function formatMoney(amount: string): string {
  return new Intl.NumberFormat("en-CA", { minimumFractionDigits: 2 }).format(
    Number.parseFloat(amount),
  );
}

function decisionModeFor(finding: ExceptionFinding): DecisionMode {
  if (finding.basis === "deterministic") return "deterministic check";
  if (finding.disposition === "ESCALATE") return "human review required";
  return "model-assisted match";
}

const DECISION_MODE_ICON: Record<DecisionMode, typeof Cog> = {
  "deterministic check": Cog,
  "model-assisted match": Scale,
  "human review required": UserCheck,
};

function DecisionModeLabel({ mode }: { mode: DecisionMode }) {
  const Icon = DECISION_MODE_ICON[mode];
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-secondary px-2.5 py-1 font-mono-tight text-[11px] tracking-wide text-secondary-foreground uppercase">
      <Icon className="size-3.5" strokeWidth={2.25} aria-hidden />
      {mode}
    </span>
  );
}

function ExhibitQuote({ evidence }: { evidence: SupportingQuoteEvidence }) {
  return (
    <figure className="rounded-lg border border-border bg-card p-5">
      <figcaption className="mb-3 font-mono-tight text-[11px] tracking-widest text-muted-foreground uppercase">
        Exhibit — {evidence.document_id} §{evidence.section}, p.{evidence.page}
      </figcaption>
      <blockquote className="font-display text-xl leading-relaxed font-medium text-balance text-foreground italic">
        &ldquo;{evidence.quote}&rdquo;
      </blockquote>
    </figure>
  );
}

function ValuePair({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-md border border-border bg-secondary/60 px-3 py-2">
      <span className="text-[11px] tracking-wide text-muted-foreground uppercase">{label}</span>
      <span className="tabular-figures font-mono-tight text-base font-medium text-foreground">
        {formatMoney(value)}
      </span>
    </div>
  );
}

function RateMismatchDetail({ finding }: { finding: ExceptionFinding }) {
  const values = finding.computed_values;
  if (!values) return null;
  return (
    <div className="grid grid-cols-2 gap-2">
      <ValuePair label="Billed rate (CAD/hr)" value={values.billed_rate_cad} />
      <ValuePair label="Authorized rate (CAD/hr)" value={values.authorized_rate_cad} />
    </div>
  );
}

function AggregateCapDetail({ finding }: { finding: ExceptionFinding }) {
  const values = finding.computed_values;
  const total = finding.evidence.find(
    (e): e is ComputedTotalEvidence => e.kind === "computed_total",
  );
  if (!values || !total) return null;
  return (
    <div className="grid grid-cols-3 gap-2">
      <ValuePair label="Invoice total" value={values.invoice_total_cad} />
      <ValuePair label="Monthly cap" value={values.cap_cad} />
      <ValuePair label="Excess" value={values.excess_cad} />
    </div>
  );
}

function AbsenceDetail({ evidence }: { evidence: AbsenceOfAuthorizationEvidence }) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-secondary/40 p-4">
      <div>
        <p className="mb-1.5 text-[11px] tracking-widest text-muted-foreground uppercase">
          Sections searched
        </p>
        <ul className="flex flex-wrap gap-1.5">
          {evidence.searched.map((s) => (
            <li
              key={s.document_id}
              className="rounded border border-border bg-card px-2 py-0.5 font-mono-tight text-xs text-foreground"
            >
              {s.document_id} §{s.sections.join(", §")}
            </li>
          ))}
        </ul>
      </div>
      <div>
        <p className="mb-1.5 text-[11px] tracking-widest text-muted-foreground uppercase">
          Quotes examined
        </p>
        <ul className="flex flex-col gap-2">
          {evidence.quotes.map((q) => (
            <li key={`${q.document_id}-${q.section}`} className="text-sm text-foreground">
              <span className="font-mono-tight text-xs text-muted-foreground">
                {q.document_id} §{q.section}, p.{q.page}
              </span>
              <p className="italic">&ldquo;{q.quote}&rdquo;</p>
            </li>
          ))}
        </ul>
      </div>
      <p className="rounded border border-status-exception/30 bg-status-exception-bg px-3 py-2 text-sm text-status-exception">
        {evidence.statement}
      </p>
    </div>
  );
}

function FindingCard({ finding }: { finding: ExceptionFinding }) {
  const quoteEvidence = finding.evidence.find(
    (e): e is SupportingQuoteEvidence => e.kind === "supporting_quote",
  );
  const absenceEvidence = finding.evidence.find(
    (e): e is AbsenceOfAuthorizationEvidence => e.kind === "absence_of_authorization",
  );
  const mode = decisionModeFor(finding);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-display text-base font-medium text-foreground">
          {finding.finding_type.replaceAll("_", " ")}
        </h3>
        <DecisionModeLabel mode={mode} />
      </div>

      {quoteEvidence && <ExhibitQuote evidence={quoteEvidence} />}
      {absenceEvidence && <AbsenceDetail evidence={absenceEvidence} />}

      {finding.finding_type === "RATE_MISMATCH" && <RateMismatchDetail finding={finding} />}
      {finding.finding_type === "AGGREGATE_CAP_EXCEEDED" && (
        <AggregateCapDetail finding={finding} />
      )}

      {finding.disposition === "ESCALATE" && (
        <p className="rounded-md border border-status-escalation/30 bg-status-escalation-bg px-3 py-2.5 text-sm text-status-escalation">
          Plausibly related to the authorized scope, but the supplied contract and statement of
          work cannot conclusively include or exclude it. Routed to human review rather than a
          confident exception.
        </p>
      )}

      <dl className="flex flex-wrap gap-x-6 gap-y-1 border-t border-border pt-3 text-xs text-muted-foreground">
        <div className="flex gap-1.5">
          <dt>Line:</dt>
          <dd className="font-mono-tight text-foreground">
            {finding.invoice_line_id ?? "invoice-level"}
          </dd>
        </div>
        <div className="flex gap-1.5">
          <dt>Disposition:</dt>
          <dd className="font-mono-tight text-foreground">{finding.disposition}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt>Drafted action:</dt>
          <dd className="font-mono-tight text-foreground">
            {finding.action.replaceAll("_", " ")}
          </dd>
        </div>
      </dl>
    </div>
  );
}

function CleanState() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
      <CheckCircle2 className="size-8 text-status-clean" strokeWidth={1.75} aria-hidden />
      <p className="font-display text-base font-medium text-foreground">
        No exceptions on this invoice
      </p>
      <p className="max-w-[32ch] text-sm text-muted-foreground">
        Every line is consistent with the supplied contract and statement of work.
      </p>
    </div>
  );
}

export function CitationPanel({
  scenario,
  selectedFinding,
}: {
  scenario: ScenarioDetail;
  selectedFinding: ExceptionFinding | null;
}) {
  if (scenario.findings.length === 0) {
    return (
      <div className="h-full overflow-y-auto p-5">
        <CleanState />
      </div>
    );
  }

  const finding = selectedFinding ?? scenario.findings[0];

  return (
    <div className={cn("flex h-full flex-col gap-5 overflow-y-auto p-5")}>
      <p className="font-mono-tight text-[11px] tracking-widest text-muted-foreground uppercase">
        Citation
      </p>
      <FindingCard finding={finding} />
    </div>
  );
}
