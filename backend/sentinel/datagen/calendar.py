"""Business calendar (backend/data/calendar.yaml): load profile, TPS multipliers and benign context events.

All timestamps in the generator are naive PKT minutes (the PS-02 CSV is naive and read as PKT).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import cache

import numpy as np
import pandas as pd
import yaml

from sentinel.config import settings

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


@cache
def load_calendar() -> dict:
    with (settings.config_dir / "calendar.yaml").open() as f:
        return yaml.safe_load(f)


def load_profile(index: pd.DatetimeIndex) -> np.ndarray:
    """Relative load per minute: hourly profile, linearly interpolated within the hour."""
    prof = load_calendar()["daily_tps_profile"]
    hours = np.array([prof[h] for h in range(24)] + [prof[0]])
    frac = index.hour.to_numpy() + index.minute.to_numpy() / 60.0
    return np.interp(frac, np.arange(25), hours)


def tps_multiplier(index: pd.DatetimeIndex) -> np.ndarray:
    mult = np.ones(len(index))
    for ev in load_calendar()["events"]:
        if ev["kind"] == "salary_day":
            mult[np.isin(index.day, ev["days_of_month"])] *= ev["tps_multiplier"]
        elif ev["kind"] == "sale":
            mult[index.normalize() == pd.Timestamp(ev["date"])] *= ev["tps_multiplier"]
    return mult


def static_events(start: datetime, end: datetime) -> list[dict]:
    """Materialise calendar.yaml into dated events within [start, end)."""
    cal = load_calendar()
    out: list[dict] = []
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while day < end:
        for ev in cal["events"]:
            if ev["kind"] == "salary_day" and day.day in ev["days_of_month"]:
                out.append(_ev(day, day + timedelta(days=1), "calendar", "*", "salary_day", ev))
            elif ev["kind"] == "sale" and day.date().isoformat() == ev["date"]:
                out.append(_ev(day, day + timedelta(days=1), "calendar", "*", "sale", ev))
            elif ev["kind"] == "bank_maintenance" and WEEKDAYS[day.weekday()] == ev["weekday"]:
                s = _at(day, ev["start"])
                out.append(_ev(s, _at(day, ev["end"]), "calendar", "PaymentGateway", "bank_maintenance", ev))
        for job in cal["schedules"]:
            s = _at(day, job["start"])
            out.append(
                _ev(s, s + timedelta(minutes=job["minutes"]), "cron", job["service"], job["name"], job)
            )
        day += timedelta(days=1)
    return [e for e in out if e["end"] > start and e["ts"] < end]


def _at(day: datetime, hhmm: str) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return day.replace(hour=h, minute=m)


def _ev(ts: datetime, end: datetime, kind: str, service: str, name: str, cfg: dict) -> dict:
    attrs = {k: v for k, v in cfg.items() if k not in ("kind",)}
    return {
        "ts": ts,
        "end": end,
        "kind": kind,
        "service": service,
        "name": name,
        "attributes": attrs,
        "caused": False,
    }
