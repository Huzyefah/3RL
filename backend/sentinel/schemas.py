"""Domain schemas. Frozen at the Phase 1 gate: changing them needs a snapshot update.

Regenerate the snapshot deliberately with
``uv run python -m sentinel.schemas --write-snapshot`` and note it in REPORT.md.

Everything reachable from ``RCA`` is strict-OpenAI compatible: no free-form objects, every
object forbids extra keys, and every field is required in the JSON schema (nullable where
optional). Missing nullable keys are filled with ``None`` on input.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from sentinel import ids
from sentinel.utilisation import Band, Direction, band, utilisation

# --- enums ------------------------------------------------------------------------------
Severity = Literal["P1", "P2", "P3"]
RootCauseCode = Literal[
    "RC-BANK", "RC-DBPOOL", "RC-OTP-PROVIDER", "RC-QUEUE", "RC-AUTH-ATTACK",
    "RC-MEMLEAK", "RC-CERT", "RC-ABRUPT", "RC-BENIGN",
]  # fmt: skip
SkepticVerdict = Literal["CONFIRMED", "DISPUTED", "BENIGN"]
ActionType = Literal[
    "create_ticket", "post_chat_card", "page_oncall", "attach_rca", "schedule_recheck",
    "reroute_bank", "otp_failover", "scale_service", "rollback", "restart",
    "throttle_source", "step_up_mfa", "close_ticket",
    "modify_ledger", "delete_data", "block_all_logins", "change_txn_limits",
]  # fmt: skip
ActionMode = Literal["AUTO", "HITL", "DENY"]
ActionStatus = Literal[
    "PENDING", "APPROVED", "REJECTED", "EXECUTED", "EXPIRED", "ROLLED_BACK", "DENIED", "FAILED",
]  # fmt: skip
GeneratedBy = Literal["llm", "statistical-fallback"]
EventKind = Literal["metric", "log", "auth", "change", "ticket"]
Rail = Literal["IBFT", "RAAST"]
IncidentStatus = Literal["OPEN", "WATCHING", "ESCALATED", "SUPPRESSED", "RESOLVED"]
Autonomy = Literal["off", "shadow", "enforce"]
TraceKind = Literal["detector", "llm", "tool_call", "handoff", "guard", "action", "note"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _NullableRequired(_Strict):
    """Strict-schema model: optional keys may be omitted on input but are always emitted."""

    @model_validator(mode="before")
    @classmethod
    def _fill_missing_with_none(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d: dict[str, Any] = dict(data)  # pyright: ignore[reportUnknownArgumentType]
            for name, f in cls.model_fields.items():
                if name not in d and f.is_required() is False and f.default is None:
                    d[name] = None
            return d
        return data


# --- inputs -----------------------------------------------------------------------------
class CES(BaseModel):
    """Common Event Schema (FP 4.3): every input is normalised to this."""

    event_id: str
    ts: datetime
    source: str
    kind: EventKind
    service: str
    segment_key: str = "*"
    metric: str | None = None
    value: float | None = None
    threshold: float | None = None
    direction: Direction | None = None
    n_total: int | None = None
    n_bad: int | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    redacted: bool = True
    seed: int | None = None

    @property
    def u(self) -> float | None:
        if self.value is None or self.threshold is None or self.direction is None:
            return None
        return utilisation(self.value, self.threshold, self.direction)

    @property
    def band(self) -> Band | None:
        u = self.u
        return None if u is None else band(u)


class MetricPoint(BaseModel):
    ts: datetime
    service: str
    metric: str
    value: float
    segment_key: str = "*"
    n_total: int | None = None
    n_bad: int | None = None


class LogRecord(BaseModel):
    ts: datetime
    service: str
    level: Literal["DEBUG", "INFO", "WARN", "ERROR", "FATAL"] = "INFO"
    message: str
    template_id: str | None = None
    segment_key: str = "*"


class ChangeEvent(BaseModel):
    ts: datetime
    service: str
    change_id: str
    kind: Literal["deploy", "config", "cert", "flag", "maintenance"] = "deploy"
    description: str = ""


# --- detection --------------------------------------------------------------------------
class RiskFeatures(BaseModel):
    """Risk = sigma(-3 + 1.5 pred + eta_term + z_term + 0.6 corrob + 1.2 band + 1.3 binom)."""

    pred: float = 0.0
    eta_term: float = 0.0
    z_term: float = 0.0
    corrob: float = 0.0
    band: float = 0.0
    binom: float = 0.0


class Candidate(BaseModel):
    candidate_id: str
    ts: datetime
    service: str
    segment_key: str = "*"
    metric: str
    value: float
    threshold: float
    direction: Direction
    u: float
    band: Band
    z: float | None = None
    eta_minutes: float | None = None
    features: RiskFeatures = Field(default_factory=RiskFeatures)
    risk: float = 0.0
    tier0: bool = False
    evidence_ids: list[str] = Field(default_factory=list)


class IncidentCandidate(BaseModel):
    incident_id: str
    opened_ts: datetime
    root_cause_service: str
    segment_key: str = "*"
    candidates: list[Candidate]
    risk: float
    tier0: bool = False
    cascade_of: str | None = None


# --- RCA contract (FP 7.5), strict ------------------------------------------------------
class Hypothesis(_Strict):
    code: RootCauseCode
    confidence: float = Field(ge=0, le=1)
    statement: str
    evidence_ids: list[str]


class SimilarIncident(_Strict):
    id: str
    similarity: float
    fix: str


class Impact(_Strict):
    customers_affected_est: int
    pkr_at_risk_per_min: float
    label: Literal["estimate"]


class ActionParams(_NullableRequired):
    """Union of all action parameters; unused ones are null."""

    bank: str | None = None
    rail: Rail | None = None
    provider: str | None = None
    service: str | None = None
    instances: int | None = Field(default=None, ge=1)
    change_id: str | None = None
    source_ids: list[str] | None = None
    team: str | None = None
    ttl_minutes: int | None = None
    delay_minutes: int | None = None


class RCAAction(_Strict):
    type: ActionType
    params: ActionParams
    rationale: str


class CommsDraft(_Strict):
    in_app_banner: str
    bank_partner_note: str


class SkepticReport(_Strict):
    verdict: SkepticVerdict
    confidence: float = Field(ge=0, le=1)


class RCA(_Strict):
    incident_id: str
    goal: str
    headline: str
    severity: Severity
    root_cause_service: str
    affected_segment: str
    eta_minutes: float | None
    hypotheses: list[Hypothesis]
    similar_incidents: list[SimilarIncident]
    runbook_steps: list[str]
    impact: Impact
    actions: list[RCAAction]
    summary_technical: str
    summary_business: str
    comms_draft: CommsDraft
    if_ignored: str
    skeptic: SkepticReport
    plan_versions: int
    generated_by: GeneratedBy
    low_confidence: bool


# --- actions ----------------------------------------------------------------------------
class ActionRequest(BaseModel):
    incident_id: str
    type: ActionType
    params: ActionParams = Field(default_factory=ActionParams)
    rationale: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    requested_by: str = "agent"
    window: str = ""
    """Idempotency window label (e.g. an event-time bucket); part of the key."""

    @property
    def idempotency_key(self) -> str:
        scope = json.dumps(self.params.model_dump(exclude_none=True), sort_keys=True)
        return ids.idempotency_key(self.type, scope, self.window)


class GuardVerdict(BaseModel):
    allowed: bool
    mode: ActionMode
    rule: str
    reason: str = ""


class ActionRecord(BaseModel):
    action_id: str
    request: ActionRequest
    idempotency_key: str
    mode: ActionMode
    status: ActionStatus = "PENDING"
    created_ts: datetime
    executed_ts: datetime | None = None
    expires_at: datetime | None = None
    rollback_at: datetime | None = None
    result: str = ""
    verdict: GuardVerdict | None = None


class Approval(BaseModel):
    approval_id: str
    action_id: str
    approver: str
    decision: Literal["APPROVED", "REJECTED"]
    ts: datetime
    expires_at: datetime
    comment: str = ""


class Ticket(BaseModel):
    ticket_id: str
    incident_id: str
    team: str
    title: str
    body: str
    cc: list[str] = Field(default_factory=list)
    status: Literal["OPEN", "CLOSED"] = "OPEN"


class Feedback(BaseModel):
    feedback_id: str
    incident_id: str
    verdict: Literal["TRUE_POSITIVE", "FALSE_POSITIVE", "WRONG_CAUSE"]
    comment: str = ""
    ts: datetime | None = None


class PolicyState(BaseModel):
    security_autonomy: Autonomy = "shadow"
    kill_switch: bool = False
    autonomous_actions_last_hour: int = 0
    pages_last_hour_by_team: dict[str, int] = Field(default_factory=dict)


# --- trace and results ------------------------------------------------------------------
class TraceStep(BaseModel):
    incident_id: str
    seq: int
    ts: datetime
    actor: str
    kind: TraceKind
    summary: str
    detail: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class IncidentResult(BaseModel):
    incident_id: str
    status: IncidentStatus = "OPEN"
    candidate: IncidentCandidate | None = None
    rca: RCA | None = None
    actions: list[ActionRecord] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)
    opened_ts: datetime | None = None
    resolved_ts: datetime | None = None
    lead_time_min: float | None = None


class ScorecardRow(BaseModel):
    system: str
    split: str
    tp: int = 0
    fp: int = 0
    fn: int = 0
    precision: float | None = None
    recall: float | None = None
    median_lead_min: float | None = None
    rca_accuracy: float | None = None
    notes: str = ""


PUBLIC_MODELS: tuple[type[BaseModel], ...] = (
    CES, MetricPoint, LogRecord, ChangeEvent, RiskFeatures, Candidate, IncidentCandidate,
    Hypothesis, SimilarIncident, Impact, ActionParams, RCAAction, CommsDraft, SkepticReport, RCA,
    ActionRequest, GuardVerdict, ActionRecord, Approval, Ticket, Feedback, PolicyState,
    TraceStep, IncidentResult, ScorecardRow,
)  # fmt: skip

SNAPSHOT_PATH = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "schema_snapshot.json"


def schema_snapshot() -> dict[str, Any]:
    return {m.__name__: m.model_json_schema() for m in PUBLIC_MODELS}


def _main(argv: list[str]) -> int:
    if "--write-snapshot" in argv:
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_PATH.write_text(json.dumps(schema_snapshot(), indent=2, sort_keys=True) + "\n")
        print(f"wrote {SNAPSHOT_PATH}")
        return 0
    print("usage: python -m sentinel.schemas --write-snapshot")
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
