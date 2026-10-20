import { Suspense } from "react";
import { apiFetch } from "@/lib/upstream";
import { Icon, Panel } from "@/components/ui";
import fallback from "@/lib/scorecard.fallback.json";

export const metadata = { title: "Scorecard · Sentinel" };

type CI = [number, number] | null;
type Config = {
  recall: number | null;
  precision: number | null;
  false_positives: number;
  alerts: number;
  lead_median: number | null;
  lead_p25: number | null;
  lead_p75: number | null;
  pct_lead_gt0_non_abrupt: number | null;
  pkr_protected_est: number;
  ci95: { recall: CI; precision: CI; fp_per_service_day?: CI; lead_median: CI };
  leads: Record<string, number>;
  pages_avoided_vs_B1?: number;
};
type Bench = { rule: string; alerts: number; tp: number; fp: number; fn: number; precision: number; recall: number };
type Scorecard = {
  splits: string;
  tau: number;
  test_incidents: number;
  test_hard_negatives: number;
  generated_at?: string;
  csv_bench: { rows: number; incidents: number; B0: Bench; B1: Bench };
  configs: Record<string, Config>;
  agents?: Record<string, { S2: { false_positives: number }; S3_pages: Config; outcomes: Record<string, number>; rca_top1_code_accuracy: number | null; skeptic_induced_misses: string[]; tokens_total: number }>;
};

async function loadScorecard(): Promise<{ data: Scorecard; live: boolean }> {
  try {
    const res = await apiFetch("/scorecard");
    if (res.ok) return { data: (await res.json()) as Scorecard, live: true };
  } catch {
    /* fall through to the bundled copy */
  }
  return { data: fallback as unknown as Scorecard, live: false };
}

const ROWS: { key: string; label: string }[] = [
  { key: "B0", label: "B0 · static u ≥ 1.0" },
  { key: "B1", label: "B1 · 95% rule (today's monitor)" },
  { key: "S1", label: "S1 · Holt forecast" },
  { key: "S2", label: "S2 · Sentinel detector + grouping" },
  { key: "S3d", label: "S3 · S2 + agents (deterministic fallback)" },
  { key: "S3", label: "S3 · S2 + agents (gpt-6-luna Skeptic) — pages" },
];

const f2 = (x: number | null | undefined) => (x == null ? "—" : x.toFixed(2));
const ci = (c: CI | undefined) => (c ? `[${c[0].toFixed(2)}–${c[1].toFixed(2)}]` : "");
const mins = (x: number | null | undefined) => (x == null ? "—" : `${x % 1 === 0 ? x.toFixed(0) : x.toFixed(1)}`);
const pkrM = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M PKR` : n > 0 ? `${(n / 1e3).toFixed(0)}K PKR` : "0 PKR");

export default function ScorecardPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted">Loading scorecard…</p>}>
      <ScorecardBody />
    </Suspense>
  );
}

async function ScorecardBody() {
  const { data, live: fromApi } = await loadScorecard();
  const { csv_bench: csv } = data;
  const agents = data.agents ?? {};
  const configs: Record<string, Config> = { ...data.configs };
  if (agents.S3_deterministic) configs.S3d = agents.S3_deterministic.S3_pages;
  if (agents.S3) configs.S3 = agents.S3.S3_pages;
  const live = agents.S3;
  const train = agents.S3_train;
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold tracking-tight">Scorecard — held-out test split</h1>
        <p className="text-xs text-muted">{data.splits}</p>
        <p className="text-xs text-muted">
          <span className="tabular font-semibold text-foreground">τ = {data.tau}</span> (tuned on train only) · {data.test_incidents} test incidents ·{" "}
          {data.test_hard_negatives} hard negatives · source: {fromApi ? "sentinel-api /scorecard" : "bundled scorecard.json"}
        </p>
        <p className="flex items-center gap-1.5 text-xs text-faint">
          {Icon.info()} Every number on this page is computed by the scorer; nothing is typed by hand.
        </p>
      </div>

      <Panel title="Raw PS-02 CSV" icon={Icon.doc()} testid="csv-panel" aside={<span className="tabular">{csv.rows} rows · {csv.incidents} incidents</span>}>
        <div className="grid gap-3 p-3.5 sm:grid-cols-2">
          <div className="rounded-lg border border-line bg-surface-2 p-3">
            <div className="text-xs text-muted">Static threshold (B0, {csv.B0.rule})</div>
            <div className="tabular mt-1 flex items-center gap-1.5 text-lg font-semibold text-crit-ink">{Icon.crit("size-4")}
              {csv.B0.tp}/{csv.incidents} caught
            </div>
          </div>
          <div className="rounded-lg border border-line bg-surface-2 p-3">
            <div className="text-xs text-muted">95% rule (B1, {csv.B1.rule})</div>
            <div className="tabular mt-1 text-lg font-semibold">
              {csv.B1.tp}/{csv.incidents} caught, precision {csv.B1.precision.toFixed(2)}{" "}
              <span className="text-sm font-medium text-warn-ink">({csv.B1.fp} false pages)</span>
            </div>
          </div>
        </div>
      </Panel>

      <Panel title="Ablation — test split, 95% bootstrap CIs" icon={Icon.scale()} testid="scorecard-table">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-left text-xs">
            <thead className="border-b border-line text-muted">
              <tr>
                {["Config", "Recall [CI]", "Precision [CI]", "False positives", "Alerts", "Median lead min (p25–p75)", "% non-abrupt lead > 0", "PKR protected (est.)"].map((h) => (
                  <th key={h} className="px-3.5 py-2 font-medium whitespace-nowrap">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="tabular divide-y divide-line">
              {ROWS.map(({ key, label }) => {
                const c = configs[key];
                if (!c) return null;
                const hero = key === (configs.S3 ? "S3" : "S2");
                return (
                  <tr key={key} data-testid={`scorecard-row-${key}`} className={hero ? "bg-accent-soft/60 font-semibold" : ""}>
                    <td className="px-3.5 py-2 whitespace-nowrap">{label}</td>
                    <td className="px-3.5 py-2 whitespace-nowrap">
                      {f2(c.recall)} <span className="font-normal text-faint">{ci(c.ci95?.recall)}</span>
                    </td>
                    <td className="px-3.5 py-2 whitespace-nowrap">
                      {f2(c.precision)} <span className="font-normal text-faint">{ci(c.ci95?.precision)}</span>
                    </td>
                    <td className="px-3.5 py-2">{c.false_positives}</td>
                    <td className="px-3.5 py-2">{c.alerts}</td>
                    <td className="px-3.5 py-2 whitespace-nowrap">
                      {mins(c.lead_median)}
                      {c.lead_p25 != null && c.lead_p75 != null && (
                        <span className="font-normal text-faint">
                          {" "}
                          ({mins(c.lead_p25)}–{mins(c.lead_p75)})
                        </span>
                      )}
                    </td>
                    <td className="px-3.5 py-2">{c.pct_lead_gt0_non_abrupt == null ? "—" : `${(c.pct_lead_gt0_non_abrupt * 100).toFixed(0)}%`}</td>
                    <td className="px-3.5 py-2 whitespace-nowrap">{pkrM(c.pkr_protected_est)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>

      {live && (
        <Panel title="Agents (S3) — what the Skeptic changed" icon={Icon.scale()} testid="s3-panel">
          <div className="grid gap-3 p-3.5 text-xs sm:grid-cols-4">
            <div><div className="text-muted">Pages vs S2 alerts</div><div className="tabular text-lg font-semibold">{live.outcomes.page} / {configs.S2?.alerts}</div></div>
            <div><div className="text-muted">False pages → P3 watch tickets</div><div className="tabular text-lg font-semibold">{configs.S2?.false_positives} → {configs.S3?.false_positives}</div></div>
            <div><div className="text-muted">Skeptic-induced misses</div><div className="tabular text-lg font-semibold">{live.skeptic_induced_misses.length}</div></div>
            <div><div className="text-muted">RCA top-1 root-cause accuracy</div><div className="tabular text-lg font-semibold">{live.rca_top1_code_accuracy == null ? "—" : `${(live.rca_top1_code_accuracy * 100).toFixed(0)}%`}</div></div>
          </div>
          {train && (
            <p className="px-3.5 pb-3 text-xs text-muted">
              Independent check on the train split (Aug 1–20, never used to edit the Skeptic): false pages {train.S2.false_positives} → {train.S3_pages.false_positives},
              recall {f2(train.S3_pages.recall)}, {train.skeptic_induced_misses.length} Skeptic-induced misses. Disputed alerts become P3 watch tickets, not pages.
            </p>
          )}
        </Panel>
      )}

      <LeadChart s2={configs.S2?.leads ?? {}} b1={configs.B1?.leads ?? {}} />
    </div>
  );
}

function LeadChart({ s2, b1 }: { s2: Record<string, number>; b1: Record<string, number> }) {
  const ids = Object.keys(s2).sort();
  const max = Math.max(1, ...ids.map((id) => Math.max(s2[id] ?? 0, b1[id] ?? 0)));
  const w = (v: number) => `${Math.max(0, (v / max) * 100)}%`;
  return (
    <Panel
      title="Lead time per incident (min before breach)"
      icon={Icon.clock()}
      testid="lead-chart"
      aside={
        <span className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <span className="inline-block size-2.5 rounded-sm" style={{ background: "#2a78d6" }} /> S2
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block size-2.5 rounded-sm bg-line-strong" /> B1
          </span>
        </span>
      }
    >
      <ul className="flex flex-col gap-2.5 p-3.5">
        {ids.map((id) => {
          const a = s2[id] ?? 0;
          const b = b1[id];
          return (
            <li key={id} className="grid grid-cols-[96px_1fr] items-center gap-2 text-xs sm:grid-cols-[120px_1fr]">
              <span className="tabular truncate text-muted">{id.replace("INC-PS02-", "INC-")}</span>
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-1.5">
                  <div className="h-2.5 rounded-sm" style={{ width: w(a), minWidth: 2, background: "#2a78d6" }} />
                  <span className="tabular font-semibold">{mins(a)}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="h-2.5 rounded-sm bg-line-strong" style={{ width: w(b ?? 0), minWidth: 2 }} />
                  <span className="tabular text-muted">{b == null ? "missed" : mins(b)}</span>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </Panel>
  );
}
