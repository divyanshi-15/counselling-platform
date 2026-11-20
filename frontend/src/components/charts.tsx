import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export const ACCENT = "#0d9488";
export const NEUTRAL = "#64748b";
const tick = { fontSize: 11, fill: NEUTRAL };
const axisLabel = (value: string, angle = 0) => ({ value, angle, position: angle ? "insideLeft" as const : "insideBottom" as const, offset: angle ? 12 : -2, style: { fontSize: 11, fill: NEUTRAL, textAnchor: "middle" as const } });

type Row = Record<string, string | number | null>;
type Fmt = (v: number) => string;

export function ChartFrame({ title, summary, children }: { title: string; summary: string; children: React.ReactNode }) {
  return (
    <figure className="space-y-2" aria-label={title}>
      <figcaption className="text-sm font-medium">{title}</figcaption>
      <div className="h-56 w-full sm:h-64" role="img" aria-label={summary}>{children}</div>
    </figure>
  );
}

export function Bars({ data, x, y, xLabel, yLabel, name }: { data: Row[]; x: string; y: string; xLabel: string; yLabel: string; name: string }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 22, left: 4 }}>
        <CartesianGrid vertical={false} stroke="#e2e8f0" />
        <XAxis dataKey={x} tick={tick} interval="preserveStartEnd" minTickGap={14} label={axisLabel(xLabel)} />
        <YAxis tick={tick} width={34} allowDecimals={false} label={axisLabel(yLabel, -90)} />
        <Tooltip cursor={{ fill: "#f1f5f9" }} />
        <Bar dataKey={y} name={name} fill={ACCENT} radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export type LineSpec = { key: string; name: string; dashed?: boolean; accent?: boolean };

export function Lines({ data, x, lines, xLabel, yLabel, fmt, domain }: {
  data: Row[]; x: string; lines: LineSpec[]; xLabel: string; yLabel: string; fmt?: Fmt; domain?: [number, number];
}) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 8, right: 12, bottom: 22, left: 4 }}>
        <CartesianGrid vertical={false} stroke="#e2e8f0" />
        <XAxis dataKey={x} tick={tick} label={axisLabel(xLabel)} />
        <YAxis tick={tick} width={fmt ? 52 : 34} domain={domain} tickFormatter={fmt} allowDecimals={false} label={axisLabel(yLabel, -90)} />
        <Tooltip formatter={(v) => (typeof v === "number" && fmt ? fmt(v) : v)} />
        {lines.map((l) => (
          <Line key={l.key} dataKey={l.key} name={l.name} type="monotone" connectNulls stroke={l.accent === false ? NEUTRAL : ACCENT}
            strokeWidth={2} strokeDasharray={l.dashed ? "5 4" : undefined} dot={{ r: 3 }} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

export type SparkPoint = { label: string; value: number };

/** Small axis-free trend line with a date + score tooltip. */
export function Spark({ data, name, color = ACCENT }: { data: SparkPoint[]; name: string; color?: string }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
        <YAxis hide domain={["dataMin - 1", "dataMax + 1"]} />
        <Tooltip formatter={(v) => [String(v), name]} labelFormatter={(l) => String(l)} contentStyle={{ fontSize: 12 }} />
        <Line dataKey="value" name={name} type="monotone" stroke={color} strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} />
        <XAxis dataKey="label" hide />
      </LineChart>
    </ResponsiveContainer>
  );
}
