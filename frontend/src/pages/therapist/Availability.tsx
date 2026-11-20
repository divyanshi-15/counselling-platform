import { useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import { Shell, fmt, type Schemas } from "./common";

const SLOT_MINUTES = 50;

function Body() {
  const { data, error, loading, reload } = useFetch<Schemas["MySlotsOut"]>("/therapists/me/availability");
  const [when, setWhen] = useState("");
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<unknown>(null);

  async function add(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setActionError(null);
    const start = new Date(when);
    try {
      await api<Schemas["MySlotOut"]>("/therapists/me/availability", {
        method: "POST", json: { starts_at: start.toISOString(), ends_at: new Date(start.getTime() + SLOT_MINUTES * 60_000).toISOString() },
      });
      setWhen(""); reload();
    } catch (err) { setActionError(err); } finally { setBusy(false); }
  }
  async function remove(id: number) {
    setBusy(true); setActionError(null);
    try { await api(`/therapists/me/availability/${id}`, { method: "DELETE" }); reload(); }
    catch (err) { setActionError(err); } finally { setBusy(false); }
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Availability" />
      <form onSubmit={(e) => void add(e)} className="flex flex-wrap items-end gap-2">
        <div className="space-y-1">
          <Label htmlFor="slot-start">New slot starts ({SLOT_MINUTES} minutes)</Label>
          <Input id="slot-start" type="datetime-local" required value={when} onChange={(e) => setWhen(e.target.value)} />
        </div>
        <Button disabled={busy || !when}>Add slot</Button>
      </form>
      {actionError != null && <ErrorMsg error={actionError} />}
      {loading ? <Loading /> : error != null || !data ? <ErrorMsg error={error} /> : data.items.length === 0 ? <Empty>No upcoming slots.</Empty> : (
        <ul className="space-y-2">
          {data.items.map((s) => (
            <li key={s.id} className="flex items-center justify-between gap-2 rounded-md border p-3 text-sm">
              <span>{fmt(s.starts_at)}</span>
              {s.booked ? <span className="text-muted-foreground">Booked</span>
                : <Button variant="outline" disabled={busy} aria-label={`Remove slot ${fmt(s.starts_at)}`} onClick={() => void remove(s.id)}>Remove</Button>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
export default function Availability() { return <Shell><Body /></Shell>; }
