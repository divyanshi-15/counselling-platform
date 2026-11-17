import { Link, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { TherapistHeader } from "@/components/TherapistHeader";
import type { TherapistItem } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useFetch } from "@/lib/useFetch";
import { fmt, type Schemas } from "@/pages/client/common";

export default function TherapistProfile() {
  const { id } = useParams();
  const { user } = useAuth();
  const t = useFetch<TherapistItem>(`/therapists/public/${id}`);
  const slots = useFetch<Schemas["AvailabilityOut"]>(`/therapists/${id}/availability`);
  if (t.loading) return <Loading />;
  if (t.error != null || !t.data) return <ErrorMsg error={t.error ?? new Error("Therapist not found.")} />;
  const p = t.data;
  const book = (slot?: number) => user?.role === "client" ? `/client/book/${p.id}${slot ? `?slot=${slot}` : ""}` : "/signup";
  return (
    <div className="space-y-6">
      <Card><CardHeader><TherapistHeader t={p} size={64} /></CardHeader>
        <CardContent className="space-y-2 text-sm">
          {p.practice && <p>Practice: <Link className="text-primary underline" to={`/p/${p.practice.slug}`}>{p.practice.name}</Link></p>}
          {p.bio && <p>{p.bio}</p>}
          {p.approaches?.length ? <p className="text-muted-foreground">Approaches: {p.approaches.join(", ")}</p> : null}
        </CardContent></Card>
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Next available sessions</h2>
        {slots.loading && <Loading />}
        {slots.error != null && <ErrorMsg error={slots.error} />}
        {slots.data?.items.length === 0 && <Empty>No open slots right now. Please check back soon.</Empty>}
        <div className="grid gap-2 sm:grid-cols-2">
          {slots.data?.items.slice(0, 6).map((s) => (
            <Card key={s.id}><CardContent className="flex items-center justify-between pt-4 text-sm">
              <span>{fmt(s.starts_at)}</span>
              <Button asChild><Link to={book(s.id)}>Book</Link></Button>
            </CardContent></Card>
          ))}
        </div>
        {!user && <p className="text-sm text-muted-foreground">You'll be asked to <Link className="underline" to="/signup">sign up</Link> or <Link className="underline" to="/login">log in</Link> first.</p>}
      </section>
    </div>
  );
}
