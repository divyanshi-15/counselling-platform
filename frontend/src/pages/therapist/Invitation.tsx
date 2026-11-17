import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Avatar } from "@/components/Avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorMsg, Loading } from "@/components/states";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { clearInvite, pendingInvite, rememberInvite } from "@/lib/invite";
import type { Schemas } from "../client/common";

type Preview = Schemas["InvitePreviewOut"];

function Frame({ children }: { children: React.ReactNode }) {
  return <div className="mx-auto max-w-md"><Card><CardHeader><CardTitle>Practice invitation</CardTitle></CardHeader><CardContent className="space-y-4">{children}</CardContent></Card></div>;
}

export default function Invitation() {
  const { user, loading } = useAuth();
  const [token] = useState(() => {
    const fromUrl = new URLSearchParams(window.location.hash.replace(/^#/, "")).get("token");
    if (fromUrl) { rememberInvite(fromUrl); history.replaceState(null, "", window.location.pathname); }  // keep the secret out of the address bar and history
    return fromUrl ?? pendingInvite();
  });
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<"accepted" | "declined" | null>(null);
  const isTherapist = user?.role === "therapist";

  useEffect(() => {
    if (!token || !isTherapist) return;
    api<Preview>("/invitations/preview", { method: "POST", json: { token } }).then(setPreview).catch(setError);
  }, [token, isTherapist]);

  async function decide(what: "accept" | "decline") {
    setBusy(true); setError(null);
    try {
      await api(`/invitations/${what}`, { method: "POST", json: { token } });
      clearInvite();
      setOutcome(what === "accept" ? "accepted" : "declined");
    } catch (e) { setError(e); } finally { setBusy(false); }
  }

  if (loading) return <Loading />;
  if (!token) return <Frame><p>This page needs the link from your invitation email.</p></Frame>;
  if (!user) {
    return (
      <Frame>
        <p>You have been invited to join a practice on Samvaad Care. Log in or sign up with the email address the invitation was sent to, then come back here to accept.</p>
        <div className="flex gap-2"><Button asChild><Link to="/login">Log in</Link></Button><Button variant="outline" asChild><Link to="/signup?role=therapist">Sign up</Link></Button></div>
      </Frame>
    );
  }
  if (!isTherapist) {
    return <Frame><p>Invitations are for therapist accounts. Log out and sign in with the therapist account the invitation was sent to.</p></Frame>;
  }
  if (outcome) {
    return (
      <Frame>
        <p role="status">{outcome === "accepted" ? "You have joined the practice. Your profile stays unlisted until it is verified." : "You declined the invitation."}</p>
        <Button asChild><Link to={outcome === "accepted" ? "/therapist/profile" : "/therapist"}>{outcome === "accepted" ? "Complete your profile" : "Go to my space"}</Link></Button>
      </Frame>
    );
  }
  if (error != null && !preview) return <Frame><ErrorMsg error={error} /><Button variant="outline" asChild><Link to="/therapist">Go to my space</Link></Button></Frame>;
  if (!preview) return <Frame><Loading /></Frame>;
  return (
    <Frame>
      <div className="flex items-center gap-3"><Avatar name={preview.practice_name} size={44} />
        <div><p className="font-semibold">{preview.practice_name}</p>{preview.city && <p className="text-sm text-muted-foreground">{preview.city}</p>}</div></div>
      <p className="text-sm">{preview.practice_name} invited <span className="font-medium">{preview.invited_email}</span> to join their team as a therapist. Accepting links your profile to this practice. Your clients and notes stay private to you.</p>
      <p className="text-xs text-muted-foreground">This invitation expires {new Date(preview.expires_at).toLocaleDateString([], { dateStyle: "medium" })}.</p>
      {error != null && <ErrorMsg error={error} />}
      <div className="flex gap-2"><Button disabled={busy} onClick={() => void decide("accept")}>Accept invitation</Button><Button variant="outline" disabled={busy} onClick={() => void decide("decline")}>Decline</Button></div>
    </Frame>
  );
}
