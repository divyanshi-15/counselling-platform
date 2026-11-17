import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { homeFor, useAuth } from "@/lib/auth";

const ROLES = [["client", "Client"], ["therapist", "Therapist"], ["practice_owner", "Owner"]] as const;
const KEY = "presenter";

export function usePresenter(): boolean {
  const [params] = useSearchParams();
  if (params.get("present") === "1") sessionStorage.setItem(KEY, "1");
  if (params.get("present") === "0") sessionStorage.removeItem(KEY);
  return sessionStorage.getItem(KEY) === "1";
}

export function PresenterBar() {
  const { user, demoLogin, logout } = useAuth();
  const nav = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function switchTo(role: string) {
    setBusy(true); setError("");
    try {
      if (user) await logout();
      nav(homeFor((await demoLogin(role)).role));
    } catch { setError(`Could not sign in as ${role}`); } finally { setBusy(false); }
  }

  return (
    <div role="toolbar" aria-label="Presenter" className="flex flex-wrap items-center gap-1 border-b bg-muted px-3 py-1 text-xs">
      <span className="mr-1 text-muted-foreground">View as</span>
      {ROLES.map(([role, label]) => (
        <button key={role} disabled={busy} onClick={() => void switchTo(role)}
          className={`rounded px-2 py-0.5 ${user?.role === role ? "bg-primary text-primary-foreground" : "hover:bg-border"}`}>{label}</button>
      ))}
      {error && <span role="alert" className="ml-2 text-destructive">{error}</span>}
    </div>
  );
}
