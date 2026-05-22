import { buildAuthHeaders } from "@/lib/auth";

export async function apiFetch(input: RequestInfo, init: RequestInit = {}, token?: string) {
  const headers = buildAuthHeaders(token || "", init.headers);
  return fetch(input, { ...init, headers });
}
