import { ArrowLeft, FileText } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { Avatar } from "@/components/Avatar";
import { RichText } from "@/components/RichText";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import type { Schemas } from "../client/common";
import { fmt } from "../client/common";
import { RequireAdmin, STATUS_LABEL, type Subject } from "./Admin";

type Decision = "verified" | "changes_requested" | "rejected";
type Doc = Schemas["DocumentOut"];

const CHECKLIST: Record<Subject, string[]> = {
  therapist: ["Name matches the documents", "Registration number confirmed with the council", "Degree and institution confirmed", "Documents are legible and current"],
  practice: ["Business registration checked", "Address matches the proof provided", "Team members are accounted for", "Page text reviewed: no guarantees, diagnoses or medical claims"],
};
const ACTIONS: { decision: Decision; label: string; variant: "default" | "outline"; className?: string }[] = [
  { decision: "verified", label: "Approve", variant: "default" },
  { decision: "changes_requested", label: "Request changes", variant: "outline" },
  { decision: "rejected", label: "Reject", variant: "outline", className: "border-destructive text-destructive" },
];
const DECISION_LABEL: Record<string, string> = { verified: "Approved", changes_requested: "Changes requested", rejected: "Rejected" };
const ACTION_LABEL: Record<string, string> = {
  "therapist.verification_submit": "Submitted for review", "practice.submit": "Submitted for review",
  "verification_document.download": "Document opened",
};
const label = (s: string) => s.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="space-y-2 rounded-md border p-4"><h2 className="font-semibold">{title}</h2>{children}</section>;
}
const Row = ({ k, v }: { k: string; v?: React.ReactNode }) => (
  <div className="flex flex-col gap-0.5 sm:flex-row sm:gap-3"><dt className="w-40 shrink-0 text-muted-foreground">{k}</dt><dd className="min-w-0 break-words">{v || "—"}</dd></div>
);

function Documents({ docs }: { docs: Doc[] }) {
  if (!docs.length) return <Empty>No documents uploaded.</Empty>;
  return (
    <ul className="space-y-2">{docs.map((d) => (
      <li key={d.id} className="flex items-center gap-2 rounded-md border p-3 text-sm">
        <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
        <span className="min-w-0">
          <a className="block truncate font-medium text-primary underline" href={`/api/verification-documents/${d.id}/download`} target="_blank" rel="noreferrer">{d.filename}</a>
          <span className="text-muted-foreground">{label(d.doc_type)} · {(d.size / 1024).toFixed(0)} KB · {fmt(d.uploaded_at)}</span>
        </span>
      </li>
    ))}</ul>
  );
}

function TherapistBody({ v }: { v: Schemas["AdminVerificationOut"] }) {
  return (
    <>
      <Section title="Profile">
        <dl className="space-y-1 text-sm">
          <Row k="Practice" v={v.practice_name} /><Row k="City" v={v.city} /><Row k="Bio" v={v.bio} />
          <Row k="Approaches" v={v.approaches.join(", ")} /><Row k="Specialisations" v={v.specialisations.join(", ")} />
          <Row k="Languages" v={v.languages.join(", ")} /><Row k="Fee" v={v.fee ? `₹${v.fee}` : null} /><Row k="Experience" v={v.years_experience != null ? `${v.years_experience} years` : null} />
        </dl>
      </Section>
      <Section title="Education">
        {!v.education.length ? <Empty>None added.</Empty> : <ul className="space-y-1 text-sm">{v.education.map((e) => <li key={e.id}>{e.degree}, {e.institution} ({e.year})</li>)}</ul>}
      </Section>
      <Section title="Licences">
        {!v.licenses.length ? <Empty>None added.</Empty> : <ul className="space-y-1 text-sm">{v.licenses.map((l) => (
          <li key={l.id}>{l.license_type} · {l.registration_body} · No. {l.registration_number} · issued {l.issue_year}{l.valid_until ? ` · valid until ${l.valid_until}` : ""}</li>
        ))}</ul>}
      </Section>
      <Section title="Documents"><Documents docs={v.documents} /></Section>
    </>
  );
}

function PracticeBody({ v }: { v: Schemas["AdminPracticeVerificationOut"] }) {
  const d = v.details;
  return (
    <>
      <Section title="Details">
        <dl className="space-y-1 text-sm">
          <Row k="Owner" v={v.owner_name} /><Row k="City" v={d.city} /><Row k="Address" v={d.address} /><Row k="Approach" v={d.approach} />
          <Row k="Specialisations" v={d.specialisations.join(", ")} /><Row k="Languages" v={d.languages.join(", ")} />
          <Row k="Session formats" v={d.session_formats.map(label).join(", ")} /><Row k="Fees" v={d.fee_min && d.fee_max ? `₹${d.fee_min} – ₹${d.fee_max}` : null} />
          <Row k="Hours" v={d.hours} /><Row k="Years operating" v={d.years_operating} />
        </dl>
      </Section>
      <Section title="Documents"><Documents docs={v.documents} /></Section>
      <Section title="Team">
        {!v.team.length ? <Empty>No therapists have joined yet.</Empty> : <ul className="space-y-1 text-sm">{v.team.map((m) => (
          <li key={m.id} className="flex items-center gap-2"><Avatar name={m.name} size={24} />{m.name ?? m.email}{m.verified && <Badge>Verified</Badge>}</li>
        ))}</ul>}
      </Section>
      <Section title="Page draft">
        {!v.page.has_draft ? <Empty>No page text saved.</Empty> : (
          <div className="space-y-2">
            {v.page.tagline && <p className="font-medium">{v.page.tagline}</p>}
            <RichText text={v.page.text ?? ""} className="text-sm" />
          </div>
        )}
      </Section>
    </>
  );
}

function Decide({ subject, id, status, onDone }: { subject: Subject; id: number; status: string; onDone: () => void }) {
  const items = CHECKLIST[subject];
  const [checked, setChecked] = useState<boolean[]>(items.map(() => false));
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  if (status !== "submitted") return <p className="rounded-md border p-3 text-sm text-muted-foreground">This item is {STATUS_LABEL[status]?.toLowerCase() ?? status}; no decision is pending.</p>;
  const allChecked = checked.every(Boolean);
  const noteOk = note.trim().length > 0;
  async function decide(decision: Decision) {
    setBusy(true); setError(null);
    try {
      await api(`/admin/${subject === "therapist" ? "therapists" : "practices"}/${id}/review`, { method: "POST", json: { decision, note: note.trim() || null } });
      onDone();
    } catch (e) { setError(e); } finally { setBusy(false); }
  }
  return (
    <Section title="Decision">
      <fieldset className="space-y-1 text-sm"><legend className="sr-only">Checklist</legend>
        {items.map((t, i) => (
          <label key={t} className="flex items-start gap-2">
            <input type="checkbox" className="mt-1" checked={checked[i]} onChange={(e) => setChecked(checked.map((c, j) => (j === i ? e.target.checked : c)))} />{t}
          </label>
        ))}
      </fieldset>
      <label className="block text-sm font-medium" htmlFor="review-note">Note to the applicant <span className="font-normal text-muted-foreground">(required to request changes or reject)</span></label>
      <Textarea id="review-note" maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)} />
      {error != null && <ErrorMsg error={error} />}
      <div className="flex flex-wrap gap-2">
        {ACTIONS.map((a) => (
          <Button key={a.decision} variant={a.variant} className={a.className} disabled={busy || (a.decision === "verified" ? !allChecked : !noteOk)} onClick={() => void decide(a.decision)}>{a.label}</Button>
        ))}
      </div>
    </Section>
  );
}

function History({ subject, id, tick }: { subject: Subject; id: number; tick: number }) {
  const { data, error, loading } = useFetch<Schemas["AuditOut"]>(`/admin/${subject === "therapist" ? "therapists" : "practices"}/${id}/audit`, { t: tick });
  return (
    <Section title="Audit history">
      {loading && !data ? <Loading /> : error != null ? <ErrorMsg error={error} /> : !data?.items.length ? <Empty>No history yet.</Empty> : (
        <ul className="space-y-2 text-sm">{data.items.map((a) => (
          <li key={a.id} className="rounded-md border p-2">
            <div className="flex flex-wrap items-center justify-between gap-1">
              <span className="font-medium">{a.decision ? DECISION_LABEL[a.decision] ?? label(a.decision) : ACTION_LABEL[a.action] ?? label(a.action.split(".").pop() ?? a.action)}</span>
              <span className="text-xs text-muted-foreground">{a.actor_name ?? "Unknown"}{a.actor_role ? ` (${label(a.actor_role)})` : ""} · {fmt(a.created_at)}</span>
            </div>
            {a.note && <p className="mt-1 text-muted-foreground">{a.note}</p>}
          </li>
        ))}</ul>
      )}
    </Section>
  );
}

function Body({ subject, id }: { subject: Subject; id: number }) {
  const [tick, setTick] = useState(0);
  const base = `/admin/${subject === "therapist" ? "therapists" : "practices"}/${id}/verification`;
  const { data, error, loading, reload } = useFetch<Schemas["AdminVerificationOut"] & Schemas["AdminPracticeVerificationOut"]>(base, { t: tick });
  const status = subject === "therapist" ? data?.status : data?.verification_status;
  return (
    <div className="space-y-4">
      <Link to="/admin" className="inline-flex items-center gap-1 text-sm text-primary hover:underline"><ArrowLeft className="h-4 w-4" />Verification queue</Link>
      {loading && !data ? <Loading /> : error != null ? <ErrorMsg error={error} /> : !data ? <Empty>Not found.</Empty> : (
        <>
          <div className="flex flex-wrap items-center gap-3">
            <Avatar name={data.name} size={44} />
            <div>
              <PageHeader title={data.name} />
              <p className="text-sm text-muted-foreground">{subject === "therapist" ? "Therapist" : "Practice"} · {STATUS_LABEL[status ?? ""] ?? status}{data.submitted_at ? ` · submitted ${fmt(data.submitted_at)}` : ""}</p>
            </div>
          </div>
          {data.reviewer_note && <p className="rounded-md bg-muted p-3 text-sm"><span className="font-medium">Last note: </span>{data.reviewer_note}</p>}
          {subject === "therapist" ? <TherapistBody v={data} /> : <PracticeBody v={data} />}
          <Decide subject={subject} id={id} status={status ?? ""} onDone={() => { setTick((t) => t + 1); reload(); }} />
          <History subject={subject} id={id} tick={tick} />
        </>
      )}
    </div>
  );
}

export default function Review() {
  const { subject, id } = useParams();
  const n = Number(id);
  if ((subject !== "therapist" && subject !== "practice") || !Number.isInteger(n)) return <Navigate to="/admin" replace />;
  return <RequireAdmin><Body subject={subject} id={n} /></RequireAdmin>;
}
