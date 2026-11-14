import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError, type User } from "./api";

interface Config { demo_mode: boolean }
interface AuthState {
  user: User | null; loading: boolean; config: Config;
  login: (email: string, password: string) => Promise<User>;
  demoLogin: (role: string) => Promise<User>;
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

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [config, setConfig] = useState<Config>({ demo_mode: false });

  useEffect(() => {
    api<Config>("/config").then(setConfig).catch(() => {});
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
  const demoLogin = useCallback(async (role: string) => {
    const r = await api<{ user: User }>("/auth/demo-login", { method: "POST", params: { role } });
    setUser(r.user);
    return r.user;
  }, []);
  const logout = useCallback(async () => {
    await api("/auth/logout", { method: "POST" });
    setUser(null);
  }, []);

  return <Ctx.Provider value={{ user, loading, config, login, demoLogin, logout }}>{children}</Ctx.Provider>;
}
