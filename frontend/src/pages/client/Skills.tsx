import { useEffect, useRef, useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Input, Textarea } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { Bars, ChartFrame, Lines } from "@/components/charts";
import { api } from "@/lib/api";
import { useLang, useT } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";
import { CrisisBox, RequireClient, type Schemas } from "./common";

const localDate = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };

function Page({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  const t = useT();
  return (
    <div className="space-y-4">
      <Link to="/client" className="text-sm underline">{t("back")}</Link>
      <div><PageHeader title={title} />{hint && <p className="text-sm text-muted-foreground">{hint}</p>}</div>
      {children}
    </div>
  );
}

// ---------- daily check-in ----------

function CheckInBody() {
  const t = useT();
  const today = localDate();
  const recent = useFetch<Schemas["MoodListOut"]>("/client/mood", { days: 2 });
  const existing = recent.data?.items.find((i) => i.entry_date === today);
  const [mood, setMood] = useState(3);
  const [sleep, setSleep] = useState("7");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [res, setRes] = useState<Schemas["MoodOut"] | null>(null);
  useEffect(() => { if (existing) { setMood(existing.mood); setSleep(String(existing.sleep_hours)); setNote(existing.note ?? ""); } }, [existing?.entry_date]); // eslint-disable-line react-hooks/exhaustive-deps

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    try { setRes(await api<Schemas["MoodOut"]>("/client/mood", { method: "PUT", json: { mood, sleep_hours: Number(sleep), note: note.trim() || null, entry_date: today } })); recent.reload(); }
    catch (err) { setError(err); } finally { setBusy(false); }
  }
  if (res?.status === "crisis") return <CrisisBox message={res.message ?? ""} />; // nothing else shown
  return (
    <Page title={t("checkin")} hint={t("checkinHint")}>
      {recent.loading && !recent.data ? <Loading /> : (
        <form onSubmit={(e) => void submit(e)} className="space-y-4">
          {existing && <p className="text-sm text-muted-foreground">{t("alreadyToday")}</p>}
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">{t("mood")} <span className="font-normal text-muted-foreground">({t("moodScale")})</span></legend>
            <div className="flex gap-2">
              {[1, 2, 3, 4, 5].map((n) => (
                <Button key={n} type="button" variant={mood === n ? "default" : "outline"} aria-pressed={mood === n} className="h-12 w-12" onClick={() => setMood(n)}>{n}</Button>
              ))}
            </div>
          </fieldset>
          <div className="max-w-xs space-y-1"><Label htmlFor="sleep">{t("sleepHours")}</Label>
            <Input id="sleep" type="number" inputMode="decimal" min={0} max={24} step={0.5} required value={sleep} onChange={(e) => setSleep(e.target.value)} /></div>
          <div className="space-y-1"><Label htmlFor="note">{t("note")}</Label>
            <Textarea id="note" rows={3} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
            <p className="text-right text-xs text-muted-foreground">{note.length}/500</p></div>
          {error != null && <ErrorMsg error={error} />}
          {res?.status === "saved" && <p role="status" className="text-sm font-medium text-emerald-700">{t("saved")}</p>}
          <Button disabled={busy}>{busy ? t("saving") : existing ? t("updateToday") : t("save")}</Button>
        </form>
      )}
    </Page>
  );
}
export function CheckIn() { return <RequireClient><CheckInBody /></RequireClient>; }

// ---------- journal ----------

function JournalBody() {
  const t = useT();
  const lang = useLang();
  const list = useFetch<Schemas["JournalListOut"]>("/client/journal");
  const [text, setText] = useState("");
  const [share, setShare] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [crisis, setCrisis] = useState<string | null>(null);
  const key = useRef(crypto.randomUUID()); // new key per entry; a double click cannot save twice

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    try {
      const r = await api<Schemas["JournalOut"]>("/client/journal", { method: "POST", headers: { "Idempotency-Key": key.current }, json: { text, shared: share } });
      if (r.status === "crisis") { setCrisis(r.message ?? ""); return; }
      setText(""); setShare(false); key.current = crypto.randomUUID(); list.reload();
    } catch (err) { setError(err); } finally { setBusy(false); }
  }
  async function setShared(id: number, shared: boolean) {
    setError(null);
    try { await api(`/client/journal/${id}`, { method: "PATCH", json: { shared } }); list.reload(); } catch (err) { setError(err); }
  }
  if (crisis) return <CrisisBox message={crisis} />; // nothing else shown
  return (
    <Page title={t("journal")} hint={t("journalHint")}>
      <form onSubmit={(e) => void submit(e)} className="space-y-3">
        <Label htmlFor="entry">{t("writeEntry")}</Label>
        <Textarea id="entry" required rows={5} maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} />
        <p className="text-right text-xs text-muted-foreground">{text.length}/2000</p>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={share} onChange={(e) => setShare(e.target.checked)} />{t("shareWithTherapist")}</label>
        {error != null && <ErrorMsg error={error} />}
        <Button disabled={busy || !text.trim()}>{busy ? t("saving") : t("saveEntry")}</Button>
      </form>
      {list.loading && !list.data ? <Loading /> : list.error != null ? <ErrorMsg error={list.error} /> : list.data!.items.length === 0 ? <Empty>{t("noEntries")}</Empty> : (
        <ul className="space-y-3">
          {list.data!.items.map((e) => (
            <li key={e.id}><Card><CardContent className="space-y-2 pt-4 text-sm">
              <p className="whitespace-pre-wrap">{e.text}</p>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs text-muted-foreground">{new Date(e.created_at).toLocaleString(lang === "hi" ? "hi-IN" : [], { dateStyle: "medium", timeStyle: "short" })}</span>
                <span className="flex items-center gap-2"><Badge>{e.shared ? t("shared") : t("private")}</Badge>
                  <Button variant="outline" onClick={() => void setShared(e.id, !e.shared)}>{e.shared ? t("unshare") : t("share")}</Button></span>
              </div>
            </CardContent></Card></li>
          ))}
        </ul>
      )}
    </Page>
  );
}
export function Journal() { return <RequireClient><JournalBody /></RequireClient>; }

// ---------- journeys ----------

export function JourneyCard({ j, onChange }: { j: Schemas["JourneyView"]; onChange: () => void }) {
  const t = useT();
  const [error, setError] = useState<unknown>(null);
  const pct = j.total ? Math.round((j.completed / j.total) * 100) : 0;
  async function complete(stepId: number) {
    setError(null);
    try { await api(`/client/journeys/${j.assignment_id}/steps/${stepId}/complete`, { method: "POST" }); onChange(); } catch (err) { setError(err); }
  }
  return (
    <Card>
      <CardHeader><CardTitle>{j.title}</CardTitle>
        <p className="text-sm text-muted-foreground">{t("week")} {j.current_week} / {j.weeks} · {j.completed} / {j.total} {t("steps")}</p></CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div role="progressbar" aria-label={t("progress")} aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} className="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div className="h-full bg-primary" style={{ width: `${pct}%` }} />
        </div>
        <h3 className="font-medium">{t("thisWeek")}</h3>
        <ul className="space-y-2">
          {j.current_steps.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3">
              <div><p>{s.text}</p><p className="text-xs text-muted-foreground">{t("exercise")}: {s.exercise_title}</p></div>
              {s.done ? <Badge className="border-emerald-400 text-emerald-800">{t("done")}</Badge> : <Button variant="outline" onClick={() => void complete(s.id)}>{t("markDone")}</Button>}
            </li>
          ))}
        </ul>
        <ol className="flex flex-wrap gap-2 text-xs text-muted-foreground" aria-label={t("progress")}>
          {j.weeks_progress.map((w) => <li key={w.week} className="rounded border px-2 py-1">{t("week")} {w.week}: {w.completed}/{w.total}</li>)}
        </ol>
        {error != null && <ErrorMsg error={error} />}
      </CardContent>
    </Card>
  );
}

function JourneysBody() {
  const t = useT();
  const list = useFetch<Schemas["ClientJourneysOut"]>("/client/journeys");
  return (
    <Page title={t("journeys")} hint={t("journeysHint")}>
      {list.loading && !list.data ? <Loading /> : list.error != null ? <ErrorMsg error={list.error} /> : list.data!.items.length === 0 ? <Empty>{t("noJourneys")}</Empty> : (
        <div className="space-y-4">{list.data!.items.map((j) => <JourneyCard key={j.assignment_id} j={j} onChange={list.reload} />)}</div>
      )}
    </Page>
  );
}
export function Journeys() { return <RequireClient><JourneysBody /></RequireClient>; }

// ---------- insights ----------

function InsightsBody() {
  const t = useT();
  const lang = useLang();
  const q = useFetch<Schemas["InsightsOut"]>("/client/insights");
  const d = q.data;
  const short = (iso: string) => new Date(iso + "T00:00:00").toLocaleDateString(lang === "hi" ? "hi-IN" : [], { month: "short", day: "numeric" });
  const rows = (d?.series ?? []).map((s) => ({ day: short(s.date), mood: s.mood ?? null, sleep: s.sleep_hours ?? null, done: s.exercises_completed }));
  const stat = (label: string, v: number | null | undefined) => (
    <Card><CardContent className="pt-4"><p className="text-2xl font-semibold">{v ?? "–"}</p><p className="text-xs text-muted-foreground">{label}</p></CardContent></Card>
  );
  return (
    <Page title={t("insights")} hint={t("insightsHint")}>
      {q.loading && !d ? <Loading /> : q.error != null || !d ? <ErrorMsg error={q.error} /> : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {stat(t("checkins"), d.checkins)}{stat(t("avgMood"), d.avg_mood)}{stat(t("avgSleep"), d.avg_sleep)}{stat(t("exercisesDone"), d.exercises_completed)}
          </div>
          <p className="text-sm text-muted-foreground">{t("exercisesAssigned")}: {d.exercises_assigned}</p>
          {d.checkins === 0 ? <Empty>{t("noData")}</Empty> : (
            <div className="space-y-6">
              <ChartFrame title={t("moodChart")} summary={`${t("moodChart")}, ${d.checkins} ${t("checkins")}`}>
                <Lines data={rows} x="day" lines={[{ key: "mood", name: t("mood") }]} xLabel={t("date")} yLabel={t("mood")} domain={[1, 5]} />
              </ChartFrame>
              <ChartFrame title={t("sleepChart")} summary={`${t("sleepChart")}, ${d.checkins} ${t("checkins")}`}>
                <Lines data={rows} x="day" lines={[{ key: "sleep", name: t("sleepHours") }]} xLabel={t("date")} yLabel={t("sleepHours")} />
              </ChartFrame>
              <ChartFrame title={t("exerciseChart")} summary={`${t("exerciseChart")}: ${d.exercises_completed}`}>
                <Bars data={rows} x="day" y="done" xLabel={t("date")} yLabel={t("exercisesDone")} name={t("exercisesDone")} />
              </ChartFrame>
            </div>
          )}
        </>
      )}
    </Page>
  );
}
export function Insights() { return <RequireClient><InsightsBody /></RequireClient>; }

// ---------- reminders ----------

function RemindersBody() {
  const t = useT();
  const q = useFetch<Schemas["RemindersOut"]>("/client/reminders");
  const [error, setError] = useState<unknown>(null);
  async function set(patch: Partial<{ daily_checkin: boolean; exercise_nudges: boolean }>) {
    if (!q.data) return;
    setError(null);
    try { await api("/client/reminders", { method: "PUT", json: { daily_checkin: q.data.daily_checkin, exercise_nudges: q.data.exercise_nudges, ...patch } }); q.reload(); } catch (err) { setError(err); }
  }
  const row = (label: string, on: boolean, key: "daily_checkin" | "exercise_nudges") => (
    <li className="flex items-center justify-between gap-3 rounded-md border p-3">
      <span id={key} className="text-sm">{label}</span>
      <Button type="button" role="switch" aria-checked={on} aria-labelledby={key} variant={on ? "default" : "outline"} onClick={() => void set({ [key]: !on })}>{on ? t("remOn") : t("remOff")}</Button>
    </li>
  );
  return (
    <Page title={t("reminders")} hint={t("remindersHint")}>
      {q.loading && !q.data ? <Loading /> : q.error != null || !q.data ? <ErrorMsg error={q.error} /> : (
        <>
          <ul className="space-y-2">{row(t("remDaily"), q.data.daily_checkin, "daily_checkin")}{row(t("remNudge"), q.data.exercise_nudges, "exercise_nudges")}</ul>
          <p className="text-xs text-muted-foreground">{t("remNote")}</p>
          {error != null && <ErrorMsg error={error} />}
        </>
      )}
    </Page>
  );
}
export function Reminders() { return <RequireClient><RemindersBody /></RequireClient>; }
