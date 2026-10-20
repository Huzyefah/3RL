"""Group candidates into incidents: same or dependency-linked services within a cascade window (FINAL_PLAN §6).

The upstream service is the root (the one the others depend on); downstream services attach as symptoms.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sentinel.schemas import Candidate, IncidentCandidate
from sentinel.topology import Topology

CASCADE_WINDOW_MIN = 25  # covers the 21-min 08-01 AuthService → PaymentGateway cascade


class Grouper:
    def __init__(self, topo: Topology | None = None, window_min: int = CASCADE_WINDOW_MIN) -> None:
        self.topo = topo or Topology.load()
        self.window = timedelta(minutes=window_min)
        self.open: list[IncidentCandidate] = []
        self._last: dict[str, datetime] = {}

    def add(self, c: Candidate) -> tuple[IncidentCandidate, bool]:
        """Attach `c` to an open incident or open a new one. Returns (incident, is_new)."""
        for inc in self.open:
            services = {inc.root_service, *inc.symptom_services}
            related = any(c.service == s or self.topo.linked(c.service, s) for s in services)
            if related and c.ts - self._last[inc.id] <= self.window:
                inc.candidates.append(c)
                self._last[inc.id] = c.ts
                if c.service not in services:
                    inc.symptom_services.append(c.service)
                self._reroot(inc)
                inc.risk = max(inc.risk, c.risk)
                return inc, False
        inc = IncidentCandidate(
            opened_at=c.ts,
            root_service=c.service,
            segment_key=c.segment_key,
            candidates=[c],
            risk=c.risk,
            tier=self.topo.tier(c.service),
        )
        self.open.append(inc)
        self._last[inc.id] = c.ts
        return inc, True

    def _reroot(self, inc: IncidentCandidate) -> None:
        services = [inc.root_service, *inc.symptom_services]

        # Root = the service most of the group depends on (directly); ties keep the earliest.
        def upstream_score(s: str) -> int:
            return sum(s in self.topo.depends_on(o) for o in services if o != s)

        root = max(services, key=lambda s: (upstream_score(s), -services.index(s)))
        if root != inc.root_service:
            inc.symptom_services = [s for s in services if s != root]
            inc.root_service = root
            inc.tier = self.topo.tier(root)
        seg = next((c.segment_key for c in inc.candidates if c.segment_key != "*"), None)
        if seg:
            inc.segment_key = seg

    def close_before(self, ts: datetime, idle_min: int = 30) -> list[IncidentCandidate]:
        done = [i for i in self.open if ts - self._last[i.id] > timedelta(minutes=idle_min)]
        self.open = [i for i in self.open if i not in done]
        return done


def group_alerts(alerts: list[dict], topo: Topology | None = None) -> list[dict]:
    """Offline grouping of scorer alerts (dicts with ts/service/segment). Returns one alert per incident group."""
    g = Grouper(topo)
    out: dict[str, dict] = {}
    for a in sorted(alerts, key=lambda x: x["ts"]):
        c = Candidate(
            ts=a["ts"],
            service=a["service"],
            metric=a["metric"],
            segment_key=a["segment"],
            u=0,
            risk=a["risk"],
        )
        inc, new = g.add(c)
        if new:
            out[inc.id] = dict(a, members=[a["service"]])
        else:
            out[inc.id]["members"].append(a["service"])
    return list(out.values())
