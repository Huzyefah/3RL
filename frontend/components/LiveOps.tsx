"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { useStream } from "@/lib/stream";
import type { BankStatus, IncidentSummary, ServiceStatus } from "@/lib/types";
import { pct, pkrCompact, segmentLabel } from "@/lib/format";
import { Countdown } from "./Countdown";
import { ActionCard } from "./ActionCard";
import { BandBadge, BAND_TONE, Icon, Panel, SeverityChip, StatusChip, UBar } from "./ui";

const OPEN = new Set(["candidate", "investigating", "watching", "awaiting_approval", "acting", "verifying"]);
const SEV_RANK = { P1: 0, P2: 1, P3: 2 } as const;

export function LiveOps() {
  const s = useStream();
  const services = s.serviceOrder.map((k) => s.services[k]).filter(Boolean);
  const banks = Object.values(s.banks).sort((a, b) => a.bank.localeCompare(b.bank));
  const incidents = Object.values(s.incidents)
    .filter((i) => OPEN.has(i.status))
    .sort((a, b) => SEV_RANK[a.severity] - SEV_RANK[b.severity] || (a.eta_at ?? "~").localeCompare(b.eta_at ?? "~"));
  const approvals = Object.values(s.actions).filter((a) => a.mode === "HITL" && a.status === "pending");
  const pkrAtRisk = incidents.reduce((sum, i) => sum + i.pkr_at_risk_per_min, 0);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h1 className="text-xl font-semibold tracking-tight">Live Ops</h1>
        <p className="text-xs text-muted">Bands: Normal &lt; 0.75 ≤ Warning &lt; 0.95 ≤ Critical (u = share of error budget used)</p>
      </div>

      <KpiStrip pkrAtRisk={pkrAtRisk} />

      <div className="grid min-w-0 items-start gap-4 lg:grid-cols-3">
        <Panel
          title="Incidents in the making"
          icon={Icon.clock()}
          testid="incidents-panel"
          className="lg:col-span-2"
          aside={<span className="tabular">{incidents.length} open</span>}
        >
          {incidents.length === 0 ? (
            <Empty>{s.synced ? "No candidates. Detectors are watching every service and segment." : "Waiting for the live stream…"}</Empty>
          ) : (
            <ul className="divide-y divide-line">
              {incidents.map((i) => (
                <IncidentRow key={i.id} incident={i} />
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Approvals inbox" icon={Icon.shield()} testid="approvals-inbox" aside={<span className="tabular">{approvals.length} pending</span>}>
          {approvals.length === 0 ? (
            <Empty>Nothing awaiting a human. HITL actions appear here with an expiry.</Empty>
          ) : (
            <ul className="flex flex-col gap-2 p-3">
              {approvals.map((a) => (
                <li key={a.id}>
                  <ActionCard action={a} compact />
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <BankStrip banks={banks} />

      <Panel title="Services" icon={Icon.list()} testid="service-grid" aside={<Legend />}>
        <div className="grid gap-px bg-line sm:grid-cols-2 xl:grid-cols-4">
          {services.length === 0
            ? Array.from({ length: 8 }, (_, k) => <div key={k} className="h-[92px] bg-surface" />)
            : services.map((svc) => <ServiceCard key={svc.service} svc={svc} />)}
        </div>
      </Panel>
    </div>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="px-3.5 py-6 text-center text-sm text-muted">{children}</p>;
}

function Legend() {
  return (
    <span className="hidden items-center gap-3 sm:flex">
      <span className="flex items-center gap-1">
        <span className="h-2.5 w-px bg-line-strong" /> ticks at 0.75 / 0.95
      </span>
    </span>
  );
}

function Kpi({ label, value, sub, testid }: { label: string; value: ReactNode; sub?: ReactNode; testid: string }) {
  return (
    <div data-testid={testid} className="min-w-0 bg-surface px-3.5 py-3">
      <div className="truncate text-[11px] font-medium tracking-wide text-muted uppercase">{label}</div>
      <div className="tabular mt-1 truncate text-2xl font-semibold tracking-tight">{value}</div>
      {sub && <div className="mt-0.5 truncate text-[11px] text-faint">{sub}</div>}
    </div>
  );
}

function KpiStrip({ pkrAtRisk }: { pkrAtRisk: number }) {
  const { kpis } = useStream();
  const dash = "—";
  return (
    <div data-testid="kpi-strip" className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-3 xl:grid-cols-6">
      <Kpi testid="kpi-preempted" label="Pre-empted today" value={kpis?.preempted_today ?? dash} sub="caught before breach" />
      <Kpi testid="kpi-lead" label="Median lead" value={kpis?.median_lead_min != null ? `${kpis.median_lead_min} min` : dash} sub="first alert → onset" />
      <Kpi testid="kpi-fp-avoided" label="FP avoided" value={kpis?.fp_avoided ?? dash} sub="argued down by Skeptic" />
      <Kpi testid="kpi-open" label="Open P1 / P2" value={kpis?.open_p1p2 ?? dash} sub="incidents needing action" />
      <Kpi testid="kpi-autonomy" label="Autonomy" value={<span className="capitalize">{kpis?.autonomy_mode ?? dash}</span>} sub="security actions" />
      <Kpi
        testid="kpi-pkr-at-risk"
        label="PKR at risk / min"
        value={pkrAtRisk > 0 ? <span className="text-crit-ink">{pkrCompact(pkrAtRisk)}</span> : "0"}
        sub="estimate · open incidents"
      />
    </div>
  );
}

function IncidentRow({ incident: i }: { incident: IncidentSummary }) {
  return (
    <li data-testid={`incident-row-${i.id}`} className="enter grid grid-cols-[1fr_auto] gap-x-4 gap-y-2 px-3.5 py-3 sm:grid-cols-[1fr_auto_auto]">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-1.5">
          <SeverityChip severity={i.severity} />
          <StatusChip status={i.status} />
          <span className="font-mono text-[11px] text-faint">{i.id}</span>
        </div>
        <Link href={`/incidents/${encodeURIComponent(i.id)}`} data-testid="incident-link" className="mt-1 block text-[15px] leading-snug font-semibold hover:text-accent-ink hover:underline">
          {i.headline}
        </Link>
        <div className="mt-0.5 text-xs text-muted">
          <span data-testid="incident-root">{i.root_service}</span> · <span data-testid="incident-segment">{segmentLabel(i.segment_key)}</span> · risk{" "}
          <span className="tabular">{pct(i.risk, 0)}</span>
        </div>
      </div>
      <div className="text-right sm:order-last">
        <div className="text-[10px] font-medium tracking-wide text-muted uppercase">ETA to breach</div>
        <div className="text-crit-ink">
          <Countdown to={i.eta_at} />
        </div>
      </div>
      <div className="col-span-2 flex items-center gap-1.5 text-xs text-muted sm:col-span-1 sm:block sm:text-right">
        <div className="text-[10px] font-medium tracking-wide uppercase">PKR at risk</div>
        <div data-testid="incident-pkr" className="tabular text-sm font-semibold text-foreground">
          {pkrCompact(i.pkr_at_risk_per_min)}/min <span className="text-[10px] font-normal text-faint">est.</span>
        </div>
      </div>
    </li>
  );
}

function BankStrip({ banks }: { banks: BankStatus[] }) {
  const tint = { good: "", warn: "bg-warn-soft", crit: "bg-crit-soft" } as const;
  return (
    <Panel title="Partner banks · payment success" icon={Icon.route()} testid="bank-strip" aside={<span>SLO floor 97%</span>}>
      <div className="grid grid-cols-2 gap-px bg-line sm:grid-cols-5">
        {(banks.length ? banks : (Array.from({ length: 5 }, () => null) as (BankStatus | null)[])).map((b, k) =>
          b ? (
            <div key={b.bank} data-testid={`bank-${b.bank}`} data-band={b.band} className={`min-w-0 px-3.5 py-3 last:col-span-2 sm:last:col-span-1 transition-colors duration-500 ${tint[BAND_TONE[b.band] as "good" | "warn" | "crit"] || "bg-surface"}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-xs font-semibold">{b.bank}</span>
                <span
                  data-testid={`bank-rail-${b.bank}`}
                  className={`rounded px-1 text-[10px] font-semibold tracking-wide ${b.rail === "RAAST" ? "bg-accent-soft text-accent-ink" : "text-muted ring-1 ring-line-strong"}`}
                >
                  {b.rail}
                </span>
              </div>
              <div className="tabular mt-1 text-xl font-semibold tracking-tight">{pct(b.success_rate, 2)}</div>
              <div className="mt-1 flex items-center justify-between gap-2">
                <BandBadge band={b.band} testid={`bank-band-${b.bank}`} />
                <span className="tabular text-[11px] text-muted">u {b.u.toFixed(2)}</span>
              </div>
            </div>
          ) : (
            <div key={k} className="h-[94px] bg-surface" />
          ),
        )}
      </div>
    </Panel>
  );
}

function ServiceCard({ svc }: { svc: ServiceStatus }) {
  // "PaymentGateway (wallet, IBFT, Raast, card)" → name + detail line, so nothing important truncates.
  const m = svc.display.match(/^(.*?)\s*\((.*)\)$/);
  const name = m ? m[1] : svc.display;
  const detail = m ? m[2] : null;
  return (
    <div data-testid={`service-card-${svc.service}`} data-band={svc.band} className="flex min-w-0 flex-col gap-2 bg-surface px-3.5 py-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-[13px] font-semibold" title={svc.display}>
            {name}
          </div>
          <div className="truncate text-[11px] text-muted" title={detail ?? undefined}>
            {svc.team} · tier {svc.tier}
            {detail && <span className="text-faint"> · {detail}</span>}
          </div>
        </div>
        <BandBadge band={svc.band} testid={`service-band-${svc.service}`} />
      </div>
      <UBar u={svc.u} band={svc.band} />
      <div className="flex items-center justify-between text-[11px] text-muted">
        <span className="truncate font-mono">{svc.metric}</span>
        <span className="tabular font-semibold text-foreground">u {svc.u.toFixed(2)}</span>
      </div>
    </div>
  );
}

