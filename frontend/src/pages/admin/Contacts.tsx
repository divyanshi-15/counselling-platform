import { Link } from "react-router-dom";
import { PageHeader } from "@/components/PageHeader";
import { Empty, ErrorMsg, Loading } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { useFetch } from "@/lib/useFetch";
import type { Schemas } from "../client/common";
import { fmt } from "../client/common";
import { RequireAdmin } from "./Admin";

const DELIVERY: Record<string, string> = { sent: "Emailed", failed: "Email failed", not_configured: "Email not set up", skipped: "Not emailed (safety)", pending: "Pending" };

function List() {
  const { data, error, loading } = useFetch<Schemas["ContactMessageOut"][]>("/admin/contact-messages");
  return (
    <div className="space-y-4">
      <div>
        <PageHeader title="Contact messages" />
        <p className="text-sm text-muted-foreground">Messages from the public contact form. High-priority messages matched the safety check and are listed first. <Link className="text-primary hover:underline" to="/admin">Back to verification queue</Link></p>
      </div>
      {loading && !data ? <Loading /> : error != null ? <ErrorMsg error={error} /> : !data?.length ? <Empty>No messages yet.</Empty> : (
        <ul className="space-y-3">
          {data.map((m) => (
            <li key={m.id} className={`rounded-md border p-4 text-sm ${m.high_priority ? "border-destructive/50 bg-destructive/5" : ""}`}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{m.name}</span>
                <a className="text-primary hover:underline break-all" href={`mailto:${m.email}`}>{m.email}</a>
                {m.high_priority && <Badge className="border-red-300 text-red-800">High priority</Badge>}
                <span className="ml-auto text-xs text-muted-foreground">{fmt(m.created_at)} · {DELIVERY[m.email_status] ?? m.email_status}</span>
              </div>
              <p className="mt-2 whitespace-pre-wrap break-words">{m.message}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function Contacts() {
  return <RequireAdmin><List /></RequireAdmin>;
}
