import { useRef, useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/input";
import { ErrorMsg } from "@/components/states";
import { api } from "@/lib/api";
import { CrisisBox, RequireClient, type Schemas } from "./common";

type Res = Schemas["BrainDumpOut"];
const MAX = 2000;

function Body() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [res, setRes] = useState<Res | null>(null);
  const key = useRef(crypto.randomUUID()); // one key per page visit: a double click cannot submit twice

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setError(null);
    try { setRes(await api<Res>("/client/brain-dump", { method: "POST", headers: { "Idempotency-Key": key.current }, json: { text } })); }
    catch (err) { setError(err); } finally { setBusy(false); }
  }

  if (res?.status === "crisis") return <CrisisBox message={res.message} />; // nothing else shown
  if (res) return (
    <div className="space-y-3">
      <p className="text-lg font-medium">{res.status === "shared" ? res.message : "Shared with your therapist"}</p>
      {res.status !== "shared" && <p className="text-sm text-muted-foreground">{res.message}</p>}
      <Button asChild><Link to="/client">Back to dashboard</Link></Button>
    </div>
  );
  return (
    <form onSubmit={(e) => void submit(e)} className="space-y-4">
      <PageHeader title="Brain dump" />
      <p className="text-sm text-muted-foreground">Write whatever is on your mind. Your therapist will see it.</p>
      <div className="space-y-1">
        <Label htmlFor="text">What is on your mind?</Label>
        <Textarea id="text" required rows={8} maxLength={MAX} value={text} onChange={(e) => setText(e.target.value)} />
        <p className="text-right text-xs text-muted-foreground">{text.length}/{MAX}</p>
      </div>
      {error != null && <ErrorMsg error={error} />}
      <Button disabled={busy || !text.trim()}>{busy ? "Sending…" : "Share with my therapist"}</Button>
    </form>
  );
}

export default function BrainDump() { return <RequireClient><Body /></RequireClient>; }
