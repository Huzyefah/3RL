"""Shared contract for the data generator (Phase 2). Frozen at the Phase 2 gate.

All timestamps are timezone-naive UTC-less wall times exactly as in the PS-02 CSV (PKT labels in the
plan; the CSV carries no zone). Series are 1-minute resolution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

import pandas as pd

Mode = Literal["ps02", "seeded"]
RCCode = Literal[
    "RC-BANK",
    "RC-DBPOOL",
    "RC-OTP-PROVIDER",
    "RC-QUEUE",
    "RC-AUTH-ATTACK",
    "RC-MEMLEAK",
    "RC-CERT",
    "RC-ABRUPT",
]
NegCode = Literal["N1", "N2", "N3", "N4", "N5", "N6"]
EpisodeKind = Literal["incident", "negative"]

# Columns of Dataset.metrics (one row per service/metric/segment per minute).
METRIC_COLUMNS = [
    "ts",  # datetime, minute resolution
    "service",  # CSV service name
    "metric",  # one of the 7 PS-02 metrics, or a segment rate metric
    "segment_key",  # "*" or "bank=BANK_C" or "provider=P1"
    "value",
    "threshold",
    "direction",  # higher_bad | lower_bad
    "n_total",  # rate metrics only, else 0
    "n_bad",
    "u",  # utilisation (sentinel.utilisation)
    "is_anchor",  # True for the 500 pinned CSV rows
    "source",  # ps02_replay | seeded_replay
]
LOG_COLUMNS = ["ts", "service", "level", "template_id", "message"]
# kind: deploy | maintenance | campaign | cron
EVENT_COLUMNS = ["ts", "kind", "service", "text", "event_id"]


@dataclass(frozen=True)
class EpisodeAssignment:
    """One row of ps02_episode_map.yaml: how a CSV CRITICAL anchor is explained."""

    anchor_ts: str  # original CSV timestamp, seconds included
    service: str
    metric: str
    kind: EpisodeKind
    code: str  # RCCode for incidents, NegCode for negatives
    episode_id: str  # INC-00NN or FA-00NN (sentinel.ids)
    onset_ts: str  # anchor floored to the minute (ISO)
    abrupt: bool = False
    segment_key: str = "*"
    cascade_parent: str | None = None  # episode_id of the upstream incident (08-01 pair only)
    benign_evidence: tuple[str, ...] = ()  # calendar/event ids a tool could find; N6 has none
    rationale: str = ""


@dataclass(frozen=True)
class GroundTruthEpisode:
    episode_id: str
    kind: EpisodeKind
    code: str
    service: str
    segment_key: str
    precursor_start: datetime  # == onset when abrupt
    onset: datetime
    end: datetime
    abrupt: bool
    anchor_ts: str | None  # None in seeded mode
    cascade_parent: str | None = None
    benign_evidence: tuple[str, ...] = ()


@dataclass
class Dataset:
    mode: Mode
    seed: int
    window: tuple[datetime, datetime]
    metrics: pd.DataFrame
    logs: pd.DataFrame
    events: pd.DataFrame
    ground_truth: list[GroundTruthEpisode] = field(default_factory=list)

    def episode(self, episode_id: str) -> GroundTruthEpisode:
        for e in self.ground_truth:
            if e.episode_id == episode_id:
                return e
        raise KeyError(episode_id)


@dataclass(frozen=True)
class MemoryDoc:
    """A short postmortem document for recall_similar (tagged source=ps02 or seeded)."""

    doc_id: str  # INC-0007 / FA-0003 / S3-E2
    ts: datetime
    code: str
    service: str
    text: str
    fix: str
    source: str  # ps02 | seeded
    split: Literal["train", "test"]
