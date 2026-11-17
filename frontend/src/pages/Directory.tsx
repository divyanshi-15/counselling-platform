import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { TherapistCard } from "@/components/TherapistCard";
import type { PracticeItem, TherapistItem } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

function Practices() {
  const [f, setF] = useState({ city: "", approach: "", fee_max: "", session_type: "" });
  const { data, error, loading } = useFetch<{ items: PracticeItem[] }>("/practices/public", f);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  return (
    <div className="space-y-6">
      <form className="grid grid-cols-2 gap-3 md:grid-cols-4" onSubmit={(e) => e.preventDefault()} aria-label="Practice filters">
        <div className="space-y-1"><Label htmlFor="p-city">City</Label><Input id="p-city" placeholder="e.g. Mysuru" value={f.city} onChange={set("city")} /></div>
        <div className="space-y-1"><Label htmlFor="p-approach">Approach</Label><Input id="p-approach" placeholder="e.g. CBT" value={f.approach} onChange={set("approach")} /></div>
        <div className="space-y-1"><Label htmlFor="p-fee">Max fee (₹)</Label><Input id="p-fee" type="number" min={0} value={f.fee_max} onChange={set("fee_max")} /></div>
        <div className="space-y-1"><Label htmlFor="p-mode">Format</Label>
          <Select id="p-mode" value={f.session_type} onChange={set("session_type")}>
            <option value="">Any</option><option value="online">Online</option><option value="in-person">In-person</option>
          </Select></div>
      </form>
      {loading && <Loading />}
      {error != null && <ErrorMsg error={error} />}
      {data && data.items.length === 0 && <Empty>No practices match these filters. Try removing one.</Empty>}
      <ul className="grid gap-4 md:grid-cols-2">
        {data?.items.map((p) => (
          <li key={p.id}>
            <Link to={`/p/${p.slug}`} className="block">
              <Card className="h-full hover:border-primary">
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

export default function Directory() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "practices" ? "practices" : "therapists";
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{tab === "practices" ? "Find a practice" : "Find a therapist"}</h1>
        <p className="text-sm text-muted-foreground">Everything listed here belongs to a published, verified practice.</p>
      </div>
      <div role="tablist" className="inline-flex rounded-md border p-0.5 text-sm">
        {(["therapists", "practices"] as const).map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setParams(t === "therapists" ? {} : { tab: t })}
            className={`rounded px-4 py-1.5 capitalize ${tab === t ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}>{t}</button>
        ))}
      </div>
      {tab === "practices" ? <Practices /> : <Therapists />}
    </div>
  );
}

function Therapists() {
  const [f, setF] = useState({ city: "", language: "", specialisation: "" });
  const { data, error, loading } = useFetch<{ items: TherapistItem[] }>("/therapists/public", f);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  return (
    <div className="space-y-6">
      <form className="grid grid-cols-1 gap-3 sm:grid-cols-3" onSubmit={(e) => e.preventDefault()} aria-label="Filters">
        <div className="space-y-1"><Label htmlFor="city">City</Label><Input id="city" placeholder="e.g. Bengaluru" value={f.city} onChange={set("city")} /></div>
        <div className="space-y-1"><Label htmlFor="language">Language</Label>
          <Select id="language" value={f.language} onChange={set("language")}>
            <option value="">Any</option><option value="en">English</option><option value="hi">Hindi</option><option value="kn">Kannada</option>
          </Select></div>
        <div className="space-y-1"><Label htmlFor="spec">Specialisation</Label><Input id="spec" placeholder="e.g. sleep" value={f.specialisation} onChange={set("specialisation")} /></div>
      </form>
      {loading && <Loading />}
      {error != null && <ErrorMsg error={error} />}
      {data && data.items.length === 0 && <Empty>No therapists match these filters. Try removing one.</Empty>}
      <div className="grid gap-4 md:grid-cols-2">{data?.items.map((t) => <TherapistCard key={t.id} t={t} showPractice />)}</div>
    </div>
  );
}
