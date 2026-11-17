import { Link } from "react-router-dom";
import { CalendarCheck, HeartHandshake, Lock, ShieldCheck, UserCheck, UsersRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const STEPS = [
  ["Find someone who fits", "Filter verified therapists by city, language and specialisation, and read their credentials before you book."],
  ["Book and share context", "Pick a slot, fill a short intake form, and join your session by video from any device."],
  ["Practise between sessions", "Your therapist releases short, evidence-based exercises. Check-ins feed back into your next session."],
] as const;

const AUDIENCES = [
  { icon: HeartHandshake, title: "For clients", points: ["Therapists verified by our team", "Sessions in English, Hindi and Kannada", "Exercises approved by your therapist", "A crisis line (Tele-MANAS 14416) on every page"], cta: ["Find a therapist", "/directory"] },
  { icon: UserCheck, title: "For therapists", points: ["A morning briefing for every client on your day", "Risk alerts pinned first, with the exact words that triggered them", "Every suggestion cites its source and is marked as inferred", "You approve anything before it reaches a client"], cta: ["Join as a therapist", "/signup"] },
  { icon: UsersRound, title: "For practices", points: ["A public page drafted for you, published only when you approve", "Listings, bookings and availability in one place", "No access to clinical notes, by design", "Verification badge once our team has checked your practice"], cta: ["List your practice", "/signup"] },
] as const;

const TRUST = [
  [Lock, "Role-based access", "Clients see only their own records. Therapists see only clients they work with. Practice owners manage listings and never see clinical data. These rules are enforced on the server, not in the interface."],
  [ShieldCheck, "Encrypted and private", "Data is encrypted in transit, sessions use httpOnly cookies, and passwords are hashed with Argon2. Public pages never show client information."],
  [UserCheck, "AI only proposes, humans approve", "The assistant drafts summaries and suggestions. Nothing is published, released or sent until a verified person approves it."],
  [CalendarCheck, "A crisis safety layer", "Every piece of client text is screened without an AI model. A match shows a fixed message with Tele-MANAS 14416 and alerts the therapist at once."],
] as const;

const FAQ = [
  ["Is this a replacement for therapy?", "No. Samvaad Care offers skill-building support alongside sessions with a qualified therapist. It is not a replacement for therapy."],
  ["What if I am in crisis?", "Call Tele-MANAS on 14416 right away. If you are in immediate danger, contact local emergency services."],
  ["Who can see what I write?", "Your therapist can see your intake, check-ins and notes. Practice owners and other therapists cannot."],
  ["Does AI talk to me or diagnose me?", "No. AI never messages clients directly, and its drafts are checked so they never include diagnoses or medication advice."],
  ["Which languages are supported?", "English, Hindi and Kannada, including romanised text, for both sessions and safety screening."],
] as const;

export default function Home() {
  return (
    <div className="space-y-16">
      <section className="space-y-5 pt-4 text-center md:pt-10">
        <h1 className="mx-auto max-w-3xl text-3xl font-semibold tracking-tight md:text-5xl">Counselling that continues between sessions</h1>
        <p className="mx-auto max-w-2xl text-muted-foreground md:text-lg">Samvaad Care connects you with verified therapists in your language, and gives them the tools to prepare well, follow up carefully and keep you safe.</p>
        <div className="flex flex-wrap justify-center gap-3">
          <Button asChild><Link to="/directory">Find a therapist</Link></Button>
          <Button asChild variant="outline"><Link to="/signup">I'm a therapist or practice</Link></Button>
        </div>
      </section>

      <section aria-labelledby="how" className="space-y-4">
        <h2 id="how" className="text-2xl font-semibold">How it works</h2>
        <ol className="grid gap-3 md:grid-cols-3">
          {STEPS.map(([t, d], i) => (
            <li key={t}><Card className="h-full"><CardHeader>
              <span className="mb-1 flex h-8 w-8 items-center justify-center rounded-full bg-primary text-sm font-medium text-primary-foreground">{i + 1}</span>
              <CardTitle className="text-lg">{t}</CardTitle></CardHeader><CardContent className="text-sm text-muted-foreground">{d}</CardContent></Card></li>
          ))}
        </ol>
      </section>

      <section aria-label="Who it is for" className="grid gap-3 md:grid-cols-3">
        {AUDIENCES.map(({ icon: Icon, title, points, cta }) => (
          <Card key={title} className="flex flex-col"><CardHeader><Icon className="h-6 w-6 text-primary" /><CardTitle className="text-lg">{title}</CardTitle></CardHeader>
            <CardContent className="flex flex-1 flex-col justify-between gap-4 text-sm">
              <ul className="list-disc space-y-1.5 pl-4">{points.map((p) => <li key={p}>{p}</li>)}</ul>
              <Button asChild variant="outline"><Link to={cta[1]}>{cta[0]}</Link></Button>
            </CardContent></Card>
        ))}
      </section>

      <section aria-labelledby="trust" className="space-y-4">
        <h2 id="trust" className="text-2xl font-semibold">Trust and security</h2>
        <div className="grid gap-3 md:grid-cols-2">
          {TRUST.map(([Icon, t, d]) => (
            <div key={t} className="flex gap-3 rounded-md border p-4"><Icon className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
              <div><h3 className="font-medium">{t}</h3><p className="text-sm text-muted-foreground">{d}</p></div></div>
          ))}
        </div>
      </section>

      <section aria-labelledby="faq" className="space-y-2">
        <h2 id="faq" className="text-2xl font-semibold">Frequently asked questions</h2>
        {FAQ.map(([q, a]) => <details key={q} className="border-b py-2"><summary className="cursor-pointer font-medium">{q}</summary><p className="pt-1 text-sm text-muted-foreground">{a}</p></details>)}
      </section>
    </div>
  );
}
