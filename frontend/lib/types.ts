export type Status = "NORMAL" | "WARNING" | "CRITICAL";

export interface ServiceState { name: string; display: string; u: number; status: Status; eta_min: number | null }
export interface BankState { bank: string; success_rate: number; u?: number; status: Status }
export interface Approval { id: string; action: string; params?: Record<string, unknown>; expires_in_s?: number; incident_id?: string }
export interface IncidentSummary { id: string; headline: string; severity: string; service: string; eta_min: number | null; status: string; verdict?: string }
export interface AppState {
  time?: string; replaying: boolean; llm: "openai" | "fallback" | string;
  kpis: { pre_empted_today?: number; fp_avoided?: number; median_lead_min?: number; open_incidents?: number };
  services: ServiceState[]; banks: BankState[]; approvals: Approval[]; incidents: IncidentSummary[];
}
export interface Hypothesis { code: string; confidence: number; statement: string; evidence_ids?: string[] }
export interface IncidentDetail {
  id?: string; headline?: string; goal?: string; severity?: string; root_cause_service?: string;
  affected_segment?: string; eta_minutes?: number | null; hypotheses?: Hypothesis[];
  similar_incidents?: { id: string; similarity: number; fix?: string }[];
  runbook_steps?: string[]; impact?: { customers_affected_est?: number; pkr_at_risk_per_min?: number; label?: string };
  actions?: (Approval | Record<string, unknown>)[]; summary_technical?: string; summary_business?: string;
  comms_draft?: string; if_ignored?: string; skeptic?: { verdict?: string; confidence?: number };
  plan_versions?: unknown; generated_by?: string; low_confidence?: boolean;
  trace?: { t?: string; step: string; detail?: unknown }[]; ticket?: unknown;
}
export interface ScoreRow { config?: string; recall?: number; precision?: number; fp_per_service_day?: number; median_lead_min?: number; pct_lead_gt0?: number; note?: string }
export interface Scorecard { split?: string; rows?: ScoreRow[]; raw_csv?: Record<string, unknown> }
