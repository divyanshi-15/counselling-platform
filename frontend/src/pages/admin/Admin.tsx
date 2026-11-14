import { useState } from "react";
import { Navigate } from "react-router-dom";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useFetch } from "@/lib/useFetch";
import type { Schemas } from "../client/common";

function Toggle({ label, verified, path, onDone }: { label: string; verified: boolean; path: string; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function flip() {
    setBusy(true); setError(null);
    try { await api(path, { method: "POST", json: { verified: !verified } }); onDone(); }
    catch (e) { setError(e); } finally { setBusy(false); }
  }
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3 text-sm">
      <span>{label}</span>
      <span className="flex items-center gap-2">
        {error != null && <ErrorMsg error={error} />}
        <Button variant={verified ? "default" : "outline"} aria-pressed={verified} aria-label={`${verified ? "Unverify" : "Verify"} ${label}`} disabled={busy} onClick={() => void flip()}>
          {verified ? "Verified" : "Not verified"}
        </Button>
      </span>
    </li>
  );
}

function Body() {
  const practices = useFetch<Schemas["PracticesOut"]>("/practices");
  const therapists = useFetch<Schemas["AdminTherapistsOut"]>("/admin/therapists");
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Admin: verification</h1>
        <p className="text-sm text-muted-foreground">Only published and verified practices, and verified therapists, appear publicly.</p>
      </div>
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Practices</h2>
        {practices.loading && !practices.data ? <Loading /> : practices.error != null ? <ErrorMsg error={practices.error} /> :
          !practices.data?.items.length ? <Empty>No practices.</Empty> :
            <ul className="space-y-2">{practices.data.items.map((p) => <Toggle key={p.id} label={`${p.name} (${p.status})`} verified={p.verified} path={`/admin/practices/${p.id}/verify`} onDone={practices.reload} />)}</ul>}
      </section>
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Therapists</h2>
        {therapists.loading && !therapists.data ? <Loading /> : therapists.error != null ? <ErrorMsg error={therapists.error} /> :
          !therapists.data?.items.length ? <Empty>No therapists.</Empty> :
            <ul className="space-y-2">{therapists.data.items.map((t) => <Toggle key={t.id} label={`${t.name ?? `Therapist #${t.id}`} · ${t.practice_name}`} verified={t.verified} path={`/admin/therapists/${t.id}/verify`} onDone={therapists.reload} />)}</ul>}
      </section>
    </div>
  );
}

export default function Admin() {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "admin") return <Navigate to="/" replace />;
  return <Body />;
}
