import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input, Textarea } from "@/components/ui/input";
import { ErrorMsg, Loading } from "@/components/states";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import { CrisisBox, RequireClient, type Schemas } from "./common";

type Tpl = Schemas["ExerciseTemplateOut"];
type Res = Schemas["CheckinOut"];

function Body() {
  const { assignmentId } = useParams();
  const ex = useFetch<Tpl>(`/client/assignments/${assignmentId}/exercise`);
  const [vals, setVals] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [res, setRes] = useState<Res | null>(null);

  async function save(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    const responses = Object.fromEntries(Object.entries(vals).filter(([, v]) => v.trim() !== ""));
    try { setRes(await api<Res>(`/client/assignments/${assignmentId}/checkin`, { method: "POST", json: { responses } })); }
    catch (err) { setError(err); } finally { setBusy(false); }
  }

  if (res?.status === "crisis") return <CrisisBox message={res.message ?? ""} />; // nothing else shown
  if (res) return <div className="space-y-3"><p>Check-in saved.</p><Button asChild><Link to="/client">Back to dashboard</Link></Button></div>;
  if (ex.loading) return <Loading />;
  if (ex.error != null || !ex.data) return <ErrorMsg error={ex.error} />;
  return (
    <form onSubmit={(e) => void save(e)} className="space-y-4">
      <h1 className="text-2xl font-semibold">{ex.data.title}</h1>
      {ex.data.template.fields.map((f) => (
        <div key={f.id} className="space-y-1">
          <Label htmlFor={f.id}>{f.label}{f.required ? " *" : ""}</Label>
          {f.type === "scale"
            ? <Input id={f.id} type="number" inputMode="numeric" min={0} max={10} required={f.required ?? undefined} value={vals[f.id] ?? ""} onChange={(e) => setVals({ ...vals, [f.id]: e.target.value })} />
            : <Textarea id={f.id} required={f.required ?? undefined} maxLength={2000} value={vals[f.id] ?? ""} onChange={(e) => setVals({ ...vals, [f.id]: e.target.value })} />}
        </div>
      ))}
      {error != null && <ErrorMsg error={error} />}
      <Button disabled={busy}>{busy ? "Saving…" : "Save check-in"}</Button>
    </form>
  );
}

export default function Exercise() { return <RequireClient><Body /></RequireClient>; }
