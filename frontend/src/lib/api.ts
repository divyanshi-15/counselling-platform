import type { components } from "@/api/schema";

export type User = components["schemas"]["UserOut"];

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown; params?: Record<string, string | number | undefined> } = {}): Promise<T> {
  const { json, params, headers, ...rest } = init;
  const qs = params
    ? "?" + new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)])).toString()
    : "";
  const res = await fetch(`/api${path}${qs.length > 1 ? qs : ""}`, {
    credentials: "include",
    ...rest,
    headers: { ...(json !== undefined ? { "Content-Type": "application/json" } : {}), ...headers },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch { /* non-JSON error body */ }
    throw new ApiError(res.status, res.status === 503 ? "AI unavailable, manual workflow open" : detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export interface PracticePage {
  tagline?: string; about?: string; location?: string;
  services?: { title: string; description: string }[];
  faq?: { question: string; answer: string }[];
  what_to_expect?: string[];
  languages?: string[]; specialties?: string[]; approaches?: string[];
  fee_range?: string; session_type?: string;
}
export interface PracticeItem { id: number; name: string; slug: string; verified: boolean; page: PracticePage }
export interface TherapistItem { id: number; name: string | null; bio: string | null; approaches: string[] | null; languages: string[] | null; fee: number | null }
