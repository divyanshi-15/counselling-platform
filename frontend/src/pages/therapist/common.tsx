import { useState } from "react";
import { Navigate, NavLink, useLocation } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorMsg, Loading } from "@/components/states";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { useFetch } from "@/lib/useFetch";
import type { Schemas } from "../client/common";

export { fmt } from "../client/common";
export type { Schemas };

export function RequireTherapist({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "therapist") return <Navigate to="/" replace />;
  return <>{children}</>;
}

const tabs = [["/therapist", "Today", true], ["/therapist/inbox", "Approval inbox", false],
  ["/therapist/bookings", "Bookings", false], ["/therapist/availability", "Availability", false], ["/therapist/profile", "Profile and verification", false], ["/therapist/activity", "Agent activity", false]] as const;

function PendingNotice() {
  const { pathname } = useLocation();
  const { data } = useFetch<Schemas["TherapistProfileOut"]>("/therapists/me/profile");
  if (!data || data.verified || pathname === "/therapist/profile") return null;
  return (
    <p role="status" className="rounded-md border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">
      <span className="font-medium">Verification pending.</span> You are not listed publicly until you are verified and linked to a practice.{" "}
      <NavLink to="/therapist/profile" className="underline">Open profile and verification</NavLink>
    </p>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <RequireTherapist>
      <div className="space-y-5">
        <nav className="flex gap-1 overflow-x-auto border-b text-sm" aria-label="Therapist">
          {tabs.map(([to, label, end]) => (
            <NavLink key={to} to={to} end={end}
              className={({ isActive }) => cn("whitespace-nowrap border-b-2 px-3 py-2", isActive ? "border-primary font-medium" : "border-transparent text-muted-foreground hover:text-foreground")}>
              {label}
            </NavLink>
          ))}
        </nav>
        <PendingNotice />
        {children}
      </div>
    </RequireTherapist>
  );
}

export const InferredBadge = () => (
  <Badge className="border-amber-400 bg-amber-50 text-amber-800" title="Written by the AI from the notes; not verified by a source">INFERRED</Badge>
);
export const SupportedBadge = () => (
  <Badge className="border-emerald-400 bg-emerald-50 text-emerald-800" title="Backed by a cited knowledge entry or note quote">SUPPORTED</Badge>
);
export const AiBadge = () => <Badge className="border-primary/40 text-primary">AI draft</Badge>;

/** Red, pinned risk alerts. The flagged text is only ever shown here, to the assigned therapist. */
export function RiskAlerts({ alerts, names, children }: { alerts: Schemas["AlertItem"][]; names: Record<number, string>; children?: (a: Schemas["AlertItem"]) => React.ReactNode }) {
  const risks = alerts.filter((a) => a.type === "risk" && !a.acknowledged);
  if (!risks.length) return null;
  return (
    <section aria-label="Risk alerts" className="sticky top-0 z-10 space-y-2 rounded-md border-2 border-red-600 bg-red-50 p-3 shadow">
      <h2 className="flex items-center gap-2 font-semibold text-red-800"><AlertTriangle className="h-5 w-5" /> {risks.length} risk alert{risks.length > 1 ? "s" : ""} — review first</h2>
      {risks.map((a) => (
        <div key={a.id} className="rounded border border-red-300 bg-white p-3 text-sm">
          <p className="font-medium text-red-800">
            {names[a.client_id] ?? `Client #${a.client_id}`} · {String(a.payload.source ?? "").replace(/_/g, " ")} · matched “{String(a.payload.match ?? "")}”
          </p>
          {typeof a.payload.text === "string" && (
            <blockquote className="mt-1 border-l-4 border-red-400 pl-3 italic text-foreground">{a.payload.text}</blockquote>
          )}
          <p className="mt-1 text-xs text-muted-foreground">Visible to you only · {new Date(a.created_at).toLocaleString()}</p>
          {children?.(a)}
        </div>
      ))}
    </section>
  );
}

export function AckButton({ id, onDone }: { id: number; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function ack() {
    setBusy(true); setError(null);
    try { await api(`/alerts/${id}/acknowledge`, { method: "POST" }); onDone(); }
    catch (e) { setError(e); } finally { setBusy(false); }
  }
  return (
    <div className="mt-2">
      <Button variant="outline" disabled={busy} onClick={() => void ack()}>{busy ? "Acknowledging…" : "Acknowledge"}</Button>
      {error != null && <ErrorMsg error={error} />}
    </div>
  );
}
