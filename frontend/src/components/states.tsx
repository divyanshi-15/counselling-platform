import { Loader2 } from "lucide-react";

export const Loading = () => (
  <p className="flex items-center gap-2 text-muted-foreground" role="status"><Loader2 className="h-4 w-4 animate-spin" /> Loading…</p>
);
export const Empty = ({ children }: { children: React.ReactNode }) => (
  <p className="rounded-md border border-dashed p-6 text-center text-muted-foreground">{children}</p>
);
export const ErrorMsg = ({ error }: { error: unknown }) => (
  <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
    {error instanceof Error ? error.message : "Something went wrong."}
  </p>
);
