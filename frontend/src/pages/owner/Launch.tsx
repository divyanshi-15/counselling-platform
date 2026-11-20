import { useEffect, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { ArrowLeft, Check, Loader2, Pencil, Rocket, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorMsg, Loading } from "@/components/states";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";
import { useFetch } from "@/lib/useFetch";
import type { Schemas } from "../client/common";

type Run = Schemas["RunOut"];
type Action = Schemas["PlanActionOut"];
type State = Schemas["LaunchStateOut"];
type Domain = { domain: string; status: string; price?: number | null; currency?: string | null; reason?: string | null };
type Plan = {
  idea: string; domains: Domain[]; recommended_domain?: string | null; checklist: string[];
  dns_plan?: { records: { type: string; name: string; data: string }[]; note?: string } | null;
  page: { tagline: string; about: string; services: Record<string, string>[]; faq: Record<string, string>[]; what_to_expect: string[] };
  welcome_email: { subject: string; body: string };
};

function Steps({ steps, running }: { steps: Run["steps"]; running: boolean }) {
  const t = useT();
  return (
    <section aria-label={t("launchSteps")} className="space-y-2">
      <h2 className="text-lg font-semibold">{t("launchSteps")}</h2>
      <ol className="space-y-1 border-l pl-4 text-sm">
        {steps.map((s) => (
          <li key={s.step}>
            <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{s.tool}</code> <span className="text-muted-foreground">{s.input}</span>
            <div>{s.result} <span className="text-xs text-muted-foreground">{s.tokens ? `· ${s.tokens} tok` : ""}</span></div>
          </li>
        ))}
        {running && <li className="flex items-center gap-2 text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />{t("launchWorking")}</li>}
      </ol>
    </section>
  );
}

function DomainRow({ d, approved, confirmed, onUse, busy }: { d: Domain; approved: boolean; confirmed: boolean; onUse: () => void; busy: boolean }) {
  const t = useT();
  const label = { available: t("launchAvailable"), taken: t("launchTaken"), unknown: t("launchUnknown"), not_checked: t("launchNotChecked") }[d.status] ?? d.status;
  const tone = d.status === "available" ? "border-emerald-400 text-emerald-800" : d.status === "taken" ? "border-red-300 text-red-800" : "text-muted-foreground";
  return (
    <li className="flex flex-wrap items-center gap-2 rounded-md border p-2 text-sm">
      <span className="font-medium break-all">{d.domain}</span>
      <Badge className={tone}>{label}</Badge>
      {d.price != null && <span className="text-xs">{d.price} {d.currency}</span>}
      {d.reason && <span className="text-xs text-muted-foreground">{d.reason}</span>}
      {confirmed ? <Badge className="ml-auto border-emerald-400 text-emerald-800">{t("launchConfirmed")}</Badge>
        : approved && d.status !== "taken" && <Button className="ml-auto" variant="outline" disabled={busy} onClick={onUse}>{t("launchUseDomain")}</Button>}
    </li>
  );
}

function PlanView({ action, state, onChange }: { action: Action; state: State; onChange: () => void }) {
  const t = useT();
  const plan = action.plan as unknown as Plan;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({ tagline: plan.page.tagline, about: plan.page.about, subject: plan.welcome_email.subject, body: plan.welcome_email.body, checklist: plan.checklist.join("\n") });
  const [note, setNote] = useState<string | null>(null);
  const pid = useParams().id;
  const approved = action.status === "approved";
  const pending = action.status === "pending";
  const records = state.custom_domain ? state.dns_plan?.records as { type: string; name: string; data: string }[] | undefined : plan.dns_plan?.records;

  async function run(fn: () => Promise<unknown>, done?: string) {
    setBusy(true); setError(null); setNote(null);
    try { await fn(); if (done) setNote(done); onChange(); } catch (e) { setError(e); } finally { setBusy(false); }
  }
  const decide = (what: "approve" | "reject") => run(() => api(`/pending-actions/${action.id}/${what}`, { method: "POST", headers: { "Idempotency-Key": action.idempotency_key } }), what === "approve" ? t("launchApproved") : t("launchRejected"));
  const save = () => run(async () => {
    await api(`/owner/practices/${pid}/launch/plans/${action.id}`, { method: "PUT", json: {
      page: { ...plan.page, tagline: draft.tagline, about: draft.about }, welcome_email: { subject: draft.subject, body: draft.body },
      checklist: draft.checklist.split("\n").map((l) => l.trim()).filter(Boolean) } });
    setEditing(false);
  });
  const use = (domain: string) => run(() => api(`/owner/practices/${pid}/launch/domain/confirm`, { method: "POST", json: { domain } }));
  const applyDns = () => run(() => api(`/owner/practices/${pid}/launch/domain/apply-dns`, { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() } }), t("launchDnsDone"));

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle className="text-lg">{t("launchDomains")}</CardTitle></CardHeader>
        <CardContent><ul className="space-y-2">{plan.domains.map((d) => <DomainRow key={d.domain} d={d} approved={approved} confirmed={state.custom_domain === d.domain} busy={busy} onUse={() => void use(d.domain)} />)}</ul></CardContent>
      </Card>
      {!!records?.length && (
        <Card>
          <CardHeader><CardTitle className="text-lg">{t("launchDns")}</CardTitle><p className="text-sm text-muted-foreground">{t("launchDnsHint")}</p></CardHeader>
          <CardContent className="space-y-3">
            <div className="overflow-x-auto"><table className="w-full text-sm"><tbody>
              {records.map((r) => <tr key={r.type + r.name} className="border-b"><td className="py-1 pr-3 font-mono">{r.type}</td><td className="pr-3 font-mono">{r.name}</td><td className="font-mono break-all">{r.data}</td></tr>)}
            </tbody></table></div>
            {state.custom_domain && (state.dns_write_enabled
              ? <Button disabled={busy} onClick={() => void applyDns()}>{t("launchDnsApply")}</Button>
              : <p className="text-sm text-muted-foreground">{t("launchDnsManual")}</p>)}
          </CardContent>
        </Card>
      )}
      <Card>
        <CardHeader><CardTitle className="text-lg">{t("launchPage")}</CardTitle></CardHeader>
        <CardContent className="space-y-3 text-sm">
          {editing ? (
            <>
              <div><Label>{t("launchTagline")}</Label><Input value={draft.tagline} maxLength={160} onChange={(e) => setDraft({ ...draft, tagline: e.target.value })} /></div>
              <div><Label>{t("launchAbout")}</Label><Textarea rows={6} value={draft.about} onChange={(e) => setDraft({ ...draft, about: e.target.value })} /></div>
              <div><Label>{t("launchSubject")}</Label><Input value={draft.subject} onChange={(e) => setDraft({ ...draft, subject: e.target.value })} /></div>
              <div><Label>{t("launchBody")}</Label><Textarea rows={5} value={draft.body} onChange={(e) => setDraft({ ...draft, body: e.target.value })} /></div>
              <div><Label>{t("launchChecklist")} ({t("launchOnePerLine")})</Label><Textarea rows={5} value={draft.checklist} onChange={(e) => setDraft({ ...draft, checklist: e.target.value })} /></div>
              <div className="flex gap-2"><Button disabled={busy} onClick={() => void save()}>{t("launchSaveEdit")}</Button><Button variant="outline" onClick={() => setEditing(false)}>{t("launchCancel")}</Button></div>
            </>
          ) : (
            <>
              <p className="text-base font-semibold">{plan.page.tagline}</p>
              <p className="whitespace-pre-line">{plan.page.about}</p>
              {plan.page.services.map((s) => <p key={s.title}><span className="font-medium">{s.title}:</span> {s.description}</p>)}
              {!!plan.page.what_to_expect.length && <ul className="list-disc pl-5">{plan.page.what_to_expect.map((w) => <li key={w}>{w}</li>)}</ul>}
              <h3 className="pt-2 font-semibold">{t("launchEmail")}</h3>
              <p className="font-medium">{plan.welcome_email.subject}</p>
              <p className="whitespace-pre-line">{plan.welcome_email.body}</p>
              <h3 className="pt-2 font-semibold">{t("launchChecklist")}</h3>
              <ul className="list-disc pl-5">{plan.checklist.map((c) => <li key={c}>{c}</li>)}</ul>
            </>
          )}
        </CardContent>
      </Card>
      <p className="text-sm text-muted-foreground">{t("launchTokens")}: {action.tokens_in + action.tokens_out} · {t("launchCost")}: ≈ ${action.cost_usd.toFixed(4)}</p>
      {error != null && <ErrorMsg error={error} />}
      {note && <p role="status" className="text-sm text-emerald-800">{note}</p>}
      {pending && !editing && (
        <div className="flex flex-wrap gap-2">
          <Button disabled={busy} onClick={() => void decide("approve")}><Check className="mr-1 h-4 w-4" />{t("launchApprove")}</Button>
          <Button variant="outline" disabled={busy} onClick={() => setEditing(true)}><Pencil className="mr-1 h-4 w-4" />{t("launchEdit")}</Button>
          <Button variant="outline" disabled={busy} onClick={() => void decide("reject")}><X className="mr-1 h-4 w-4" />{t("launchReject")}</Button>
        </div>
      )}
    </div>
  );
}

function Body({ id }: { id: string }) {
  const t = useT();
  const state = useFetch<State>(`/owner/practices/${id}/launch`);
  const [idea, setIdea] = useState("");
  const [run, setRun] = useState<Run | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const runId = run?.run_id;
  const running = run?.status === "running";

  useEffect(() => {
    if (!runId || !running) return;
    const timer = setInterval(() => {
      api<Run>(`/owner/practices/${id}/launch/runs/${runId}`).then((r) => { setRun(r); if (r.status !== "running") state.reload(); }).catch(setError);
    }, 1000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, running, id]);

  async function start() {
    setStarting(true); setError(null);
    try { setRun(await api<Run>(`/owner/practices/${id}/launch/run`, { method: "POST", json: { idea } })); }
    catch (e) { setError(e); } finally { setStarting(false); }
  }
  const action = run?.action ?? (run && run.status !== "complete" ? null : state.data?.latest ?? null);
  const latest = state.data?.latest && state.data.latest.id === action?.id ? state.data.latest : action;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Button variant="ghost" asChild><Link to="/owner"><ArrowLeft className="mr-1 h-4 w-4" /> Practice owner</Link></Button>
      <h1 className="flex items-center gap-2 text-2xl font-semibold"><Rocket className="h-6 w-6 text-primary" />{t("launchTitle")}</h1>
      <p className="text-sm text-muted-foreground">{t("launchIntro")}</p>
      <div className="space-y-2">
        <Label htmlFor="idea">{t("launchIdea")}</Label>
        <Textarea id="idea" rows={4} maxLength={1000} value={idea} onChange={(e) => setIdea(e.target.value)} />
        <Button disabled={starting || running || idea.trim().length < 10} onClick={() => void start()}>{running || starting ? t("launchWorking") : t("launchStart")}</Button>
      </div>
      {error != null && <ErrorMsg error={error} />}
      {run && <Steps steps={run.steps} running={running} />}
      {run && run.status !== "running" && run.status !== "complete" && (
        <div role="alert" className="space-y-2 rounded-md border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">
          <p>{run.message}</p>
          <Button variant="outline" asChild><Link to={`/owner/setup/${id}`}>{t("launchManual")}</Link></Button>
        </div>
      )}
      {state.loading && !state.data ? <Loading /> : state.data && latest && <PlanView key={latest.id + latest.status + (state.data.custom_domain ?? "") + JSON.stringify(latest.plan).length} action={latest} state={state.data} onChange={state.reload} />}
    </div>
  );
}

export default function Launch() {
  const { user, loading } = useAuth();
  const { id } = useParams();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "practice_owner" || !id) return <Navigate to="/" replace />;
  return <Body id={id} />;
}
