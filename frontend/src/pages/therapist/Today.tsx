import { useState } from "react";
import { Link } from "react-router-dom";
import { Moon, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import { AiBadge, InferredBadge, RiskAlerts, Shell, SupportedBadge, fmt, type Schemas } from "./common";

type Briefing = Schemas["BriefingItem"];

function Suggestion({ s, retrieved }: { s: Schemas["BriefingSuggestion"]; retrieved: Schemas["RetrievedRef"][] }) {
  const titles = s.chunk_ids.map((id) => retrieved.find((r) => r.id === id)?.title ?? `Knowledge entry #${id}`);
  return (
    <li className="space-y-1.5 rounded-md border p-3">
      <div className="flex flex-wrap items-center gap-2">
        {s.label === "SUPPORTED" ? <SupportedBadge /> : <InferredBadge />}
      </div>
      <p>{s.text}</p>
      <div className="space-y-1 text-xs text-muted-foreground">
        {titles.map((t, i) => <p key={i}>📚 Source: <span className="font-medium text-foreground">{t}</span></p>)}
        {s.note_quotes.map((q, i) => <p key={i}>📝 From your notes: <q className="italic text-foreground">{q}</q></p>)}
        {!titles.length && !s.note_quotes.length && <p>No citation — treat as an unverified idea.</p>}
        {s.support_note && <p>{s.support_note}</p>}
      </div>
    </li>
  );
}

function BriefingCard({ b, name }: { b: Briefing; name: string }) {
  const d = b.briefing;
  const scores = Object.entries(d.scores ?? {});
  return (
    <Card className="overflow-hidden border-l-4 border-l-primary">
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
        <div>
          <CardTitle className="text-lg">{name}</CardTitle>
          <p className="text-sm text-muted-foreground">Session {fmt(d.session_starts_at)}</p>
        </div>
        <div className="flex gap-2"><AiBadge />
          <Badge className={b.status === "draft" ? "" : b.status === "approved" ? "border-emerald-400 text-emerald-800" : "text-muted-foreground"}>{b.status}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {d.status === "error" ? <ErrorMsg error={new Error(d.summary)} /> : (
          <>
            <div className="rounded-md bg-muted p-3">
              <p className="mb-1 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Summary {d.summary_label === "INFERRED" && <InferredBadge />}
              </p>
              <p>{d.summary}</p>
              {d.status === "manual" && <p className="mt-1 text-sm font-medium">AI unavailable, manual workflow open. Showing knowledge entries to review yourself.</p>}
            </div>
            {d.status === "risk_stop" && <p role="alert" className="rounded-md border border-red-400 bg-red-50 p-2 text-sm text-red-800">Risk flag on this client: no AI content was generated. Review your notes directly.</p>}
            {scores.length > 0 && (
              <p className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
                {scores.map(([k, v]) => <span key={k}>{k}: <span className="font-medium text-foreground">{typeof v === "object" ? JSON.stringify(v) : String(v)}</span></span>)}
              </p>
            )}
            {d.suggestions.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-sm font-medium">Suggestions for your review</h3>
                <ul className="space-y-2">{d.suggestions.map((s, i) => <Suggestion key={i} s={s} retrieved={d.retrieved} />)}</ul>
              </div>
            )}
          </>
        )}
        <div className="flex gap-2 text-sm">
          <Button variant="outline" asChild><Link to={`/therapist/clients/${b.client_id}`}>Client file</Link></Button>
          {b.status === "draft" && <Button variant="outline" asChild><Link to="/therapist/inbox">Decide in inbox</Link></Button>}
        </div>
      </CardContent>
    </Card>
  );
}

function Body() {
  const alerts = useFetch<Schemas["AlertsOut"]>("/therapists/me/alerts");
  const briefings = useFetch<Schemas["BriefingsOut"]>("/therapists/me/briefings");
  const bookings = useFetch<Schemas["TherapistBookingsOut"]>("/therapists/me/bookings");
  const [busy, setBusy] = useState<"day" | "night" | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const names: Record<number, string> = {};
  bookings.data?.items.forEach((b) => { if (b.client.name) names[b.client.id] = b.client.name; });
  const nm = (id: number) => names[id] ?? `Client #${id}`;

  async function run(kind: "day" | "night") {
    setBusy(kind); setError(null); setMsg(null);
    try {
      if (kind === "day") {
        const r = await api<Schemas["PrepareDayOut"]>("/therapists/me/prepare-my-day", { method: "POST" });
        setMsg(r.items.length ? `Briefed ${r.items.length} client${r.items.length > 1 ? "s" : ""} (${r.items.filter((i) => i.reused).length} already prepared).` : "No confirmed sessions in the next 24 hours.");
      } else {
        const r = await api<Schemas["OvernightOut"]>("/therapist/overnight-check", { method: "POST" });
        setMsg(r.summary);
      }
      alerts.reload(); briefings.reload();
    } catch (e) { setError(e); } finally { setBusy(null); }
  }

  const latest = new Map<number, Briefing>();
  briefings.data?.items.forEach((b) => { if (!latest.has(b.client_id)) latest.set(b.client_id, b); });

  return (
    <div className="space-y-5">
      {alerts.error != null && <ErrorMsg error={alerts.error} />}
      {alerts.data && <RiskAlerts alerts={alerts.data.items} names={names} />}

      <section className="rounded-lg border bg-gradient-to-br from-primary/10 to-transparent p-4 sm:p-6">
        <h1 className="text-2xl font-semibold">Prepare my day</h1>
        <p className="mt-1 text-sm text-muted-foreground">Briefings for sessions in the next 24 hours. Everything here is a draft for you to check; nothing is sent to clients.</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button disabled={busy !== null} onClick={() => void run("day")}><Sparkles className="mr-2 h-4 w-4" />{busy === "day" ? "Preparing…" : "Prepare my day"}</Button>
          <Button variant="outline" disabled={busy !== null} onClick={() => void run("night")}><Moon className="mr-2 h-4 w-4" />{busy === "night" ? "Checking…" : "Run overnight check now"}</Button>
        </div>
        {msg && <p role="status" className="mt-3 text-sm">{msg}</p>}
        {error != null && <div className="mt-3"><ErrorMsg error={error} /></div>}
      </section>

      {briefings.loading ? <Loading /> : briefings.error != null ? <ErrorMsg error={briefings.error} /> :
        latest.size === 0 ? <Empty>No briefings yet. Press “Prepare my day” when you have confirmed sessions today.</Empty> : (
          <div className="grid gap-4 lg:grid-cols-2">
            {[...latest.values()].map((b) => <BriefingCard key={b.id} b={b} name={nm(b.client_id)} />)}
          </div>
        )}

      {alerts.data && alerts.data.items.some((a) => a.type !== "risk") && (
        <section className="space-y-2">
          <h2 className="font-semibold">Monitoring alerts</h2>
          <ul className="space-y-2">
            {alerts.data.items.filter((a) => a.type !== "risk").map((a) => (
              <li key={a.id} className="rounded-md border p-3 text-sm">
                <span className="font-medium">{nm(a.client_id)}</span> · {String(a.payload.finding ?? a.type)}
                {a.payload.detail != null && <span className="text-muted-foreground"> — {String(a.payload.detail)}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export default function Today() { return <Shell><Body /></Shell>; }
