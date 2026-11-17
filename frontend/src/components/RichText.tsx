import { useRef } from "react";
import { Bold, Heading2, Italic, List } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";

/** Small, safe subset: blank-line paragraphs, "## " headings, "- " bullets, **bold**, *italic*. Rendered as React nodes, never as HTML. */
function inline(text: string): React.ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g).filter(Boolean).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") && part.length > 4 ? <strong key={i}>{part.slice(2, -2)}</strong>
      : part.startsWith("*") && part.endsWith("*") && part.length > 2 ? <em key={i}>{part.slice(1, -1)}</em> : part);
}

export function RichText({ text, className = "" }: { text: string; className?: string }) {
  const blocks = text.replace(/\r/g, "").split(/\n{2,}/).map((b) => b.trim()).filter(Boolean);
  return (
    <div className={`space-y-3 ${className}`}>
      {blocks.map((block, i) => {
        const lines = block.split("\n");
        if (lines.every((l) => l.startsWith("- "))) {
          return <ul key={i} className="list-disc space-y-1 pl-5">{lines.map((l, j) => <li key={j}>{inline(l.slice(2))}</li>)}</ul>;
        }
        if (block.startsWith("## ")) return <h3 key={i} className="text-base font-semibold">{inline(block.slice(3))}</h3>;
        return <p key={i}>{lines.map((l, j) => <span key={j}>{j > 0 && <br />}{inline(l)}</span>)}</p>;
      })}
    </div>
  );
}

export function RichEditor({ id, value, onChange, disabled, label }: { id: string; value: string; onChange: (v: string) => void; disabled?: boolean; label: string }) {
  const ref = useRef<HTMLTextAreaElement>(null);
  function edit(fn: (sel: string) => string, placeholder: string) {
    const el = ref.current;
    if (!el) return;
    const [a, b] = [el.selectionStart, el.selectionEnd];
    const next = value.slice(0, a) + fn(value.slice(a, b) || placeholder) + value.slice(b);
    onChange(next);
    requestAnimationFrame(() => el.focus());
  }
  const bullets = (s: string) => s.split("\n").map((l) => (l.startsWith("- ") ? l : `- ${l}`)).join("\n");
  const tools = [
    { icon: Bold, label: "Bold", run: () => edit((s) => `**${s}**`, "bold text") },
    { icon: Italic, label: "Italic", run: () => edit((s) => `*${s}*`, "italic text") },
    { icon: Heading2, label: "Heading", run: () => edit((s) => `\n\n## ${s}\n\n`, "Heading") },
    { icon: List, label: "Bulleted list", run: () => edit((s) => `\n\n${bullets(s)}\n\n`, "List item") },
  ];
  return (
    <div className="space-y-1">
      <div role="toolbar" aria-label={`${label} formatting`} className="flex gap-1">
        {tools.map(({ icon: Icon, label: l, run }) => (
          <Button key={l} type="button" variant="outline" className="h-8 w-8 px-0" disabled={disabled} aria-label={l} title={l} onClick={run}><Icon className="h-4 w-4" /></Button>
        ))}
      </div>
      <Textarea ref={ref} id={id} aria-label={label} rows={10} maxLength={5000} disabled={disabled} value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}
