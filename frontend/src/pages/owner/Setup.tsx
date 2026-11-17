import { useRef, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Circle, FileText, Mail, Sparkles, Trash2, Upload } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { RichEditor, RichText } from "@/components/RichText";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { useFetch } from "@/lib/useFetch";
import { fmt, type Schemas } from "../client/common";

type Setup = Schemas["SetupOut"];
type Details = Schemas["DetailsOut"];

const STEPS = ["Details", "Documents", "Team", "Page", "Submit"] as const;
type Step = (typeof STEPS)[number];
const MAX_MB = 5;

const STATUS: Record<string, { label: string; tone: string; text: string }> = {
  draft: { label: "Draft", tone: "border-slate-300 bg-slate-50 text-slate-800", text: "Complete the steps below and submit your practice for verification. It is not listed publicly until it is verified and published." },
  submitted: { label: "Submitted", tone: "border-sky-300 bg-sky-50 text-sky-900", text: "Your practice is with our reviewer. Details and documents are locked until a decision is made." },
  changes_requested: { label: "Changes requested", tone: "border-amber-400 bg-amber-50 text-amber-900", text: "Please address the reviewer's note, then submit again." },
  verified: { label: "Verified", tone: "border-emerald-400 bg-emerald-50 text-emerald-900", text: "Your practice is verified. You can now publish your page." },
  rejected: { label: "Not verified", tone: "border-red-400 bg-red-50 text-red-900", text: "We could not verify this practice. Contact the platform team if you think this is a mistake." },
};

function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function run<T>(fn: () => Promise<T>, after?: (r: T) => void): Promise<boolean> {
    setBusy(true); setError(null);
    try { const r = await fn(); after?.(r); return true; } catch (e) { setError(e); return false; } finally { setBusy(false); }
  }
  return { busy, error, run, clear: () => setError(null) };
}

function Panel({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader><CardTitle className="text-lg">{title}</CardTitle>{hint && <p className="text-sm text-muted-foreground">{hint}</p>}</CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  );
}

function StatusBanner({ s }: { s: Setup }) {
  const m = STATUS[s.verification_status] ?? STATUS.draft;
  return (
    <div role="status" className={cn("space-y-1 rounded-md border p-4 text-sm", m.tone)}>
      <p className="flex flex-wrap items-center gap-2 font-semibold">Verification status <Badge className="border-current bg-white/60">{m.label}</Badge>
        {s.status === "published" && <Badge className="border-current bg-white/60">Page published</Badge>}</p>
      <p>{m.text}</p>
      {s.reviewer_note && (
        <blockquote className="mt-2 rounded border border-current/30 bg-white/70 p-2 text-foreground">
          <span className="block text-xs font-medium uppercase tracking-wide text-muted-foreground">Reviewer note{s.reviewed_at ? ` · ${fmt(s.reviewed_at)}` : ""}</span>
          {s.reviewer_note}
        </blockquote>
      )}
      {s.submitted_at && <p className="text-xs opacity-80">Submitted {fmt(s.submitted_at)}</p>}
    </div>
  );
}

const LOCK = "These fields are locked while the practice is under review or closed.";
const list = (v: string) => v.split(",").map((x) => x.trim()).filter(Boolean);
const toggle = (cur: string[], v: string) => (cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v]);

// ---------- 1. details ----------

function DetailsStep({ s, reload }: { s: Setup; reload: () => void }) {
  const d = s.details;
  const { busy, error, run } = useAction();
  const [saved, setSaved] = useState(false);
  const [f, setF] = useState({
    name: d.name, city: d.city ?? "", address: d.address ?? "", approach: d.approach ?? "", specialisations: (d.specialisations ?? []).join(", "),
    hours: d.hours ?? "", fee_min: d.fee_min?.toString() ?? "", fee_max: d.fee_max?.toString() ?? "", years: d.years_operating?.toString() ?? "",
  });
  const [langs, setLangs] = useState<string[]>(d.languages ?? []);
  const [formats, setFormats] = useState<string[]>(d.session_formats ?? []);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => { setSaved(false); setF({ ...f, [k]: e.target.value }); };
  const locked = !s.can_edit_details;
  return (
    <Panel title="Practice details" hint="These details feed your verification and the page draft.">
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); setSaved(false);
        void run(() => api(`/owner/practices/${s.id}/details`, { method: "PUT", json: {
          name: f.name, city: f.city, address: f.address, approach: f.approach, hours: f.hours,
          specialisations: list(f.specialisations), languages: langs, session_formats: formats,
          ...(f.fee_min ? { fee_min: Number(f.fee_min) } : {}), ...(f.fee_max ? { fee_max: Number(f.fee_max) } : {}),
          ...(f.years !== "" ? { years_operating: Number(f.years) } : {}),
        } }), () => { setSaved(true); reload(); }); }}>
        <fieldset disabled={locked} className="contents">
          <div className="space-y-1"><Label htmlFor="d-name">Practice name</Label><Input id="d-name" required maxLength={255} value={f.name} onChange={set("name")} /></div>
          <div className="space-y-1"><Label htmlFor="d-city">City</Label><Input id="d-city" required maxLength={120} value={f.city} onChange={set("city")} /></div>
          <div className="space-y-1 sm:col-span-2"><Label htmlFor="d-address">Address</Label><Input id="d-address" required maxLength={400} value={f.address} onChange={set("address")} /></div>
          <div className="space-y-1 sm:col-span-2"><Label htmlFor="d-approach">Approach</Label>
            <Textarea id="d-approach" required rows={3} maxLength={600} value={f.approach} onChange={set("approach")} placeholder="For example: CBT-informed, with one small skill to practise each week" /></div>
          <div className="space-y-1 sm:col-span-2"><Label htmlFor="d-spec">Specialisations (comma separated)</Label><Input id="d-spec" required value={f.specialisations} onChange={set("specialisations")} placeholder="stress, sleep, relationships" /></div>
          <fieldset className="space-y-1"><legend className="text-sm font-medium">Languages</legend>
            <div className="flex gap-4 text-sm">{[["en", "English"], ["hi", "Hindi"]].map(([v, l]) => (
              <label key={v} className="flex items-center gap-2"><input type="checkbox" checked={langs.includes(v)} onChange={() => { setSaved(false); setLangs(toggle(langs, v)); }} /> {l}</label>))}</div></fieldset>
          <fieldset className="space-y-1"><legend className="text-sm font-medium">Session formats</legend>
            <div className="flex gap-4 text-sm">{[["online", "Online"], ["in_person", "In person"]].map(([v, l]) => (
              <label key={v} className="flex items-center gap-2"><input type="checkbox" checked={formats.includes(v)} onChange={() => { setSaved(false); setFormats(toggle(formats, v)); }} /> {l}</label>))}</div></fieldset>
          <div className="space-y-1"><Label htmlFor="d-fmin">Fee from (INR)</Label><Input id="d-fmin" type="number" min={1} required value={f.fee_min} onChange={set("fee_min")} /></div>
          <div className="space-y-1"><Label htmlFor="d-fmax">Fee up to (INR)</Label><Input id="d-fmax" type="number" min={1} required value={f.fee_max} onChange={set("fee_max")} /></div>
          <div className="space-y-1"><Label htmlFor="d-hours">Hours</Label><Input id="d-hours" required maxLength={300} value={f.hours} onChange={set("hours")} placeholder="Mon-Fri, 10:00-17:00 IST" /></div>
          <div className="space-y-1"><Label htmlFor="d-years">Years operating</Label><Input id="d-years" type="number" min={0} max={100} required value={f.years} onChange={set("years")} /></div>
        </fieldset>
        <div className="space-y-2 sm:col-span-2">
          {locked && <p className="text-sm text-muted-foreground">{LOCK}</p>}
          {error != null && <ErrorMsg error={error} />}
          <div className="flex items-center gap-3">
            <Button disabled={busy || locked || langs.length === 0 || formats.length === 0}>{busy ? "Saving…" : "Save details"}</Button>
            {(langs.length === 0 || formats.length === 0) && !locked && <span className="text-sm text-muted-foreground">Choose at least one language and one session format.</span>}
            {saved && <span role="status" className="text-sm text-emerald-700">Saved</span>}
          </div>
        </div>
      </form>
    </Panel>
  );
}

// ---------- 2. documents ----------

function DocumentsStep({ s, reload }: { s: Setup; reload: () => void }) {
  const { busy, error, run, clear } = useAction();
  const [target, setTarget] = useState<string>("");
  const input = useRef<HTMLInputElement>(null);
  const label = (t: string) => s.required_documents.find((r) => r.doc_type === t)?.label ?? t;
  function pick(docType: string) { clear(); setTarget(docType); input.current?.click(); }
  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !target) return;
    if (file.size > MAX_MB * 1024 * 1024) { void run(() => Promise.reject(new Error(`Files must be ${MAX_MB} MB or smaller.`))); return; }
    const form = new FormData();
    form.append("doc_type", target);
    form.append("file", file);
    void run(() => api(`/owner/practices/${s.id}/documents`, { method: "POST", body: form }), reload);
  }
  return (
    <Panel title="Documents" hint={`PDF, JPG or PNG, up to ${MAX_MB} MB each, at most 10 files. Upload at least one. Only you and our reviewer can see them.`}>
      <input ref={input} type="file" hidden accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" onChange={onFile} aria-label="Choose a document" />
      <ul className="space-y-2">
        {s.required_documents.map((r) => (
          <li key={r.doc_type} className="flex flex-wrap items-center gap-2 rounded-md border p-3 text-sm">
            {r.uploaded ? <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden /> : <Circle className="h-4 w-4 text-muted-foreground" aria-hidden />}
            <span className="font-medium">{r.label}</span>
            <Badge className={r.uploaded ? "border-emerald-400 text-emerald-800" : "text-muted-foreground"}>{r.uploaded ? "Uploaded" : "Not uploaded"}</Badge>
            <Button className="ml-auto" variant="outline" disabled={busy || !s.can_edit_documents} onClick={() => pick(r.doc_type)}><Upload className="h-4 w-4" />{r.uploaded ? "Add another" : "Upload"}</Button>
          </li>
        ))}
      </ul>
      {error != null && <ErrorMsg error={error} />}
      {s.documents.length === 0 ? <Empty>No documents uploaded yet.</Empty> : (
        <ul className="space-y-2" aria-label="Uploaded documents">
          {s.documents.map((d) => (
            <li key={d.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <div className="min-w-0"><p className="flex items-center gap-2 font-medium"><FileText className="h-4 w-4 shrink-0" aria-hidden /><span className="truncate">{d.filename}</span></p>
                <p className="text-muted-foreground">{label(d.doc_type)} · {Math.max(1, Math.round(d.size / 1024))} KB · {fmt(d.uploaded_at)}</p></div>
              <div className="flex shrink-0 gap-2">
                <Button variant="outline" asChild><a href={`/api/verification-documents/${d.id}/download`} target="_blank" rel="noreferrer">Open</a></Button>
                {s.can_edit_documents && <Button variant="outline" disabled={busy} aria-label={`Remove ${d.filename}`}
                  onClick={() => void run(() => api(`/owner/practices/${s.id}/documents/${d.id}`, { method: "DELETE" }), reload)}><Trash2 className="h-4 w-4" /></Button>}
              </div>
            </li>
          ))}
        </ul>
      )}
      {!s.can_edit_documents && <p className="text-sm text-muted-foreground">Documents are locked while the practice is under review or closed.</p>}
    </Panel>
  );
}

// ---------- 3. team ----------

const EMAIL_NOTE: Record<string, string> = {
  sent: "Invitation sent.",
  already_sent: "That invitation was already sent.",
  not_configured: "Invitation created, but email is not set up here, so nothing was sent.",
  failed: "Invitation created, but the email could not be sent. Revoke it and try again.",
};

function TeamStep({ s, reload }: { s: Setup; reload: () => void }) {
  const { busy, error, run } = useAction();
  const [email, setEmail] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const key = useRef(crypto.randomUUID());  // one key per invitation attempt: a retry of the same click never sends twice
  const [confirmId, setConfirmId] = useState<number | null>(null);
  return (
    <div className="space-y-4">
      <Panel title="Invite a therapist" hint="They get a single-use link by email that expires in 7 days. They log in or sign up with this email address, then accept.">
        <form className="flex flex-wrap items-end gap-2" onSubmit={(e) => { e.preventDefault(); setNote(null);
          void run(() => api<Schemas["InviteCreateOut"]>(`/owner/practices/${s.id}/invites`, { method: "POST", json: { email }, headers: { "Idempotency-Key": key.current } }),
            (r) => { setNote(EMAIL_NOTE[r.email_status] ?? "Invitation created."); setEmail(""); key.current = crypto.randomUUID(); reload(); }); }}>
          <div className="min-w-56 flex-1 space-y-1"><Label htmlFor="inv-email">Therapist email</Label><Input id="inv-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>
          <Button disabled={busy}><Mail className="h-4 w-4" />{busy ? "Sending…" : "Send invitation"}</Button>
        </form>
        {note && <p role="status" className="text-sm text-emerald-700">{note}</p>}
        {error != null && <ErrorMsg error={error} />}
      </Panel>
      <Panel title="Pending invitations">
        {s.invites.length === 0 ? <Empty>No pending invitations.</Empty> : (
          <ul className="space-y-2">{s.invites.map((i) => (
            <li key={i.id} className="flex flex-wrap items-center gap-2 rounded-md border p-3 text-sm">
              <Avatar name={i.email} size={28} />
              <div className="min-w-0 flex-1"><p className="truncate font-medium">{i.email}</p>
                <p className="text-muted-foreground">{i.status === "expired" ? "Expired" : "Expires"} {fmt(i.expires_at)}</p></div>
              <Badge className={i.status === "expired" ? "text-muted-foreground" : "border-amber-400 text-amber-800"}>{i.status}</Badge>
              <Button variant="outline" disabled={busy} onClick={() => void run(() => api(`/owner/practices/${s.id}/invites/${i.id}/revoke`, { method: "POST" }), reload)}>Revoke</Button>
            </li>))}</ul>
        )}
      </Panel>
      <Panel title="Team" hint="Removing a therapist unlists them from this practice. Their clients and care are not affected.">
        {s.team.length === 0 ? <Empty>No therapists on this team yet.</Empty> : (
          <ul className="space-y-2">{s.team.map((m) => (
            <li key={m.id} className="flex flex-wrap items-center gap-2 rounded-md border p-3 text-sm">
              <Avatar name={m.name} size={32} />
              <div className="min-w-0 flex-1"><p className="truncate font-medium">{m.name ?? m.email}</p><p className="truncate text-muted-foreground">{m.email}</p></div>
              <Badge className={m.verified ? "border-emerald-400 text-emerald-800" : "text-muted-foreground"}>{m.verified ? "verified" : "not verified"}</Badge>
              {confirmId === m.id ? (
                <span className="flex gap-2">
                  <Button disabled={busy} onClick={() => void run(() => api(`/owner/practices/${s.id}/team/${m.id}`, { method: "DELETE" }), () => { setConfirmId(null); reload(); })}>Confirm remove</Button>
                  <Button variant="outline" onClick={() => setConfirmId(null)}>Cancel</Button>
                </span>
              ) : <Button variant="outline" onClick={() => setConfirmId(m.id)} aria-label={`Remove ${m.name ?? m.email}`}>Remove</Button>}
            </li>))}</ul>
        )}
      </Panel>
    </div>
  );
}

// ---------- 4. page ----------

const INPUT_LABELS: [keyof Details, string][] = [["name", "Name"], ["city", "City"], ["approach", "Approach"], ["specialisations", "Specialisations"],
  ["languages", "Languages"], ["session_formats", "Session formats"], ["fee_min", "Fee from (INR)"], ["fee_max", "Fee up to (INR)"], ["hours", "Hours"], ["years_operating", "Years operating"]];
const show = (v: unknown) => (Array.isArray(v) ? v.join(", ") : v == null || v === "" ? "–" : String(v));

function PreviewCard({ s, tagline, text }: { s: Setup; tagline: string; text: string }) {
  const p = s.preview;
  return (
    <div className="space-y-3 rounded-md border bg-muted/30 p-4 text-sm" aria-label="Public page preview">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Public preview (read-only)</p>
      <h3 className="text-xl font-semibold">{s.name}</h3>
      <p className="text-muted-foreground">{tagline || p.tagline || "Your tagline appears here."}</p>
      {text || p.about ? <RichText text={text || p.about} /> : <p className="text-muted-foreground">Your page text appears here.</p>}
      <p className="text-xs text-muted-foreground">{[p.location, p.languages?.join(", "), p.specialties?.join(", "), p.fee_range, p.session_type].filter(Boolean).join(" · ")}</p>
    </div>
  );
}

function PageStep({ s, reload }: { s: Setup; reload: () => void }) {
  const pg = s.page;
  const [tagline, setTagline] = useState(pg.tagline ?? "");
  const [text, setText] = useState(pg.text ?? "");
  const [confirming, setConfirming] = useState(false);
  const [saved, setSaved] = useState(false);
  const save = useAction(), gen = useAction(), pub = useAction();
  const dirty = tagline !== (pg.tagline ?? "") || text !== (pg.text ?? "");
  const inputs = (pg.inputs ?? s.details) as Record<string, unknown>;
  const editable = s.can_edit_page;
  function sync(p: Schemas["PageOut"]) { setTagline(p.tagline ?? ""); setText(p.text ?? ""); setConfirming(false); setSaved(false); reload(); }
  function generate() {
    void gen.run(() => api<Schemas["PageOut"]>(`/owner/practices/${s.id}/page/generate`, { method: "POST", json: { confirm: pg.has_draft } }), sync);
  }
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Panel title={pg.inputs ? "Details used for this draft" : "Details the draft will use"} hint="The draft is generated only from these saved details. Your address is not sent to the AI.">
          <dl className="space-y-1 text-sm">{INPUT_LABELS.map(([k, l]) => (
            <div key={k} className="grid grid-cols-[8rem_1fr] gap-2"><dt className="text-muted-foreground">{l}</dt><dd className="break-words">{show(inputs[k])}</dd></div>))}</dl>
          {pg.inputs_changed && <p role="status" className="rounded-md border border-amber-400 bg-amber-50 p-2 text-sm text-amber-900">Your details changed since this draft was written. Regenerate if you want the draft to reflect them.</p>}
        </Panel>
        <Panel title="Page text" hint="AI proposes a draft; you edit it freely and save. Nothing goes public until you publish.">
          <div className="flex flex-wrap items-center gap-2">
            {pg.has_draft && <Badge className="border-primary/40 text-primary">{pg.source === "ai" ? "AI draft" : pg.source === "edited" ? "AI draft, edited by you" : "Written by you"}</Badge>}
            {!confirming && <Button variant="outline" disabled={gen.busy || !editable} onClick={() => (pg.has_draft ? setConfirming(true) : generate())}>
              <Sparkles className="h-4 w-4" />{gen.busy ? "Drafting…" : pg.has_draft ? "Regenerate from details" : "Draft from details"}</Button>}
          </div>
          {confirming && (
            <div role="alertdialog" aria-label="Confirm regenerate" className="space-y-2 rounded-md border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">
              <p>Regenerating replaces your current text{dirty ? ", including your unsaved changes" : ""}. This cannot be undone.</p>
              <div className="flex gap-2"><Button disabled={gen.busy} onClick={generate}>{gen.busy ? "Drafting…" : "Replace with a new draft"}</Button><Button variant="outline" onClick={() => setConfirming(false)}>Keep my text</Button></div>
            </div>
          )}
          {gen.error != null && <ErrorMsg error={gen.error} />}
          {gen.error != null && <p className="text-sm text-muted-foreground">You can write the page yourself below.</p>}
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); setSaved(false);
            void save.run(() => api<Schemas["PageOut"]>(`/owner/practices/${s.id}/page`, { method: "PUT", json: { tagline, text } }), (p) => { sync(p); setSaved(true); }); }}>
            <div className="space-y-1"><Label htmlFor="p-tagline">Tagline</Label><Input id="p-tagline" required maxLength={200} disabled={!editable} value={tagline} onChange={(e) => { setSaved(false); setTagline(e.target.value); }} /></div>
            <div className="space-y-1"><Label htmlFor="p-text">About your practice</Label>
              <RichEditor id="p-text" label="About your practice" value={text} disabled={!editable} onChange={(v) => { setSaved(false); setText(v); }} /></div>
            {!editable && <p className="text-sm text-muted-foreground">The page is locked while the practice is under review or closed.</p>}
            {save.error != null && <ErrorMsg error={save.error} />}
            <div className="flex items-center gap-3">
              <Button disabled={save.busy || !editable || !dirty || !text.trim() || !tagline.trim()}>{save.busy ? "Saving…" : "Save page"}</Button>
              {dirty && <span className="text-sm text-amber-800">Unsaved changes</span>}
              {saved && !dirty && <span role="status" className="text-sm text-emerald-700">Saved</span>}
            </div>
          </form>
        </Panel>
      </div>
      <PreviewCard s={s} tagline={tagline} text={text} />
      <Panel title="Publish" hint="Publishing is your decision. It needs a verified practice and shows your saved text publicly.">
        {s.verification_status !== "verified" && <p className="text-sm text-muted-foreground">Publishing opens once an admin has verified your practice.</p>}
        {pub.error != null && <ErrorMsg error={pub.error} />}
        <Button disabled={pub.busy || !s.can_publish || dirty} onClick={() => void pub.run(() => api(`/owner/practices/${s.id}/publish`, { method: "POST" }), reload)}>
          {pub.busy ? "Publishing…" : s.status === "published" ? "Publish saved changes" : "Publish page"}</Button>
        {dirty && s.can_publish && <p className="text-sm text-muted-foreground">Save your changes first.</p>}
        {s.status === "published" && <p className="text-sm"><Link className="text-primary underline" to={`/p/${s.slug}`}>View public page</Link></p>}
      </Panel>
    </div>
  );
}

// ---------- 5. submit ----------

function SubmitStep({ s, reload }: { s: Setup; reload: () => void }) {
  const { busy, error, run } = useAction();
  const items: [string, boolean][] = [
    ["Details complete", !s.missing.some((m) => m.startsWith("Details"))],
    ["At least one document uploaded", !s.missing.some((m) => m.startsWith("Documents"))],
    ["Page text saved", !s.missing.some((m) => m.startsWith("Page"))],
  ];
  const closed = !["draft", "changes_requested"].includes(s.verification_status);
  return (
    <Panel title="Submit for verification" hint="Our reviewer checks your details and documents. You will see the decision and any note here.">
      <ul className="space-y-2" aria-label="Submission checklist">
        {items.map(([l, ok]) => (
          <li key={l} className="flex items-center gap-2 text-sm">{ok ? <CheckCircle2 className="h-4 w-4 text-emerald-600" aria-hidden /> : <Circle className="h-4 w-4 text-muted-foreground" aria-hidden />}
            <span className={ok ? "" : "text-muted-foreground"}>{l}</span><span className="sr-only">{ok ? "done" : "to do"}</span></li>))}
      </ul>
      {s.missing.length > 0 && <ul className="list-disc pl-5 text-sm text-muted-foreground">{s.missing.map((m) => <li key={m}>{m}</li>)}</ul>}
      {error != null && <ErrorMsg error={error} />}
      <Button disabled={busy || !s.can_submit} onClick={() => void run(() => api(`/owner/practices/${s.id}/submit`, { method: "POST" }), reload)}>
        {busy ? "Submitting…" : s.verification_status === "changes_requested" ? "Submit again" : "Submit for verification"}</Button>
      {closed && <p className="text-sm text-muted-foreground">{s.verification_status === "submitted" ? "Submitted. We will review it shortly." : STATUS[s.verification_status]?.text}</p>}
    </Panel>
  );
}

// ---------- shell ----------

function Stepper({ s, step, onStep }: { s: Setup; step: Step; onStep: (x: Step) => void }) {
  const done: Record<Step, boolean> = {
    Details: !s.missing.some((m) => m.startsWith("Details")), Documents: !s.missing.some((m) => m.startsWith("Documents")),
    Team: s.team.length > 0, Page: !s.missing.some((m) => m.startsWith("Page")), Submit: s.verification_status !== "draft" && s.verification_status !== "changes_requested",
  };
  return (
    <nav aria-label="Practice setup steps"><ol className="grid grid-cols-5 gap-1 sm:gap-2">
      {STEPS.map((x, i) => (
        <li key={x}><button type="button" aria-current={x === step ? "step" : undefined} onClick={() => onStep(x)}
          className={cn("flex w-full flex-col items-center gap-1 rounded-md border p-2 text-xs sm:flex-row sm:justify-center sm:gap-2 sm:text-sm", x === step ? "border-primary bg-primary/5 font-semibold text-primary" : "hover:bg-muted")}>
          <span className={cn("flex h-6 w-6 items-center justify-center rounded-full border text-xs", done[x] ? "border-emerald-500 bg-emerald-500 text-white" : "")}>{done[x] ? <CheckCircle2 className="h-4 w-4" aria-label="done" /> : i + 1}</span>
          <span>{x}</span></button></li>))}
    </ol></nav>
  );
}

function Body({ id }: { id: number }) {
  const { data, error, loading, reload } = useFetch<Setup>(`/owner/practices/${id}/setup`);
  const [step, setStep] = useState<Step>("Details");
  if (loading && !data) return <Loading />;
  if (error != null || !data) return <div className="space-y-3"><ErrorMsg error={error ?? new Error("Practice not found.")} /><Button variant="outline" asChild><Link to="/owner">Back to my practices</Link></Button></div>;
  // keyed on the server state so forms re-initialise after a save, a regenerate or a status change
  const key = `${data.page.updated_at}|${data.verification_status}|${data.name}|${data.details.city}|${data.details.hours}`;
  return (
    <div className="space-y-5">
      <div className="space-y-1">
        <Link to="/owner" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline"><ArrowLeft className="h-4 w-4" />My practices</Link>
        <h1 className="text-2xl font-semibold">Practice setup · {data.name}</h1>
      </div>
      <StatusBanner s={data} />
      <Stepper s={data} step={step} onStep={setStep} />
      <div key={`${step}-${key}`}>
        {step === "Details" && <DetailsStep s={data} reload={reload} />}
        {step === "Documents" && <DocumentsStep s={data} reload={reload} />}
        {step === "Team" && <TeamStep s={data} reload={reload} />}
        {step === "Page" && <PageStep s={data} reload={reload} />}
        {step === "Submit" && <SubmitStep s={data} reload={reload} />}
      </div>
      <div className="flex justify-between">
        <Button variant="outline" disabled={step === STEPS[0]} onClick={() => setStep(STEPS[STEPS.indexOf(step) - 1])}>Back</Button>
        <Button variant="outline" disabled={step === STEPS[STEPS.length - 1]} onClick={() => setStep(STEPS[STEPS.indexOf(step) + 1])}>Next</Button>
      </div>
    </div>
  );
}

export function NewPractice() {
  const nav = useNavigate();
  const { busy, error, run } = useAction();
  const [f, setF] = useState({ name: "", city: "" });
  return (
    <Card>
      <CardHeader><CardTitle>Set up a new practice</CardTitle></CardHeader>
      <CardContent>
        <form className="grid gap-3 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault();
          void run(() => api<Setup>("/owner/practices", { method: "POST", json: f }), (r) => nav(`/owner/setup/${r.id}`)); }}>
          <div className="space-y-1"><Label htmlFor="np-name">Practice name</Label><Input id="np-name" required maxLength={255} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></div>
          <div className="space-y-1"><Label htmlFor="np-city">City</Label><Input id="np-city" required maxLength={120} value={f.city} onChange={(e) => setF({ ...f, city: e.target.value })} /></div>
          <div className="space-y-2 sm:col-span-2">{error != null && <ErrorMsg error={error} />}<Button disabled={busy}>{busy ? "Creating…" : "Start setup"}</Button></div>
        </form>
      </CardContent>
    </Card>
  );
}

export default function PracticeSetup() {
  const { id } = useParams();
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "practice_owner") return <Navigate to="/" replace />;
  const n = Number(id);
  if (!Number.isInteger(n) || n < 1) return <p>Practice not found.</p>;
  return <Body id={n} />;
}
