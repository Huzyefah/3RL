"""Historical corpus for recall_similar: one short postmortem per PS-02 episode (FINAL_PLAN §5).

During evaluation only train-split documents are in memory, so test incidents can never be "recalled".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sentinel.datagen.episodes import Episode, load_map
from sentinel.eval.splits import PS02_TEST, PS02_TRAIN
from sentinel.topology import Topology

FIXES = {
    "RC-BANK": "Rerouted {seg} IBFT via Raast for 40 min; partner-bank NOC notified; reverted after their switch recovered.",
    "RC-DBPOOL": "Raised DB pool 20→40 and rolled back the slow-query release; added the missing index.",
    "RC-OTP-PROVIDER": "Failed OTP over from SMS provider P1 to P2; raised a ticket with P1.",
    "RC-QUEUE": "Scaled settlement consumers 4→8; backlog drained before the 16:00 cut-off.",
    "RC-MEMLEAK": "Rolling restart of the affected pods; leak fixed in the model-loader cache.",
    "N1": "No action: marketing-campaign surge; capacity held and metrics recovered.",
    "N3": "No action: scheduled batch job; plateau ended on schedule.",
    "N5": "No action: transient spike already recovering.",
    "N6": "No action: unexplained excursion; watched 15 min, recovered on its own.",
}
SYMPTOMS = {
    "RC-BANK": "issuer timeouts (ISO8583 RC=91) rose at {seg} before payment latency breached",
    "RC-DBPOOL": "connection pool use climbed convexly, then p99 latency and errors followed",
    "RC-OTP-PROVIDER": "OTP delivery from provider P1 fell; NotificationHub retries saturated resources",
    "RC-QUEUE": "settlement consumer lag accelerated; disk and latency rose with the backlog",
    "RC-MEMLEAK": "memory rose linearly with GC overhead, then CPU and p99 latency",
    "N1": "every signal ramped together during a traffic surge",
    "N3": "a plateau began at a scheduled batch start",
    "N5": "a 1–3 minute touch of CRITICAL with no trend",
    "N6": "a short excursion with no corroborating evidence",
}
RUNBOOKS = {
    "RC-BANK": [
        "Confirm the segment (bank) breakdown",
        "Check Raast health (u < 0.75)",
        "Request reroute_bank (HITL)",
        "Notify partner-bank NOC",
    ],
    "RC-DBPOOL": [
        "Check recent deploys",
        "Inspect slow-query log",
        "Request scale_service or rollback (HITL)",
    ],
    "RC-OTP-PROVIDER": ["Compare P1 vs P2 delivery", "Check P2 health", "Request otp_failover (HITL)"],
    "RC-QUEUE": ["Project lag drain vs 16:00 cut-off", "Request scale consumers (HITL)", "Warn finance ops"],
    "RC-MEMLEAK": ["Confirm linear memory ramp", "Request restart (HITL)", "Open engineering ticket"],
}


@dataclass(frozen=True)
class MemoryDoc:
    id: str
    source: Literal["ps02"]
    label: Literal["incident", "false_alarm"]
    code: str
    service: str
    metric: str
    segment: str
    ts: str
    text: str
    fix: str
    runbook: tuple[str, ...]


def to_doc(e: Episode, topo: Topology) -> MemoryDoc:
    seg = e.segment.split("=")[-1] if e.segment != "*" else "the platform"
    text = (
        f"{e.id} on {e.ts[:16]} PKT: {topo.services[e.service]['display']} {e.metric} reached u={e.u:.3f}. "
        f"Pattern: {SYMPTOMS[e.code].format(seg=seg)}."
    )
    return MemoryDoc(
        id=e.id,
        source="ps02",
        label="incident" if e.kind == "incident" else "false_alarm",
        code=e.code,
        service=e.service,
        metric=e.metric,
        segment=e.segment,
        ts=e.ts,
        text=text,
        fix=FIXES[e.code].format(seg=seg),
        runbook=tuple(RUNBOOKS.get(e.code, ())),
    )


def corpus(split: Literal["train", "test", "all"] = "train") -> list[MemoryDoc]:
    topo = Topology.load()
    lo, hi = {"train": PS02_TRAIN, "test": PS02_TEST, "all": (PS02_TRAIN[0], PS02_TEST[1])}[split]
    return [to_doc(e, topo) for e in load_map() if lo <= e.onset < hi]
