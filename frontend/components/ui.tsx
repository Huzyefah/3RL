import type { ReactNode } from "react";
import type { Band, IncidentStatus, Severity } from "@/lib/types";
import { BAND_CRITICAL, BAND_WARNING } from "@/lib/format";

type Tone = "good" | "warn" | "crit" | "info" | "accent";

const TONE: Record<Tone, string> = {
  good: "bg-good-soft text-good-ink",
  warn: "bg-warn-soft text-warn-ink",
  crit: "bg-crit-soft text-crit-ink",
  info: "bg-info-soft text-info-ink",
  accent: "bg-accent-soft text-accent-ink",
};

export const BAND_TONE: Record<Band, Tone> = { NORMAL: "good", WARNING: "warn", CRITICAL: "crit" };
export const BAND_LABEL: Record<Band, string> = { NORMAL: "Normal", WARNING: "Warning", CRITICAL: "Critical" };

// ── Icons (16px, currentColor). Each status colour is paired with one of these plus a text label. ──
const svg = (path: ReactNode, cls = "size-3.5") => (
  <svg viewBox="0 0 16 16" className={`${cls} shrink-0`} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    {path}
  </svg>
);
export const Icon = {
  ok: (c?: string) => svg(<><circle cx="8" cy="8" r="6.2" /><path d="M5.3 8.2l1.8 1.8 3.6-3.8" /></>, c),
  warn: (c?: string) => svg(<><path d="M8 2.2l6.2 11H1.8z" /><path d="M8 6.6v3" /><path d="M8 11.6v.1" /></>, c),
  crit: (c?: string) => svg(<><path d="M5.4 1.8h5.2l3.6 3.6v5.2l-3.6 3.6H5.4l-3.6-3.6V5.4z" /><path d="M6 6l4 4M10 6l-4 4" /></>, c),
  info: (c?: string) => svg(<><circle cx="8" cy="8" r="6.2" /><path d="M8 7.2v3.6" /><path d="M8 5.2v.1" /></>, c),
  clock: (c?: string) => svg(<><circle cx="8" cy="8" r="6.2" /><path d="M8 4.6V8l2.4 1.6" /></>, c),
  shield: (c?: string) => svg(<><path d="M8 1.8l5.2 2v4c0 3-2.2 5.2-5.2 6.4C5 13 2.8 10.8 2.8 7.8v-4z" /></>, c),
  bolt: (c?: string) => svg(<path d="M9 1.8L3.6 9h4l-1 5.2L12.4 7h-4z" />, c),
  route: (c?: string) => svg(<><circle cx="3.6" cy="12.4" r="1.6" /><circle cx="12.4" cy="3.6" r="1.6" /><path d="M5.2 12.4h4.4a2.4 2.4 0 000-4.8H6.4a2.4 2.4 0 010-4.8h4.4" /></>, c),
  search: (c?: string) => svg(<><circle cx="7" cy="7" r="4.4" /><path d="M10.4 10.4l3.6 3.6" /></>, c),
  target: (c?: string) => svg(<><circle cx="8" cy="8" r="6.2" /><circle cx="8" cy="8" r="3.2" /><circle cx="8" cy="8" r=".6" /></>, c),
  list: (c?: string) => svg(<><path d="M5.6 4h8M5.6 8h8M5.6 12h8" /><path d="M2.4 4h.1M2.4 8h.1M2.4 12h.1" /></>, c),
  scale: (c?: string) => svg(<><path d="M8 2v12M3.6 14h8.8" /><path d="M2 8.4l2.2-4.6 2.2 4.6a2.2 2.2 0 01-4.4 0zM9.6 8.4l2.2-4.6L14 8.4a2.2 2.2 0 01-4.4 0z" /></>, c),
  doc: (c?: string) => svg(<><path d="M4 1.8h5.4L12.4 5v9.2H4z" /><path d="M9.2 1.8V5.2h3.2M6 8.4h4.4M6 11h4.4" /></>, c),
  check: (c?: string) => svg(<path d="M3.4 8.4l3 3 6.2-6.6" />, c),
  x: (c?: string) => svg(<path d="M4 4l8 8M12 4l-8 8" />, c),
  up: (c?: string) => svg(<><path d="M5.2 7.2V14H2.4V7.2zM5.2 7.2L8 1.8c1.2 0 2 .8 2 2v2.4h3a1.4 1.4 0 011.4 1.6l-.8 4.8a1.6 1.6 0 01-1.6 1.4H5.2" /></>, c),
  down: (c?: string) => svg(<><path d="M5.2 8.8V2H2.4v6.8zM5.2 8.8L8 14.2c1.2 0 2-.8 2-2V9.8h3a1.4 1.4 0 001.4-1.6l-.8-4.8A1.6 1.6 0 0012 2H5.2" /></>, c),
};

export const BAND_ICON: Record<Band, (c?: string) => ReactNode> = { NORMAL: Icon.ok, WARNING: Icon.warn, CRITICAL: Icon.crit };

export function Chip({ tone = "info", icon, children, testid, className = "" }: { tone?: Tone; icon?: ReactNode; children: ReactNode; testid?: string; className?: string }) {
  return (
    <span data-testid={testid} className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-semibold leading-4 tracking-wide whitespace-nowrap ${TONE[tone]} ${className}`}>
      {icon}
      {children}
    </span>
  );
}

export function BandBadge({ band, testid }: { band: Band; testid?: string }) {
  return (
    <Chip tone={BAND_TONE[band]} icon={BAND_ICON[band]()} testid={testid}>
      {BAND_LABEL[band]}
    </Chip>
  );
}

const SEV_TONE: Record<Severity, Tone> = { P1: "crit", P2: "warn", P3: "info" };
export function SeverityChip({ severity }: { severity: Severity }) {
  const icon = severity === "P1" ? Icon.crit() : severity === "P2" ? Icon.warn() : Icon.info();
  return (
    <Chip tone={SEV_TONE[severity]} icon={icon} testid="severity-chip">
      {severity}
    </Chip>
  );
}

const STATUS: Record<IncidentStatus, { tone: Tone; label: string; icon: (c?: string) => ReactNode }> = {
  candidate: { tone: "info", label: "Candidate", icon: Icon.target },
  investigating: { tone: "accent", label: "Investigating", icon: Icon.search },
  watching: { tone: "info", label: "Watching", icon: Icon.clock },
  awaiting_approval: { tone: "warn", label: "Awaiting approval", icon: Icon.shield },
  acting: { tone: "accent", label: "Acting", icon: Icon.bolt },
  verifying: { tone: "accent", label: "Verifying", icon: Icon.scale },
  resolved: { tone: "good", label: "Resolved", icon: Icon.ok },
  suppressed: { tone: "info", label: "Suppressed", icon: Icon.x },
};
export function StatusChip({ status }: { status: IncidentStatus }) {
  const s = STATUS[status] ?? STATUS.candidate;
  return (
    <Chip tone={s.tone} icon={s.icon()} testid="status-chip">
      {s.label}
    </Chip>
  );
}

export function Panel({ title, icon, aside, children, testid, className = "" }: { title: string; icon?: ReactNode; aside?: ReactNode; children: ReactNode; testid?: string; className?: string }) {
  return (
    <section data-testid={testid} className={`min-w-0 overflow-hidden rounded-xl border border-line bg-surface ${className}`}>
      <header className="flex min-w-0 items-center justify-between gap-2 border-b border-line px-3.5 py-2.5">
        <h2 className="flex min-w-0 items-center gap-1.5 text-[13px] font-semibold tracking-tight">
          {icon && <span className="text-muted">{icon}</span>}
          <span className="truncate">{title}</span>
        </h2>
        {aside && <div className="flex shrink-0 items-center gap-2 text-xs text-muted">{aside}</div>}
      </header>
      {children}
    </section>
  );
}

const U_MAX = 1.2;
/** Thin utilisation bar with ticks at the WARNING (0.75) and CRITICAL (0.95) boundaries. */
export function UBar({ u, band }: { u: number; band: Band }) {
  const fill = { NORMAL: "bg-good", WARNING: "bg-warn", CRITICAL: "bg-crit" }[band];
  const pctOf = (x: number) => `${Math.min(100, (x / U_MAX) * 100)}%`;
  return (
    <div className="relative h-1.5 w-full rounded-full bg-surface-2" role="meter" aria-valuemin={0} aria-valuemax={U_MAX} aria-valuenow={Number(u.toFixed(2))} aria-label="utilisation">
      <div className={`absolute inset-y-0 left-0 rounded-full ${fill} transition-[width] duration-500`} style={{ width: pctOf(u) }} />
      {[BAND_WARNING, BAND_CRITICAL].map((t) => (
        <span key={t} className="absolute -top-0.5 h-2.5 w-px bg-line-strong" style={{ left: pctOf(t) }} title={`u = ${t}`} />
      ))}
    </div>
  );
}

export function ConfidenceBar({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="relative h-1.5 w-24 shrink-0 rounded-full bg-surface-2 sm:w-32">
        <div className="absolute inset-y-0 left-0 rounded-full bg-accent" style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
      <span className="tabular text-xs font-semibold">{Math.round(value * 100)}%</span>
    </div>
  );
}
