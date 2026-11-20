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
type Domain = { domain: string; status: string; price?: number | null; currency?: string | null; reason?: string | null; link_url: string };
type Rec = { type: string; name: string; data: string };
type Plan = {
  idea: string; slugs: { slug: string; available: boolean }[]; chosen_slug: string; domains: Domain[]; domain_note?: string | null; checklist: string[];
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

function CopyButton({ text }: { text: string }) {
  const t = useT();
  const [done, setDone] = useState(false);
  return <Button type="button" variant="outline" className="h-8 px-2 text-xs" onClick={() => { void navigator.clipboard.writeText(text).then(() => { setDone(true); setTimeout(() => setDone(false), 1500); }); }}>{done ? t("launchCopied") : t("launchCopy")}</Button>;
}

function DomainRow({ d, approved, confirmed, onRegistered, busy }: { d: Domain; approved: boolean; confirmed: boolean; onRegistered: () => void; busy: boolean }) {
  const t = useT();
  const label = { available: t("launchAvailable"), taken: t("launchTaken") }[d.status];
  return (
    <li className="space-y-2 rounded-md border p-2 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium break-all">{d.domain}</span>
        {d.status === "unchecked" ? <Badge className="text-muted-foreground">{t("launchNotCheckedInApp")}</Badge>
          : <Badge className={d.status === "available" ? "border-emerald-400 text-emerald-800" : "border-red-300 text-red-800"}>{label}</Badge>}
        {d.price != null && <span className="text-xs">{d.price} {d.currency}</span>}
        {confirmed && <Badge className="ml-auto border-emerald-400 text-emerald-800">{t("launchConfirmed")}</Badge>}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" asChild><a href={d.link_url} target="_blank" rel="noopener noreferrer">{t("launchCheckGoDaddy")}</a></Button>
        {approved && !confirmed && d.status !== "taken" && <Button variant="outline" disabled={busy} onClick={onRegistered}>{t("launchRegistered")}</Button>}
      </div>
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
  const records = state.custom_domain ? (state.dns_plan?.records as Rec[] | undefined) : undefined;
  const origin = window.location.origin;

  async function run(fn: () => Promise<unknown>, done?: string) {
    setBusy(true); setError(null); setNote(null);
    try { await fn(); if (done) setNote(done); onChange(); } catch (e) { setError(e); } finally { setBusy(false); }
  }
  const decide = (what: "approve" | "reject") => run(() => api(`/pending-actions/${action.id}/${what}`, { method: "POST", headers: { "Idempotency-Key": action.idempotency_key } }), what === "approve" ? t("launchApproved") : t("launchRejected"));
  const put = (page: Plan["page"], email: Plan["welcome_email"], checklist: string[], slug?: string) =>
    api(`/owner/practices/${pid}/launch/plans/${action.id}`, { method: "PUT", json: { page, welcome_email: email, checklist, ...(slug ? { slug } : {}) } });
  const save = () => run(async () => {
    await put({ ...plan.page, tagline: draft.tagline, about: draft.about }, { subject: draft.subject, body: draft.body }, draft.checklist.split("\n").map((l) => l.trim()).filter(Boolean));
    setEditing(false);
  });
  const useSlug = (slug: string) => run(() => put(plan.page, plan.welcome_email, plan.checklist, slug));
  const registered = (domain: string) => run(() => api(`/owner/practices/${pid}/launch/domain/confirm`, { method: "POST", json: { domain } }));
  const applyDns = () => run(() => api(`/owner/practices/${pid}/launch/domain/apply-dns`, { method: "POST", headers: { "Idempotency-Key": crypto.randomUUID() } }), t("launchDnsDone"));

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader><CardTitle className="text-lg">{t("launchSlug")}</CardTitle><p className="text-sm text-muted-foreground">{t("launchSlugHint")}</p></CardHeader>
        <CardContent><ul className="space-y-2">
          {plan.slugs.map((o) => (
            <li key={o.slug} className="flex flex-wrap items-center gap-2 rounded-md border p-2 text-sm">
              <span className="font-mono break-all">{origin}/p/{o.slug}</span>
              <Badge className={o.available ? "border-emerald-400 text-emerald-800" : "border-red-300 text-red-800"}>{o.available ? t("launchAvailable") : t("launchTaken")}</Badge>
              {o.slug === plan.chosen_slug ? <Badge className="ml-auto">{t("launchChosen")}</Badge>
                : pending && o.available && <Button className="ml-auto" variant="outline" disabled={busy} onClick={() => void useSlug(o.slug)}>{t("launchUseSlug")}</Button>}
            </li>
          ))}
          {!plan.slugs.some((o) => o.slug === plan.chosen_slug) && <li className="rounded-md border p-2 font-mono text-sm break-all">{origin}/p/{plan.chosen_slug} <Badge className="ml-2">{t("launchChosen")}</Badge></li>}
        </ul></CardContent>
      </Card>
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
            </>
          )}
        </CardContent>
      </Card>
      {!editing && (
        <Card>
          <CardHeader><CardTitle className="text-lg">{t("launchChecklist")}</CardTitle></CardHeader>
          <CardContent><ul className="list-disc pl-5 text-sm">{plan.checklist.map((c) => <li key={c}>{c}</li>)}</ul></CardContent>
        </Card>
      )}
      <details className="rounded-lg border p-4" open={!!state.custom_domain}>
        <summary className="cursor-pointer text-lg font-semibold">{t("launchOptional")}</summary>
        <div className="mt-3 space-y-3">
          <p className="text-sm text-muted-foreground">{t("launchOptionalHint")}</p>
          {plan.domain_note && <p className="text-sm text-muted-foreground">{plan.domain_note}</p>}
          {!!plan.domains.length && (
            <>
              <ul className="space-y-2">{plan.domains.map((d) => <DomainRow key={d.domain} d={d} approved={approved} confirmed={state.custom_domain === d.domain} busy={busy} onRegistered={() => void registered(d.domain)} />)}</ul>
              <p className="text-sm">{t("launchPurchaseNote")}</p>
            </>
          )}
          {!!records?.length && (
            <div className="space-y-2">
              <h3 className="font-semibold">{t("launchDns")}: {state.custom_domain}</h3>
              <p className="text-sm text-muted-foreground">{t("launchRecordsHint")}</p>
              <ul className="space-y-1">{records.map((r) => (
                <li key={r.type + r.name} className="flex flex-wrap items-center gap-2 text-sm">
                  <code className="font-mono">{r.type}</code><code className="font-mono">{r.name}</code><code className="font-mono break-all">{r.data}</code><CopyButton text={r.data} />
                </li>))}</ul>
              {state.dns_write_enabled
                ? <Button disabled={busy} onClick={() => void applyDns()}>{t("launchDnsApply")}</Button>
                : <p className="text-sm text-muted-foreground">{t("launchDnsManual")}</p>}
            </div>
          )}
        </div>
      </details>
      <p className="text-sm text-muted-foreground">{t("launchTokens")}: {action.tokens_in + action.tokens_out}{action.cost_usd != null && <> · {t("launchCost")}: ≈ ${action.cost_usd.toFixed(4)}</>}</p>
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
