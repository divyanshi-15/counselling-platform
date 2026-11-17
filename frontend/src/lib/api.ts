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

type S = components["schemas"];
export type PracticePage = S["PublicPracticePage"];
export type PracticeItem = S["PublicPractice"] & { status?: string };
export type TherapistItem = S["PublicTherapist"];
