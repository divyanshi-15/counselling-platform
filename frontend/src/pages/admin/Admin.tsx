import { CheckCircle2, Circle } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { Avatar } from "@/components/Avatar";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth";
import { useFetch } from "@/lib/useFetch";
import type { Schemas } from "../client/common";
import { fmt } from "../client/common";

export type Subject = "therapist" | "practice";
type Status = "submitted" | "changes_requested" | "rejected" | "verified";
export const STATUS_LABEL: Record<string, string> = { submitted: "Awaiting review", changes_requested: "Changes requested", rejected: "Rejected", verified: "Verified", draft: "Draft" };
const STATUSES: Status[] = ["submitted", "changes_requested", "rejected", "verified"];

function Completeness({ items }: { items: Schemas["CompletenessItem"][] }) {
  return (
    <ul className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
      {items.map((c) => (
        <li key={c.label} className={`flex items-center gap-1 ${c.ok ? "text-foreground" : "text-muted-foreground"}`}>
          {c.ok ? <CheckCircle2 className="h-3.5 w-3.5 text-primary" aria-label="complete" /> : <Circle className="h-3.5 w-3.5" aria-label="missing" />}
          {c.label}{c.count != null ? ` (${c.count})` : ""}
        </li>
      ))}
    </ul>
  );
}

function Queue() {
  const [subject, setSubject] = useState<Subject>("therapist");
  const [status, setStatus] = useState<Status>("submitted");
  const { data, error, loading } = useFetch<Schemas["QueueOut"]>("/admin/verification-queue", { subject, status });
  return (
    <div className="space-y-4">
      <div>
        <PageHeader title="Verification queue" />
        <p className="text-sm text-muted-foreground">Only published and verified practices, and verified therapists, appear publicly. <Link className="text-primary hover:underline" to="/admin/contact-messages">Contact messages</Link></p>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="tablist" aria-label="Subject" className="inline-flex rounded-md border p-0.5">
          {(["therapist", "practice"] as Subject[]).map((s) => (
            <button key={s} role="tab" aria-selected={subject === s} onClick={() => setSubject(s)}
              className={`rounded px-4 py-1.5 text-sm font-medium ${subject === s ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}>
              {s === "therapist" ? "Therapists" : "Practices"}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm">Status
          <select className="h-9 rounded-md border bg-background px-2" value={status} onChange={(e) => setStatus(e.target.value as Status)}>
            {STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
          </select>
        </label>
      </div>
      {loading && !data ? <Loading /> : error != null ? <ErrorMsg error={error} /> :
        !data?.items.length ? <Empty>Nothing {status === "submitted" ? "waiting for review" : `with status “${STATUS_LABEL[status].toLowerCase()}”`}.</Empty> : (
          <div className="overflow-x-auto rounded-md border">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/50 text-xs uppercase text-muted-foreground">
                <tr><th className="p-3">{subject === "therapist" ? "Therapist" : "Practice"}</th><th className="p-3">City</th><th className="p-3">Submitted</th><th className="p-3">Completeness</th></tr>
              </thead>
              <tbody>
                {data.items.map((i) => (
                  <tr key={i.id} className="border-t align-top">
                    <td className="p-3">
                      <Link className="flex items-center gap-2 font-medium text-primary hover:underline" to={`/admin/review/${subject}/${i.id}`}>
                        <Avatar name={i.name} size={28} />{i.name}
                      </Link>
                      {status !== "submitted" && <Badge className="mt-1">{STATUS_LABEL[i.verification_status] ?? i.verification_status}</Badge>}
                    </td>
                    <td className="p-3">{i.city ?? "—"}</td>
                    <td className="p-3 whitespace-nowrap">{i.submitted_at ? fmt(i.submitted_at) : "—"}</td>
                    <td className="p-3"><Completeness items={i.completeness} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
    </div>
  );
}

export function RequireAdmin({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "admin") return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function Admin() {
  return <RequireAdmin><Queue /></RequireAdmin>;
}
