const MARK = (
  <>
    <path d="M30 40 C14 34 5 25 5 16 C5 10 9.5 6.5 14.5 6.5 C19 6.5 22.5 9.5 24 13.5" fill="none" stroke="#2F7F79" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M18 40 C34 34 43 25 43 16 C43 10 38.5 6.5 33.5 6.5 C29 6.5 25.5 9.5 24 13.5" fill="none" stroke="#3E9A92" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round" />
    <circle cx="24" cy="21" r="3.6" fill="#D9825B" />
    <path d="M17.8 31 C19.5 25.6 28.5 25.6 30.2 31 Z" fill="#D9825B" />
  </>
);

/** The embrace mark alone. */
export function Mark({ className = "" }: { className?: string }) {
  return <svg role="img" aria-label="Saarthi" viewBox="0 0 48 48" className={`h-8 w-8 shrink-0 ${className}`}>{MARK}</svg>;
}

/** Mark + "Saarthi" text. `compact` shows the mark only; `onDark` switches the text to white. */
export function Wordmark({ className = "", compact = false, onDark = false }: { className?: string; compact?: boolean; onDark?: boolean }) {
  if (compact) return <Mark className={className} />;
  return (
    <span role="img" aria-label="Saarthi" className={`inline-flex items-center gap-2 ${className}`}>
      <svg aria-hidden="true" viewBox="0 0 48 48" className="h-8 w-8 shrink-0">{MARK}</svg>
      <span aria-hidden="true" className="text-[1.4rem] font-semibold leading-none tracking-tight"
        style={{ fontFamily: 'Georgia, "Times New Roman", serif', color: onDark ? "#fff" : "#1F2D2B" }}>Saarthi</span>
    </span>
  );
}
