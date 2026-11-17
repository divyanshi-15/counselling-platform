import { Link } from "react-router-dom";
import { Wordmark } from "@/components/Wordmark";

const COLS: [string, [string, string][]][] = [
  ["Product", [["Find a therapist", "/directory"], ["Browse practices", "/directory?tab=practices"], ["Log in", "/login"]]],
  ["For therapists", [["Join as a therapist", "/signup"], ["Therapist log in", "/login"]]],
  ["For practices", [["List your practice", "/signup"], ["Practice owner log in", "/login"]]],
  ["Safety and legal", [["Safety and crisis resources", "/safety"], ["Privacy", "/privacy"], ["Terms", "/terms"]]],
];

export function Footer() {
  return (
    <footer className="mt-8 border-t bg-muted/40">
      <div className="mx-auto grid max-w-5xl gap-6 px-4 py-8 sm:grid-cols-2 md:grid-cols-5">
        <div className="space-y-2 md:col-span-1">
          <Wordmark />
          <p className="text-sm text-muted-foreground">Counselling that continues between sessions.</p>
        </div>
        {COLS.map(([title, links]) => (
          <nav key={title} aria-label={title} className="space-y-2 text-sm">
            <h2 className="font-medium">{title}</h2>
            <ul className="space-y-1.5">{links.map(([l, to]) => <li key={l}><Link className="text-muted-foreground hover:text-foreground hover:underline" to={to}>{l}</Link></li>)}</ul>
          </nav>
        ))}
      </div>
      <div className="border-t px-4 py-3 text-center text-xs text-muted-foreground">
        <p>If you are in crisis, call Tele-MANAS 14416. Skill-building support, not a replacement for therapy.</p>
        <p className="mt-1 text-[11px]">Sample data</p>
      </div>
    </footer>
  );
}
