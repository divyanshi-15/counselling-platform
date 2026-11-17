import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ErrorMsg } from "@/components/states";
import { api } from "@/lib/api";
import { homeFor, useAuth } from "@/lib/auth";

export default function Signup() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const preset = ({ therapist: "therapist", practice: "practice_owner", client: "client" } as Record<string, string>)[params.get("role") ?? ""] ?? "client";
  const [f, setF] = useState({ name: "", email: "", password: "", role: preset, language: "en" });
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      await api("/auth/register", { method: "POST", json: f });
      nav(homeFor((await login(f.email, f.password)).role));
    } catch (err) { setError(err); } finally { setBusy(false); }
  }

  return (
    <div className="mx-auto max-w-sm space-y-6">
      <h1 className="text-2xl font-semibold">Sign up</h1>
      <form className="space-y-3" onSubmit={submit}>
        <div className="space-y-1"><Label htmlFor="name">Name</Label><Input id="name" required value={f.name} onChange={set("name")} /></div>
        <div className="space-y-1"><Label htmlFor="email">Email</Label><Input id="email" type="email" required value={f.email} onChange={set("email")} /></div>
        <div className="space-y-1"><Label htmlFor="password">Password (8+ characters)</Label><Input id="password" type="password" minLength={8} required value={f.password} onChange={set("password")} /></div>
        <div className="space-y-1"><Label htmlFor="role">I am a</Label>
          <Select id="role" value={f.role} onChange={set("role")}>
            <option value="client">Client</option><option value="therapist">Therapist</option><option value="practice_owner">Practice owner</option>
          </Select></div>
        <div className="space-y-1"><Label htmlFor="language">Language</Label>
          <Select id="language" value={f.language} onChange={set("language")}>
            <option value="en">English</option><option value="hi">Hindi</option>
          </Select></div>
        {error != null && <ErrorMsg error={error} />}
        <Button className="w-full" disabled={busy}>Create account</Button>
      </form>
      <p className="text-sm">Have an account? <Link className="text-primary underline" to="/login">Log in</Link></p>
    </div>
  );
}
