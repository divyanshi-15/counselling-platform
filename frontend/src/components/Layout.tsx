import { Avatar } from "@/components/Avatar";
import { useEffect, useState } from "react";
import { Menu, X } from "lucide-react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { homeFor, useAuth } from "@/lib/auth";
import { Footer } from "@/components/Footer";
import { Mark, Wordmark } from "@/components/Wordmark";

export const CRISIS_NOTICE = "If you are in crisis or thinking of harming yourself, call Tele-MANAS 14416 now.";
export const SUPPORT_NOTICE = "This is skill-building support, not a replacement for therapy.";
const CRISIS_NOTICE_HI = "अगर आप संकट में हैं या खुद को नुकसान पहुँचाने के बारे में सोच रहे हैं, तो अभी Tele-MANAS 14416 पर कॉल करें।";
const SUPPORT_NOTICE_HI = "यह कौशल-निर्माण सहायता है, थेरेपी का विकल्प नहीं।";

const TITLES: [string, string][] = [["/login", "Log in"], ["/signup", "Sign up"], ["/p/", "Practice"], ["/client", "My space"], ["/therapist", "Therapist"], ["/owner", "Practice owner"], ["/admin", "Admin"], ["/directory", "Find a therapist"], ["/therapists/", "Therapist profile"], ["/privacy", "Privacy"], ["/terms", "Terms"], ["/safety", "Safety"], ["/contact", "Contact"]];

export function Layout() {
  const { pathname } = useLocation();
  useEffect(() => {
    const hit = TITLES.find(([p]) => pathname.startsWith(p));
    document.title = hit ? `${hit[1]} · Saarthi` : "Saarthi";
  }, [pathname]);
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const wide = pathname === "/" || pathname.startsWith("/directory") || pathname.startsWith("/p/");
  const box = wide ? "max-w-6xl" : "max-w-5xl";
  useEffect(() => setOpen(false), [pathname]);
  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-40 border-b bg-background/90 backdrop-blur">
        <div className={`mx-auto flex h-16 ${box} items-center justify-between gap-2 px-4 sm:px-6`}>
          <Link to="/" aria-label="Saarthi home"><Mark className="sm:hidden" /><Wordmark className="hidden sm:inline-flex" /></Link>
          {user ? (
            <nav className="flex items-center gap-2 text-sm">
              <Button variant="ghost" asChild><Link to={homeFor(user.role)} className="gap-2"><Avatar name={user.name} size={24} />My space</Link></Button>
              <Button variant="outline" onClick={() => void logout()}>Log out</Button>
            </nav>
          ) : (
            <>
              <nav className="hidden items-center gap-2 text-sm md:flex">
                <Button variant="ghost" asChild><Link to="/directory">Find a therapist</Link></Button>
                <Button variant="ghost" asChild><Link to="/login">Log in</Link></Button>
                <Button variant="accent" asChild><Link to="/signup">Sign up</Link></Button>
              </nav>
              <Button variant="ghost" className="px-2 md:hidden" aria-label={open ? "Close menu" : "Open menu"} aria-expanded={open} aria-controls="mobile-nav" onClick={() => setOpen((o) => !o)}>
                {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
              </Button>
            </>
          )}
        </div>
        {!user && open && (
          <nav id="mobile-nav" className={`mx-auto flex ${box} flex-col gap-1 border-t px-4 py-3 text-sm sm:px-6 md:hidden`}>
            <Button variant="ghost" className="justify-start" asChild><Link to="/directory">Find a therapist</Link></Button>
            <Button variant="ghost" className="justify-start" asChild><Link to="/login">Log in</Link></Button>
            <Button variant="accent" asChild><Link to="/signup">Sign up</Link></Button>
          </nav>
        )}
      </header>
      {user?.role === "client" && (
        <div className="border-b bg-primary-soft text-sm text-center px-4 py-2">
          <p className="font-medium">{user.language === "hi" ? CRISIS_NOTICE_HI : CRISIS_NOTICE}</p>
          <p className="text-muted-foreground">{user.language === "hi" ? SUPPORT_NOTICE_HI : SUPPORT_NOTICE}</p>
        </div>
      )}
      <main className={`mx-auto w-full ${box} flex-1 px-4 py-6 sm:px-6`}>
        <Outlet />
      </main>
      <Footer wide={wide} />
    </div>
  );
}
