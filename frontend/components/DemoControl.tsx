"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useStream } from "@/lib/stream";
import { BandBadge, Chip, Icon, Panel } from "./ui";

type Episode = {
  id: string;
  kind: "incident" | "negative";
  code: string;
  service: string;
  metric: string;
  segment: string;
  onset: string;
  abrupt: boolean;
  lead_min: number;
  split: "train" | "test";
};
type Policy = { llm_mode: string; autonomy_mode: string; tau: number; autoplay: boolean; speed: number; now_playing: string | null };

const NEG_LABEL: Record<string, string> = {
  N1: "surge (benign)",
  N3: "batch job (benign)",
  N5: "transient spike",
  N6: "unexplained (no evidence)",
};
// Episodes that tell the story best, in pitch order.
const FEATURED = ["INC-PS02-0001", "NEG-PS02-0017", "INC-PS02-0020", "NEG-PS02-0010"];

async function call(path: string, init?: RequestInit) {
  const res = await fetch(`/api${path}`, { cache: "no-store", ...init });
  const body = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, body };
}

export function DemoControl() {
  const state = useStream();
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [msg, setMsg] = useState<string>("");
  const [filter, setFilter] = useState<"featured" | "test" | "all">("featured");

  const refresh = useCallback(async () => {
    const p = await call("/policy");
    if (p.ok) setPolicy(p.body);
  }, []);

  useEffect(() => {
    call("/demo/episodes").then((r) => r.ok && setEpisodes(r.body));
    const first = setTimeout(refresh, 0);
    const t = setInterval(refresh, 3000);
    return () => {
      clearTimeout(first);
      clearInterval(t);
    };
  }, [refresh]);

  const putPolicy = async (patch: Partial<Policy>) => {
    const r = await call("/policy", { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify(patch) });
    setMsg(r.ok ? `Policy updated: ${JSON.stringify(patch)}` : `Policy update failed (${r.status})`);
    refresh();
  };
  const replay = async (id: string) => {
    const r = await call(`/demo/replay?episode_id=${encodeURIComponent(id)}`, { method: "POST" });
    setMsg(r.ok ? `Replaying ${id} through the real detector → agents (autoplay paused). Watch Live Ops.` : `Replay refused (${r.status}): ${r.body?.detail ?? ""}`);
    refresh();
  };
  const reset = async () => {
    const r = await call("/demo/reset", { method: "POST" });
    setMsg(r.ok ? "Reset: incidents, actions and bank routing cleared." : `Reset failed (${r.status})`);
  };

  const shown = episodes.filter((e) => (filter === "featured" ? FEATURED.includes(e.id) : filter === "test" ? e.split === "test" : true));
  const playing = policy?.now_playing;

  return (
    <div className="mx-auto w-full max-w-7xl space-y-4 px-4 py-6">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Demo control</h1>
          <p className="text-sm text-muted">
            Replays real PS-02 episodes (synthetic replay between the 500 pinned CSV rows) through the live detector, agents and policy guard.
          </p>
        </div>
        {msg && (
          <p data-testid="demo-msg" className="rounded-md border border-line bg-surface-2 px-3 py-1.5 text-xs">
            {msg}
          </p>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Replay" icon={Icon.bolt()} testid="demo-replay" aside={playing ? <Chip tone="warn">Now playing {playing}</Chip> : <Chip tone="good">Idle</Chip>}>
          <div className="space-y-3 p-4 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-muted">Autoplay demo loop</span>
              <button
                type="button"
                data-testid="toggle-autoplay"
                onClick={() => putPolicy({ autoplay: !policy?.autoplay })}
                className="rounded-md border border-line-strong px-3 py-1 text-xs font-semibold hover:bg-surface-2"
              >
                {policy?.autoplay ? "On (pause)" : "Off (resume)"}
              </button>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-muted">Replay speed</span>
              <div className="flex gap-1">
                {[10, 20, 40, 80].map((s) => (
                  <button
                    key={s}
                    type="button"
                    data-testid={`speed-${s}`}
                    onClick={() => putPolicy({ speed: s })}
                    className={`rounded-md border px-2 py-1 text-xs font-semibold ${policy?.speed === s ? "border-foreground bg-foreground text-background" : "border-line-strong hover:bg-surface-2"}`}
                  >
                    {s}×
                  </button>
                ))}
              </div>
            </div>
            <button
              type="button"
              data-testid="demo-reset"
              onClick={reset}
              className="w-full rounded-md border border-line-strong px-3 py-1.5 text-xs font-semibold hover:bg-surface-2"
            >
              {Icon.x()} Reset incidents &amp; routing
            </button>
          </div>
        </Panel>

        <Panel title="Agents & safety" icon={Icon.shield()} testid="demo-policy">
          <div className="space-y-3 p-4 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-muted">LLM mode</span>
              <div className="flex gap-1">
                {["live", "off"].map((m) => (
                  <button
                    key={m}
                    type="button"
                    data-testid={`llm-${m}`}
                    onClick={() => putPolicy({ llm_mode: m })}
                    className={`rounded-md border px-2 py-1 text-xs font-semibold ${policy?.llm_mode === m ? "border-foreground bg-foreground text-background" : "border-line-strong hover:bg-surface-2"}`}
                  >
                    {m === "live" ? "Live (gpt-6-luna)" : "Off → fallback"}
                  </button>
                ))}
              </div>
            </div>
            <p className="text-xs text-muted">
              &ldquo;Off&rdquo; simulates an OpenAI outage: the runtime ships a deterministic statistical-fallback RCA and still pages (I7).
            </p>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-muted">Security autonomy</span>
              <div className="flex gap-1">
                {["shadow", "enforce", "off"].map((m) => (
                  <button
                    key={m}
                    type="button"
                    data-testid={`autonomy-${m}`}
                    onClick={() => putPolicy({ autonomy_mode: m })}
                    className={`rounded-md border px-2 py-1 text-xs font-semibold capitalize ${policy?.autonomy_mode === m ? "border-foreground bg-foreground text-background" : "border-line-strong hover:bg-surface-2"}`}
                  >
                    {m}
                  </button>
                ))}
              </div>
            </div>
            <p className="text-xs text-muted">Detector threshold τ = {policy?.tau ?? "—"} (tuned on the train split only).</p>
          </div>
        </Panel>

        <Panel title="Partner banks (live)" icon={Icon.info()} testid="demo-banks">
          <ul className="divide-y divide-line text-sm">
            {Object.values(state.banks).sort((a, b) => a.bank.localeCompare(b.bank)).map((b) => (
              <li key={b.bank} className="flex items-center justify-between gap-2 px-4 py-2">
                <span className="font-mono text-xs">{b.bank}</span>
                <span className="tabular-nums">{(b.success_rate * 100).toFixed(2)}%</span>
                <span className="rounded border border-line px-1.5 text-[10px] text-muted">{b.rail}</span>
                <BandBadge band={b.band} />
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <Panel
        title="PS-02 episodes"
        icon={Icon.clock()}
        testid="demo-episodes"
        aside={
          <div className="flex gap-1">
            {(["featured", "test", "all"] as const).map((f) => (
              <button
                key={f}
                type="button"
                onClick={() => setFilter(f)}
                className={`rounded-md border px-2 py-0.5 text-[11px] font-semibold capitalize ${filter === f ? "border-foreground bg-foreground text-background" : "border-line-strong"}`}
              >
                {f === "test" ? "test split" : f}
              </button>
            ))}
          </div>
        }
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wide text-muted">
              <tr>
                <th className="px-4 py-2">Episode</th>
                <th className="px-2 py-2">Ground truth</th>
                <th className="px-2 py-2">Service · metric</th>
                <th className="px-2 py-2">Onset (PKT)</th>
                <th className="px-2 py-2">Split</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {shown.map((e) => (
                <tr key={e.id} data-testid={`episode-${e.id}`}>
                  <td className="px-4 py-2 font-mono text-xs">{e.id}</td>
                  <td className="px-2 py-2">
                    {e.kind === "incident" ? (
                      <Chip tone="crit" icon={Icon.crit()}>
                        {e.code}
                        {e.abrupt ? " · abrupt" : ` · ${e.lead_min} min precursor`}
                      </Chip>
                    ) : (
                      <Chip tone="good" icon={Icon.check()}>
                        {e.code} · {NEG_LABEL[e.code] ?? "hard negative"}
                      </Chip>
                    )}
                  </td>
                  <td className="px-2 py-2 text-xs">
                    {e.service} · <span className="font-mono">{e.metric}</span>
                    {e.segment !== "*" && <span className="text-muted"> · {e.segment}</span>}
                  </td>
                  <td className="px-2 py-2 text-xs tabular-nums">{e.onset.replace("T", " ").slice(5, 16)}</td>
                  <td className="px-2 py-2 text-xs">{e.split}</td>
                  <td className="px-4 py-2 text-right">
                    <button
                      type="button"
                      data-testid={`replay-${e.id}`}
                      onClick={() => replay(e.id)}
                      className="rounded-md bg-foreground px-3 py-1 text-xs font-semibold text-background disabled:opacity-40"
                    >
                      Replay
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="px-4 py-2 text-xs text-muted">
          Replays start 45 minutes before the precursor so you see the forecast form. After pressing Replay, open{" "}
          <Link href="/" className="text-accent-ink underline">
            Live Ops
          </Link>
          .
        </p>
      </Panel>
    </div>
  );
}
