import { useParams } from "react-router-dom";
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
      <iframe title="Video session" allow="camera; microphone; fullscreen; display-capture" className="h-[70vh] w-full rounded-md border"
        src={`https://meet.jit.si/${encodeURIComponent(data.room_name)}`} />
    </div>
  );
}

export default function Session() { return <RequireClient><Body /></RequireClient>; }
