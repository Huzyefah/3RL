"use client";
import { useCallback, useEffect, useRef, useState } from "react";

export function usePoll<T>(path: string | null, ms = 1500) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const alive = useRef(true);
  const load = useCallback(async () => {
    if (!path) return;
    try {
      const r = await fetch(`/api${path}`, { cache: "no-store" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = (await r.json()) as T;
      if (alive.current) { setData(j); setError(null); }
    } catch (e) {
      if (alive.current) setError(e instanceof Error ? e.message : "error");
    }
  }, [path]);
  useEffect(() => {
    alive.current = true;
    const first = setTimeout(load, 0);
    const id = setInterval(load, ms);
    return () => { alive.current = false; clearTimeout(first); clearInterval(id); };
  }, [load, ms]);
  return { data, error, reload: load };
}

export async function post(path: string, body?: unknown): Promise<{ ok: boolean; status: number }> {
  try {
    const r = await fetch(`/api${path}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    return { ok: r.ok, status: r.status };
  } catch {
    return { ok: false, status: 0 };
  }
}
