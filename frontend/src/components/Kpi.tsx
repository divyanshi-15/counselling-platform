import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function Kpi({ label, value, hint, tooltip, alert = false }: { label: string; value: React.ReactNode; hint?: string; tooltip?: string; alert?: boolean }) {
  return (
    <Card className={cn(alert && "border-red-400 bg-red-50 text-red-800")}>
      <CardContent className="space-y-0.5 p-3 sm:p-4">
        <p title={tooltip} className={cn("text-xs uppercase tracking-wide text-muted-foreground", alert && "text-red-800", tooltip && "cursor-help")}>{label}</p>
        <p className="font-display text-2xl font-semibold tabular-nums">{value}</p>
        {hint && <p className={cn("text-xs text-muted-foreground", alert && "text-red-800")}>{hint}</p>}
      </CardContent>
    </Card>
  );
}

export const KpiRow = ({ children }: { children: React.ReactNode }) => (
  <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{children}</div>
);
