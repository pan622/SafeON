// Use a same-origin path by default. During local/LAN development Vite proxies
// /api to the Python backend, so browsers on other machines never try to call
// their own 127.0.0.1. NEXT_PUBLIC_API_BASE remains available for deployments
// that intentionally use a separate API origin.
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "/api/v1";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data?.detail;
    const error = new Error(detail?.message || detail || "请求失败") as Error & { code?: string };
    error.code = detail?.code;
    throw error;
  }
  return data as T;
}

export type Job = {
  job_id: string; status: string; progress: number; stage_message: string;
  error?: { code: string; message: string } | null;
  result?: Record<string, unknown> | null; download_url?: string | null;
};
