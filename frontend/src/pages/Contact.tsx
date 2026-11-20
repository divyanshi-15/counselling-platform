import { ContactForm } from "@/components/ContactForm";
import { CRISIS_NOTICE } from "@/components/Layout";

export default function Contact() {
  return (
    <div className="mx-auto max-w-xl space-y-4">
      <h1 className="text-2xl font-semibold">Contact us</h1>
      <p className="text-sm text-muted-foreground">Questions about Saarthi, your practice or your account? Write to us and we will reply by email. / सारथी के बारे में कोई सवाल? हमें लिखें, हम ईमेल से जवाब देंगे।</p>
      <p role="note" className="rounded-md border bg-muted/50 p-3 text-sm font-medium">{CRISIS_NOTICE} / अगर आप संकट में हैं, तो अभी Tele-MANAS 14416 पर कॉल करें।</p>
      <div className="relative"><ContactForm /></div>
    </div>
  );
}
