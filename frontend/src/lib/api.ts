/** Minimal typed client for the Aivanta API. */

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public status: number, public code: string, public details: Record<string, unknown> = {}) {
    super(code);
  }
}

export type TokenGetter = () => string | null;

export async function apiFetch<T>(path: string, token: string | null, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "network");
  }
  if (!res.ok) {
    let code = "unknown";
    let details: Record<string, unknown> = {};
    try {
      const body = await res.json();
      code = body?.error?.code ?? code;
      details = body?.error?.details ?? {};
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, code, details);
  }
  const type = res.headers.get("content-type") || "";
  return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

export async function downloadFile(path: string, token: string | null, filename: string): Promise<void> {
  const res = await fetch(`${API_URL}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) throw new ApiError(res.status, "unknown");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
