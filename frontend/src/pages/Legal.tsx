import { useLocation } from "react-router-dom";

const Section = ({ h, children }: { h: string; children: React.ReactNode }) => <section className="space-y-1"><h2 className="text-lg font-semibold">{h}</h2><div className="space-y-2 text-sm text-muted-foreground">{children}</div></section>;

function Safety() {
  return (<>
    <h1 className="text-2xl font-semibold">Safety and crisis resources</h1>
    <Section h="If you are in crisis">
      <p><strong className="text-foreground">Call Tele-MANAS on 14416</strong>, the government of India's free tele-mental-health service, available around the clock in many languages.</p>
      <p>If you or someone near you is in immediate danger, contact local emergency services right away.</p>
    </Section>
    <Section h="What this platform is">
      <p>Samvaad Care offers skill-building support alongside sessions with a qualified therapist. It is not a replacement for therapy and is not an emergency service.</p>
    </Section>
    <Section h="How we screen for risk">
      <p>Text that clients write is screened for signs of crisis in English and Hindi, without using an AI model. If a match is found, you see a fixed message with the Tele-MANAS number and your therapist is alerted with high priority.</p>
    </Section>
  </>);
}

function Privacy() {
  return (<>
    <h1 className="text-2xl font-semibold">Privacy</h1>
    <Section h="What we collect"><p>Your account details, intake answers, check-ins, and notes your therapist records. Practices and therapists provide their public profile details.</p></Section>
    <Section h="Who can see it">
      <p>Clients see only their own records. Therapists see only the clients they work with. Practice owners manage listings and never see clinical records. Public pages never show client information.</p>
    </Section>
    <Section h="How it is protected"><p>Data is encrypted in transit and passwords are hashed. Sign-in uses secure, httpOnly cookies.</p></Section>
    <Section h="AI assistance">
      <p>AI tools draft summaries and suggestions for therapists. Nothing reaches you until a person approves it, and client text is wrapped as data so it cannot give instructions to the model.</p>
    </Section>
    <Section h="Your choices"><p>You can ask your practice to correct or delete your records at any time.</p></Section>
  </>);
}

function Terms() {
  return (<>
    <h1 className="text-2xl font-semibold">Terms of use</h1>
    <Section h="Using the service"><p>You must give accurate information and keep your sign-in details private. You may use Samvaad Care only for lawful purposes.</p></Section>
    <Section h="Not emergency care"><p>The platform is not an emergency service and does not replace therapy. In a crisis, call Tele-MANAS on 14416.</p></Section>
    <Section h="Therapists and practices"><p>Practices and therapists are independent professionals. A verified badge means our team has checked their listing details, not that we guarantee any outcome.</p></Section>
    <Section h="Bookings"><p>Sessions are agreed between you and your therapist. Please cancel in good time if you cannot attend.</p></Section>
    <Section h="AI features"><p>AI output is a draft for a human to review. It does not provide diagnoses or medical advice.</p></Section>
  </>);
}

export default function Legal() {
  const { pathname } = useLocation();
  return <div className="mx-auto max-w-2xl space-y-5">{pathname === "/privacy" ? <Privacy /> : pathname === "/terms" ? <Terms /> : <Safety />}</div>;
}
