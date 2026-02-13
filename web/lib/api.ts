export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || "";
}

export async function apiFetch(path: string, options: RequestInit = {}) {
  const headers: HeadersInit = { "Content-Type": "application/json", ...(options.headers || {}) };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const resp = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!resp.ok) throw new Error(await resp.text());
  return resp;
}
