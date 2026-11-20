import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import { Shell, fmt, type Schemas } from "./common";
import { Avatar } from "@/components/Avatar";
import { formatAlert, formatEvidence, formatScoreChange } from "@/lib/evidence";
import { Item9Chip, ScoresPair } from "./Overnight";
import { Journeys, MoodTrendCard, SharedJournal } from "./Skills";

const ITEMS = { PHQ9: 9, GAD7: 7 } as const;

function Assessments({ clientId }: { clientId: string }) {
  const list = useFetch<Schemas["AssessmentsOut"]>(`/clients/${clientId}/assessments`);
  const [type, setType] = useState<"PHQ9" | "GAD7">("PHQ9");
  const [scores, setScores] = useState<string[]>(Array(9).fill("0"));
  const [error, setError] = useState<unknown>(null);
  const [alert, setAlert] = useState(false);
  const pick = (t: "PHQ9" | "GAD7") => { setType(t); setScores(Array(ITEMS[t]).fill("0")); setAlert(false); };
  async function save(e: React.FormEvent) {
    e.preventDefault(); setError(null);
    try {
      const r = await api<Schemas["AssessmentOut"]>(`/clients/${clientId}/assessments`, { method: "POST", json: { type, item_scores: scores.map(Number) } });
      setAlert(!!r.risk_alert); list.reload();
    } catch (err) { setError(err); }
  }
  return (
    <div className="space-y-4">
      <form onSubmit={(e) => void save(e)} className="space-y-3">
        <div className="flex gap-2">{(["PHQ9", "GAD7"] as const).map((t) => <Button key={t} type="button" variant={t === type ? "default" : "outline"} onClick={() => pick(t)}>{t === "PHQ9" ? "PHQ-9" : "GAD-7"}</Button>)}</div>
        <div className="grid grid-cols-5 gap-2 sm:grid-cols-9">
          {scores.map((s, i) => (
            <div key={i} className="space-y-1"><Label htmlFor={`i${i}`} className="text-xs">Item {i + 1}</Label>
              <Input id={`i${i}`} type="number" min={0} max={3} required value={s} onChange={(e) => setScores(scores.map((x, j) => (j === i ? e.target.value : x)))} /></div>
          ))}
        </div>
        {error != null && <ErrorMsg error={error} />}
        {alert && <p role="alert" className="rounded-md border-2 border-red-600 bg-red-50 p-3 text-sm font-medium text-red-800">Item 9 is above 0. A high-priority risk alert was raised on your Today page.</p>}
        <Button>Record score</Button>
      </form>
      {list.loading ? <Loading /> : list.error != null ? <ErrorMsg error={list.error} /> : list.data!.items.length === 0 ? <Empty>No scores recorded.</Empty> : (
        <ul className="space-y-1 text-sm">
          {[...list.data!.items].reverse().map((a) => (
            <li key={a.id} className="flex justify-between rounded border p-2"><span>{a.type === "PHQ9" ? "PHQ-9" : "GAD-7"} · {fmt(a.taken_at)}</span><span className="font-medium">{a.total}</span></li>
          ))}
        </ul>
      )}
    </div>
  );
}

function CasePlan({ clientId }: { clientId: string }) {
  const plans = useFetch<Schemas["CasePlansOut"]>(`/clients/${clientId}/case-plans`);
  const latest = plans.data?.items[0];
  const [approach, setApproach] = useState("CBT");
  const [text, setText] = useState("");
  const [goals, setGoals] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (latest) { setApproach(latest.approach); setText(latest.formulation_text); setGoals(latest.goals.map((g) => g.text).join("\n")); }
  }, [latest?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  async function save(approve: boolean) {
    setBusy(true); setError(null);
    const lines = goals.split("\n").map((g) => g.trim()).filter(Boolean);
    try {
      await api(`/clients/${clientId}/case-plans`, { method: "POST", json: { approach, formulation_text: text, approve, goals: lines.map((g, i) => ({ id: `g${i + 1}`, text: g })) } });
      plans.reload();
    } catch (err) { setError(err); } finally { setBusy(false); }
  }
  if (plans.loading && !plans.data) return <Loading />;
  if (plans.error != null) return <ErrorMsg error={plans.error} />;
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">The formulation is yours: written by you, never by the AI. Each save is a new version.</p>
      {latest && <p className="flex items-center gap-2 text-sm">Version {latest.version} <Badge className={latest.approved_at ? "border-emerald-400 text-emerald-800" : "text-muted-foreground"}>{latest.approved_at ? "approved" : "draft"}</Badge></p>}
      <div className="space-y-1"><Label htmlFor="approach">Approach</Label><Input id="approach" value={approach} maxLength={32} onChange={(e) => setApproach(e.target.value)} /></div>
      <div className="space-y-1"><Label htmlFor="form">Formulation</Label><Textarea id="form" rows={8} value={text} onChange={(e) => setText(e.target.value)} /></div>
      {latest?.update_notes && (
        <div className="space-y-1 rounded-md border bg-muted/40 p-3 text-sm" aria-label="Update notes">
          <p className="font-medium">{latest.update_notes_label}</p>
          <p className="whitespace-pre-wrap">{latest.update_notes}</p>
        </div>
      )}
      <div className="space-y-1"><Label htmlFor="goals">Goals (one per line)</Label><Textarea id="goals" rows={4} value={goals} onChange={(e) => setGoals(e.target.value)} /></div>
      {error != null && <ErrorMsg error={error} />}
      <div className="flex gap-2">
        <Button disabled={busy || !text.trim() || !approach.trim()} onClick={() => void save(true)}>Save &amp; approve new version</Button>
        <Button variant="outline" disabled={busy || !text.trim() || !approach.trim()} onClick={() => void save(false)}>Save as draft</Button>
      </div>
    </div>
  );
}

function Overview({ clientId }: { clientId: string }) {
  const status = useFetch<Schemas["OvernightStatusOut"]>("/therapist/overnight-status");
  const alerts = useFetch<Schemas["AlertsOut"]>("/therapists/me/alerts");
  const c = status.data?.clients.find((x) => String(x.client_id) === clientId);
  if (status.loading && !status.data) return <Loading />;
  if (status.error != null) return <ErrorMsg error={status.error} />;
  if (!c) return <Empty>No monitoring data for this client yet.</Empty>;
  const evidence = formatEvidence(c.evidence);
  const open = (alerts.data?.items ?? []).filter((a) => String(a.client_id) === clientId && a.type !== "risk" && !a.acknowledged);
  const change = formatScoreChange(c.scores);
  return (
    <div className="space-y-3">
      {c.scores.item9_positive && <Item9Chip />}
      {change && <p className="text-sm text-muted-foreground">{change}</p>}
      <ScoresPair scores={c.scores} />
      {evidence.length > 0 && <ul className="list-disc space-y-0.5 pl-5 text-sm">{evidence.map((t, i) => <li key={i}>{t}</li>)}</ul>}
      {open.length > 0 && (
        <div className="space-y-1"><h3 className="text-sm font-medium">Open monitoring alerts</h3>
          <ul className="list-disc space-y-0.5 pl-5 text-sm">{open.map((a) => <li key={a.id}>{formatAlert(a.type, a.payload)}</li>)}</ul></div>
      )}
    </div>
  );
}

function Body() {
  const { clientId = "" } = useParams();
  const status = useFetch<Schemas["OvernightStatusOut"]>("/therapist/overnight-status");
  const name = status.data?.clients.find((x) => String(x.client_id) === clientId)?.name;
  return (
    <div className="space-y-4">
      <h1 className="flex items-center gap-3 text-2xl font-semibold">{name ? <><Avatar name={name} size={40} />{name}</> : `Client file #${clientId}`}</h1>
      <Card><CardHeader><CardTitle>Overview</CardTitle></CardHeader><CardContent><Overview clientId={clientId} /></CardContent></Card>
      <Card><CardHeader><CardTitle>PHQ-9 / GAD-7</CardTitle></CardHeader><CardContent><Assessments clientId={clientId} /></CardContent></Card>
      <Card><CardHeader><CardTitle>Mood and sleep, last 14 days</CardTitle></CardHeader><CardContent><MoodTrendCard clientId={clientId} /></CardContent></Card>
      <Card><CardHeader><CardTitle>Journeys</CardTitle></CardHeader><CardContent><Journeys clientId={clientId} /></CardContent></Card>
      <Card><CardHeader><CardTitle>Shared journal entries</CardTitle></CardHeader><CardContent><SharedJournal clientId={clientId} /></CardContent></Card>
      <Card><CardHeader><CardTitle>Case plan</CardTitle></CardHeader><CardContent><CasePlan clientId={clientId} /></CardContent></Card>
    </div>
  );
}
export default function Client() { return <Shell><Body /></Shell>; }
