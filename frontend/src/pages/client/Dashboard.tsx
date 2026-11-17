import { NameWithAvatar } from "@/components/Avatar";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { useFetch } from "@/lib/useFetch";
import { fmt, RequireClient, type Schemas } from "./common";

type Dash = Schemas["ClientDashboardOut"];

function Body() {
  const { data, error, loading } = useFetch<Dash>("/client/dashboard");
  if (loading) return <Loading />;
  if (error != null || !data) return <ErrorMsg error={error} />;
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">My dashboard</h1>
      <div className="grid gap-3 md:grid-cols-2">
        <Card><CardHeader><CardTitle>My practice</CardTitle></CardHeader><CardContent className="text-sm">
          {data.practice ? <Link className="underline" to={`/p/${data.practice.slug}`}>{data.practice.name}</Link>
            : <Empty>No practice yet. <Link className="underline" to="/">Browse practices</Link> to book a session.</Empty>}
        </CardContent></Card>
        <Card><CardHeader><CardTitle>My therapist</CardTitle></CardHeader><CardContent className="space-y-1 text-sm">
          {data.therapist ? <><NameWithAvatar name={data.therapist.name}><span className="font-medium">{data.therapist.name}</span></NameWithAvatar><p className="text-muted-foreground">{data.therapist.bio}</p></>
            : <p className="text-muted-foreground">Not assigned yet.</p>}
        </CardContent></Card>
      </div>
      <Card><CardHeader><CardTitle>Upcoming session</CardTitle></CardHeader><CardContent className="space-y-3 text-sm">
        {data.upcoming_session ? (
          <>
            <p>{fmt(data.upcoming_session.starts_at)} – {fmt(data.upcoming_session.ends_at)}</p>
            <div className="flex flex-wrap gap-2">
              <Button asChild><Link to={`/client/session/${data.upcoming_session.id}`}>Join session</Link></Button>
              <Button variant="outline" asChild><Link to={`/client/intake/${data.upcoming_session.id}`}>Intake form</Link></Button>
            </div>
          </>
        ) : <p className="text-muted-foreground">No upcoming session.</p>}
      </CardContent></Card>
      <Card><CardHeader><CardTitle>Brain dump</CardTitle></CardHeader><CardContent className="space-y-3 text-sm">
        <p className="text-muted-foreground">Write down what is on your mind. It is shared with your therapist.</p>
        <Button variant="outline" asChild><Link to="/client/brain-dump">Write a brain dump</Link></Button>
      </CardContent></Card>
      <section>
        <h2 className="mb-2 text-lg font-semibold">Approved exercises</h2>
        {data.approved_exercises.length === 0 ? <Empty>No exercises from your therapist yet.</Empty> : (
          <div className="grid gap-3 md:grid-cols-2">
            {data.approved_exercises.map((e) => (
              <Card key={e.assignment_id}><CardContent className="flex items-center justify-between gap-2 pt-4">
                <div><p className="font-medium">{e.title}</p><Badge>{e.status}</Badge></div>
                <Button variant="outline" asChild><Link to={`/client/exercise/${e.assignment_id}`}>Open</Link></Button>
              </CardContent></Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export default function ClientDashboard() { return <RequireClient><Body /></RequireClient>; }
