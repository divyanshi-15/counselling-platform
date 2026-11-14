import { useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ErrorMsg, Loading } from "@/components/states";
import { useFetch } from "@/lib/useFetch";
import { RequireClient, type Schemas } from "./common";

function Body() {
  const { bookingId } = useParams();
  const { data, error, loading } = useFetch<Schemas["RoomOut"]>(`/bookings/${bookingId}/room`);
  if (loading) return <Loading />;
  if (error != null || !data) return <ErrorMsg error={error} />;
  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-semibold">Your session</h1>
      <p className="text-muted-foreground">Your session opens in a new tab.</p>
      <Button asChild><a href={`https://meet.jit.si/${encodeURIComponent(data.room_name)}`} target="_blank" rel="noopener noreferrer">Open session room</a></Button>
    </div>
  );
}

export default function Session() { return <RequireClient><Body /></RequireClient>; }
