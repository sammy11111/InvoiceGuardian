import { AlertTriangle, CircleCheck, GitBranch } from "lucide-react";

import type { InvoiceDisposition, LineStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const DISPOSITION_CONFIG: Record<
  InvoiceDisposition,
  { label: string; icon: typeof CircleCheck; bg: string; fg: string }
> = {
  CLEAN: {
    label: "Clean",
    icon: CircleCheck,
    bg: "bg-status-clean-bg",
    fg: "text-status-clean",
  },
  EXCEPTIONS_FOUND: {
    label: "Exceptions found",
    icon: AlertTriangle,
    bg: "bg-status-exception-bg",
    fg: "text-status-exception",
  },
  ESCALATION_REQUIRED: {
    label: "Escalation required",
    icon: GitBranch,
    bg: "bg-status-escalation-bg",
    fg: "text-status-escalation",
  },
};

export function DispositionBadge({
  disposition,
  className,
}: {
  disposition: InvoiceDisposition;
  className?: string;
}) {
  const config = DISPOSITION_CONFIG[disposition];
  const Icon = config.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
        config.bg,
        config.fg,
        className,
      )}
    >
      <Icon className="size-3.5" strokeWidth={2.25} aria-hidden />
      {config.label}
    </span>
  );
}

const LINE_STATUS_CONFIG: Record<LineStatus, { label: string; bg: string; fg: string }> = {
  clean: { label: "Clean", bg: "bg-status-clean-bg", fg: "text-status-clean" },
  flagged: { label: "Flagged", bg: "bg-status-exception-bg", fg: "text-status-exception" },
  escalated: { label: "Escalated", bg: "bg-status-escalation-bg", fg: "text-status-escalation" },
};

export function LineStatusChip({ status }: { status: LineStatus }) {
  const config = LINE_STATUS_CONFIG[status];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium tracking-wide uppercase",
        config.bg,
        config.fg,
      )}
    >
      {config.label}
    </span>
  );
}
