import { Avatar } from "@/components/Avatar";
import { useEffect } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { homeFor, useAuth } from "@/lib/auth";
import { Footer } from "@/components/Footer";
import { Wordmark } from "@/components/Wordmark";

export const CRISIS_NOTICE = "If you are in crisis or thinking of harming yourself, call Tele-MANAS 14416 now.";
export const SUPPORT_NOTICE = "This is skill-building support, not a replacement for therapy.";

const TITLES: [string, string][] = [["/login", "Log in"], ["/signup", "Sign up"], ["/p/", "Practice"], ["/client", "My space"], ["/therapist", "Therapist"], ["/owner", "Practice owner"], ["/admin", "Admin"], ["/directory", "Find a therapist"], ["/therapists/", "Therapist profile"], ["/privacy", "Privacy"], ["/terms", "Terms"], ["/safety", "Safety"]];

export function Layout() {
  const { pathname } = useLocation();
  useEffect(() => {
    const hit = TITLES.find(([p]) => pathname.startsWith(p));
    document.title = hit ? `${hit[1]} · Samvaad Care` : "Samvaad Care";
  }, [pathname]);
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b">
        <div className="mx-auto max-w-5xl flex items-center justify-between gap-2 px-4 h-14">
          <Link to="/" aria-label="Samvaad Care home"><Wordmark /></Link>
          <nav className="flex items-center gap-2 text-sm">
            {user ? (
              <>
                <Button variant="ghost" asChild><Link to={homeFor(user.role)} className="gap-2"><Avatar name={user.name} size={24} />My space</Link></Button>
                <Button variant="outline" onClick={() => void logout()}>Log out</Button>
              </>
            ) : (
              <>
                <Button variant="ghost" asChild><Link to="/directory">Find a therapist</Link></Button>
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
      <Footer />
    </div>
  );
}
