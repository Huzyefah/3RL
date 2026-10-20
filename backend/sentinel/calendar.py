"""Business calendar (salary days, campaigns, maintenance, EOD) from ``data/calendar.yaml``."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, ConfigDict

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "calendar.yaml"
LOCAL_TZ = ZoneInfo("Asia/Karachi")


class CalendarEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: str
    description: str
    tps_multiplier: float = 1.0
    authored_to_explain_anchor: bool = False
    # Exactly one timing style: days_of_month, absolute start/end, weekday+HH:MM, or cron.
    days_of_month: list[int] | None = None
    start: str | None = None
    end: str | None = None
    weekday: int | None = None
    cron: str | None = None
    tz: str | None = None
    duration_min: int | None = None
    service: str | None = None
    segment: str | None = None
    benign_for: list[str] | None = None

    def active_at(self, ts: datetime) -> bool:
        if ts.tzinfo is not None:
            ts = ts.astimezone(LOCAL_TZ).replace(tzinfo=None)
        if self.days_of_month is not None:
            return ts.day in self.days_of_month
        if self.cron is not None:  # only the "M H * * *" daily form is supported
            minute, hour = self.cron.split()[:2]
            begin = ts.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
            return begin <= ts < begin + timedelta(minutes=self.duration_min or 0)
        if self.start is None or self.end is None:
            return False
        if self.weekday is not None:
            if ts.weekday() != self.weekday:
                return False
            return time.fromisoformat(self.start) <= ts.time() < time.fromisoformat(self.end)
        return datetime.fromisoformat(self.start) <= ts < datetime.fromisoformat(self.end)


def load_calendar(path: Path | str | None = None) -> list[CalendarEvent]:
    raw = yaml.safe_load(Path(path or DEFAULT_PATH).read_text())
    return [CalendarEvent.model_validate(e) for e in raw["events"]]


def events_at(ts: datetime, calendar: list[CalendarEvent] | None = None) -> list[CalendarEvent]:
    """Calendar events active at ``ts`` (naive timestamps are Asia/Karachi wall clock)."""
    return [e for e in (calendar if calendar is not None else load_calendar()) if e.active_at(ts)]
