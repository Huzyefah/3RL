// Server-only helpers for the same-origin proxy to the private sentinel-api. Never import from client code.
import "server-only";

export const API_URL = (process.env.SENTINEL_API_URL ?? "http://localhost:8080").replace(/\/$/, "");

// On Cloud Run (K_SERVICE is set) sentinel-api is private: attach a Google ID token minted by the metadata server.
let cached: { token: string; exp: number } | null = null;

async function idToken(): Promise<string | null> {
  if (!process.env.K_SERVICE) return null;
  if (cached && cached.exp > Date.now()) return cached.token;
  const res = await fetch(
    `http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience=${encodeURIComponent(API_URL)}`,
    { headers: { "Metadata-Flavor": "Google" }, cache: "no-store" },
  );
  if (!res.ok) throw new Error(`metadata identity ${res.status}`);
  cached = { token: await res.text(), exp: Date.now() + 45 * 60_000 };
  return cached.token;
}

// Forwards only safe headers. Mutating requests carry the operator token, which lives only on the server.
export async function upstreamHeaders(req?: Request): Promise<Headers> {
  const h = new Headers();
  if (req) {
    for (const name of ["content-type", "accept", "last-event-id"]) {
      const v = req.headers.get(name);
      if (v) h.set(name, v);
    }
    if (req.method !== "GET" && req.method !== "HEAD" && process.env.OPERATOR_TOKEN) {
      h.set("x-operator-token", process.env.OPERATOR_TOKEN);
    }
  }
  const token = await idToken();
  if (token) h.set("authorization", `Bearer ${token}`);
  return h;
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = await upstreamHeaders();
  return fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store" });
}
