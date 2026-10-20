"""Dataset → CES envelopes, and the in-process replayer (FINAL_PLAN §4.3).

One envelope per service per tick, carrying all of that service's metrics — the same shape finpay-sim emits:
    {"service": str, "ts": iso, "events": [CES, ...]}
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable, Iterator
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sentinel.bus import Bus
from sentinel.datagen.generator import Dataset, Series

PKT = ZoneInfo("Asia/Karachi")


def _by_service(ds: Dataset) -> dict[str, list[Series]]:
    out: dict[str, list[Series]] = defaultdict(list)
    for s in ds.series.values():
        out[s.service].append(s)
    return out


def envelopes_at(ds: Dataset, i: int, source: str = "ps02_replay", grouped=None) -> list[dict]:
    ts = ds.index[i].to_pydatetime().replace(tzinfo=PKT).isoformat()
    out = []
    for svc, series in (grouped or _by_service(ds)).items():
        events = []
        for s in series:
            ev = {
                "event_id": f"{ds.mode}-{ds.seed}-{i}-{s.service}-{s.metric}-{s.segment}",
                "ts": ts,
                "source": source,
                "kind": "metric",
                "service": s.service,
                "segment_key": s.segment,
                "metric": s.metric,
                "value": s.value_at(i),
                "threshold": s.threshold_at(i),
                "direction": s.direction,
                "n_total": int(s.n_total[i]) if s.n_total is not None else None,
                "n_bad": int(s.n_bad[i]) if s.n_bad is not None else None,
                "attributes": {},
                "redacted": True,
                "seed": ds.seed,
            }
            events.append(ev)
        out.append({"service": svc, "ts": ts, "events": events})
    return out


def iter_envelopes(ds: Dataset, start: datetime | None = None, end: datetime | None = None) -> Iterator[list[dict]]:
    i0 = ds.loc(start) if start else 0
    i1 = ds.loc(end) if end else len(ds.index)
    grouped = _by_service(ds)
    for i in range(max(0, i0), min(len(ds.index), i1)):
        yield envelopes_at(ds, i, grouped=grouped)


def episode_window(ds: Dataset, episode_id: str, before_min: int = 30, after_min: int = 15) -> tuple[datetime, datetime]:
    ep = next(e for e in ds.episodes if e.id == episode_id)
    return ep.precursor_start - timedelta(minutes=before_min), ep.end + timedelta(minutes=after_min)


async def replay(
    ds: Dataset,
    bus: Bus,
    speed: float = 600.0,
    start: datetime | None = None,
    end: datetime | None = None,
    episode_id: str | None = None,
    on_tick: Callable[[int], Awaitable[None]] | None = None,
) -> int:
    """Publish envelopes minute by minute; `speed`× real time (0 = as fast as possible). Returns ticks sent."""
    if episode_id:
        start, end = episode_window(ds, episode_id)
    ticks = 0
    for envs in iter_envelopes(ds, start, end):
        for env in envs:
            await bus.publish(env)
        ticks += 1
        if on_tick:
            await on_tick(ticks)
        if speed > 0:
            await asyncio.sleep(60.0 / speed)
    return ticks
