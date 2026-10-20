"use client";
import Link from "next/link";
import { use, useState } from "react";
import { ApprovalRow, Nav, Panel, Waiting } from "@/components/bits";
import { Button } from "@/components/ui/button";
import { usePoll } from "@/lib/use-poll";
import type { IncidentDetail } from "@/lib/types";

const txt = (v: unknown) => (typeof v === "string" ? v : v == null ? "" : JSON.stringify(v));

export default function Incident({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: d, error, reload } = usePoll<IncidentDetail>(`/incidents/${id}`, 1500);
  const [biz, setBiz] = useState(false);
  return (
    <main className="mx-auto w-full max-w-5xl flex-1 space-y-4 p-4 md:p-6">
      <header className="flex items-center justify-between">
        <Link href="/" className="text-sm text-zinc-400 hover:text-zinc-100">← Live Ops</Link>
        <Nav />
      </header>
      {!d ? <Waiting error={error} /> : (
        <>
          <div>
            <div className="font-mono text-xs text-zinc-500">{id} · {d.severity ?? "—"} · {d.root_cause_service ?? "—"} · {d.affected_segment ?? ""}</div>
            <h1 className="text-2xl font-semibold">{d.headline ?? "Analysis in progress"}</h1>
            <p className="text-zinc-400">{d.goal}</p>
            <p className="mt-1 font-mono text-sm text-amber-300">ETA {d.eta_minutes != null ? `${Math.round(d.eta_minutes)} min` : "—"}
              {d.generated_by ? ` · by ${d.generated_by}` : ""}{d.low_confidence ? " · low confidence" : ""}</p>
          </div>

          <Panel title="Summary">
            <div className="mb-2 flex gap-2">
              <Button size="sm" variant={biz ? "outline" : "default"} onClick={() => setBiz(false)}>Technical</Button>
              <Button size="sm" variant={biz ? "default" : "outline"} onClick={() => setBiz(true)}>Business</Button>
            </div>
            <p className="text-sm">{(biz ? d.summary_business : d.summary_technical) || "—"}</p>
            {d.impact && <p className="mt-2 font-mono text-xs text-zinc-400">{d.impact.label} · ~{d.impact.customers_affected_est ?? "—"} customers · PKR {d.impact.pkr_at_risk_per_min ?? "—"}/min at risk</p>}
            {d.if_ignored && <p className="mt-2 text-sm text-red-300">If ignored: {d.if_ignored}</p>}
          </Panel>

          <div className="grid gap-4 md:grid-cols-2">
            <Panel title="Hypotheses">
              <ul className="space-y-3">
                {d.hypotheses?.map((h) => (
                  <li key={h.code}>
                    <div className="flex justify-between text-sm"><span className="font-mono">{h.code}</span><span className="tabular-nums">{Math.round(h.confidence * 100)}%</span></div>
                    <div className="my-1 h-1.5 rounded bg-zinc-800"><div className="h-full rounded bg-sky-400" style={{ width: `${h.confidence * 100}%` }} /></div>
                    <p className="text-sm text-zinc-300">{h.statement}</p>
                    <div className="mt-1 flex flex-wrap gap-1">{h.evidence_ids?.map((e) => <span key={e} className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-xs">{e}</span>)}</div>
                  </li>
                )) ?? <p className="text-sm text-zinc-500">—</p>}
              </ul>
            </Panel>
            <div className="space-y-4">
              <Panel title="Skeptic">
                <p className="text-sm">{d.skeptic?.verdict ?? "—"} {d.skeptic?.confidence != null && <span className="font-mono text-zinc-400">({Math.round(d.skeptic.confidence * 100)}%)</span>}</p>
              </Panel>
              <Panel title="Similar incidents">
                <ul className="space-y-1 text-sm">
                  {d.similar_incidents?.length ? d.similar_incidents.map((s) => (
                    <li key={s.id}>{Math.round(s.similarity * 100)}% like <span className="font-mono">{s.id}</span>{s.fix ? ` — fix: ${s.fix}` : ""}</li>
                  )) : <li className="text-zinc-500">none</li>}
                </ul>
              </Panel>
              <Panel title="Actions">
                <ul className="space-y-2">
                  {d.actions?.length ? d.actions.map((a, i) => {
                    const x = a as { id?: string; action?: string };
                    return x.id && x.action
                      ? <ApprovalRow key={x.id} a={a as { id: string; action: string }} onDone={reload} />
                      : <li key={i} className="font-mono text-xs text-zinc-300">{txt(a)}</li>;
                  }) : <li className="text-sm text-zinc-500">none</li>}
                </ul>
              </Panel>
            </div>
          </div>

          {d.runbook_steps?.length ? (
            <Panel title="Runbook"><ol className="list-decimal space-y-1 pl-5 text-sm">{d.runbook_steps.map((s, i) => <li key={i}>{s}</li>)}</ol></Panel>
          ) : null}
          <Panel title="Comms draft"><p className="whitespace-pre-wrap text-sm">{d.comms_draft || "—"}</p></Panel>
          <Panel title="Trace (plan v1 → tools → skeptic → plan v2 → guard → action → verification)">
            <ol className="space-y-1 border-l border-zinc-700 pl-3 font-mono text-xs">
              {d.trace?.length ? d.trace.map((t, i) => (
                <li key={i}><span className="text-zinc-500">{t.t ?? ""}</span> <span className="text-sky-300">{t.step}</span> {txt(t.detail)}</li>
              )) : <li className="text-zinc-500">waiting for trace…</li>}
            </ol>
          </Panel>
        </>
      )}
    </main>
  );
}
