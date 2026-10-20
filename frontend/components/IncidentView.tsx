"use client";

import Link from "next/link";
import { useMemo, useState, type ReactNode } from "react";
import { mergeSteps, useStream } from "@/lib/stream";
import type { ActionView, IncidentDetail, RCA, TraceStep } from "@/lib/types";
import { hhmmss, pct, pkrCompact, segmentLabel } from "@/lib/format";
import { ActionCard } from "./ActionCard";
import { Countdown } from "./Countdown";
import { EvidenceChip } from "./EvidenceChip";
import { Chip, ConfidenceBar, Icon, Panel, SeverityChip, StatusChip } from "./ui";

export function IncidentView({ initial }: { initial: IncidentDetail }) {
  const stream = useStream();
  const id = initial.incident.id;
  const incident = stream.incidents[id] ?? initial.incident;
  const rca = initial.rca;
  const trace = useMemo(() => mergeSteps(initial.trace, stream.traces[id] ?? []), [initial.trace, stream.traces, id]);
  const actions = useMemo(() => {
    const map = new Map<string, ActionView>(initial.actions.map((a) => [a.id, a]));
    for (const a of Object.values(stream.actions)) if (a.incident_id === id) map.set(a.id, a);
    return [...map.values()];
  }, [initial.actions, stream.actions, id]);

  return (
    <div className="flex min-w-0 flex-col gap-4" data-testid="incident-page">
      <Link href="/" className="w-fit text-xs text-muted hover:text-foreground">
        ← Live Ops
      </Link>

      {/* Goal banner + headline + countdown */}
      <section data-testid="incident-banner" className="min-w-0 overflow-hidden rounded-xl border border-line bg-surface">
        <div data-testid="goal-banner" className="flex items-start gap-2 border-b border-line bg-accent-soft px-4 py-2 text-[13px] text-accent-ink">
          <span className="mt-0.5">{Icon.target()}</span>
          <span className="min-w-0">
            <span className="font-semibold">Goal:</span> {rca?.goal ?? "Commander is setting the goal…"}
          </span>
        </div>
        <div className="grid gap-4 px-4 py-4 md:grid-cols-[1fr_auto]">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-1.5">
              <SeverityChip severity={incident.severity} />
              <StatusChip status={incident.status} />
              <span className="font-mono text-xs text-faint">{incident.id}</span>
              {rca && rca.plan_versions > 1 && (
                <Chip tone="accent" icon={Icon.route()}>
                  Re-planned · v{rca.plan_versions}
                </Chip>
              )}
            </div>
            <h1 data-testid="incident-headline" className="mt-2 text-xl leading-tight font-semibold tracking-tight sm:text-2xl">
              {incident.headline}
            </h1>
            <p className="mt-1 text-sm text-muted">
              Root cause service <span className="font-semibold text-foreground">{incident.root_service}</span> · segment{" "}
              <span className="font-mono text-foreground">{segmentLabel(incident.segment_key)}</span> · opened {hhmmss(incident.opened_at)} PKT
            </p>
          </div>
          <div className="flex gap-6 md:justify-end md:text-right">
            <div>
              <div className="text-[10px] font-medium tracking-wide text-muted uppercase">ETA to SLO breach</div>
              <div className="text-crit-ink">
                <Countdown to={incident.eta_at} size="lg" />
              </div>
            </div>
            <div>
              <div className="text-[10px] font-medium tracking-wide text-muted uppercase">PKR at risk</div>
              <div className="tabular text-2xl font-semibold tracking-tight sm:text-3xl">{pkrCompact(incident.pkr_at_risk_per_min)}</div>
              <div className="text-[11px] text-faint">per min · estimate</div>
            </div>
          </div>
        </div>
      </section>

      {/* DOM order (summary → verdict/actions → trace) is the mobile order; on desktop the side column spans both rows. */}
      <div className="grid min-w-0 items-start gap-4 lg:grid-cols-3">
        <div className="flex min-w-0 flex-col gap-4 lg:col-span-2">
          {rca ? <Summary rca={rca} /> : <Panel title="Summary" icon={Icon.doc()}><p className="p-4 text-sm text-muted">The RCA is being written…</p></Panel>}
          {rca && <Hypotheses rca={rca} />}
        </div>
        <div className="flex min-w-0 flex-col gap-4 lg:col-start-3 lg:row-span-2 lg:row-start-1">
          {rca && <Skeptic rca={rca} />}
          <Panel title="Actions" icon={Icon.bolt()} testid="incident-actions" aside={<span className="tabular">{actions.length}</span>}>
            {actions.length === 0 ? (
              <p className="p-4 text-sm text-muted">No actions requested yet.</p>
            ) : (
              <ul className="flex flex-col gap-2 p-3">
                {actions.map((a) => (
                  <li key={a.id}>
                    <ActionCard action={a} />
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          {rca && <Similar rca={rca} />}
          {rca && <Comms rca={rca} />}
          {rca && <IfIgnored rca={rca} />}
          <Feedback incidentId={id} />
        </div>
        <div className="min-w-0 lg:col-span-2">
          <TraceTimeline steps={trace} />
        </div>
      </div>
    </div>
  );
}

function Summary({ rca }: { rca: RCA }) {
  const [mode, setMode] = useState<"technical" | "business">("technical");
  const opts = [
    { k: "technical", label: "Technical" },
    { k: "business", label: "Business" },
  ] as const;
  return (
    <Panel
      title="Summary"
      icon={Icon.doc()}
      testid="summary-panel"
      aside={
        <div data-testid="summary-toggle" role="tablist" aria-label="Summary audience" className="flex rounded-md border border-line-strong p-0.5">
          {opts.map((o) => (
            <button
              key={o.k}
              type="button"
              role="tab"
              aria-selected={mode === o.k}
              data-testid={`summary-toggle-${o.k}`}
              onClick={() => setMode(o.k)}
              className={`rounded px-2.5 py-0.5 text-xs font-semibold ${mode === o.k ? "bg-foreground text-background" : "text-muted hover:text-foreground"}`}
            >
              {o.label}
            </button>
          ))}
        </div>
      }
    >
      <div className="px-4 py-3.5">
        <p data-testid="summary-text" data-mode={mode} className="text-[15px] leading-relaxed">
          {mode === "technical" ? rca.summary_technical : rca.summary_business}
        </p>
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
          <span>
            Customers affected <span className="tabular font-semibold text-foreground">~{rca.impact.customers_affected_est.toLocaleString("en-US")}</span> (estimate)
          </span>
          <span>
            Generated by <span className="font-semibold text-foreground">{rca.generated_by}</span>
          </span>
          {rca.low_confidence && (
            <Chip tone="warn" icon={Icon.warn()}>
              Low confidence
            </Chip>
          )}
        </div>
      </div>
    </Panel>
  );
}

function Hypotheses({ rca }: { rca: RCA }) {
  return (
    <Panel title="Hypotheses" icon={Icon.search()} testid="hypotheses" aside={<span>ranked by confidence</span>}>
      <ol className="divide-y divide-line">
        {rca.hypotheses.map((h, i) => (
          <li key={`${h.code}-${i}`} data-testid={`hypothesis-${i}`} className="px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="flex items-center gap-2">
                <span className="text-xs font-semibold text-faint">#{i + 1}</span>
                <span className="font-mono text-[13px] font-semibold">{h.code}</span>
              </span>
              <ConfidenceBar value={h.confidence} />
            </div>
            <p className="mt-1.5 text-sm leading-relaxed">{h.statement}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {h.evidence_ids.map((e) => (
                <EvidenceChip key={e} id={e} context={`Hypothesis #${i + 1} (${h.code})`} />
              ))}
            </div>
          </li>
        ))}
      </ol>
    </Panel>
  );
}

const VERDICT = {
  CONFIRMED: { tone: "crit", icon: Icon.crit, note: "Skeptic could not argue it down: real incident." },
  DISPUTED: { tone: "warn", icon: Icon.warn, note: "Skeptic disputes; Commander must re-plan." },
  BENIGN: { tone: "good", icon: Icon.ok, note: "Skeptic found a benign mechanism." },
} as const;

function Skeptic({ rca }: { rca: RCA }) {
  const v = VERDICT[rca.skeptic.verdict] ?? VERDICT.DISPUTED;
  return (
    <Panel title="Skeptic verdict" icon={Icon.scale()} testid="skeptic-verdict">
      <div className="px-4 py-3.5">
        <div className="flex items-center justify-between gap-2">
          <Chip tone={v.tone} icon={v.icon()} className="text-xs">
            {rca.skeptic.verdict}
          </Chip>
          <ConfidenceBar value={rca.skeptic.confidence} />
        </div>
        <p className="mt-2 text-xs text-muted">{v.note}</p>
        {!!rca.skeptic.counter_evidence?.length && (
          <ul className="mt-2 list-disc space-y-1 pl-4 text-xs">
            {rca.skeptic.counter_evidence.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        )}
      </div>
    </Panel>
  );
}

function Similar({ rca }: { rca: RCA }) {
  return (
    <Panel title="Similar incidents" icon={Icon.list()} testid="similar-incidents">
      <ul className="divide-y divide-line">
        {rca.similar_incidents.map((s) => (
          <li key={s.id} className="flex items-start justify-between gap-3 px-4 py-2.5">
            <div className="min-w-0">
              <div className="font-mono text-xs font-semibold">{s.id}</div>
              <div className="text-xs text-muted">{s.fix}</div>
            </div>
            <span className="tabular shrink-0 text-sm font-semibold">{pct(s.similarity, 0)}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function Comms({ rca }: { rca: RCA }) {
  return (
    <Panel title="Comms draft" icon={Icon.doc()} testid="comms-draft">
      <div className="flex flex-col gap-3 px-4 py-3.5 text-sm">
        <Quote label="In-app banner">{rca.comms_draft.in_app_banner}</Quote>
        <Quote label="Bank partner note">{rca.comms_draft.bank_partner_note}</Quote>
      </div>
    </Panel>
  );
}

function Quote({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="text-[10px] font-medium tracking-wide text-muted uppercase">{label}</div>
      <p className="mt-1 rounded-md border-l-2 border-line-strong bg-surface-2 px-3 py-2 text-[13px] leading-relaxed">{children}</p>
    </div>
  );
}

function IfIgnored({ rca }: { rca: RCA }) {
  return (
    <div data-testid="if-ignored" className="flex gap-2 rounded-xl border border-line bg-crit-soft px-4 py-3 text-[13px] text-crit-ink">
      <span className="mt-0.5">{Icon.warn()}</span>
      <span>
        <span className="font-semibold">If ignored:</span> {rca.if_ignored}
      </span>
    </div>
  );
}

function Feedback({ incidentId }: { incidentId: string }) {
  const [vote, setVote] = useState<"up" | "down" | null>(null);
  const [note, setNote] = useState<string>("");
  // Feedback closes the loop: 👎 raises the detector threshold for this service, 👍 stores the RCA in RAG memory.
  const send = async (k: "up" | "down") => {
    setVote(k);
    const res = await fetch("/api/feedback", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ incident_id: incidentId, kind: k }),
    });
    const body = await res.json().catch(() => ({}));
    setNote(res.ok ? body.note ?? "Thanks — feedback recorded." : `Feedback failed (${res.status})`);
  };
  const btn = (k: "up" | "down", label: string) => (
    <button
      type="button"
      data-testid={`feedback-${k}`}
      aria-pressed={vote === k}
      onClick={() => send(k)}
      className={`inline-flex flex-1 items-center justify-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-semibold ${
        vote === k ? "border-foreground bg-foreground text-background" : "border-line-strong hover:bg-surface-2"
      }`}
    >
      {label}
    </button>
  );
  return (
    <Panel title="Was this RCA useful?" icon={Icon.info()} testid="feedback">
      <div className="flex gap-2 p-3">
        {btn("up", "👍 Useful")}
        {btn("down", "👎 Not useful")}
      </div>
      {note && (
        <p data-testid="feedback-note" className="px-3 pb-3 text-xs text-muted">
          {note}
        </p>
      )}
    </Panel>
  );
}

// ── Agent trace ──

const AGENT: Record<string, string> = {
  commander: "Commander",
  investigator: "Investigator",
  skeptic: "Skeptic",
  guard: "Policy guard",
  log_analyst: "Log Analyst",
  security_sentinel: "Security Sentinel",
};

function stepLabel(s: TraceStep): { label: string; tone: "accent" | "info" | "warn" | "good" | "crit"; icon: ReactNode } {
  const verdict = typeof s.args.verdict === "string" ? s.args.verdict : null;
  switch (s.kind) {
    case "goal":
      return { label: "Goal", tone: "accent", icon: Icon.target() };
    case "plan":
      return { label: `Plan v${s.args.version ?? 1}`, tone: "accent", icon: Icon.route() };
    case "tool_call":
      return { label: "Tool call", tone: "info", icon: Icon.search() };
    case "challenge": {
      const tone = verdict === "CONFIRMED" ? "crit" : verdict === "BENIGN" ? "good" : "warn";
      const icon = verdict === "CONFIRMED" ? Icon.crit() : verdict === "BENIGN" ? Icon.ok() : Icon.warn();
      return { label: `Challenge${verdict ? ` · ${verdict}` : ""}`, tone, icon };
    }
    case "guard":
      return { label: `Guard${verdict ? ` · ${verdict}` : ""}`, tone: verdict === "DENY" ? "crit" : "warn", icon: Icon.shield() };
    case "verify":
      return { label: "Verify", tone: "good", icon: Icon.scale() };
    case "rca":
      return { label: "RCA", tone: "info", icon: Icon.doc() };
    default:
      return { label: s.kind.replace(/_/g, " "), tone: "info", icon: Icon.info() };
  }
}

function TraceTimeline({ steps }: { steps: TraceStep[] }) {
  const tokens = steps.reduce((n, s) => n + s.tokens, 0);
  return (
    <Panel
      title="Agent trace"
      icon={Icon.list()}
      testid="trace-timeline"
      aside={
        <span className="tabular">
          {steps.length} steps · {tokens.toLocaleString("en-US")} tok
        </span>
      }
    >
      {steps.length === 0 ? (
        <p className="p-4 text-sm text-muted">Waiting for the Commander…</p>
      ) : (
        <ol className="relative px-4 py-3">
          {steps.map((s, idx) => {
            const l = stepLabel(s);
            const isPlan2 = s.kind === "plan" && Number(s.args.version) > 1;
            return (
              <li key={s.step} data-testid={`trace-step-${s.step}`} data-kind={s.kind} className="enter relative grid grid-cols-[20px_1fr] gap-x-3 pb-3 last:pb-0">
                {idx < steps.length - 1 && <span className="absolute top-5 bottom-0 left-[9.5px] w-px bg-line" aria-hidden />}
                <span className={`relative z-10 mt-0.5 grid size-5 place-items-center rounded-full ring-4 ring-surface ${isPlan2 ? "bg-accent text-background" : "bg-surface-2 text-muted"}`}>
                  {l.icon}
                </span>
                <div className={`min-w-0 ${isPlan2 ? "rounded-lg border border-accent/40 bg-accent-soft/50 px-2.5 py-1.5" : ""}`}>
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span className="text-xs font-semibold">{AGENT[s.agent] ?? s.agent}</span>
                    <Chip tone={l.tone} testid={`trace-kind-${s.step}`}>
                      {l.label}
                    </Chip>
                    {s.tool && <span className="font-mono text-[11px] text-muted">{s.tool}()</span>}
                    <span className="tabular ml-auto text-[11px] text-faint">
                      {hhmmss(s.ts)} · {s.latency_ms} ms{s.tokens ? ` · ${s.tokens} tok` : ""}
                    </span>
                  </div>
                  <p className="mt-1 text-[13px] leading-relaxed">{s.summary}</p>
                  {s.evidence_id && (
                    <div className="mt-1.5">
                      <EvidenceChip id={s.evidence_id} context={`Trace step ${s.step} (${AGENT[s.agent] ?? s.agent})`} />
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </Panel>
  );
}
