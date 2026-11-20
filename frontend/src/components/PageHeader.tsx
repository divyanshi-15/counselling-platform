import { cn } from "@/lib/utils";

/** Page title in the display serif, with an optional one-line subtitle and action slot. */
export function PageHeader({ title, subtitle, action, className }: { title: React.ReactNode; subtitle?: React.ReactNode; action?: React.ReactNode; className?: string }) {
  const h1 = <h1 className={cn("font-display text-2xl font-semibold tracking-tight", className)}>{title}</h1>;
  if (!subtitle && !action) return h1;
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="space-y-1">{h1}{subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}</div>
      {action}
    </div>
  );
}
