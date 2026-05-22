export function buildAuthHeaders(token: string, base?: HeadersInit): Headers {
  const headers = new Headers(base || {});

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  return headers;
}
