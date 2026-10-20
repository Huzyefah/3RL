"""Deterministic postmortem corpus for ``recall_similar`` (no LLM).

Each of the 28 PS-02 incidents and 22 false alarms becomes a short doc built from the episode map
and the runbooks. Evaluation rule: unless ``include_test`` is set, only train-split docs exist.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import cache, lru_cache
from pathlib import Path
from typing import Literal

from sentinel.datagen.episode_map import load_episode_map
from sentinel.datagen.types import EpisodeAssignment, MemoryDoc
from sentinel.eval.splits import split_of

RUNBOOK_DIR = Path(__file__).resolve().parents[2] / "data" / "runbooks"

# Typical time from onset to recovery, minutes (estimate used in the narrative only).
_DURATION_MIN = {
    "RC-BANK": 45,
    "RC-DBPOOL": 25,
    "RC-OTP-PROVIDER": 20,
    "RC-QUEUE": 60,
    "RC-AUTH-ATTACK": 15,
    "RC-MEMLEAK": 90,
    "RC-CERT": 30,
    "RC-ABRUPT": 20,
}

_BENIGN = {
    "N1": "business campaign or salary-day surge in proportion to traffic",
    "N3": "scheduled end-of-day settlement batch",
    "N4": "short deploy blip that settled after the rollout",
    "N5": "transient spike that self-resolved within minutes with no error signal",
    "N6": "unexplained: no calendar, deploy or maintenance evidence, it recovered on its own",
}


_FA_DURATION_MIN = 10  # false alarms self-resolve quickly

# doc_id -> naive wall time the episode ended (onset + estimated duration). A postmortem only
# exists once the episode is over; ``MemoryDoc.ts`` stays the onset for display.
_CLOSED_AT: dict[str, datetime] = {}


@cache
def _runbook(code: str) -> tuple[str, str]:
    """(signal, preventive action) from RC-*.md."""
    text = (RUNBOOK_DIR / f"{code}.md").read_text()
    signal = next(
        (ln[len("Signal:") :].strip() for ln in text.splitlines() if ln.startswith("Signal:")), ""
    )
    return signal.rstrip("."), text.split("## Preventive action")[1].strip()


def _segment(a: EpisodeAssignment) -> str:
    return "" if a.segment_key == "*" else f" (segment {a.segment_key})"


def _incident_doc(a: EpisodeAssignment, by_id: dict[str, EpisodeAssignment]) -> MemoryDoc:
    signal, fix = _runbook(a.code)
    parts = [f"Incident: {a.service} {a.metric} went CRITICAL{_segment(a)}."]
    if a.abrupt:
        parts.append("No precursor was visible; the metric jumped without a lead signal.")
    else:
        parts.append(f"Precursor pattern: {signal}.")
    if a.cascade_parent:
        up = by_id[a.cascade_parent]
        parts.append(
            f"Cascade: the upstream {up.service} connection pool leak ({up.episode_id}) "
            f"exhausted shared database capacity and spread to {a.service}."
        )
    parts.append(f"Root cause class {a.code}. Fix: {fix}")
    parts.append(f"Estimated duration {_DURATION_MIN[a.code]} minutes.")
    return _doc(a, " ".join(parts), fix)


def _false_alarm_doc(a: EpisodeAssignment) -> MemoryDoc:
    ev = f" Benign evidence: {', '.join(a.benign_evidence)}." if a.benign_evidence else ""
    text = (
        f"False alarm: {a.service} {a.metric} breached its threshold{_segment(a)} "
        f"but was not an incident ({a.code}). Mechanism: {_BENIGN[a.code]}.{ev} "
        "Check the calendar, cron and deploy log before escalating."
    )
    return _doc(a, text, _runbook("RC-BENIGN")[1])


def _doc(a: EpisodeAssignment, text: str, fix: str) -> MemoryDoc:
    onset = datetime.fromisoformat(a.onset_ts)
    minutes = _DURATION_MIN[a.code] if a.kind == "incident" else _FA_DURATION_MIN
    _CLOSED_AT[a.episode_id] = onset + timedelta(minutes=minutes)
    return MemoryDoc(
        doc_id=a.episode_id,
        ts=onset,
        code=a.code,
        service=a.service,
        text=text,
        fix=fix,
        source="ps02",
        split=split_of(a.onset_ts),
    )


@lru_cache(maxsize=1)
def _all_docs() -> tuple[MemoryDoc, ...]:
    eps = load_episode_map()
    by_id = {a.episode_id: a for a in eps}
    docs = [_incident_doc(a, by_id) if a.kind == "incident" else _false_alarm_doc(a) for a in eps]
    return tuple(sorted(docs, key=lambda d: (d.ts, d.doc_id)))


def corpus(
    split: Literal["train", "test", "all"] = "all", include_test: bool = False
) -> list[MemoryDoc]:
    """Docs of ``split``; without ``include_test`` test-split docs are never returned."""
    return [
        d
        for d in _all_docs()
        if (split == "all" or d.split == split) and (include_test or d.split == "train")
    ]


def docs_before(
    ts: datetime, exclude_id: str | None = None, include_test: bool = False
) -> list[MemoryDoc]:
    """Docs whose episode had ended strictly before ``ts`` (no future or in-flight leakage).

    Docs are naive (CSV wall time); a tz-aware ``ts`` (CES/EventClock are UTC) is reduced to its
    naive wall-clock fields. ``exclude_id`` is dropped.
    """
    ts = ts.replace(tzinfo=None)
    return [
        d
        for d in corpus("all", include_test=include_test)
        if _CLOSED_AT[d.doc_id] < ts and d.doc_id != exclude_id
    ]
