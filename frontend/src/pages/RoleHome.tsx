import { Navigate } from "react-router-dom";
import { Loading } from "@/components/states";
import { homeFor, useAuth } from "@/lib/auth";

// Signed-in landing; role screens are added in later frontend stages.
export default function RoleHome() {
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  return (
    <div className="space-y-2">
      <h1 className="text-2xl font-semibold">Welcome, {user.name ?? user.email}</h1>
      <p className="text-muted-foreground">Signed in as {user.role}. Workspace: {homeFor(user.role)}</p>
    </div>
  );
}
