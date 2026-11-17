import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorMsg } from "@/components/states";
import { homeFor, useAuth } from "@/lib/auth";
import { pendingInvite } from "@/lib/invite";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const next = params.get("next");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function run(fn: () => Promise<{ role: string }>) {
    setBusy(true); setError(null);
    try { const role = (await fn()).role; const home = homeFor(role); nav(role === "therapist" && pendingInvite() ? "/invitation" : next === home ? next : home); } catch (e) { setError(e); } finally { setBusy(false); }
  }

  return (
    <div className="mx-auto max-w-sm space-y-6">
      <h1 className="text-2xl font-semibold">Log in</h1>
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); void run(() => login(email, password)); }}>
        <div className="space-y-1"><Label htmlFor="email">Email</Label><Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></div>
        <div className="space-y-1"><Label htmlFor="password">Password</Label><Input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} /></div>
        {error != null && <ErrorMsg error={error} />}
        <Button className="w-full" disabled={busy}>Log in</Button>
      </form>
      <p className="text-sm">No account? <Link className="text-primary underline" to="/signup">Sign up</Link></p>
    </div>
  );
}
