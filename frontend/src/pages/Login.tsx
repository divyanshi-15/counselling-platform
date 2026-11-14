import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorMsg } from "@/components/states";
import { homeFor, useAuth } from "@/lib/auth";

const DEMO_ROLES = [["client", "Client"], ["therapist", "Therapist"], ["practice_owner", "Practice owner"], ["admin", "Admin"]] as const;

export default function Login() {
  const { login, demoLogin, config } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function run(fn: () => Promise<{ role: string }>) {
    setBusy(true); setError(null);
    try { nav(homeFor((await fn()).role)); } catch (e) { setError(e); } finally { setBusy(false); }
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
      {config.demo_mode && (
        <div className="space-y-2 rounded-md border p-3">
          <p className="text-sm font-medium">Demo login</p>
          <div className="grid grid-cols-2 gap-2">
            {DEMO_ROLES.map(([role, label]) => <Button key={role} variant="outline" disabled={busy} onClick={() => void run(() => demoLogin(role))}>{label}</Button>)}
          </div>
        </div>
      )}
    </div>
  );
}
