const PALETTE = [
  ["#DCEDEA", "#1D5753"], ["#F8E3D8", "#8A3F1D"], ["#E8EEDD", "#3F5A1E"], ["#F6EBCB", "#6B4A0C"],
  ["#E3ECF0", "#2A5163"], ["#F1E2E6", "#7A2E45"], ["#E9E5F2", "#4A3A7A"], ["#EFE9DC", "#5A4A2A"],
];

export function initials(name: string): string {
  const parts = name.replace(/^(dr|mr|ms|mrs)\.?\s+/i, "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  return ((parts[0][0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

export function Avatar({ name, size = 36, className = "" }: { name?: string | null; size?: number; className?: string }) {
  const n = name?.trim() || "?";
  let h = 0;
  for (const c of n) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  const [bg, fg] = PALETTE[h % PALETTE.length];
  return (
    <span aria-hidden="true" className={`inline-flex shrink-0 items-center justify-center rounded-full font-medium select-none ${className}`}
      style={{ width: size, height: size, background: bg, color: fg, fontSize: size * 0.4 }}>
      {initials(n)}
    </span>
  );
}

export function NameWithAvatar({ name, size = 32, children }: { name?: string | null; size?: number; children?: React.ReactNode }) {
  return <span className="inline-flex items-center gap-2"><Avatar name={name} size={size} />{children ?? <span>{name}</span>}</span>;
}
