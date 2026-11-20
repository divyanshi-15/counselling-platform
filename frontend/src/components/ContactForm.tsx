import { Loader2 } from "lucide-react";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import type { components } from "@/api/schema";

type Lang = "en" | "hi";
type Out = components["schemas"]["ContactOut"];
const MAX = 1500;
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

const T = {
  en: { name: "Your name", email: "Email address", message: "Message", send: "Send message", sending: "Sending…", left: "characters left",
        fixName: "Please enter your name.", fixEmail: "Please enter a valid email address.", fixMessage: "Please write a message.",
        error: "We could not send your message. Please try again in a moment.", wait: "Too many messages from this device. Please try again later.",
        again: "Send another message", thanks: "Thank you" },
  hi: { name: "आपका नाम", email: "ईमेल पता", message: "संदेश", send: "संदेश भेजें", sending: "भेजा जा रहा है…", left: "अक्षर बाकी",
        fixName: "कृपया अपना नाम लिखें।", fixEmail: "कृपया सही ईमेल पता लिखें।", fixMessage: "कृपया संदेश लिखें।",
        error: "आपका संदेश भेजा नहीं जा सका। कृपया थोड़ी देर बाद फिर कोशिश करें।", wait: "इस डिवाइस से बहुत संदेश आ चुके हैं। कृपया बाद में कोशिश करें।",
        again: "एक और संदेश भेजें", thanks: "धन्यवाद" },
} as const;

export function ContactForm() {
  const [lang, setLang] = useState<Lang>(useLang());
  const t = T[lang];
  const [f, setF] = useState({ name: "", email: "", message: "", website: "" });
  const [errs, setErrs] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Out | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const key = useRef(crypto.randomUUID());  // one key per message, so a retry after a network error never duplicates it

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const next: Record<string, string> = {};
    if (!f.name.trim()) next.name = t.fixName;
    if (!EMAIL.test(f.email.trim())) next.email = t.fixEmail;
    if (!f.message.trim()) next.message = t.fixMessage;
    setErrs(next);
    if (Object.keys(next).length) return;
    setBusy(true); setFailure(null);
    try {
      setResult(await api<Out>("/contact", { method: "POST", headers: { "Idempotency-Key": key.current }, json: { ...f, language: lang } }));
    } catch (err) {
      setFailure(err instanceof Error && "status" in err && err.status === 429 ? t.wait : t.error);
    } finally { setBusy(false); }
  }

  if (result) {
    const crisis = result.status === "crisis";
    return (
      <div role="status" className={`space-y-3 rounded-md border p-4 text-sm ${crisis ? "border-destructive/40 bg-destructive/5" : "bg-muted/40"}`}>
        {!crisis && <p className="font-medium">{t.thanks}</p>}
        <p>{result.message}</p>
        {!crisis && <Button variant="outline" onClick={() => { setResult(null); setF({ name: "", email: "", message: "", website: "" }); key.current = crypto.randomUUID(); }}>{t.again}</Button>}
      </div>
    );
  }

  const field = "space-y-1";
  const err = (k: string) => errs[k] && <p id={`c-${k}-err`} role="alert" className="text-xs text-destructive">{errs[k]}</p>;
  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <div className="flex justify-end gap-1 text-xs" role="group" aria-label="Language">
        {(["en", "hi"] as Lang[]).map((l) => (
          <button key={l} type="button" aria-pressed={lang === l} onClick={() => setLang(l)}
            className={`rounded px-2 py-1 ${lang === l ? "bg-primary text-primary-foreground" : "border text-muted-foreground"}`}>{l === "en" ? "English" : "हिन्दी"}</button>
        ))}
      </div>
      <div className={field}><Label htmlFor="c-name">{t.name}</Label>
        <Input id="c-name" autoComplete="name" maxLength={100} value={f.name} aria-invalid={!!errs.name} aria-describedby={errs.name ? "c-name-err" : undefined} onChange={(e) => setF({ ...f, name: e.target.value })} />{err("name")}</div>
      <div className={field}><Label htmlFor="c-email">{t.email}</Label>
        <Input id="c-email" type="email" autoComplete="email" maxLength={254} value={f.email} aria-invalid={!!errs.email} aria-describedby={errs.email ? "c-email-err" : undefined} onChange={(e) => setF({ ...f, email: e.target.value })} />{err("email")}</div>
      <div className={field}><Label htmlFor="c-message">{t.message}</Label>
        <textarea id="c-message" rows={6} maxLength={MAX} value={f.message} aria-invalid={!!errs.message} aria-describedby={errs.message ? "c-message-err" : undefined}
          className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          onChange={(e) => setF({ ...f, message: e.target.value })} />
        <p className="text-right text-xs text-muted-foreground">{MAX - f.message.length} {t.left}</p>{err("message")}</div>
      <div aria-hidden="true" className="absolute -left-[9999px] h-0 w-0 overflow-hidden">
        <label>Website<input tabIndex={-1} autoComplete="off" name="website" value={f.website} onChange={(e) => setF({ ...f, website: e.target.value })} /></label>
      </div>
      {failure && <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">{failure}</p>}
      <Button type="submit" disabled={busy} className="w-full sm:w-auto">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}{busy ? t.sending : t.send}</Button>
    </form>
  );
}
