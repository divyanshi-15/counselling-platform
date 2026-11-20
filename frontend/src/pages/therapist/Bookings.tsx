import { NameWithAvatar } from "@/components/Avatar";
import { PageHeader } from "@/components/PageHeader";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { useFetch } from "@/lib/useFetch";
import { Shell, fmt, type Schemas } from "./common";

function Body() {
  const { data, error, loading } = useFetch<Schemas["TherapistBookingsOut"]>("/therapists/me/bookings");
  if (loading) return <Loading />;
  if (error != null || !data) return <ErrorMsg error={error} />;
  return (
    <div className="space-y-4">
      <PageHeader title="Bookings" />
      {data.items.length === 0 ? <Empty>No bookings yet.</Empty> : (
        <ul className="space-y-2">
          {data.items.map((b) => (
            <li key={b.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3">
              <div>
                <NameWithAvatar name={b.client.name}><span className="font-medium">{b.client.name ?? `Client #${b.client.id}`}</span></NameWithAvatar>
                <p className="text-sm text-muted-foreground">{fmt(b.starts_at)}</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge className="text-muted-foreground">{b.status}</Badge>
                <Button variant="outline" asChild><Link to={`/therapist/bookings/${b.id}`}>Open</Link></Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
export default function Bookings() { return <Shell><Body /></Shell>; }
