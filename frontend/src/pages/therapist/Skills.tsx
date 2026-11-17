import { useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input, Select } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { ChartFrame, Lines } from "@/components/charts";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import { fmt, type Schemas } from "./common";

export type Step = { week: number; exercise: string; text_en: string; text_hi?: string | null };
export type Programme = { title_en: string; title_hi?: string | null; steps: Step[] };
type Trend = { days?: number; count?: number; avg_mood?: number | null; avg_sleep?: number | null; entries?: { date: string; mood: number; sleep_hours: number }[] };

/** Plain numbers only: no interpretation. Used on the client file and in the briefing. */
export function MoodTrend({ trend }: { trend: Trend | null | undefined }) {
  if (!trend || !trend.count) return <p className="text-sm text-muted-foreground">No mood check-ins in the last 14 days.</p>;
  const rows = (trend.entries ?? []).map((e) => ({ day: e.date.slice(5), mood: e.mood, sleep: e.sleep_hours }));
  return (
    <div className="space-y-3">
      <p className="flex flex-wrap gap-x-4 text-sm text-muted-foreground">
        <span>Last {trend.days ?? 14} days: <span className="font-medium text-foreground">{trend.count}</span> check-ins</span>
        <span>Average mood <span className="font-medium text-foreground">{trend.avg_mood}</span> / 5</span>
        <span>Average sleep <span className="font-medium text-foreground">{trend.avg_sleep}</span> h</span>
      </p>
      <div className="grid gap-4 md:grid-cols-2">
        <ChartFrame title="Mood (1-5)" summary={`Mood over ${trend.count} check-ins`}><Lines data={rows} x="day" lines={[{ key: "mood", name: "Mood" }]} xLabel="Date" yLabel="Mood" domain={[1, 5]} /></ChartFrame>
        <ChartFrame title="Sleep (hours)" summary={`Sleep over ${trend.count} check-ins`}><Lines data={rows} x="day" lines={[{ key: "sleep", name: "Sleep" }]} xLabel="Date" yLabel="Hours" /></ChartFrame>
      </div>
    </div>
  );
}

export function MoodTrendCard({ clientId }: { clientId: string }) {
  const q = useFetch<Schemas["MoodTrendOut"]>(`/clients/${clientId}/mood-trend`);
  if (q.loading) return <Loading />;
  if (q.error != null) return <ErrorMsg error={q.error} />;
  return <MoodTrend trend={q.data} />;
}

export function SharedJournal({ clientId }: { clientId: string }) {
  const q = useFetch<Schemas["SharedJournalOut"]>(`/clients/${clientId}/journal`);
  if (q.loading) return <Loading />;
  if (q.error != null) return <ErrorMsg error={q.error} />;
  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground">Only entries the client chose to share. Private entries are never shown to you.</p>
      {q.data!.items.length === 0 ? <Empty>Nothing shared.</Empty> : (
        <ul className="space-y-2">{q.data!.items.map((e) => (
          <li key={e.id} className="rounded border p-3 text-sm"><p className="whitespace-pre-wrap">{e.text}</p><p className="mt-1 text-xs text-muted-foreground">{fmt(e.created_at)}</p></li>
        ))}</ul>
      )}
    </div>
  );
}

export function ProgrammeEditor({ value, onChange, exercises }: { value: Programme; onChange: (p: Programme) => void; exercises: { slug: string; title: string }[] }) {
  const set = (i: number, patch: Partial<Step>) => onChange({ ...value, steps: value.steps.map((s, j) => (j === i ? { ...s, ...patch } : s)) });
  return (
    <div className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-2">
        <div className="space-y-1"><Label htmlFor="pt-en">Title (English)</Label><Input id="pt-en" maxLength={200} value={value.title_en} onChange={(e) => onChange({ ...value, title_en: e.target.value })} /></div>
        <div className="space-y-1"><Label htmlFor="pt-hi">Title (Hindi)</Label><Input id="pt-hi" maxLength={200} value={value.title_hi ?? ""} onChange={(e) => onChange({ ...value, title_hi: e.target.value })} /></div>
      </div>
      <ul className="space-y-2">
        {value.steps.map((s, i) => (
          <li key={i} className="space-y-2 rounded border p-2">
            <div className="flex flex-wrap items-end gap-2">
              <div className="w-20 space-y-1"><Label htmlFor={`w${i}`} className="text-xs">Week</Label><Input id={`w${i}`} type="number" min={1} max={8} value={s.week} onChange={(e) => set(i, { week: Number(e.target.value) })} /></div>
              <div className="min-w-40 flex-1 space-y-1"><Label htmlFor={`x${i}`} className="text-xs">Exercise</Label>
                <Select id={`x${i}`} value={s.exercise} onChange={(e) => set(i, { exercise: e.target.value })}>{exercises.map((x) => <option key={x.slug} value={x.slug}>{x.title}</option>)}</Select></div>
              <Button type="button" variant="outline" disabled={value.steps.length === 1} onClick={() => onChange({ ...value, steps: value.steps.filter((_, j) => j !== i) })}>Remove</Button>
            </div>
            <Input aria-label={`Step ${i + 1} text (English)`} placeholder="Step text (English)" maxLength={400} value={s.text_en} onChange={(e) => set(i, { text_en: e.target.value })} />
            <Input aria-label={`Step ${i + 1} text (Hindi)`} placeholder="Step text (Hindi)" maxLength={400} value={s.text_hi ?? ""} onChange={(e) => set(i, { text_hi: e.target.value })} />
          </li>
        ))}
      </ul>
      <Button type="button" variant="outline" onClick={() => onChange({ ...value, steps: [...value.steps, { week: Math.max(1, ...value.steps.map((s) => s.week)), exercise: exercises[0]?.slug ?? "", text_en: "", text_hi: "" }] })}>Add step</Button>
    </div>
  );
}

export const clean = (p: Programme): Programme => ({
  title_en: p.title_en.trim(), title_hi: p.title_hi?.trim() || null,
  steps: p.steps.map((s) => ({ week: s.week, exercise: s.exercise, text_en: s.text_en.trim(), text_hi: s.text_hi?.trim() || null })),
});

export function Journeys({ clientId }: { clientId: string }) {
  const assigned = useFetch<Schemas["TherapistJourneysOut"]>(`/clients/${clientId}/journeys`);
  const lib = useFetch<Schemas["LibraryOut"]>("/therapists/me/journeys");
  const [templateId, setTemplateId] = useState("");
  const [building, setBuilding] = useState(false);
  const [prog, setProg] = useState<Programme>({ title_en: "", title_hi: "", steps: [{ week: 1, exercise: "", text_en: "", text_hi: "" }] });
  const [focus, setFocus] = useState("");
  const [weeks, setWeeks] = useState("3");
  const [msg, setMsg] = useState<{ text: string; inbox?: boolean } | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const exercises = lib.data?.exercises ?? [];

  async function run(fn: () => Promise<void>) { setBusy(true); setError(null); setMsg(null); try { await fn(); } catch (e) { setError(e); } finally { setBusy(false); } }
  const assign = (json: unknown) => run(async () => {
    await api(`/clients/${clientId}/journeys`, { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, json });
    setMsg({ text: "Programme assigned. The client sees it on their dashboard." }); setBuilding(false); assigned.reload(); lib.reload();
  });
  const draft = () => run(async () => {
    const r = await api<Schemas["DraftOut"]>(`/clients/${clientId}/journeys/draft`, { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() }, json: { focus, weeks: Number(weeks) } });
    setMsg({ text: r.message, inbox: r.status === "drafted" });
  });
  if (lib.loading && !lib.data) return <Loading />;
  return (
    <div className="space-y-4">
      {assigned.data?.items.length ? (
        <ul className="space-y-1 text-sm">{assigned.data.items.map((j) => (
          <li key={j.assignment_id} className="flex flex-wrap justify-between gap-2 rounded border p-2"><span className="font-medium">{j.title}</span>
            <span className="text-muted-foreground">Week {j.current_week} of {j.weeks} · {j.completed} of {j.total} steps done</span></li>
        ))}</ul>
      ) : <p className="text-sm text-muted-foreground">No programme assigned yet.</p>}
      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-48 flex-1 space-y-1"><Label htmlFor="tpl">Assign from library</Label>
          <Select id="tpl" value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
            <option value="">Choose a programme…</option>
            {lib.data?.items.map((j) => <option key={j.id} value={j.id}>{j.title_en}{j.own ? " (yours)" : ""}</option>)}
          </Select></div>
        <Button disabled={busy || !templateId} onClick={() => void assign({ template_id: Number(templateId) })}>Assign</Button>
        <Button variant="outline" onClick={() => setBuilding(!building)}>{building ? "Close editor" : "Build your own"}</Button>
      </div>
      {building && (
        <div className="space-y-3 rounded-md border p-3">
          <ProgrammeEditor value={prog} onChange={setProg} exercises={exercises} />
          <Button disabled={busy || !prog.title_en.trim() || prog.steps.some((s) => !s.text_en.trim() || !s.exercise)} onClick={() => void assign({ programme: clean(prog) })}>Assign programme</Button>
        </div>
      )}
      <div className="space-y-2 rounded-md border p-3">
        <p className="flex items-center gap-2 text-sm font-medium">Draft with AI <Badge className="border-amber-400 bg-amber-50 text-amber-800">proposal only</Badge></p>
        <p className="text-xs text-muted-foreground">The draft goes to your approval inbox. You edit and approve it; nothing reaches the client before that.</p>
        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-48 flex-1 space-y-1"><Label htmlFor="focus">Focus</Label><Input id="focus" maxLength={200} placeholder="e.g. winding down worry in the evening" value={focus} onChange={(e) => setFocus(e.target.value)} /></div>
          <div className="w-24 space-y-1"><Label htmlFor="weeks">Weeks</Label><Select id="weeks" value={weeks} onChange={(e) => setWeeks(e.target.value)}>{[2, 3, 4, 5, 6].map((n) => <option key={n}>{n}</option>)}</Select></div>
          <Button variant="outline" disabled={busy || !focus.trim()} onClick={() => void draft()}>Prepare draft</Button>
        </div>
      </div>
      {msg && <p role="status" className="text-sm">{msg.text} {msg.inbox && <Link className="underline" to="/therapist/inbox">Open inbox</Link>}</p>}
      {error != null && <ErrorMsg error={error} />}
    </div>
  );
}

export function JourneyDraftDetail({ id, status, draft, onSaved }: { id: number; status: string; draft: Programme; onSaved: () => void }) {
  const lib = useFetch<Schemas["LibraryOut"]>("/therapists/me/journeys");
  const [editing, setEditing] = useState(false);
  const [val, setVal] = useState<Programme>(draft);
  const [error, setError] = useState<unknown>(null);
  async function save() {
    setError(null);
    try { await api(`/pending-actions/${id}/journey-draft`, { method: "PUT", json: clean(val) }); setEditing(false); onSaved(); } catch (e) { setError(e); }
  }
  return (
    <div className="space-y-2 text-sm">
      <p className="font-medium">{draft.title_en}</p>
      {editing ? (
        <div className="space-y-2">
          <ProgrammeEditor value={val} onChange={setVal} exercises={lib.data?.exercises ?? []} />
          {error != null && <ErrorMsg error={error} />}
          <div className="flex gap-2"><Button onClick={() => void save()}>Save edits</Button><Button variant="outline" onClick={() => { setVal(draft); setEditing(false); }}>Cancel</Button></div>
        </div>
      ) : (
        <>
          <ol className="space-y-1">{draft.steps.map((s, i) => <li key={i}><span className="text-muted-foreground">Week {s.week} · {s.exercise.replace(/_/g, " ")}:</span> {s.text_en}</li>)}</ol>
          {status === "pending" && <Button variant="outline" onClick={() => setEditing(true)}>Edit draft</Button>}
        </>
      )}
    </div>
  );
}
