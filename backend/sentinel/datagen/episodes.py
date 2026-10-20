"""PS-02 episode map: every CRITICAL CSV row becomes an incident episode or a hard negative (FINAL_PLAN §5).

The map is a fixed, seeded table committed to backend/data/ps02_episode_map.yaml so anyone can audit it:
    uv run python -m sentinel.datagen.episodes --write
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import yaml

from sentinel.config import settings
from sentinel.eval.csv_bench import load_ps02

MAP_SEED = 20261020
MAP_PATH = settings.config_dir / "ps02_episode_map.yaml"

# Precursor lead ranges in minutes (FINAL_PLAN §3.3) and post-onset duration ranges.
LEAD_RANGE = {
    "RC-BANK": (20, 45),
    "RC-DBPOOL": (10, 40),
    "RC-OTP-PROVIDER": (10, 30),
    "RC-QUEUE": (60, 120),
    "RC-MEMLEAK": (40, 120),
    "RC-ABRUPT": (0, 0),
}
DURATION_RANGE = (10, 40)
NEGATIVE_MIX = {"N1": 6, "N3": 5, "N5": 6, "N6": 5}  # 22 false CRITICALs; N2/N4 arrive in P1
ABRUPT_SHARE = 0.2
SURGE_CONFOUNDER_SHARE = 0.15
DEPLOY_CONFOUNDER_SHARE = 0.25
BANKS = ["BANK_A", "BANK_B", "BANK_C", "BANK_D", "BANK_E"]

# The two CSV cascades (within 25 min): (root, symptom) by row timestamp.
CASCADES = [
    ("2026-08-01T10:38:14", "2026-08-01T10:59:06"),
    ("2026-08-16T06:20:01", "2026-08-16T06:32:07"),
]
# Kept non-abrupt so the demo beats exist: the 08-01 cascade and one RC-BANK episode in the test split.
NEVER_ABRUPT = {"2026-08-01T10:38:14", "2026-08-01T10:59:06", "2026-08-22T19:55:05"}


def code_for(service: str, metric: str) -> str:
    """Metric/service → root-cause code. Deterministic and auditable (see ps02_episode_map.yaml)."""
    if service == "NotificationHub":
        return "RC-OTP-PROVIDER"  # OTP provider trouble shows up as retries saturating the hub
    if service == "PaymentGateway" and metric in ("latency_p99", "error_rate", "queue_depth"):
        return "RC-BANK"  # a slow partner bank backs up payments
    if metric in ("memory_usage", "cpu_usage"):
        return "RC-MEMLEAK"  # leak → GC thrash → CPU
    if metric == "queue_depth" or (metric in ("latency_p99", "disk_io") and service in BATCH_SERVICES):
        return "RC-QUEUE"  # settlement / batch consumers falling behind
    return "RC-DBPOOL"


BATCH_SERVICES = {"DataPipeline", "ReportGenerator", "AnalyticsDashboard"}


@dataclass
class Episode:
    id: str
    kind: str  # incident | negative
    anchor_row: int
    ts: str  # CSV timestamp (PKT, naive ISO)
    service: str
    metric: str
    u: float
    code: str  # RC-* for incidents, N1/N3/N5/N6 for negatives
    abrupt: bool = False
    lead_min: int = 0
    duration_min: int = 0
    segment: str = "*"
    cascade_root: str | None = None
    confounders: list[str] = field(default_factory=list)

    @property
    def onset(self) -> datetime:
        return datetime.fromisoformat(self.ts).replace(second=0)

    @property
    def precursor_start(self) -> datetime:
        return self.onset - timedelta(minutes=self.lead_min)

    @property
    def end(self) -> datetime:
        return self.onset + timedelta(minutes=self.duration_min)


def build_episode_map(seed: int = MAP_SEED) -> list[Episode]:
    rng = np.random.default_rng(seed)
    df = load_ps02().reset_index(names="row")
    crit = df[df["alert_level"] == "CRITICAL"].sort_values("timestamp")
    inc = crit[crit["is_incident"] == 1]
    neg = crit[crit["is_incident"] == 0]

    # Same-series alert anchors bound how far a precursor may reach back without crossing another anchor.
    alerts = df[df["alert_level"] != "NORMAL"]

    def max_lead(row) -> int:
        same = alerts[(alerts.service_name == row.service_name) & (alerts.metric_type == row.metric_type)]
        prev = same[same.timestamp < row.timestamp].timestamp
        return 120 if prev.empty else int((row.timestamp - prev.max()).total_seconds() // 60) - 10

    cascade_symptoms = {s: r for r, s in CASCADES}
    eligible_abrupt = [
        r.timestamp.isoformat() for r in inc.itertuples() if r.timestamp.isoformat() not in NEVER_ABRUPT
    ]
    n_abrupt = round(ABRUPT_SHARE * len(inc))
    abrupt = set(rng.choice(eligible_abrupt, size=n_abrupt, replace=False))

    episodes: list[Episode] = []
    for i, r in enumerate(inc.itertuples(), start=1):
        ts = r.timestamp.isoformat()
        code = code_for(r.service_name, r.metric_type)
        root = cascade_symptoms.get(ts)
        if root is not None:  # a cascade symptom shares its root's cause
            root_row = inc[inc.timestamp == datetime.fromisoformat(root)].iloc[0]
            code = code_for(root_row.service_name, root_row.metric_type)
        is_abrupt = ts in abrupt
        lo, hi = LEAD_RANGE[code]
        lead = 0 if is_abrupt else int(min(rng.integers(lo, hi + 1), max_lead(r)))
        seg = "*"
        if code == "RC-BANK":
            seg = f"bank={rng.choice(BANKS)}"
        elif code == "RC-OTP-PROVIDER":
            seg = "provider=P1"
        episodes.append(
            Episode(
                id=f"INC-PS02-{i:04d}",
                kind="incident",
                anchor_row=int(r.row),
                ts=ts,
                service=r.service_name,
                metric=r.metric_type,
                u=float(r.u),
                code=code,
                abrupt=is_abrupt,
                lead_min=lead,
                duration_min=int(rng.integers(*DURATION_RANGE)),
                segment=seg,
                cascade_root=root,
            )
        )
    by_ts = {e.ts: e for e in episodes}
    for _, s in CASCADES:
        by_ts[s].cascade_root = by_ts[by_ts[s].cascade_root].id

    # Confounders: real incidents that look benign (surge) or follow a deploy that caused them.
    # A surge must never sit next to an N6 on the same service, or the N6 would gain benign evidence.
    n6_kinds = [k for k, n in NEGATIVE_MIX.items() for _ in range(n)]
    n6_rng = np.random.default_rng(seed + 1)
    n6_rng.shuffle(n6_kinds)
    # N6 is "no benign explanation": it may not fall on a calendar-event day (salary days, sale) — swap it away.
    special = [r.timestamp.day in (1, 2, 3, 14) for r in neg.itertuples()]
    for a, k in enumerate(n6_kinds):
        if k == "N6" and special[a]:
            b = next(b for b in range(len(n6_kinds)) if not special[b] and n6_kinds[b] != "N6")
            n6_kinds[a], n6_kinds[b] = n6_kinds[b], k
    n6 = [(r.service_name, r.timestamp) for r, k in zip(neg.itertuples(), n6_kinds, strict=True) if k == "N6"]

    def near_n6(e: Episode) -> bool:
        return any(svc == e.service and abs((ts - e.onset).total_seconds()) < 4 * 3600 for svc, ts in n6)

    real = [e for e in episodes if not e.abrupt and not near_n6(e)]
    for e in rng.choice(real, size=round(SURGE_CONFOUNDER_SHARE * len(episodes)), replace=False):
        e.confounders.append("surge")
    deployable = [e for e in episodes if e.code in ("RC-DBPOOL", "RC-MEMLEAK")]
    for e in rng.choice(
        deployable, size=max(1, round(DEPLOY_CONFOUNDER_SHARE * len(deployable))), replace=False
    ):
        e.confounders.append("deploy")

    kinds = n6_kinds
    for j, (r, kind) in enumerate(zip(neg.itertuples(), kinds, strict=True), start=1):
        lead = {"N1": int(rng.integers(20, 41)), "N3": 5, "N5": 0, "N6": int(rng.integers(5, 9))}[kind]
        dur = {
            "N1": int(rng.integers(3, 8)),
            "N3": int(rng.integers(15, 26)),
            "N5": 2,
            "N6": int(rng.integers(3, 7)),
        }[kind]
        episodes.append(
            Episode(
                id=f"NEG-PS02-{j:04d}",
                kind="negative",
                anchor_row=int(r.row),
                ts=r.timestamp.isoformat(),
                service=r.service_name,
                metric=r.metric_type,
                u=float(r.u),
                code=kind,
                lead_min=min(lead, max_lead(r)),
                duration_min=dur,
            )
        )
    return episodes


def write_map(episodes: list[Episode], path: Path = MAP_PATH) -> None:
    doc = {
        "seed": MAP_SEED,
        "note": "Generated by `python -m sentinel.datagen.episodes --write`. Do not hand-edit.",
        "episodes": [asdict(e) for e in episodes],
    }
    path.write_text(yaml.safe_dump(doc, sort_keys=False, width=120))


def load_map(path: Path = MAP_PATH) -> list[Episode]:
    with path.open() as f:
        return [Episode(**e) for e in yaml.safe_load(f)["episodes"]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    eps = build_episode_map()
    if args.write:
        write_map(eps)
    from collections import Counter

    print(Counter(e.code for e in eps), "abrupt:", sum(e.abrupt for e in eps))


if __name__ == "__main__":
    main()
