import { formatAlert, formatEvidence, formatFinding, formatScoreChange, plain } from "./evidence.ts";

const fail: string[] = [];
const BAD = /\[object Object\]|undefined|null|NaN/;
const check = (name: string, out: string | string[], expect: string[] = []) => {
  const text = Array.isArray(out) ? out.join(" | ") : out;
  if (BAD.test(text)) fail.push(`${name}: contains forbidden text -> ${text}`);
  for (const e of expect) if (!text.includes(e)) fail.push(`${name}: missing "${e}" in -> ${text}`);
  if (!text.trim()) fail.push(`${name}: empty output`);
};

const plateau = { plateau: [{ measure: "PHQ9", readings: 3, first: 8, latest: 8, slope_per_week: 0 }, { measure: "GAD7", readings: 4, first: 12, latest: 11, slope_per_week: -0.4 }] };
const homework = { homework: { assigned: 5, completed: 2, rate: 0.4 } };
const goals = { goal_untouched: [{ goal_id: "g1", goal: "Practise worry postponement", sessions_checked: 3 }] };

check("plateau", formatEvidence(plateau), ["Plateau: PHQ-9 stayed at 8 over the last 3 readings", "GAD-7 went from 12 to 11"]);
check("homework", formatEvidence(homework), ["2 of 5 recent exercises completed (40%)"]);
check("homework-named", formatFinding("homework", { title: "Thought record", assigned_at: "2026-11-12" }), ["'Thought record' assigned 12 Nov, not yet completed"]);
check("goal", formatEvidence(goals), ["Goal untouched: 'Practise worry postponement' had no activity in the last 3 sessions"]);
check("all", formatEvidence({ ...plateau, ...homework, ...goals }), ["Plateau", "Homework", "Goal untouched"]);
check("alert-goal", formatAlert("goal_untouched", { finding: "x", detail: goals.goal_untouched }), ["Practise worry postponement"]);
check("alert-homework", formatAlert("homework", { finding: "under 50% of recent exercises completed", detail: homework.homework }), ["2 of 5"]);
check("alert-plateau", formatAlert("plateau", { finding: "no meaningful PHQ-9/GAD-7 improvement over 14 days", detail: plateau.plateau }), ["PHQ-9 stayed at 8", "no meaningful improvement"]);
check("alert-no-detail", formatAlert("plateau", { finding: "no meaningful PHQ-9/GAD-7 improvement over 14 days" }), ["no meaningful improvement"]);
check("score-change", formatScoreChange({ PHQ9: { first: 22, latest: 8, series: [{ taken_at: "2026-05-29T13:26:00+00:00", total: 22 }] }, GAD7: { first: 17, latest: 7, series: [] } }), ["PHQ-9 22 to 8 and GAD-7 17 to 7 since 29 May"]);
// missing fields are omitted, never invented or stringified
check("sparse-plateau", formatEvidence({ plateau: [{ measure: "PHQ9" }] }), ["PHQ-9 shows no meaningful improvement"]);
check("sparse-homework", formatEvidence({ homework: {} }), ["Homework"]);
check("unknown-kind", formatEvidence({ new_kind: [{ a: { b: 1 }, c: null, d: undefined }] }), ["New kind"]);
check("nested-objects", plain({ a: [{ b: 1 }, { c: { d: "x" } }], e: null }), ["b 1"]);
check("junk", formatEvidence({ plateau: "oops", homework: null, goal_untouched: [null, 3, "x"] }));
if (formatEvidence(undefined).length || formatEvidence(null).length) fail.push("null/undefined evidence must give no sentences");

if (fail.length) { console.error("evidence formatter check FAILED:\n" + fail.join("\n")); process.exit(1); }
console.log("evidence formatter check passed");
