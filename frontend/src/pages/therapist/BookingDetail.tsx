import { humanKey, plain } from "@/lib/evidence";
import { Avatar } from "@/components/Avatar";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorMsg, Loading } from "@/components/states";
import { ApiError, api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import { Shell, fmt, type Schemas } from "./common";

function Intake({ bookingId }: { bookingId: string }) {
  const resp = useFetch<Schemas["IntakeResponseOut"]>(`/bookings/${bookingId}/intake-response`);
  const form = useFetch<Schemas["IntakeFormOut"]>(`/bookings/${bookingId}/intake-form`);
  if (resp.loading || form.loading) return <Loading />;
  if (resp.error instanceof ApiError && resp.error.status === 404) return <p className="text-sm text-muted-foreground">Intake form not submitted yet.</p>;
  if (resp.error != null || !resp.data) return <ErrorMsg error={resp.error} />;
  const labels = new Map(form.data?.fields.map((f) => [f.id, f.label]));
  return (
    <dl className="space-y-2 text-sm">
      {Object.entries(resp.data.answers).map(([k, v]) => (
        <div key={k}><dt className="text-muted-foreground">{labels.get(k) ?? humanKey(k)}</dt><dd className="whitespace-pre-wrap">{plain(v) || "–"}</dd></div>
      ))}
    </dl>
  );
}

function Notes({ bookingId }: { bookingId: string }) {
  const [text, setText] = useState("");
  const [source, setSource] = useState<"typed" | "transcript">("typed");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState<Schemas["SessionNotesOut"] | null>(null);
  const existing = useFetch<Schemas["SessionNotesOut"]>(`/bookings/${bookingId}/session-notes`);
  useEffect(() => { if (existing.data) { setText(existing.data.raw_notes); setSource(existing.data.source === "transcript" ? "transcript" : "typed"); } }, [existing.data]);

  async function save(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    try { setSaved(await api<Schemas["SessionNotesOut"]>(`/bookings/${bookingId}/session-notes`, { method: "PUT", json: { raw_notes: text, source } })); }
    catch (err) { setError(err); } finally { setBusy(false); }
  }
  return (
    <form onSubmit={(e) => void save(e)} className="space-y-3">
      <div className="space-y-1">
        <Label htmlFor="notes">Session notes (private to you)</Label>
        <Textarea id="notes" required rows={8} value={text} onChange={(e) => setText(e.target.value)} />
      </div>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={source === "transcript"} onChange={(e) => setSource(e.target.checked ? "transcript" : "typed")} /> This is a transcript</label>
      {error != null && <ErrorMsg error={error} />}
      {saved?.safety?.flagged && <p role="alert" className="rounded-md border-2 border-red-600 bg-red-50 p-3 text-sm font-medium text-red-800">Risk language detected in these notes. A high-priority alert is pinned on your Today page.</p>}
      {saved && !saved.safety?.flagged && <p role="status" className="text-sm text-muted-foreground">Saved.</p>}
      <Button disabled={busy || !text.trim()}>{busy ? "Saving…" : "Save notes"}</Button>
    </form>
  );
}

function Body() {
  const { bookingId = "" } = useParams();
  const bookings = useFetch<Schemas["TherapistBookingsOut"]>("/therapists/me/bookings");
  const room = useFetch<Schemas["RoomOut"]>(`/bookings/${bookingId}/room`);
  const b = bookings.data?.items.find((x) => String(x.id) === bookingId);
  if (bookings.loading) return <Loading />;
  if (bookings.error != null) return <ErrorMsg error={bookings.error} />;
  if (!b) return <p>Booking not found.</p>;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h1 className="flex items-center gap-3 text-2xl font-semibold"><Avatar name={b.client.name} size={40} />{b.client.name ?? `Client #${b.client.id}`}</h1>
          <p className="text-muted-foreground">{fmt(b.starts_at)} · {b.status}</p>
        </div>
        <div className="flex gap-2">
          {room.data && (
            <Button asChild><a href={`https://meet.jit.si/${encodeURIComponent(room.data.room_name)}`} target="_blank" rel="noopener noreferrer"><ExternalLink className="mr-2 h-4 w-4" />Open session room</a></Button>
          )}
          <Button variant="outline" asChild><Link to={`/therapist/clients/${b.client.id}`}>Client file</Link></Button>
        </div>
      </div>
      <Card><CardHeader><CardTitle>Intake</CardTitle></CardHeader><CardContent><Intake bookingId={bookingId} /></CardContent></Card>
      <Card><CardHeader><CardTitle>Notes</CardTitle></CardHeader><CardContent><Notes bookingId={bookingId} /></CardContent></Card>
    </div>
  );
}
export default function BookingDetail() { return <Shell><Body /></Shell>; }
