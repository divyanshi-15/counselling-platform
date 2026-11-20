import { useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { api } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";
import { fmt, RequireClient, type Schemas } from "./common";

type Slot = Schemas["SlotOut"];

function Body() {
  const { therapistId } = useParams();
  const slots = useFetch<Schemas["AvailabilityOut"]>(`/therapists/${therapistId}/availability`);
  const [params] = useSearchParams();
  const [picked, setSlot] = useState<Slot | null>(null);
  const slot = picked ?? slots.data?.items.find((s) => String(s.id) === params.get("slot")) ?? null;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [booking, setBooking] = useState<Schemas["BookingOut"] | null>(null);

  async function confirm() {
    if (!slot) return;
    setBusy(true); setError(null);
    try { setBooking(await api<Schemas["BookingOut"]>("/bookings", { method: "POST", json: { availability_slot_id: slot.id } })); }
    catch (e) { setError(e); } finally { setBusy(false); }
  }

  if (booking) return (
    <div className="space-y-3">
      <PageHeader title="Booking confirmed" />
      <p>{slot && fmt(slot.starts_at)}</p>
      <Button asChild><Link to={`/client/intake/${booking.id}`}>Fill in intake form</Link></Button>
    </div>
  );
  return (
    <div className="space-y-4">
      <PageHeader title="Book a session" />
      {slots.loading && <Loading />}
      {slots.error != null && <ErrorMsg error={slots.error} />}
      {slots.data?.items.length === 0 && <Empty>No open slots right now.</Empty>}
      <div className="grid gap-2 sm:grid-cols-2">
        {slots.data?.items.map((s) => (
          <Card key={s.id} className={slot?.id === s.id ? "border-primary" : ""}><CardContent className="flex items-center justify-between pt-4 text-sm">
            <span>{fmt(s.starts_at)}</span>
            <Button variant={slot?.id === s.id ? "default" : "outline"} onClick={() => setSlot(s)}>Select</Button>
          </CardContent></Card>
        ))}
      </div>
      {slot && <Button disabled={busy} onClick={() => void confirm()}>{busy ? "Booking…" : `Confirm ${fmt(slot.starts_at)}`}</Button>}
      {error != null && <ErrorMsg error={error} />}
    </div>
  );
}

export default function Book() { return <RequireClient><Body /></RequireClient>; }
