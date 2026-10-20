import type { NextRequest } from "next/server";
import { API_URL, upstreamHeaders } from "@/lib/upstream";

// Same-origin proxy: /api/<path> → ${SENTINEL_API_URL}/<path>. Streams bodies through, so SSE works.
async function proxy(req: NextRequest, ctx: RouteContext<"/api/[...path]">): Promise<Response> {
  const { path } = await ctx.params;
  const url = `${API_URL}/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: req.method,
      headers: await upstreamHeaders(req),
      body: hasBody ? await req.arrayBuffer() : undefined,
      cache: "no-store",
      signal: req.signal,
    });
  } catch {
    return Response.json({ error: "upstream_unreachable" }, { status: 502 });
  }
  const headers = new Headers();
  for (const name of ["content-type", "cache-control"]) {
    const v = upstream.headers.get(name);
    if (v) headers.set(name, v);
  }
  if (headers.get("content-type")?.startsWith("text/event-stream")) {
    headers.set("cache-control", "no-cache, no-transform");
    headers.set("x-accel-buffering", "no");
  }
  return new Response(upstream.body, { status: upstream.status, headers });
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as DELETE };
