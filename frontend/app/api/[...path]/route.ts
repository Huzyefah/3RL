// D2: same-origin streaming proxy from sentinel-web to sentinel-api.
// No proxy.ts / middleware.ts: they would sit in front of this and can buffer.
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
]);

function stripHopByHop(headers: Headers): Headers {
  const out = new Headers();
  // Headers named in Connection are also hop-by-hop.
  const extra = (headers.get("connection") ?? "")
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);
  headers.forEach((value, key) => {
    const k = key.toLowerCase();
    if (!HOP_BY_HOP.has(k) && !extra.includes(k)) out.set(key, value);
  });
  return out;
}

async function proxy(
  request: Request,
  ctx: { params: Promise<{ path: string[] }> },
): Promise<Response> {
  const base = (process.env.API_INTERNAL_URL ?? "http://localhost:8080").replace(/\/+$/, "");
  const { path } = await ctx.params;
  const search = new URL(request.url).search;
  const target = `${base}/${path.map(encodeURIComponent).join("/")}${search}`;

  const headers = stripHopByHop(request.headers); // includes Last-Event-ID
  const hasBody = !["GET", "HEAD"].includes(request.method);

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      signal: request.signal,
      redirect: "manual",
      cache: "no-store",
      // required by undici when streaming a request body
      ...(hasBody ? { duplex: "half" } : {}),
    } as RequestInit);
  } catch (err) {
    if (request.signal.aborted) return new Response(null, { status: 499 });
    return Response.json(
      { error: "upstream_unavailable", detail: (err as Error).message },
      { status: 502 },
    );
  }

  const respHeaders = stripHopByHop(upstream.headers);
  // fetch() already decoded the body; drop stale encoding headers.
  respHeaders.delete("content-encoding");
  const type = upstream.headers.get("content-type") ?? "";
  if (type.toLowerCase().startsWith("text/event-stream")) {
    respHeaders.set("Cache-Control", "no-cache, no-transform");
    respHeaders.set("X-Accel-Buffering", "no");
    respHeaders.delete("connection");
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: respHeaders,
  });
}

export {
  proxy as GET,
  proxy as POST,
  proxy as PUT,
  proxy as PATCH,
  proxy as DELETE,
  proxy as HEAD,
  proxy as OPTIONS,
};
