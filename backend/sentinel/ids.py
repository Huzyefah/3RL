"""ID schemes (D9) and deterministic evidence / idempotency IDs."""

import hashlib
import json
import re
from datetime import datetime
from typing import Any

_KIND_RE = re.compile(r"^[a-z_]+$")
PS02_INCIDENTS = 28
PS02_FALSE_ALARMS = 22


def ps02_incident_id(n: int) -> str:
    """Ground-truth PS-02 incident, chronological: INC-0001..INC-0028."""
    if not 1 <= n <= PS02_INCIDENTS:
        raise ValueError(f"PS-02 incident number out of range: {n}")
    return f"INC-{n:04d}"


def false_alarm_id(n: int) -> str:
    """PS-02 false CRITICAL: FA-0001..FA-0022."""
    if not 1 <= n <= PS02_FALSE_ALARMS:
        raise ValueError(f"PS-02 false-alarm number out of range: {n}")
    return f"FA-{n:04d}"


def runtime_incident_id(event_ts: datetime, n: int) -> str:
    """Runtime incident, dated by the event clock: INC-YYYY-MMDD-NNN."""
    return f"INC-{event_ts:%Y-%m%d}-{n:03d}"


def seeded_episode_id(seed: int, n: int) -> str:
    """Seeded-generator episode: S{seed}-E{n}."""
    return f"S{seed}-E{n}"


def _digest(*parts: Any) -> str:
    blob = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def evidence_id(kind: str, payload: Any) -> str:
    """``<kind>:<hash8>``; same kind and payload always give the same ID."""
    if not _KIND_RE.fullmatch(kind):
        raise ValueError(f"evidence kind must match [a-z_]+: {kind!r}")
    return f"{kind}:{_digest(kind, payload)[:8]}"


def idempotency_key(action_type: str, scope: str, window: str) -> str:
    """``hash(type, scope, window)`` (FP 8.2)."""
    return _digest(action_type, scope, window)[:16]
