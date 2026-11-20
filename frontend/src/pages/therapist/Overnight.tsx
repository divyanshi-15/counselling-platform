import { Link } from "react-router-dom";
import { ArrowDown, ArrowUp, Minus } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { Spark, ACCENT } from "@/components/charts";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Empty } from "@/components/states";
import { formatEvidence, runTime, shortDate } from "@/lib/evidence";
import { TechnicalDetails } from "@/components/TechnicalDetails";
import type { Schemas } from "./common";

type Series = NonNullable<Schemas["ScoresOut"]["PHQ9"]>;
export const WARN = "#A8552F";

/** One measure: latest score, change since first reading, count and sparkline. */
export function ScoreStat({ label, s }: { label: string; s: Series | null | undefined }) {
  if (!s) return <div className="rounded-md border border-dashed p-3 text-sm text-muted-foreground"><p className="font-medium text-foreground">{label}</p>No readings yet</div>;
  const up = s.change > 0, down = s.change < 0;
  const Icon = up ? ArrowUp : down ? ArrowDown : Minus;
  const colour = up ? "text-amber-700" : down ? "text-primary" : "text-muted-foreground";
  const since = shortDate(s.series[0]?.taken_at);
  const data = s.series.map((p) => ({ label: shortDate(p.taken_at) || "", value: p.total }));
  return (
    <div className="rounded-md border p-3" aria-label={label}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-medium">{label}</p>
          <p className="text-2xl font-semibold leading-tight">{s.latest}</p>
        </div>
        <p className={`flex items-center gap-1 text-sm font-medium ${colour}`}>
          <Icon className="h-4 w-4" aria-hidden />
          {s.change === 0 ? "No change" : `${Math.abs(s.change)} ${up ? "higher" : "lower"}`}
          <span className="sr-only">{up ? "worsening" : down ? "improving" : ""}</span>
        </p>
      </div>
      <p className="text-xs text-muted-foreground">{s.count} reading{s.count === 1 ? "" : "s"}{since && s.count > 1 ? ` since ${since}` : ""}{s.count > 1 ? `; first was ${s.first}` : ""}</p>
      {data.length > 1 && <div className="mt-1 h-12 w-full" role="img" aria-label={`${label} trend`}><Spark data={data} name={label} color={up ? WARN : ACCENT} /></div>}
    </div>
  );
}

export function ScoresPair({ scores }: { scores: Schemas["ScoresOut"] }) {
  return <div className="grid gap-3 sm:grid-cols-2"><ScoreStat label="PHQ-9" s={scores.PHQ9} /><ScoreStat label="GAD-7" s={scores.GAD7} /></div>;
}

export function Item9Chip() {
  return <Badge className="border-red-500 bg-red-50 font-semibold text-red-800">Item 9 positive: high priority</Badge>;
}

function statusChips(c: Schemas["OvernightClient"]) {
  const chips: { text: string; cls: string }[] = [];
  if (c.findings.includes("plateau")) chips.push({ text: "Plateau", cls: "border-amber-400 bg-amber-50 text-amber-900" });
  if (c.findings.includes("homework") || c.findings.includes("goal_untouched")) chips.push({ text: "Needs follow-up", cls: "border-amber-400 bg-amber-50 text-amber-900" });
  if (!c.findings.includes("plateau") && [c.scores.PHQ9, c.scores.GAD7].some((s) => s && s.change < 0)) chips.push({ text: "Improving", cls: "border-primary/50 bg-primary/10 text-primary" });
  return chips;
}

function ClientCard({ c }: { c: Schemas["OvernightClient"] }) {
  const name = c.name ?? `Client #${c.client_id}`;
  const chips = statusChips(c);
  const sentences = formatEvidence(c.evidence);
  return (
    <Card className={c.scores.item9_positive ? "border-2 border-red-500" : ""}>
      <CardContent className="space-y-3 pt-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Link to={`/therapist/clients/${c.client_id}`} className="flex items-center gap-2 font-medium hover:underline"><Avatar name={name} size={32} />{name}</Link>
          <div className="flex flex-wrap gap-1.5">{c.scores.item9_positive && <Item9Chip />}{chips.map((x) => <Badge key={x.text} className={x.cls}>{x.text}</Badge>)}</div>
        </div>
        <ScoresPair scores={c.scores} />
        {sentences.length > 0 && <ul className="list-disc space-y-0.5 pl-5 text-sm">{sentences.map((t, i) => <li key={i}>{t}</li>)}</ul>}
        <TechnicalDetails data={{ ids: c.scores.ids, PHQ9: c.scores.PHQ9, GAD7: c.scores.GAD7, findings: c.evidence }} />
      </CardContent>
    </Card>
  );
}

export function OvernightPanel({ status }: { status: Schemas["OvernightStatusOut"] }) {
  const when = runTime(status.ran_at);
  return (
    <section className="space-y-3" aria-label="Overnight check">
      <h2 className="text-lg font-semibold">Overnight check</h2>
      <p role="status" className="text-sm text-muted-foreground">
        Checked {status.clients_checked} client{status.clients_checked === 1 ? "" : "s"} · {status.needs_attention} need{status.needs_attention === 1 ? "s" : ""} attention · {when ? `last run ${when}` : "not run yet"}
      </p>
      {status.clients.length === 0 ? <Empty>No clients to check yet.</Empty> : (
        <div className="grid gap-3 lg:grid-cols-2">
          {[...status.clients].sort((a, b) => Number(b.scores.item9_positive) - Number(a.scores.item9_positive) || b.findings.length - a.findings.length)
            .map((c) => <ClientCard key={c.client_id} c={c} />)}
        </div>
      )}
    </section>
  );
}
