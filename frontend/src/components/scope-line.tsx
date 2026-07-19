import { cn } from "@/lib/utils";

export const SCOPE_LINE_TEXT =
  "Reviews invoice consistency against supplied contracts. Never decides payment, never determines fraud. All actions are drafts requiring human approval.";

export function ScopeLine({ className }: { className?: string }) {
  return <p className={cn("text-xs text-muted-foreground", className)}>{SCOPE_LINE_TEXT}</p>;
}
