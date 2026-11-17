import { useState } from "react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { ChartFrame, Lines } from "@/components/charts";
import { Kpi, KpiRow } from "@/components/Kpi";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { cn, monthLabel, pct } from "@/lib/utils";
import { useFetch } from "@/lib/useFetch";
import type { Schemas } from "./common";

type Data = Schemas["TherapistAnalyticsOut"];
type Trend = Data["clients"][number];

function Change({ v }: { v: number | null | undefined }) {
  if (v == null) return <span className="text-muted-foreground">–</span>;
  const Icon = v < 0 ? ArrowDownRight : v > 0 ? ArrowUpRight : Minus;
  return (
    <span className={cn("inline-flex items-center gap-0.5 tabular-nums", v < 0 ? "font-medium text-primary" : v > 0 ? "font-medium" : "text-muted-foreground")}
      title={v < 0 ? "Lower than first reading (improving)" : v > 0 ? "Higher than first reading" : "No change"}>
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />{v > 0 ? `+${v}` : v}
    </span>
  );
}

function ScoreChart({ clients }: { clients: Trend[] }) {
  const [id, setId] = useState(clients[0]?.client_id);
  const c = clients.find((x) => x.client_id === id) ?? clients[0];
  const months = [...new Set([...c.phq9.points, ...c.gad7.points].map((p) => p.month))].sort();
  const find = (s: Trend["phq9"], m: string) => s.points.find((p) => p.month === m)?.average ?? null;
  const data = months.map((m) => ({ month: monthLabel(m), phq9: find(c.phq9, m), gad7: find(c.gad7, m) }));
  return (
    <Card>
      <CardHeader className="space-y-2">
        <CardTitle className="text-base">PHQ-9 and GAD-7, monthly average</CardTitle>
        <div className="flex gap-2 overflow-x-auto pb-1" role="group" aria-label="Choose client">
          {clients.map((x) => (
            <button key={x.client_id} type="button" aria-pressed={x.client_id === c.client_id} onClick={() => setId(x.client_id)}
              className={cn("inline-flex shrink-0 items-center gap-2 rounded-full border py-1 pl-1 pr-3 text-sm", x.client_id === c.client_id ? "border-primary bg-primary/5 font-medium" : "text-muted-foreground hover:text-foreground")}>
              <Avatar name={x.name} size={24} />{x.name ?? `Client ${x.client_id}`}
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? <Empty>No PHQ-9 or GAD-7 readings in the last 6 months.</Empty> : (
          <ChartFrame title={`${c.name ?? "Client"}: scores by month`} summary={`PHQ-9 latest ${c.phq9.latest ?? "none"}, GAD-7 latest ${c.gad7.latest ?? "none"}`}>
            <Lines data={data} x="month" xLabel="Month" yLabel="Score" domain={[0, 27]}
              lines={[{ key: "phq9", name: "PHQ-9" }, { key: "gad7", name: "GAD-7", dashed: true, accent: false }]} />
          </ChartFrame>
        )}
        <p className="mt-1 flex gap-4 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1"><span className="inline-block h-0.5 w-5 bg-primary" />PHQ-9</span>
          <span className="inline-flex items-center gap-1"><span className="inline-block h-0 w-5 border-t-2 border-dashed border-slate-500" />GAD-7</span>
        </p>
      </CardContent>
    </Card>
  );
}

export function TherapistAnalytics() {
  const { data, error, loading } = useFetch<Data>("/analytics/therapist");
  if (loading && !data) return <Loading />;
  if (error != null) return <ErrorMsg error={error} />;
  if (!data) return null;
  const s = data.sessions_completed;
  const delta = s.last_30_days - s.previous_30_days;
  return (
    <section className="space-y-4" aria-label="Practice overview">
      <h2 className="text-lg font-semibold">Your caseload</h2>
      <KpiRow>
        <Kpi label="Sessions, 30 days" value={s.last_30_days} hint={`${delta >= 0 ? "+" : ""}${delta} vs previous 30 days`} />
        <Kpi label="Exercise completion" value={pct(data.exercise_completion_rate)} hint={data.exercises_assigned ? `${data.exercises_assigned} assigned` : "None assigned yet"} />
        <Kpi label="Open alerts" value={data.open_alerts} alert={data.open_alerts > 0} hint={data.open_alerts ? "Needs your review" : "All acknowledged"} />
        <Kpi label="Upcoming, 7 days" value={data.upcoming_sessions_7_days} hint="Confirmed sessions" />
      </KpiRow>
      {data.clients.length === 0 ? <Empty>Score trends appear once your clients have PHQ-9 or GAD-7 readings.</Empty> : (
        <>
          <ScoreChart clients={data.clients} />
          <Card>
            <CardHeader><CardTitle className="text-base">Clients, last 6 months</CardTitle></CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full min-w-[420px] text-sm">
                <thead><tr className="border-b text-left text-xs text-muted-foreground">
                  <th className="py-1.5 font-medium">Client</th><th className="font-medium">PHQ-9</th><th className="font-medium">Change</th><th className="font-medium">GAD-7</th><th className="font-medium">Change</th>
                </tr></thead>
                <tbody>{data.clients.map((c) => (
                  <tr key={c.client_id} className="border-b last:border-0">
                    <td className="py-2"><span className="inline-flex items-center gap-2"><Avatar name={c.name} size={28} />{c.name}</span></td>
                    <td className="tabular-nums">{c.phq9.latest ?? "–"}</td><td><Change v={c.phq9.change} /></td>
                    <td className="tabular-nums">{c.gad7.latest ?? "–"}</td><td><Change v={c.gad7.change} /></td>
                  </tr>))}
                </tbody>
              </table>
              <p className="mt-2 text-xs text-muted-foreground">Change compares the latest score with the first reading in the window. Lower is better.</p>
            </CardContent>
          </Card>
        </>
      )}
    </section>
  );
}
