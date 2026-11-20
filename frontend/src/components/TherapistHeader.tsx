import { Star } from "lucide-react";
import { Avatar } from "@/components/Avatar";
import type { TherapistItem } from "@/lib/api";

export function TherapistHeader({ t, size = 48 }: { t: TherapistItem; size?: number }) {
  const facts = [
    t.credentials,
    t.years_experience ? `${t.years_experience} yrs experience` : "",
    t.languages?.length ? t.languages.map((l) => l.toUpperCase()).join(", ") : "",
    t.fee ? `₹${t.fee.toLocaleString("en-IN")} / session` : "",
  ].filter(Boolean);
  return (
    <div className="flex items-start gap-3">
      <Avatar name={t.name} size={size} />
      <div className="min-w-0 space-y-1">
        <p className="font-display text-lg font-semibold leading-tight">{t.name}</p>
        {t.rating != null && (t.review_count ?? 0) > 0 && (
          <p className="flex items-center gap-1 text-sm"><Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />{t.rating.toFixed(1)} <span className="text-muted-foreground">({t.review_count} reviews)</span></p>
        )}
        {facts.length > 0 && <p className="text-sm text-muted-foreground">{facts.join(" · ")}</p>}
        {t.specialisations?.length ? <p className="flex flex-wrap gap-1 pt-0.5">{t.specialisations.map((s) => <span key={s} className="rounded-full bg-primary-soft px-2.5 py-0.5 text-xs font-medium text-primary-hover">{s}</span>)}</p> : null}
      </div>
    </div>
  );
}
