"use client";
import Link from "next/link";
import { useState } from "react";
import { Activity, RotateCcw, Zap, FlaskConical } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApprovalRow, Nav, Panel, Stat, Waiting, statusBar } from "@/components/bits";
import { post, usePoll } from "@/lib/use-poll";
import type { AppState } from "@/lib/types";

const dash = (v: unknown) => (v === undefined || v === null ? "—" : String(v));

export default function Home() {
  const { data, error, reload } = usePoll<AppState>("/state", 1500);
  const [note, setNote] = useState("");
  async function demo(path: string, body?: unknown) {
    const r = await post(path, body);
    setNote(r.ok ? `ok: ${path}` : `failed ${path} (${r.status})`);
    reload();
  }
  return (
    <main className="mx-auto w-full max-w-7xl flex-1 space-y-4 p-4 md:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Activity className="size-5 text-emerald-400" aria-hidden="true" />
          <h1 className="text-xl font-semibold tracking-tight">Sentinel <span className="text-zinc-500">/ Live Ops</span></h1>
          <span className="rounded border border-sky-500/40 bg-sky-500/10 px-1.5 py-0.5 font-mono text-xs text-sky-300">synthetic replay</span>
          {data && (
            <span className="rounded border border-zinc-700 px-1.5 py-0.5 font-mono text-xs text-zinc-300">
              LLM: {data.llm}
            </span>
          )}
          {data?.replaying && <span className="font-mono text-xs text-amber-300">● replaying</span>}
        </div>
        <Nav />
      </header>

      <Panel title="Demo controls">
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={() => demo("/demo/replay", { episode_id: "INC-0002" })}><Zap aria-hidden="true" /> Replay 08-01 cascade (INC-0002)</Button>
          <Button variant="outline" onClick={() => demo("/demo/replay", { episode_id: "FA-0014" })}><FlaskConical aria-hidden="true" /> Replay salary-day false alarm (FA-0014)</Button>
          <Button variant="outline" onClick={() => demo("/demo/chaos/bank_c_slow")}>Break BANK_C (chaos)</Button>
          <Button variant="ghost" onClick={() => demo("/demo/reset")}><RotateCcw aria-hidden="true" /> Reset</Button>
          <span className="font-mono text-xs text-zinc-500">{note}</span>
        </div>
      </Panel>

      {!data ? (
        <Waiting error={error} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            {[
              ["Pre-empted today", data.kpis?.pre_empted_today],
              ["False alarms avoided", data.kpis?.fp_avoided],
              ["Median lead (min)", data.kpis?.median_lead_min],
              ["Open incidents", data.kpis?.open_incidents],
            ].map(([l, v]) => (
              <div key={l as string} className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-3">
                <div className="font-mono text-xs uppercase tracking-widest text-zinc-500">{l as string}</div>
                <div className="mt-1 text-3xl font-semibold tabular-nums">{dash(v)}</div>
              </div>
            ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Panel title="Services" className="lg:col-span-2">
              {data.services?.length ? (
                <ul className="grid gap-2 sm:grid-cols-2">
                  {data.services.map((s) => (
                    <li key={s.name} className="rounded border border-zinc-800 p-2">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm">{s.display ?? s.name}</span>
                        <Stat status={s.status} />
                      </div>
                      <div className="mt-2 h-2 overflow-hidden rounded bg-zinc-800" role="progressbar" aria-valuenow={Math.round((s.u ?? 0) * 100)} aria-valuemin={0} aria-valuemax={100} aria-label={`${s.display} utilisation`}>
                        <div className={`h-full ${statusBar(s.status)}`} style={{ width: `${Math.min(100, Math.max(0, (s.u ?? 0) * 100))}%` }} />
                      </div>
                      <div className="mt-1 flex justify-between font-mono text-xs text-zinc-400">
                        <span>u {(s.u ?? 0).toFixed(2)}</span>
                        {s.eta_min != null && <span>breach in ~{Math.round(s.eta_min)} min</span>}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : <p className="text-sm text-zinc-500">No services yet.</p>}
            </Panel>

            <div className="space-y-4">
              <Panel title="Banks (success rate)">
                <ul className="space-y-1.5">
                  {data.banks?.map((b) => (
                    <li key={b.bank} className="flex items-center justify-between gap-2 text-sm">
                      <span className="font-mono">{b.bank}</span>
                      <span className="tabular-nums">{(b.success_rate * 100).toFixed(1)}%</span>
                      <Stat status={b.status} />
                    </li>
                  ))}
                </ul>
              </Panel>
              <Panel title="Approvals inbox">
                {data.approvals?.length ? (
                  <ul className="space-y-2">{data.approvals.map((a) => <ApprovalRow key={a.id} a={a} onDone={reload} />)}</ul>
                ) : <p className="text-sm text-zinc-500">Nothing pending.</p>}
              </Panel>
            </div>
          </div>

          <Panel title="Incidents in the making">
            {data.incidents?.length ? (
              <ul className="divide-y divide-zinc-800">
                {data.incidents.map((i) => (
                  <li key={i.id}>
                    <Link href={`/incidents/${i.id}`} className="flex flex-wrap items-center justify-between gap-2 py-2 hover:bg-zinc-800/40">
                      <span><span className="font-mono text-zinc-500">{i.id}</span> {i.headline}</span>
                      <span className="font-mono text-xs text-zinc-400">
                        {i.severity} · {i.service} · {i.eta_min != null ? `ETA ${Math.round(i.eta_min)}m` : "no ETA"} · {i.status}{i.verdict ? ` · ${i.verdict}` : ""}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-zinc-500">No incidents.</p>}
          </Panel>
        </>
      )}
    </main>
  );
}
