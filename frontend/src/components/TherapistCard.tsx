import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { TherapistHeader } from "@/components/TherapistHeader";
import { useAuth } from "@/lib/auth";
import type { TherapistItem } from "@/lib/api";

export function TherapistCard({ t, showPractice = false }: { t: TherapistItem; showPractice?: boolean }) {
  const { user } = useAuth();
  return (
    <Card>
      <CardHeader><TherapistHeader t={t} /></CardHeader>
      <CardContent className="space-y-1 text-sm">
        <p className="line-clamp-3">{t.bio}</p>
        <p className="text-muted-foreground">{(t.approaches ?? []).join(", ")}</p>
        {showPractice && t.practice && <Link className="text-primary underline" to={`/p/${t.practice.slug}`}>{t.practice.name}</Link>}
        <div className="flex flex-wrap gap-2 pt-2">
          <Button asChild variant="outline"><Link to={`/therapists/${t.id}`}>View profile</Link></Button>
          <Button asChild><Link to={user?.role === "client" ? `/client/book/${t.id}` : "/signup"}>Book a session</Link></Button>
        </div>
      </CardContent>
    </Card>
  );
}
