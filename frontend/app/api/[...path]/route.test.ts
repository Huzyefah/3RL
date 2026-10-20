import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GET, POST, dynamic, runtime } from "./route";

const ctx = (...path: string[]) => ({ params: Promise.resolve({ path }) });
const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  delete process.env.API_INTERNAL_URL;
});
afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllGlobals();
});

describe("D2 proxy route handler", () => {
  it("exports force-dynamic / nodejs", () => {
    expect(dynamic).toBe("force-dynamic");
    expect(runtime).toBe("nodejs");
  });

  it("forwards method, path, query, signal and headers minus hop-by-hop", async () => {
    fetchMock.mockResolvedValue(new Response("ok", { headers: { "x-up": "1" } }));
    const req = new Request("http://web/api/runs/1/events?x=2", {
      headers: {
        "Last-Event-ID": "42",
        Authorization: "Bearer t",
        Connection: "keep-alive, x-private",
        "X-Private": "drop",
        "Keep-Alive": "timeout=5",
      },
    });
    const res = await GET(req, ctx("runs", "1", "events"));
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8080/runs/1/events?x=2");
    expect(init.method).toBe("GET");
    expect(init.signal).toBe(req.signal);
    const h = init.headers as Headers;
    expect(h.get("last-event-id")).toBe("42");
    expect(h.get("authorization")).toBe("Bearer t");
    expect(h.get("connection")).toBeNull();
    expect(h.get("keep-alive")).toBeNull();
    expect(h.get("x-private")).toBeNull();
    expect(res.headers.get("x-up")).toBe("1");
  });

  it("uses API_INTERNAL_URL and forwards POST bodies", async () => {
    process.env.API_INTERNAL_URL = "http://api:9000/";
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    const req = new Request("http://web/api/x", { method: "POST", body: "hi" });
    const res = await POST(req, ctx("x"));
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api:9000/x");
    expect(init.method).toBe("POST");
    expect(init.body).toBeTruthy();
    expect(res.status).toBe(204);
  });

  it("sets SSE headers and passes the stream through untouched", async () => {
    const body = new ReadableStream();
    fetchMock.mockResolvedValue(
      new Response(body, {
        headers: { "content-type": "text/event-stream", Connection: "keep-alive" },
      }),
    );
    const res = await GET(new Request("http://web/api/s"), ctx("s"));
    expect(res.headers.get("cache-control")).toBe("no-cache, no-transform");
    expect(res.headers.get("x-accel-buffering")).toBe("no");
    expect(res.headers.get("connection")).toBeNull();
    expect(res.body).toBe(body);
  });

  it("does not add SSE headers to other content types", async () => {
    fetchMock.mockResolvedValue(Response.json({ a: 1 }));
    const res = await GET(new Request("http://web/api/j"), ctx("j"));
    expect(res.headers.get("x-accel-buffering")).toBeNull();
  });

  it("returns 502 when upstream is down", async () => {
    fetchMock.mockRejectedValue(new Error("boom"));
    const res = await GET(new Request("http://web/api/j"), ctx("j"));
    expect(res.status).toBe(502);
  });
});
