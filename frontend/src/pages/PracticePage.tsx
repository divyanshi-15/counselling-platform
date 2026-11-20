import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { RichText } from "@/components/RichText";
import { TherapistCard } from "@/components/TherapistCard";
import { api, type PracticeItem, type TherapistItem } from "@/lib/api";
import { useFetch } from "@/lib/useFetch";

export default function PracticePage() {
  const { slug } = useParams();
  const { user } = useAuth();
  const { data, error, loading } = useFetch<{ practice: PracticeItem }>(`/p/${slug}`);
  const practice = data?.practice;
  const therapists = useFetch<{ items: (TherapistItem)[] }>("/therapists/public", practice ? { practice_id: practice.id } : undefined);

  if (loading) return <Loading />;
  if (error != null || !practice) return <ErrorMsg error={error ?? new Error("Practice not found.")} />;
  const pg = practice.page;

  return (
    <div className="space-y-8">
      <section>
        <h1 className="text-2xl font-semibold">{practice.name} <Badge className="ml-2 border-primary text-primary">Verified</Badge></h1>
        <p className="text-muted-foreground">{pg.tagline}</p>
      </section>
      <section><h2 className="mb-3 text-xl font-semibold">About</h2><RichText text={pg.about} /></section>
      <section>
        <h2 className="mb-3 text-xl font-semibold">Services</h2>
        {pg.services?.length ? (
          <div className="grid gap-3 md:grid-cols-2">
            {pg.services.map((s) => <Card key={s.title}><CardHeader><CardTitle>{s.title}</CardTitle></CardHeader><CardContent className="text-sm">{s.description}</CardContent></Card>)}
          </div>
        ) : <Empty>No services listed yet.</Empty>}
      </section>
      <section>
        <h2 className="mb-3 text-xl font-semibold">What to expect</h2>
        {pg.what_to_expect?.length ? <ul className="list-disc pl-5 space-y-1">{pg.what_to_expect.map((w) => <li key={w}>{w}</li>)}</ul> : <Empty>Nothing listed yet.</Empty>}
      </section>
      <section>
        <h2 className="mb-3 text-xl font-semibold">FAQ</h2>
        {pg.faq?.length ? pg.faq.map((q) => (
          <details key={q.question} className="mb-2 rounded-2xl border bg-card px-5 py-3 shadow-sm"><summary className="cursor-pointer font-medium">{q.question}</summary><p className="pt-1 text-sm">{q.answer}</p></details>
        )) : <Empty>No questions yet.</Empty>}
      </section>
      <section>
        <h2 className="mb-3 text-xl font-semibold">Verified therapists</h2>
        {therapists.loading && <Loading />}
        {therapists.error != null && <ErrorMsg error={therapists.error} />}
        {therapists.data && therapists.data.items.length === 0 && <Empty>No verified therapists yet.</Empty>}
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {therapists.data?.items.map((t) => <TherapistCard key={t.id} t={t} />)}
        </div>
      </section>
      <ContactForm practiceName={practice.name} />
    </div>
  );
}

function ContactForm({ practiceName }: { practiceName: string }) {
  const [form, setForm] = useState({ name: "", email: "", message: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<{ status: string; message: string } | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      setResult(await api("/practices/contact", { method: "POST", json: { ...form, practice: practiceName } }));
    } catch (err) { setError(err); } finally { setBusy(false); }
  }

  return (
    <section>
      <h2 className="mb-3 text-xl font-semibold">Contact</h2>
      {result ? (
        <p role="status" className={result.status === "crisis" ? "rounded-md border-2 border-destructive p-4 font-semibold" : "rounded-md border p-4"}>{result.message}</p>
      ) : (
        <form onSubmit={submit} className="max-w-md space-y-3">
          <div className="space-y-1"><Label htmlFor="c-name">Name</Label><Input id="c-name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div className="space-y-1"><Label htmlFor="c-email">Email</Label><Input id="c-email" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
          <div className="space-y-1"><Label htmlFor="c-msg">Message</Label><Textarea id="c-msg" required value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} /></div>
          {error != null && <ErrorMsg error={error} />}
          <Button disabled={busy}>{busy ? "Sending…" : "Send"}</Button>
        </form>
      )}
    </section>
  );
}
