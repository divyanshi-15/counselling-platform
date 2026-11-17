import { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { Bot, Check, Settings2, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { NewPractice } from "./Setup";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { api, type PracticePage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useFetch } from "@/lib/useFetch";
import type { Schemas } from "../client/common";
import { PracticeAnalytics } from "./PracticeAnalytics";

function Preview({ page }: { page: PracticePage }) {
  return (
    <div className="space-y-2 rounded-md border bg-muted/40 p-3 text-sm" aria-label="Page preview">
      <p className="text-base font-semibold">{page.tagline}</p>
      <p>{page.about}</p>
      {page.services?.map((s) => <p key={s.title}><span className="font-medium">{s.title}:</span> {s.description}</p>)}
      {page.faq?.map((f) => <p key={f.question}><span className="font-medium">{f.question}</span> {f.answer}</p>)}
      {!!page.what_to_expect?.length && <ul className="list-disc pl-5">{page.what_to_expect.map((w) => <li key={w}>{w}</li>)}</ul>}
      <p className="text-xs text-muted-foreground">{[page.location, page.languages?.join(", "), page.specialties?.join(", "), page.approaches?.join(", "), page.fee_range, page.session_type].filter(Boolean).join(" · ")}</p>
    </div>
  );
}

function PublishRow({ a, practice, onDone }: { a: Schemas["OwnerActionItem"]; practice?: Schemas["PracticeItemOut"]; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function decide(what: "approve" | "reject") {
    setBusy(true); setError(null);
    try { await api(`/pending-actions/${a.id}/${what}`, { method: "POST", headers: { "Idempotency-Key": a.idempotency_key } }); onDone(); }
    catch (e) { setError(e); } finally { setBusy(false); }
  }
  return (
    <Card className="border-l-4 border-l-primary">
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
        <CardTitle className="text-lg">Publish “{practice?.name ?? `practice #${a.practice_id}`}”</CardTitle>
        <Badge className={a.status === "pending" ? "border-amber-400 text-amber-800" : "text-muted-foreground"}>{a.status}</Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        <Preview page={(a.payload.draft ?? {}) as PracticePage} />
        {error != null && <ErrorMsg error={error} />}
        {a.status === "pending" && (
          <div className="flex gap-2">
            <Button disabled={busy} onClick={() => void decide("approve")}><Check className="mr-1 h-4 w-4" />Approve to publish</Button>
            <Button variant="outline" disabled={busy} onClick={() => void decide("reject")}><X className="mr-1 h-4 w-4" />Reject</Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function PracticeCard({ p, onDraft }: { p: Schemas["PracticeItemOut"]; onDraft: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const page = p.page as PracticePage;
  async function draft() {
    setBusy(true); setError(null);
    try {
      await api(`/practices/${p.id}/draft-with-agent`, { method: "POST", json: { name: p.name, location: page.location ?? "Bengaluru", languages: page.languages ?? [], specialties: page.specialties ?? [], approaches: page.approaches ?? [], fee_range: page.fee_range ?? "2000-3000", session_type: page.session_type ?? "online" } });
      onDraft();
    } catch (e) { setError(e); } finally { setBusy(false); }
  }
  return (
    <li className="space-y-2 rounded-md border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{p.name}</span>
        <Badge>{p.status}</Badge>
        <Badge className={p.verified ? "border-emerald-400 text-emerald-800" : "text-muted-foreground"}>{p.verified ? "verified" : "not verified"}</Badge>
        <Button className="ml-auto" asChild><Link to={`/owner/setup/${p.id}`}><Settings2 className="h-4 w-4" />Practice setup</Link></Button>
        <Button variant="outline" disabled={busy} onClick={() => void draft()}><Sparkles className="mr-2 h-4 w-4" />{busy ? "Drafting…" : "Draft with agent"}</Button>
      </div>
      {p.status === "published" && !p.verified && <p className="text-xs text-muted-foreground">Published, but not shown publicly until an admin verifies it.</p>}
      {error != null && <ErrorMsg error={error} />}
    </li>
  );
}

function AgentActivity({ practices }: { practices: Schemas["PracticeItemOut"][] }) {
  const [id, setId] = useState<number>(practices[0].id);
  const { data, error, loading } = useFetch<Schemas["AgentRunsOut"]>(`/practices/${id}/agent-runs`);
  const runs = new Map<string, Schemas["AgentRunItem"][]>();
  data?.items.forEach((r) => runs.set(r.run_id, [...(runs.get(r.run_id) ?? []), r]));
  return (
    <section className="space-y-3" aria-label="Agent activity">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold">Agent activity</h2>
        <select aria-label="Practice" className="h-10 rounded-md border border-input bg-background px-3 text-sm" value={id} onChange={(e) => setId(Number(e.target.value))}>
          {practices.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </div>
      <p className="text-sm text-muted-foreground">Every step the drafting agent took. It only proposes a page; nothing is published until you approve it above.</p>
      {loading ? <Loading /> : error != null ? <ErrorMsg error={error} /> : runs.size === 0 ? <Empty>No agent runs for this practice yet.</Empty> : (
        <ol className="space-y-3">
          {[...runs.entries()].map(([rid, steps]) => (
            <li key={rid} className="rounded-lg border p-3">
              <p className="mb-2 flex items-center gap-2 text-sm font-medium"><Bot className="h-4 w-4 text-primary" /> Launch agent <Badge className="text-muted-foreground">{steps.length} steps / max 8 tool calls</Badge></p>
              <ol className="space-y-1 border-l pl-4 text-sm">
                {[...steps].sort((a, b) => a.step - b.step).map((s) => <li key={s.step}><code className="rounded bg-muted px-1.5 py-0.5 text-xs">{s.tool}</code> {s.summary}</li>)}
              </ol>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function Body() {
  const practices = useFetch<Schemas["PracticesOut"]>("/practices");
  const actions = useFetch<Schemas["OwnerActionsOut"]>("/pending-actions");
  const [rev, setRev] = useState(0);
  const reload = () => { practices.reload(); actions.reload(); setRev((n) => n + 1); };
  const byId = new Map(practices.data?.items.map((p) => [p.id, p]));
  const pending = actions.data?.items.filter((a) => a.type === "publish_page" && a.status === "pending") ?? [];
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Practice owner</h1>
      <PracticeAnalytics />
      <NewPractice />
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">My practices</h2>
        {practices.loading && !practices.data ? <Loading /> : practices.error != null ? <ErrorMsg error={practices.error} /> :
          !practices.data?.items.length ? <Empty>No practices yet. Start by setting one up above.</Empty> :
            <ul className="space-y-2">{practices.data.items.map((p) => <PracticeCard key={p.id} p={p} onDraft={reload} />)}</ul>}
      </section>
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Pages waiting for your approval</h2>
        {actions.loading && !actions.data ? <Loading /> : actions.error != null ? <ErrorMsg error={actions.error} /> :
          pending.length === 0 ? <Empty>Nothing waiting. Drafts appear here for you to preview and approve.</Empty> :
            <div className="space-y-4">{pending.map((a) => <PublishRow key={a.id} a={a} practice={byId.get(a.practice_id)} onDone={reload} />)}</div>}
      </section>
      {practices.data && practices.data.items.length > 0 && <AgentActivity key={rev} practices={practices.data.items} />}
    </div>
  );
}

export default function Owner() {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "practice_owner") return <Navigate to="/" replace />;
  return <Body />;
}
