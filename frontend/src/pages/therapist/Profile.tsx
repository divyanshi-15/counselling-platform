import { useRef, useState } from "react";
import { CheckCircle2, Circle, FileText, Trash2 } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { useFetch } from "@/lib/useFetch";
import { Shell, fmt, type Schemas } from "./common";

type Verification = Schemas["VerificationOut"];
type ProfileData = Schemas["TherapistProfileOut"];

const STATUS: Record<string, { label: string; tone: string; text: string }> = {
  draft: { label: "Draft", tone: "border-slate-300 bg-slate-50 text-slate-800", text: "Complete your credentials and submit them for verification. Your profile is not listed publicly until it is verified." },
  submitted: { label: "Submitted", tone: "border-sky-300 bg-sky-50 text-sky-900", text: "Your credentials are with our reviewer. Documents and credentials are locked until a decision is made." },
  changes_requested: { label: "Changes requested", tone: "border-amber-400 bg-amber-50 text-amber-900", text: "Please address the reviewer's note, then submit again." },
  verified: { label: "Verified", tone: "border-emerald-400 bg-emerald-50 text-emerald-900", text: "Your profile is verified. Editing a licence sends it back for review and removes it from public listings until approved." },
  rejected: { label: "Not verified", tone: "border-red-400 bg-red-50 text-red-900", text: "We could not verify these credentials. Contact the platform team if you think this is a mistake." },
};
const DOC_TYPES = [["degree_certificate", "Degree certificate"], ["registration_certificate", "Registration certificate"], ["identity_proof", "Identity proof"], ["other", "Other"]] as const;
const docLabel = (t: string) => DOC_TYPES.find(([v]) => v === t)?.[1] ?? t;
const MAX_MB = 5;

function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function run(fn: () => Promise<unknown>, after?: () => void): Promise<boolean> {
    setBusy(true); setError(null);
    try { await fn(); after?.(); return true; } catch (e) { setError(e); return false; } finally { setBusy(false); }
  }
  return { busy, error, run };
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader><CardTitle className="text-lg">{title}</CardTitle>{hint && <p className="text-sm text-muted-foreground">{hint}</p>}</CardHeader>
      <CardContent className="space-y-3">{children}</CardContent>
    </Card>
  );
}

function StatusBanner({ v }: { v: Verification }) {
  const s = STATUS[v.status] ?? STATUS.draft;
  return (
    <div role="status" className={cn("space-y-1 rounded-md border p-4 text-sm", s.tone)}>
      <p className="flex flex-wrap items-center gap-2 font-semibold">Verification status <Badge className="border-current bg-white/60">{s.label}</Badge></p>
      <p>{s.text}</p>
      {v.reviewer_note && (
        <blockquote className="mt-2 rounded border border-current/30 bg-white/70 p-2 text-foreground">
          <span className="block text-xs font-medium uppercase tracking-wide text-muted-foreground">Reviewer note{v.reviewed_at ? ` · ${fmt(v.reviewed_at)}` : ""}</span>
          {v.reviewer_note}
        </blockquote>
      )}
      {v.submitted_at && <p className="text-xs opacity-80">Submitted {fmt(v.submitted_at)}</p>}
    </div>
  );
}

function ProfileForm({ profile, onSaved }: { profile: ProfileData; onSaved: () => void }) {
  const { busy, error, run } = useAction();
  const [saved, setSaved] = useState(false);
  const [bio, setBio] = useState(profile.bio ?? "");
  const [langs, setLangs] = useState<string[]>(profile.languages ?? []);
  const [spec, setSpec] = useState((profile.specialisations ?? []).join(", "));
  const [fee, setFee] = useState(String(profile.fee ?? ""));
  const [years, setYears] = useState(String(profile.years_experience ?? 0));
  const toggle = (l: string) => setLangs((cur) => (cur.includes(l) ? cur.filter((x) => x !== l) : [...cur, l]));
  return (
    <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); setSaved(false);
      void run(() => api("/therapists/me/profile", { method: "PATCH", json: {
        bio, languages: langs, fee: Number(fee), years_experience: Number(years),
        specialisations: spec.split(",").map((s) => s.trim()).filter(Boolean),
      } }), () => { setSaved(true); onSaved(); }); }}>
      <div className="space-y-1">
        <Label htmlFor="bio">About you</Label>
        <Textarea id="bio" rows={4} maxLength={2000} value={bio} onChange={(e) => setBio(e.target.value)} />
      </div>
      <fieldset className="space-y-1">
        <legend className="text-sm font-medium">Languages</legend>
        <div className="flex gap-4 text-sm">
          {[["en", "English"], ["hi", "Hindi"]].map(([v, l]) => (
            <label key={v} className="flex items-center gap-2"><input type="checkbox" checked={langs.includes(v)} onChange={() => toggle(v)} /> {l}</label>
          ))}
        </div>
      </fieldset>
      <div className="space-y-1">
        <Label htmlFor="spec">Specialisations (comma separated)</Label>
        <Input id="spec" value={spec} onChange={(e) => setSpec(e.target.value)} placeholder="anxiety, sleep, work stress" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1"><Label htmlFor="fee">Fee per session (INR)</Label>
          <Input id="fee" type="number" min={1} required value={fee} onChange={(e) => setFee(e.target.value)} /></div>
        <div className="space-y-1"><Label htmlFor="years">Years of experience</Label>
          <Input id="years" type="number" min={0} max={60} required value={years} onChange={(e) => setYears(e.target.value)} /></div>
      </div>
      {error != null && <ErrorMsg error={error} />}
      <div className="flex items-center gap-3">
        <Button disabled={busy || langs.length === 0}>{busy ? "Saving…" : "Save profile"}</Button>
        {langs.length === 0 && <span className="text-sm text-muted-foreground">Choose at least one language.</span>}
        {saved && <span role="status" className="text-sm text-emerald-700">Saved</span>}
      </div>
    </form>
  );
}

function ListRow({ title, sub, onDelete, disabled, label }: { title: string; sub: string; onDelete?: () => void; disabled: boolean; label: string }) {
  return (
    <li className="flex items-start justify-between gap-2 rounded-md border p-3 text-sm">
      <div><p className="font-medium">{title}</p><p className="text-muted-foreground">{sub}</p></div>
      {onDelete && <Button variant="outline" disabled={disabled} aria-label={label} onClick={onDelete}><Trash2 className="h-4 w-4" /></Button>}
    </li>
  );
}

function EducationSection({ v, locked, reload }: { v: Verification; locked: boolean; reload: () => void }) {
  const { busy, error, run } = useAction();
  const [f, setF] = useState({ degree: "", institution: "", year: "" });
  return (
    <Section title="Education" hint="Your qualifying degrees.">
      {v.education.length === 0 ? <Empty>No education added yet.</Empty> : (
        <ul className="space-y-2">{v.education.map((e) => (
          <ListRow key={e.id} title={e.degree} sub={`${e.institution} · ${e.year}`} disabled={busy} label={`Remove ${e.degree}`}
            onDelete={locked ? undefined : () => void run(() => api(`/therapists/me/education/${e.id}`, { method: "DELETE" }), reload)} />
        ))}</ul>
      )}
      {locked ? <p className="text-sm text-muted-foreground">Education is locked while your profile is under review or closed.</p> : (
        <form className="grid gap-2 sm:grid-cols-4" onSubmit={(e) => { e.preventDefault();
          void run(() => api("/therapists/me/education", { method: "POST", json: { ...f, year: Number(f.year) } }), () => { setF({ degree: "", institution: "", year: "" }); reload(); }); }}>
          <div className="space-y-1"><Label htmlFor="edu-degree">Degree</Label><Input id="edu-degree" required maxLength={150} value={f.degree} onChange={(e) => setF({ ...f, degree: e.target.value })} /></div>
          <div className="space-y-1"><Label htmlFor="edu-inst">Institution</Label><Input id="edu-inst" required maxLength={200} value={f.institution} onChange={(e) => setF({ ...f, institution: e.target.value })} /></div>
          <div className="space-y-1"><Label htmlFor="edu-year">Year</Label><Input id="edu-year" type="number" required min={1950} max={new Date().getFullYear()} value={f.year} onChange={(e) => setF({ ...f, year: e.target.value })} /></div>
          <div className="flex items-end"><Button disabled={busy}>Add education</Button></div>
        </form>
      )}
      {error != null && <ErrorMsg error={error} />}
    </Section>
  );
}

function LicenseSection({ v, locked, reload }: { v: Verification; locked: boolean; reload: () => void }) {
  const { busy, error, run } = useAction();
  const blank = { license_type: "", registration_body: "", registration_number: "", issue_year: "", valid_until: "" };
  const [f, setF] = useState(blank);
  const set = (k: keyof typeof blank) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });
  return (
    <Section title="Licences and registration" hint="Registration numbers are visible only to you and the verification reviewer, never on your public profile.">
      {v.licenses.length === 0 ? <Empty>No licence added yet.</Empty> : (
        <ul className="space-y-2">{v.licenses.map((l) => (
          <ListRow key={l.id} title={`${l.license_type} · ${l.registration_number}`} disabled={busy} label={`Remove ${l.license_type} ${l.registration_number}`}
            sub={`${l.registration_body} · issued ${l.issue_year}${l.valid_until ? ` · valid until ${l.valid_until}` : ""}`}
            onDelete={locked ? undefined : () => void run(() => api(`/therapists/me/licenses/${l.id}`, { method: "DELETE" }), reload)} />
        ))}</ul>
      )}
      {locked ? <p className="text-sm text-muted-foreground">Licences are locked while your profile is under review or closed.</p> : (
        <form className="grid gap-2 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault();
          void run(() => api("/therapists/me/licenses", { method: "POST", json: {
            license_type: f.license_type, registration_body: f.registration_body, registration_number: f.registration_number,
            issue_year: Number(f.issue_year), valid_until: f.valid_until || null } }), () => { setF(blank); reload(); }); }}>
          <div className="space-y-1"><Label htmlFor="lic-type">Licence type</Label><Input id="lic-type" required maxLength={100} value={f.license_type} onChange={set("license_type")} /></div>
          <div className="space-y-1"><Label htmlFor="lic-body">Registration body</Label><Input id="lic-body" required maxLength={150} value={f.registration_body} onChange={set("registration_body")} /></div>
          <div className="space-y-1"><Label htmlFor="lic-num">Registration number</Label><Input id="lic-num" required maxLength={60} value={f.registration_number} onChange={set("registration_number")} /></div>
          <div className="space-y-1"><Label htmlFor="lic-year">Issue year</Label><Input id="lic-year" type="number" required min={1950} max={new Date().getFullYear()} value={f.issue_year} onChange={set("issue_year")} /></div>
          <div className="space-y-1"><Label htmlFor="lic-valid">Valid until (optional)</Label><Input id="lic-valid" type="date" value={f.valid_until} onChange={set("valid_until")} /></div>
          <div className="flex items-end"><Button disabled={busy}>Add licence</Button></div>
        </form>
      )}
      {v.status === "verified" && !locked && <p className="text-sm text-amber-800">Adding or removing a licence sends your profile back for review.</p>}
      {error != null && <ErrorMsg error={error} />}
    </Section>
  );
}

function DocumentSection({ v, reload }: { v: Verification; reload: () => void }) {
  const { busy, error, run } = useAction();
  const [type, setType] = useState<string>(DOC_TYPES[0][0]);
  const [clientError, setClientError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const editable = v.can_edit_documents;

  function upload(e: React.FormEvent) {
    e.preventDefault(); setClientError(null);
    const file = input.current?.files?.[0];
    if (!file) return setClientError("Choose a file to upload.");
    if (file.size > MAX_MB * 1024 * 1024) return setClientError(`That file is larger than ${MAX_MB} MB.`);
    const body = new FormData();
    body.append("doc_type", type); body.append("file", file);
    void run(() => api("/therapists/me/documents", { method: "POST", body }), () => { if (input.current) input.current.value = ""; reload(); });
  }
  return (
    <Section title="Documents" hint={`PDF, JPG or PNG, up to ${MAX_MB} MB each. Stored privately; only you and the verification reviewer can open them.`}>
      {v.documents.length === 0 ? <Empty>No documents uploaded yet.</Empty> : (
        <ul className="space-y-2">{v.documents.map((d) => (
          <li key={d.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
            <span className="flex min-w-0 items-center gap-2">
              <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="min-w-0"><a className="block truncate font-medium text-primary underline" href={`/api/verification-documents/${d.id}/download`}>{d.filename}</a>
                <span className="text-muted-foreground">{docLabel(d.doc_type)} · {(d.size / 1024).toFixed(0)} KB · {fmt(d.uploaded_at)}</span></span>
            </span>
            {editable && <Button variant="outline" disabled={busy} aria-label={`Delete ${d.filename}`} onClick={() => void run(() => api(`/therapists/me/documents/${d.id}`, { method: "DELETE" }), reload)}><Trash2 className="h-4 w-4" /></Button>}
          </li>
        ))}</ul>
      )}
      {editable ? (
        <form className="flex flex-wrap items-end gap-2" onSubmit={upload}>
          <div className="space-y-1"><Label htmlFor="doc-type">Document type</Label>
            <Select id="doc-type" value={type} onChange={(e) => setType(e.target.value)}>{DOC_TYPES.map(([val, l]) => <option key={val} value={val}>{l}</option>)}</Select></div>
          <div className="space-y-1"><Label htmlFor="doc-file">File</Label><Input id="doc-file" ref={input} type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" /></div>
          <Button disabled={busy}>{busy ? "Uploading…" : "Upload"}</Button>
        </form>
      ) : <p className="text-sm text-muted-foreground">Documents can only be changed while your profile is a draft or changes are requested.</p>}
      {clientError && <p role="alert" className="text-sm text-destructive">{clientError}</p>}
      {error != null && <ErrorMsg error={error} />}
    </Section>
  );
}

const CHECKS: [string, string][] = [["education", "At least one education entry"], ["license", "At least one licence"], ["document", "At least one document"]];

function SubmitSection({ v, reload }: { v: Verification; reload: () => void }) {
  const { busy, error, run } = useAction();
  const canSubmit = v.status === "draft" || v.status === "changes_requested";
  return (
    <Section title="Submit for verification">
      <ul className="space-y-1 text-sm" aria-label="Submission checklist">
        {CHECKS.map(([key, label]) => {
          const done = !v.missing.includes(key);
          return <li key={key} className="flex items-center gap-2">{done ? <CheckCircle2 className="h-4 w-4 text-emerald-600" /> : <Circle className="h-4 w-4 text-muted-foreground" />}
            <span className={done ? "" : "text-muted-foreground"}>{label}</span></li>;
        })}
      </ul>
      {error != null && <ErrorMsg error={error} />}
      <Button disabled={!canSubmit || v.missing.length > 0 || busy} onClick={() => void run(() => api("/therapists/me/verification/submit", { method: "POST" }), reload)}>
        {busy ? "Submitting…" : v.status === "changes_requested" ? "Resubmit for verification" : "Submit for verification"}
      </Button>
      {!canSubmit && <p className="text-sm text-muted-foreground">{v.status === "submitted" ? "Already submitted." : v.status === "verified" ? "You are verified." : "This profile can no longer be submitted."}</p>}
    </Section>
  );
}

function Body() {
  const { user } = useAuth();
  const verification = useFetch<Verification>("/therapists/me/verification");
  const profile = useFetch<ProfileData>("/therapists/me/profile");
  const reload = () => { verification.reload(); profile.reload(); };
  const v = verification.data, p = profile.data;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Avatar name={user?.name} size={48} />
        <div><h1 className="text-2xl font-semibold">Profile and verification</h1>
          <p className="text-sm text-muted-foreground">{user?.name}</p></div>
      </div>
      {(verification.loading && !v) || (profile.loading && !p) ? <Loading /> :
        verification.error != null || profile.error != null || !v || !p ? <ErrorMsg error={verification.error ?? profile.error} /> : (
          <>
            <StatusBanner v={v} />
            <Section title="Profile" hint="Shown on your public profile once you are verified."><ProfileForm key={JSON.stringify([p.bio, p.fee])} profile={p} onSaved={reload} /></Section>
            <EducationSection v={v} locked={v.status === "submitted" || v.status === "rejected"} reload={reload} />
            <LicenseSection v={v} locked={v.status === "submitted" || v.status === "rejected"} reload={reload} />
            <DocumentSection v={v} reload={reload} />
            <SubmitSection v={v} reload={reload} />
          </>
        )}
    </div>
  );
}

export default function Profile() { return <Shell><Body /></Shell>; }
