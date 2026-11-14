import { Link, Outlet } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { homeFor, useAuth } from "@/lib/auth";

export const CRISIS_NOTICE = "If you are in crisis or thinking of harming yourself, call Tele-MANAS 14416 now.";
export const SUPPORT_NOTICE = "This is skill-building support, not a replacement for therapy.";

export function Layout() {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen flex flex-col">
      <div role="note" className="bg-primary text-primary-foreground text-center text-sm py-1.5 px-3">
        Demo: use fictional information only.
      </div>
      <header className="border-b">
        <div className="mx-auto max-w-5xl flex items-center justify-between gap-2 px-4 h-14">
          <Link to="/" className="font-semibold">Counselling Platform</Link>
          <nav className="flex items-center gap-2 text-sm">
            {user ? (
              <>
                <Button variant="ghost" asChild><Link to={homeFor(user.role)}>My space</Link></Button>
                <Button variant="outline" onClick={() => void logout()}>Log out</Button>
              </>
            ) : (
              <>
                <Button variant="ghost" asChild><Link to="/login">Log in</Link></Button>
                <Button asChild><Link to="/signup">Sign up</Link></Button>
              </>
            )}
          </nav>
        </div>
      </header>
      {user?.role === "client" && (
        <div className="bg-muted border-b text-sm text-center px-4 py-2">
          <p className="font-medium">{CRISIS_NOTICE}</p>
          <p className="text-muted-foreground">{SUPPORT_NOTICE}</p>
        </div>
      )}
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
