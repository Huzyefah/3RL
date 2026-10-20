"use client";
import Link from "next/link";
import { Nav, Panel, Waiting } from "@/components/bits";
import { usePoll } from "@/lib/use-poll";
import type { Scorecard } from "@/lib/types";

const f = (v: unknown, d = 2) => (typeof v === "number" ? v.toFixed(d) : "—");

export default function ScorecardPage() {
  const { data, error } = usePoll<Scorecard>("/scorecard", 10000);
  return (
    <main className="mx-auto w-full max-w-6xl flex-1 space-y-4 p-4 md:p-6">
      <header className="flex items-center justify-between">
        <Link href="/" className="text-sm text-zinc-400 hover:text-zinc-100">← Live Ops</Link>
        <Nav />
      </header>
      <h1 className="text-2xl font-semibold">Scorecard <span className="font-mono text-sm text-zinc-500">split: {data?.split ?? "—"}</span></h1>
      {!data ? <Waiting error={error} /> : (
        <>
          <Panel title="Ablation">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left font-mono text-xs uppercase text-zinc-500">
                  <tr>{["Config", "Recall", "Precision", "FP / svc-day", "Median lead (min)", "% lead > 0", "Note"].map((h) => <th key={h} className="py-1 pr-3">{h}</th>)}</tr>
                </thead>
                <tbody>
                  {data.rows?.length ? data.rows.map((r, i) => (
                    <tr key={i} className="border-t border-zinc-800 tabular-nums">
                      <td className="py-1.5 pr-3 font-mono">{r.config ?? "—"}</td>
                      <td className="pr-3">{f(r.recall)}</td><td className="pr-3">{f(r.precision)}</td>
                      <td className="pr-3">{f(r.fp_per_service_day)}</td><td className="pr-3">{f(r.median_lead_min, 1)}</td>
                      <td className="pr-3">{f(r.pct_lead_gt0)}</td><td className="text-zinc-400">{r.note ?? "—"}</td>
                    </tr>
                  )) : <tr><td colSpan={7} className="py-3 text-zinc-500">No rows yet.</td></tr>}
                </tbody>
              </table>
            </div>
          </Panel>
          <Panel title="Raw CSV baseline">
            <pre className="overflow-x-auto font-mono text-xs text-zinc-300">{data.raw_csv ? JSON.stringify(data.raw_csv, null, 2) : "—"}</pre>
          </Panel>
        </>
      )}
    </main>
  );
}
