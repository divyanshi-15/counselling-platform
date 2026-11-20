/** Turns monitoring findings / evidence into readable sentences. Pure functions, no imports: safe to run under node for checks. */

type Obj = Record<string, unknown>;
const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const has = (v: unknown): boolean => v !== null && v !== undefined && v !== "" && !(typeof v === "number" && Number.isNaN(v));
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const str = (v: unknown): string | null => (typeof v === "string" && v.trim() && v !== "null" && v !== "undefined" ? v.trim() : null);

export const MEASURE_LABEL: Record<string, string> = { PHQ9: "PHQ-9", GAD7: "GAD-7", phq9: "PHQ-9", gad7: "GAD-7" };
export const measureLabel = (m: unknown) => MEASURE_LABEL[String(m)] ?? (str(m) ?? "Score");

export const humanKey = (k: string) => {
  const s = k.replace(/[_-]+/g, " ").trim();
  return s ? s[0].toUpperCase() + s.slice(1) : "";
};

/** "29 May" (or "29 May 2025" when `year`). Returns "" for anything that is not a date. */
export function shortDate(v: unknown, year = false): string {
  const s = str(v);
  if (!s) return "";
  const d = new Date(/^\d{4}-\d{2}-\d{2}$/.test(s) ? `${s}T00:00:00Z` : s);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", ...(year ? { year: "numeric" } : {}), timeZone: "Asia/Kolkata" });
}

/** "20 Nov, 6:56 PM IST" */
export function runTime(v: unknown): string {
  const s = str(v);
  if (!s) return "";
  const d = new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(s) ? s : `${s}Z`);
  if (Number.isNaN(d.getTime())) return "";
  const day = d.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "Asia/Kolkata" });
  const time = d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true, timeZone: "Asia/Kolkata" });
  return `${day}, ${time} IST`;
}

/** Last-resort readable summary of any value. Never returns "[object Object]", "undefined" or "null". */
export function plain(v: unknown, depth = 0): string {
  if (!has(v)) return "";
  if (typeof v === "string") return str(v) ?? "";
  if (typeof v === "number" || typeof v === "bigint") return String(v);
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (Array.isArray(v)) return v.map((x) => plain(x, depth + 1)).filter(Boolean).join("; ");
  if (isObj(v)) {
    if (depth > 2) return "";
    return Object.entries(v).map(([k, x]) => {
      const t = plain(x, depth + 1);
      return t ? `${humanKey(k).toLowerCase()} ${t}` : "";
    }).filter(Boolean).join(", ");
  }
  return "";
}

const list = (v: unknown): Obj[] => (Array.isArray(v) ? v.filter(isObj) : isObj(v) ? [v] : []);
const quote = (s: string) => `'${s}'`;

function plateau(e: Obj): string {
  const m = measureLabel(e.measure), first = num(e.first), latest = num(e.latest), n = num(e.readings);
  const over = n !== null ? ` over ${first !== null && latest !== null && first === latest ? "the last " : ""}${n} readings` : "";
  if (latest !== null && first !== null && first === latest) return `${m} stayed at ${latest}${over}`;
  if (latest !== null && first !== null) return `${m} went from ${first} to ${latest}${over}, with no meaningful improvement`;
  if (latest !== null) return `${m} is at ${latest}${over}, with no meaningful improvement`;
  return `${m} shows no meaningful improvement${over}`;
}

function homework(e: Obj): string {
  const done = num(e.completed), total = num(e.assigned);
  let rate = num(e.rate);
  if (rate === null && done !== null && total) rate = done / total;
  const title = str(e.title) ?? str(e.exercise) ?? str(e.name);
  const when = shortDate(e.assigned_at ?? e.created_at);
  if (title && done === null) return `${quote(title)} assigned${when ? ` ${when}` : ""}, not yet completed`;
  if (done !== null && total !== null) return `${done} of ${total} recent exercises completed${rate !== null ? ` (${Math.round(rate * 100)}%)` : ""}`;
  if (rate !== null) return `${Math.round(rate * 100)}% of recent exercises completed`;
  return "Fewer than half of recent exercises completed";
}

function goal(e: Obj): string {
  const g = str(e.goal) ?? str(e.text), n = num(e.sessions_checked);
  const span = n !== null ? `in the last ${n} sessions` : "in recent sessions";
  return g ? `${quote(g)} had no activity ${span}` : `A plan goal had no activity ${span}`;
}

const LEAD: Record<string, string> = { plateau: "Plateau", homework: "Homework", goal_untouched: "Goal untouched" };
const BUILD: Record<string, (e: Obj) => string> = { plateau, homework, goal_untouched: goal };

/** One finding kind (+ its detail) -> readable sentences. */
export function formatFinding(kind: string, detail: unknown): string[] {
  const build = BUILD[kind];
  if (!build) {
    const t = plain(detail);
    return t ? [`${humanKey(kind)}: ${t}`] : [humanKey(kind)].filter(Boolean);
  }
  const items = list(detail);
  const lead = LEAD[kind];
  if (items.length === 0) return [kind === "plateau" ? `${lead}: no meaningful improvement` : kind === "homework" ? `${lead}: ${homework({})}` : `${lead}: a plan goal had no recent activity`];
  return items.map((e) => `${lead}: ${build(e)}`);
}

/** The `findings` object of a plan-update action (kind -> detail) -> sentences. */
export function formatEvidence(findings: unknown): string[] {
  if (!isObj(findings)) return [];
  return Object.entries(findings).flatMap(([k, v]) => formatFinding(k, v));
}

/** A monitoring alert's payload -> one readable sentence (finding label + evidence). */
export function formatAlert(type: string, payload: unknown): string {
  const p = isObj(payload) ? payload : {};
  const sentences = BUILD[type] ? formatFinding(type, p.detail) : [];
  const label = str(p.finding);
  if (sentences.length) return sentences.join(". ");
  const extra = plain(p.detail);
  return [label ?? humanKey(type), extra].filter(Boolean).join(" — ");
}

type Series = { first?: unknown; latest?: unknown; series?: unknown };
/** "PHQ-9 22 to 8 and GAD-7 17 to 7 since 29 May" from a scores object. */
export function formatScoreChange(scores: unknown): string {
  if (!isObj(scores)) return "";
  const parts: string[] = [];
  let since = "";
  for (const k of ["PHQ9", "GAD7"]) {
    const s = scores[k] as Series | undefined;
    if (!isObj(s)) continue;
    const first = num(s.first), latest = num(s.latest);
    if (latest === null) continue;
    parts.push(first !== null && first !== latest ? `${measureLabel(k)} ${first} to ${latest}` : `${measureLabel(k)} ${latest}`);
    const pts = Array.isArray(s.series) ? s.series : [];
    const d = isObj(pts[0]) ? shortDate(pts[0].taken_at) : "";
    if (d && (!since || k === "PHQ9")) since = d;
  }
  if (!parts.length) return "";
  return parts.join(" and ") + (since && parts.some((p) => p.includes(" to ")) ? ` since ${since}` : "");
}
