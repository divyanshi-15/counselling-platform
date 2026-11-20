import { Bot } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { useFetch } from "@/lib/useFetch";
import { TechnicalDetails } from "@/components/TechnicalDetails";
import { humanKey } from "@/lib/evidence";
import { Shell, fmt, type Schemas } from "./common";

const TOOLS: Record<string, string> = {
  get_intake: "Read intake", get_scores: "Read scores", structure_notes: "Structure notes", compare_to_plan: "Compare to plan",
  retrieve_knowledge: "Find knowledge entries", draft_exercises: "Draft exercises", check_client: "Check client", summary: "Summary",
};

function Body() {
  const { data, error, loading } = useFetch<Schemas["AgentRunsOut"]>("/therapists/me/agent-runs");
  const bookings = useFetch<Schemas["TherapistBookingsOut"]>("/therapists/me/bookings");
  const names = new Map<number, string>();
  bookings.data?.items.forEach((b) => { if (b.client.name) names.set(b.client.id, b.client.name); });
  const readable = (t: string) => t.replace(/^Client (\d+)/, (m, id: string) => names.get(Number(id)) ?? m);
  if (loading) return <Loading />;
  if (error != null || !data) return <ErrorMsg error={error} />;
  const runs = new Map<string, Schemas["AgentRunItem"][]>();
  data.items.forEach((r) => runs.set(r.run_id, [...(runs.get(r.run_id) ?? []), r]));
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Agent activity</h1>
        <p className="text-sm text-muted-foreground">Every step the assistant took on your behalf. It never acts on its own: results land in your approval inbox.</p>
      </div>
      {runs.size === 0 ? <Empty>No agent runs yet.</Empty> : (
        <ol className="space-y-4">
          {[...runs.entries()].map(([id, steps]) => {
            const steps_ = [...steps].sort((a, b) => a.step - b.step);
            const monitor = steps_.some((s) => s.tool === "check_client" || s.tool === "summary");
            return (
              <li key={id} className="rounded-lg border p-4">
                <div className="mb-3 flex flex-wrap items-center gap-2">
                  <Bot className="h-4 w-4 text-primary" />
                  <span className="font-medium">{monitor ? "Overnight monitor" : "Prepare my day"}</span>
                  <Badge className="text-muted-foreground">{steps_.length} step{steps_.length > 1 ? "s" : ""} / max 8 tool calls</Badge>
                  <span className="text-xs text-muted-foreground">{fmt(steps_[0].created_at + (steps_[0].created_at.endsWith("Z") ? "" : "Z"))}</span>
                </div>
                <ol className="relative space-y-2 border-l pl-4">
                  {steps_.map((s) => (
                    <li key={s.step} className="text-sm">
                      <span className="absolute -ml-[21px] mt-1.5 h-2.5 w-2.5 rounded-full border-2 border-primary bg-background" />
                      <span className="mr-1 rounded bg-muted px-1.5 py-0.5 text-xs">{TOOLS[s.tool] ?? humanKey(s.tool)}</span>{readable(s.summary)}
                    </li>
                  ))}
                </ol>
                <div className="mt-2"><TechnicalDetails data={steps_.map((x) => ({ step: x.step, tool: x.tool, summary: x.summary, at: x.created_at }))} /></div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}

export default function Activity() { return <Shell><Body /></Shell>; }
