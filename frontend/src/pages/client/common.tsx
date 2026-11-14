import type { components } from "@/api/schema";
import { Navigate } from "react-router-dom";
import { Loading } from "@/components/states";
import { useAuth } from "@/lib/auth";

export function RequireClient({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== "client") return <Navigate to="/" replace />;
  return <>{children}</>;
}

export function CrisisBox({ message }: { message: string }) {
  return (
    <div role="alert" className="rounded-md border-2 border-destructive bg-destructive/5 p-5 text-lg font-medium text-destructive">
      {message}
    </div>
  );
}

export const fmt = (iso: string) => new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });

export type Schemas = components["schemas"];
