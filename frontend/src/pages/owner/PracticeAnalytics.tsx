import { Bars, ChartFrame, Lines } from "@/components/charts";
import { Kpi, KpiRow } from "@/components/Kpi";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { inr, monthLabel, pct } from "@/lib/utils";
import { useFetch } from "@/lib/useFetch";
import type { Schemas } from "../client/common";

type Data = Schemas["PracticeAnalyticsOut"];

export function PracticeAnalytics() {
  const { data, error, loading } = useFetch<Data>("/analytics/practice");
  if (loading && !data) return <Loading />;
  if (error != null) return <ErrorMsg error={error} />;
  if (!data) return null;
  const weekly = data.bookings_per_week.map((w) => ({ week: new Date(`${w.week_start}T00:00:00Z`).toLocaleDateString("en-IN", { day: "numeric", month: "short", timeZone: "UTC" }), bookings: w.bookings }));
  const monthly = data.revenue_per_month.map((m) => ({ month: monthLabel(m.month), revenue: m.revenue_inr }));
  const totalBookings = weekly.reduce((n, w) => n + w.bookings, 0);
  const currentRevenue = data.revenue_per_month.at(-1)?.revenue_inr ?? 0;
  const sixMonths = data.revenue_per_month.reduce((n, m) => n + m.revenue_inr, 0);
  const u = data.utilisation_next_14_days;
  const top = data.top_specialisations;
  const max = Math.max(1, ...top.map((t) => t.bookings));
  return (
    <section className="space-y-4" aria-label="Practice performance">
      <h2 className="text-lg font-semibold">Performance</h2>
      <KpiRow>
        <Kpi label="Bookings, 12 weeks" value={totalBookings} />
        <Kpi label="Utilisation, 14 days" value={pct(u.utilisation)} hint={`${u.booked_slots} of ${u.available_slots} slots booked`} />
        <Kpi label="Revenue, this month" value={inr(currentRevenue)} />
        <Kpi label="Revenue, 6 months" value={inr(sixMonths)} />
      </KpiRow>
      {totalBookings === 0 && sixMonths === 0 ? <Empty>Charts appear once your therapists have bookings.</Empty> : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card><CardContent className="pt-4">
            <ChartFrame title="Bookings per week" summary={`${totalBookings} bookings over the last 12 weeks`}>
              <Bars data={weekly} x="week" y="bookings" xLabel="Week starting" yLabel="Bookings" name="Bookings" />
            </ChartFrame>
          </CardContent></Card>
          <Card><CardContent className="pt-4">
            <ChartFrame title="Revenue per month (₹)" summary={`${inr(sixMonths)} over the last 6 months`}>
              <Lines data={monthly} x="month" xLabel="Month" yLabel="Revenue" fmt={(v) => (v >= 1000 ? `₹${new Intl.NumberFormat("en-IN").format(v / 1000)}k` : inr(v))}
                lines={[{ key: "revenue", name: "Revenue" }]} />
            </ChartFrame>
          </CardContent></Card>
        </div>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="text-base">Top specialisations by bookings</CardTitle></CardHeader>
          <CardContent>
            {top.length === 0 ? <Empty>No bookings yet.</Empty> : (
              <ol className="space-y-2">{top.map((t) => (
                <li key={t.specialisation} className="space-y-1 text-sm">
                  <div className="flex justify-between"><span className="capitalize">{t.specialisation}</span><span className="tabular-nums text-muted-foreground">{t.bookings}</span></div>
                  <div className="h-1.5 rounded bg-muted"><div className="h-1.5 rounded bg-primary" style={{ width: `${(t.bookings / max) * 100}%` }} /></div>
                </li>))}
              </ol>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-base">Therapist utilisation, next 14 days</CardTitle></CardHeader>
          <CardContent>
            {u.by_therapist.length === 0 ? <Empty>No open slots in the next 14 days.</Empty> : (
              <ul className="space-y-2 text-sm">{u.by_therapist.map((t) => (
                <li key={t.therapist ?? ""} className="flex justify-between gap-2"><span>{t.therapist}</span>
                  <span className="tabular-nums text-muted-foreground">{t.booked_slots}/{t.available_slots} · {pct(t.utilisation)}</span></li>))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
