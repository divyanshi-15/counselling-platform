import { Link } from "react-router-dom";
import { Wordmark } from "@/components/Wordmark";

const COLS: [string, [string, string][]][] = [
  ["Product", [["Find a therapist", "/directory"], ["Browse practices", "/directory?tab=practices"], ["Log in", "/login?next=/client"]]],
  ["For therapists", [["Join as a therapist", "/signup?role=therapist"], ["Therapist log in", "/login?next=/therapist"]]],
  ["For practices", [["List your practice", "/signup?role=practice"], ["Practice owner log in", "/login?next=/owner"]]],
  ["Safety and legal", [["Safety and crisis resources", "/safety"], ["Privacy", "/privacy"], ["Terms", "/terms"], ["Contact", "/contact"]]],
];

export function Footer() {
  return (
    <footer className="mt-12 border-t bg-muted">
      <div className="mx-auto grid max-w-5xl gap-8 px-4 py-10 sm:grid-cols-2 md:grid-cols-5">
        <div className="space-y-2 md:col-span-1">
          <Wordmark />
          <p className="text-sm text-muted-foreground">Counselling that continues between sessions.</p>
        </div>
        {COLS.map(([title, links]) => (
          <nav key={title} aria-label={title} className="space-y-2 text-sm">
            <h2 className="font-display text-base font-semibold">{title}</h2>
            <ul className="space-y-1.5">{links.map(([l, to]) => <li key={l}><Link className="text-muted-foreground hover:text-foreground hover:underline" to={to}>{l}</Link></li>)}</ul>
          </nav>
        ))}
      </div>
      <div className="border-t bg-primary-soft px-4 py-4 text-center text-sm text-foreground">
        <p className="font-medium">If you are in crisis, call Tele-MANAS 14416. Skill-building support, not a replacement for therapy.</p>
        <p className="mt-1 text-xs text-muted-foreground">Sample data</p>
      </div>
    </footer>
  );
}
