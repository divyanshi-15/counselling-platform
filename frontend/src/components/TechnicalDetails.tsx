/** Collapsed raw payload for debugging; never the primary display. */
export function TechnicalDetails({ data, label = "Technical details" }: { data: unknown; label?: string }) {
  let text = "";
  try { text = typeof data === "string" ? data : JSON.stringify(data, null, 2) ?? ""; } catch { text = ""; }
  if (!text) return null;
  return (
    <details className="text-xs text-muted-foreground">
      <summary className="cursor-pointer select-none">{label}</summary>
      <pre className="mt-1 max-h-60 overflow-auto whitespace-pre-wrap break-words rounded bg-muted p-2">{text}</pre>
    </details>
  );
}
