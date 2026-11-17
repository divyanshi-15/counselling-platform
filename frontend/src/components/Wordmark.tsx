export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <svg role="img" aria-label="Samvaad Care" viewBox="0 0 168 32" className={`h-7 w-auto ${className}`}>
      <rect width="32" height="32" rx="8" fill="var(--primary)" />
      <path d="M9 11.5c0-1.7 1.3-3 3-3h8a3 3 0 0 1 3 3v6a3 3 0 0 1-3 3h-4l-4.5 3.5V20.5H12a3 3 0 0 1-3-3z" fill="#fff" />
      <text x="42" y="22.5" fontFamily="Inter Variable, Inter, system-ui, sans-serif" fontSize="19" fontWeight="650" fill="currentColor">
        Samvaad <tspan fill="var(--primary)">Care</tspan>
      </text>
    </svg>
  );
}
