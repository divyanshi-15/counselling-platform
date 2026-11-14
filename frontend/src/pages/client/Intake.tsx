import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/input";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import { CrisisBox, RequireClient, type Schemas } from "./common";

type Result = Schemas["IntakeSubmitOut"];

function Body() {
  const { bookingId } = useParams();
  const form = useFetch<Schemas["IntakeFormOut"]>(`/bookings/${bookingId}/intake-form`);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState<Result | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    try { setDone(await api<Result>(`/bookings/${bookingId}/intake-response`, { method: "POST", json: { answers } })); }
    catch (err) { setError(err); } finally { setBusy(false); }
  }

  if (done?.safety.flagged) return <CrisisBox message={done.safety.message ?? ""} />;
  if (done) return <div className="space-y-3"><p>Intake saved. Thank you.</p><Button asChild><Link to="/client">Back to dashboard</Link></Button></div>;
  if (form.loading) return <Loading />;
  if (form.error != null) return <ErrorMsg error={form.error} />;
  if (!form.data?.fields.length) return <Empty>Your therapist has not set an intake form.</Empty>;
  return (
    <form onSubmit={(e) => void submit(e)} className="space-y-4">
      <h1 className="text-2xl font-semibold">Intake form</h1>
      {form.data.fields.map((f) => (
        <div key={f.id} className="space-y-1">
          <Label htmlFor={f.id}>{f.label}</Label>
          <Textarea id={f.id} required={f.required ?? undefined} maxLength={2000} value={answers[f.id] ?? ""} onChange={(e) => setAnswers({ ...answers, [f.id]: e.target.value })} />
        </div>
      ))}
      {error != null && <ErrorMsg error={error} />}
      <Button disabled={busy}>{busy ? "Saving…" : "Submit"}</Button>
    </form>
  );
}

export default function Intake() { return <RequireClient><Body /></RequireClient>; }
