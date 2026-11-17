import { Avatar } from "@/components/Avatar";
import { useState } from "react";
import { Check, Eye, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import { AiBadge, InferredBadge, Shell, type Schemas } from "./common";

type Item = Schemas["TherapistActionItem"];
const TITLES: Record<string, string> = { release_exercise: "Release exercise to client", apply_plan_update: "Update case plan", copilot_briefing: "Briefing draft" };

function Side({ title, snap, other }: { title: string; snap: Schemas["PlanSnapshot"]; other: Schemas["PlanSnapshot"] }) {
  const goalChanged = (g: string) => !other.goals.includes(g);
  return (
    <div className="space-y-2 rounded border bg-background p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</p>
      <p><span className="text-muted-foreground">Approach:</span> <span className={snap.approach !== other.approach ? "bg-amber-100 px-1" : ""}>{snap.approach}</span></p>
      <div>
        <p className="text-muted-foreground">Goals:</p>
        <ul className="list-disc pl-5">{snap.goals.map((g) => <li key={g} className={goalChanged(g) ? "bg-amber-100" : ""}>{g}</li>)}</ul>
      </div>
      <p className="whitespace-pre-wrap text-xs">{snap.formulation}</p>
      {snap.update_notes && (
        <div className={`rounded border p-2 text-xs ${snap.update_notes !== other.update_notes ? "bg-amber-100" : ""}`}>
          <p className="font-medium">{snap.update_notes_label}</p>
          <p className="whitespace-pre-wrap">{snap.update_notes}</p>
        </div>
      )}
    </div>
  );
}

function WhatChanges({ diff }: { diff: Schemas["PlanDiff"] }) {
  return (
    <div className="space-y-2 rounded-md border-2 border-primary bg-primary/5 p-3" aria-label="What changes">
      <p className="text-xs font-semibold uppercase tracking-wide">What changes</p>
      {diff.stale && <p role="alert" className="text-sm font-medium text-destructive">The plan changed since this draft; approving will be refused. Reject it and re-run the check.</p>}
      <p className="text-sm">
        {diff.changed.length ? `Changed: ${diff.changed.join(", ")}.` : "No change."}
        {!diff.changed.includes("goals") && !diff.changed.includes("approach") && " Goals and approach stay as they are; your formulation is not touched; the AI draft is added as separate update notes."}
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <Side title="Before (current version)" snap={diff.before} other={diff.after} />
        <Side title="After (new version)" snap={diff.after} other={diff.before} />
      </div>
    </div>
  );
}

function Detail({ a }: { a: Item }) {
  const p = a.payload;
  if (a.type === "apply_plan_update") {
    const findings = (p.findings ?? {}) as Record<string, unknown>;
    return (
      <div className="space-y-2 text-sm">
        <p className="font-medium">Text that would be appended to the case-plan formulation (new version):</p>
        <blockquote className="whitespace-pre-wrap rounded border-l-4 border-primary bg-muted p-3">{String(p.update_text ?? "")}</blockquote>
        <p className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          {p.ai_status === "ok" ? <InferredBadge /> : <Badge>manual text</Badge>}
          Based on: {Object.entries(findings).map(([k, v]) => `${k.replace(/_/g, " ")} (${String(v)})`).join("; ") || "monitoring findings"}
        </p>
      </div>
    );
  }
  if (a.type === "release_exercise") {
    return (
      <div className="space-y-1 text-sm">
        <p className="font-medium">Exercise: {a.client_view.title ?? String(p.exercise)}</p>
        {a.client_view.fields.length > 0 && (
          <ul className="list-disc pl-5 text-muted-foreground">{a.client_view.fields.map((f, i) => <li key={i}>{f}</li>)}</ul>
        )}
      </div>
    );
  }
  return <p className="text-sm text-muted-foreground">Approving marks the briefing as reviewed. Rejecting discards it.</p>;
}

function Row({ a, onDone }: { a: Item; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function decide(what: "approve" | "reject") {
    setBusy(true); setError(null);
    try { await api(`/pending-actions/${a.id}/${what}`, { method: "POST", headers: { "Idempotency-Key": a.idempotency_key } }); onDone(); }
    catch (e) { setError(e); } finally { setBusy(false); }
  }
  const reaches = a.client_view.kind === "exercise";
  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
        <div>
          <CardTitle>{TITLES[a.type] ?? a.type}</CardTitle>
          <p className="flex items-center gap-1.5 text-sm text-muted-foreground"><Avatar name={a.client_name} size={20} /><span>For {a.client_name ?? `client #${String(a.payload.client_id ?? "?")}`}</span></p>
        </div>
        <div className="flex gap-2"><AiBadge /><Badge className={a.status === "pending" ? "border-amber-400 text-amber-800" : "text-muted-foreground"}>{a.status}</Badge></div>
      </CardHeader>
      <CardContent className="space-y-3">
        <Detail a={a} />
        {a.diff && <WhatChanges diff={a.diff} />}
        <div className={reaches ? "rounded-md border-2 border-primary bg-primary/5 p-3" : "rounded-md border border-dashed bg-muted p-3"}>
          <p className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide"><Eye className="h-4 w-4" /> What reaches the client</p>
          <p className="text-sm">{a.client_view.note}</p>
          {reaches && <p className="mt-1 text-sm font-medium">“{a.client_view.title}”</p>}
        </div>
        {error != null && <ErrorMsg error={error} />}
        {a.status === "pending" ? (
          <div className="flex gap-2">
            <Button disabled={busy} onClick={() => void decide("approve")}><Check className="mr-1 h-4 w-4" />Approve</Button>
            <Button variant="outline" disabled={busy} onClick={() => void decide("reject")}><X className="mr-1 h-4 w-4" />Reject</Button>
          </div>
        ) : <p className="text-xs text-muted-foreground">Decided{a.decided_at ? ` ${new Date(a.decided_at).toLocaleString()}` : ""}.</p>}
      </CardContent>
    </Card>
  );
}

function Body() {
  const { data, error, loading, reload } = useFetch<Schemas["TherapistActionsOut"]>("/therapists/me/pending-actions");
  if (loading && !data) return <Loading />;
  if (error != null || !data) return <ErrorMsg error={error} />;
  const pending = data.items.filter((i) => i.status === "pending");
  const done = data.items.filter((i) => i.status !== "pending");
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Approval inbox</h1>
        <p className="text-sm text-muted-foreground">The AI only proposes. Nothing happens until you approve it here.</p>
      </div>
      {pending.length === 0 ? <Empty>Nothing waiting for approval.</Empty> : <div className="space-y-4">{pending.map((a) => <Row key={a.id} a={a} onDone={reload} />)}</div>}
      {done.length > 0 && (
        <details className="space-y-3">
          <summary className="cursor-pointer text-sm font-medium">Decided ({done.length})</summary>
          <div className="mt-3 space-y-3">{done.map((a) => <Row key={a.id} a={a} onDone={reload} />)}</div>
        </details>
      )}
    </div>
  );
}

export default function Inbox() { return <Shell><Body /></Shell>; }
