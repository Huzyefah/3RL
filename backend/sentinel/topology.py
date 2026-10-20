"""Service dependency graph from backend/data/services.yaml."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml

from sentinel.config import settings


@dataclass(frozen=True)
class Topology:
    services: dict[str, dict]

    @classmethod
    def load(cls, path: Path | None = None) -> Topology:
        return _load(path or settings.config_dir / "services.yaml")

    def depends_on(self, service: str) -> list[str]:
        return list(self.services[service].get("depends_on", []))

    def dependants(self, service: str) -> list[str]:
        return [s for s, cfg in self.services.items() if service in cfg.get("depends_on", [])]

    def blast_radius(self, service: str) -> list[str]:
        """Every service that transitively depends on `service` (who is hurt if it degrades)."""
        seen: set[str] = set()
        queue = deque(self.dependants(service))
        while queue:
            s = queue.popleft()
            if s not in seen:
                seen.add(s)
                queue.extend(self.dependants(s))
        return sorted(seen)

    def linked(self, a: str, b: str) -> bool:
        """Direct dependency edge in either direction."""
        return b in self.depends_on(a) or a in self.depends_on(b)

    def team(self, service: str) -> str:
        return self.services[service]["team"]

    def tier(self, service: str) -> int:
        return int(self.services[service]["tier"])


@cache
def _load(path: Path) -> Topology:
    with path.open() as f:
        return Topology(services=yaml.safe_load(f)["services"])
