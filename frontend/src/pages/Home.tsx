import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import type { PracticeItem } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

export default function Home() {
  const [f, setF] = useState({ language: "", specialty: "", approach: "", fee_max: "", session_type: "" });
  const { data, error, loading } = useFetch<{ items: PracticeItem[] }>("/practices/public", f);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Find a verified practice</h1>
      <form className="grid grid-cols-2 gap-3 md:grid-cols-5" onSubmit={(e) => e.preventDefault()} aria-label="Filters">
        <div className="space-y-1"><Label htmlFor="language">Language</Label>
          <Select id="language" value={f.language} onChange={set("language")}>
            <option value="">Any</option><option value="en">English</option><option value="hi">Hindi</option><option value="kn">Kannada</option>
          </Select></div>
        <div className="space-y-1"><Label htmlFor="specialty">Specialty</Label>
          <Input id="specialty" placeholder="e.g. sleep" value={f.specialty} onChange={set("specialty")} /></div>
        <div className="space-y-1"><Label htmlFor="approach">Approach</Label>
          <Input id="approach" placeholder="e.g. CBT" value={f.approach} onChange={set("approach")} /></div>
        <div className="space-y-1"><Label htmlFor="fee">Max fee (INR)</Label>
          <Input id="fee" type="number" min={0} value={f.fee_max} onChange={set("fee_max")} /></div>
        <div className="space-y-1"><Label htmlFor="mode">Format</Label>
          <Select id="mode" value={f.session_type} onChange={set("session_type")}>
            <option value="">Any</option><option value="online">Online</option><option value="in-person">In-person</option>
          </Select></div>
      </form>
      {loading && <Loading />}
      {error != null && <ErrorMsg error={error} />}
      {data && data.items.length === 0 && <Empty>No practices match these filters.</Empty>}
      <ul className="grid gap-4 md:grid-cols-2">
        {data?.items.map((p) => (
          <li key={p.id}>
            <Link to={`/p/${p.slug}`} className="block">
              <Card className="hover:border-primary">
                <CardHeader><CardTitle>{p.name} <Badge className="ml-2 border-primary text-primary">Verified</Badge></CardTitle></CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <p>{p.page.tagline}</p>
                  <p className="text-muted-foreground">{[p.page.location, p.page.session_type, p.page.fee_range].filter(Boolean).join(" · ")}</p>
                  <div className="flex flex-wrap gap-1">{[...(p.page.specialties ?? []), ...(p.page.approaches ?? [])].map((t) => <Badge key={t}>{t}</Badge>)}</div>
                </CardContent>
              </Card>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
