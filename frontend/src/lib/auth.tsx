import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError, type User } from "./api";

interface AuthState {
  user: User | null; loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);
export const useAuth = () => {
  const v = useContext(Ctx);
  if (!v) throw new Error("AuthProvider missing");
  return v;
};

export const homeFor = (role: string) =>
  ({ client: "/client", therapist: "/therapist", practice_owner: "/owner", admin: "/admin" })[role] ?? "/";

/** Therapists whose credentials are still open land on the profile page; everyone else on their usual home. */
export async function landingFor(role: string): Promise<string> {
  if (role === "therapist") {
    try {
      const p = await api<{ verification_status: string }>("/therapists/me/profile");
      if (p.verification_status === "draft" || p.verification_status === "changes_requested") return "/therapist/profile";
    } catch { /* fall back to the dashboard */ }
  }
  return homeFor(role);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<User>("/auth/me")
      .then(setUser)
      .catch((e) => { if (!(e instanceof ApiError && e.status === 401)) console.error(e); })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const r = await api<{ user: User }>("/auth/login", { method: "POST", json: { email, password } });
    setUser(r.user);
    return r.user;
  }, []);
  const logout = useCallback(async () => {
    await api("/auth/logout", { method: "POST" });
    setUser(null);
  }, []);

  return <Ctx.Provider value={{ user, loading, login, logout }}>{children}</Ctx.Provider>;
}
