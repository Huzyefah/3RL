// Contracts shared with sentinel-api (FINAL_PLAN §7.5, §10). Keep in lockstep with the backend Pydantic models.

export type Band = "NORMAL" | "WARNING" | "CRITICAL";
export type Severity = "P1" | "P2" | "P3";
export type Rail = "IBFT" | "RAAST";

export interface ServiceStatus {
  service: string; // PS-02 CSV service id, e.g. "PaymentGateway"
  display: string;
  team: string;
  tier: number;
  u: number; // fraction of error budget used; 1.0 = SLO breached
  band: Band;
  metric: string; // the metric driving u, e.g. "latency_p99"
}

export interface BankStatus {
  bank: string; // BANK_A … BANK_E
  success_rate: number; // 0..1
  u: number;
  band: Band;
  rail: Rail;
}

export type IncidentStatus =
  | "candidate"
  | "investigating"
  | "watching"
  | "awaiting_approval"
  | "acting"
  | "verifying"
  | "resolved"
  | "suppressed";

export interface IncidentSummary {
  id: string;
  root_service: string;
  segment_key: string | null; // e.g. "bank=BANK_C"
  severity: Severity;
  headline: string;
  status: IncidentStatus;
  eta_minutes: number | null;
  eta_at: string | null; // ISO-8601
  risk: number; // 0..1
  opened_at: string; // ISO-8601
  pkr_at_risk_per_min: number; // estimate
}

export interface Hypothesis {
  code: string;
  confidence: number;
  statement: string;
  evidence_ids: string[];
}

export interface SimilarIncident {
  id: string;
  similarity: number;
  fix: string;
}

export interface ProposedAction {
  type: string;
  params: Record<string, unknown>;
  rationale: string;
}

export type SkepticVerdict = "CONFIRMED" | "DISPUTED" | "BENIGN";

export interface RCA {
  incident_id: string;
  goal: string;
  headline: string;
  severity: Severity;
  root_cause_service: string;
  affected_segment: string | null;
  eta_minutes: number | null;
  hypotheses: Hypothesis[];
  similar_incidents: SimilarIncident[];
  runbook_steps: string[];
  impact: { customers_affected_est: number; pkr_at_risk_per_min: number; label: "estimate" };
  actions: ProposedAction[];
  summary_technical: string;
  summary_business: string;
  comms_draft: { in_app_banner: string; bank_partner_note: string };
  if_ignored: string;
  skeptic: { verdict: SkepticVerdict; confidence: number; counter_evidence?: string[] };
  plan_versions: number;
  generated_by: "llm" | "statistical-fallback";
  low_confidence: boolean;
}

export type TraceAgent = "commander" | "investigator" | "skeptic" | "guard" | "log_analyst" | "security_sentinel" | string;
export type TraceKind = "goal" | "plan" | "tool_call" | "challenge" | "guard" | "action" | "verify" | "rca" | "note";

export interface TraceStep {
  incident_id: string;
  step: number; // 1-based, monotonically increasing per incident
  ts: string; // ISO-8601
  agent: TraceAgent;
  kind: TraceKind | string;
  tool?: string | null;
  args: Record<string, unknown>; // plan steps carry {version: n}; challenge steps carry {verdict}
  summary: string;
  evidence_id?: string | null;
  tokens: number;
  latency_ms: number;
}

export type ActionMode = "AUTO" | "HITL" | "DENY" | "SHADOW";
export type ActionState = "pending" | "approved" | "rejected" | "executing" | "executed" | "verified" | "rolled_back" | "expired" | "denied";

export interface ActionView {
  id: string;
  incident_id: string;
  type: string;
  params: Record<string, unknown>;
  mode: ActionMode;
  status: ActionState | string;
  reason: string;
  expires_at?: string | null;
}

export interface Kpis {
  preempted_today: number;
  median_lead_min: number | null;
  fp_avoided: number;
  open_p1p2: number;
  autonomy_mode: string; // e.g. "shadow" | "enforce" | "off"
}

// GET /incidents/{id}
export interface IncidentDetail {
  incident: IncidentSummary;
  rca: RCA | null;
  trace: TraceStep[];
  actions: ActionView[];
}

// SSE: every message is `event: message`, `id: <seq>`, `data: <one of these>`.
export type SentinelEvent =
  | { type: "snapshot"; services: ServiceStatus[]; banks: BankStatus[]; incidents: IncidentSummary[]; kpis: Kpis; actions?: ActionView[] }
  | ({ type: "metric" } & ServiceStatus)
  | ({ type: "bank" } & BankStatus)
  | { type: "incident"; incident: IncidentSummary }
  | { type: "trace"; step: TraceStep }
  | { type: "action"; action: ActionView }
  | { type: "kpis"; kpis: Kpis };
