"""Frozen contracts shared by every module (FINAL_PLAN §4.3, §7.5, §8)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Direction = Literal["higher_bad", "lower_bad"]
Band = Literal["NORMAL", "WARNING", "CRITICAL"]
Severity = Literal["P1", "P2", "P3"]
Verdict = Literal["CONFIRMED", "DISPUTED", "BENIGN"]
LLMMode = Literal["fake", "live", "off"]

WARNING_U = 0.75
CRITICAL_U = 0.95

RC_CODES = (
    "RC-BANK",
    "RC-DBPOOL",
    "RC-OTP-PROVIDER",
    "RC-QUEUE",
    "RC-AUTH-ATTACK",
    "RC-MEMLEAK",
    "RC-CERT",
    "RC-ABRUPT",
    "RC-BENIGN",
)


def utilisation(value: float, threshold: float, direction: Direction) -> float:
    """Fraction of the error budget used; 1.0 means the SLO is breached (FINAL_PLAN §3.2)."""
    if direction == "higher_bad":
        return value / threshold
    return (1.0 - value) / (1.0 - threshold)


def band(u: float) -> Band:
    if u >= CRITICAL_U:
        return "CRITICAL"
    if u >= WARNING_U:
        return "WARNING"
    return "NORMAL"


def _new_id() -> str:
    return uuid.uuid4().hex


class CES(BaseModel):
    """Common Event Schema: every input is normalised to this before anything reads it."""

    event_id: str = Field(default_factory=_new_id)
    ts: datetime
    source: str  # ps02_replay | seeded_replay | finpay-sim | cloud-monitoring | webhook:<vendor>
    kind: Literal["metric", "log", "auth", "change", "ticket"] = "metric"
    service: str
    segment_key: str = "*"
    metric: str | None = None
    value: float | None = None
    threshold: float | None = None
    direction: Direction = "higher_bad"
    n_total: int | None = None
    n_bad: int | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    redacted: bool = True
    seed: int | None = None

    @property
    def u(self) -> float | None:
        if self.value is None or self.threshold is None:
            return None
        return utilisation(self.value, self.threshold, self.direction)


class Candidate(BaseModel):
    """One (service, metric, segment) whose detector risk crossed τ."""

    id: str = Field(default_factory=lambda: "cand-" + _new_id()[:12])
    ts: datetime
    service: str
    metric: str
    segment_key: str = "*"
    u: float
    eta_minutes: float | None = None
    z: float = 0.0
    corroboration: float = 0.0
    band: bool = False
    binom: bool = False
    predictive: bool = False
    risk: float
    triggers: list[str] = Field(default_factory=list)


class IncidentCandidate(BaseModel):
    """Grouped candidates: the upstream root plus downstream symptoms (FINAL_PLAN §6 grouping)."""

    id: str = Field(default_factory=lambda: "INC-" + _new_id()[:10].upper())
    opened_at: datetime
    root_service: str
    segment_key: str = "*"
    candidates: list[Candidate]
    symptom_services: list[str] = Field(default_factory=list)
    risk: float
    tier: int = 1

    @property
    def eta_minutes(self) -> float | None:
        etas = [c.eta_minutes for c in self.candidates if c.eta_minutes is not None]
        return min(etas) if etas else None


class Hypothesis(BaseModel):
    code: str
    confidence: float = Field(ge=0, le=1)
    statement: str
    evidence_ids: list[str] = Field(default_factory=list)


class SimilarIncident(BaseModel):
    id: str
    similarity: float
    fix: str


class Impact(BaseModel):
    customers_affected_est: int = 0
    pkr_at_risk_per_min: float = 0.0
    label: Literal["estimate"] = "estimate"


class ProposedAction(BaseModel):
    type: str
    params: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class SkepticSummary(BaseModel):
    verdict: Verdict
    confidence: float = Field(ge=0, le=1)


class CommsDraft(BaseModel):
    in_app_banner: str = ""
    bank_partner_note: str = ""


class RCA(BaseModel):
    """The Commander's output contract (FINAL_PLAN §7.5)."""

    incident_id: str
    goal: str
    headline: str
    severity: Severity
    root_cause_service: str
    affected_segment: str = "*"
    eta_minutes: float | None = None
    hypotheses: list[Hypothesis]
    similar_incidents: list[SimilarIncident] = Field(default_factory=list)
    runbook_steps: list[str] = Field(default_factory=list)
    impact: Impact = Field(default_factory=Impact)
    actions: list[ProposedAction] = Field(default_factory=list)
    summary_technical: str
    summary_business: str
    comms_draft: CommsDraft = Field(default_factory=CommsDraft)
    if_ignored: str = ""
    skeptic: SkepticSummary | None = None
    plan_versions: int = 1
    generated_by: Literal["llm", "statistical-fallback"] = "llm"
    low_confidence: bool = False

    @classmethod
    def fallback_example(cls) -> RCA:
        return cls(
            incident_id="INC-EXAMPLE",
            goal="Prevent PaymentGateway failures before the forecast breach",
            headline="PaymentGateway connection_pool will breach in ~12 min",
            severity="P2",
            root_cause_service="PaymentGateway",
            eta_minutes=12,
            hypotheses=[
                Hypothesis(code="RC-DBPOOL", confidence=0.5, statement="Pool use rising", evidence_ids=[])
            ],
            summary_technical="Statistical fallback: detector features only.",
            summary_business="Possible payment slowdown; engineers notified.",
            generated_by="statistical-fallback",
            low_confidence=True,
        )


class Action(BaseModel):
    """A requested action after the Policy Guard has decided its mode (FINAL_PLAN §8)."""

    id: str = Field(default_factory=lambda: "act-" + _new_id()[:12])
    incident_id: str
    type: str
    params: dict[str, Any] = Field(default_factory=dict)
    mode: Literal["AUTO", "HITL", "DENY", "SHADOW"]
    status: Literal[
        "pending", "approved", "rejected", "executed", "failed", "expired", "rolled_back", "denied"
    ]
    reason: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    requested_at: datetime
    expires_at: datetime | None = None
    rollback_at: datetime | None = None
    decided_by: str | None = None
    idempotency_key: str = ""


class Ticket(BaseModel):
    id: str = Field(default_factory=lambda: "TKT-" + _new_id()[:8].upper())
    incident_id: str
    team: str
    cc: list[str] = Field(default_factory=list)
    severity: Severity
    title: str
    body: str
    created_at: datetime
    status: Literal["open", "closed"] = "open"


class TraceStep(BaseModel):
    incident_id: str
    step: int
    ts: datetime
    agent: str  # commander | investigator | skeptic | runtime | guard | executor
    kind: str  # goal | plan | tool_call | verdict | replan | guard | action | verify | rca | fallback
    tool: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    evidence_id: str | None = None
    tokens: int = 0
    latency_ms: int = 0


class PolicyState(BaseModel):
    """Runtime-mutable switches (PUT /policy). Never toggled by redeploying."""

    llm_mode: LLMMode = "fake"
    security_autonomy: Literal["off", "shadow", "enforce"] = "shadow"
    kill_switch: bool = False
    skeptic_enabled: bool = True
