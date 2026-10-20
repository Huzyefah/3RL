"""Service dependency graph loaded from ``data/services.yaml`` (FP 3.1)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "services.yaml"


class MetricSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    threshold: float
    direction: Literal["higher_is_bad", "lower_is_bad"]


class Service(BaseModel):
    model_config = ConfigDict(extra="forbid")
    novapay_name: str
    owner: str
    tier: int
    depends_on: list[str]
    segments: dict[str, list[str]]
    metrics: dict[str, MetricSpec]
    segment_metrics: dict[str, MetricSpec]


class Topology:
    """Dependency graph. Services are keyed by CSV name; NovaPay names are accepted as aliases."""

    def __init__(
        self, services: dict[str, Service], banks: list[str], otp_providers: list[str]
    ) -> None:
        self.services = services
        self.banks = banks
        self.otp_providers = otp_providers
        self._alias = {s.novapay_name: k for k, s in services.items()}
        for svc in services.values():
            for dep in svc.depends_on:
                if dep not in services:
                    raise ValueError(f"unknown dependency {dep!r}")
        self._dependants: dict[str, set[str]] = {k: set() for k in services}
        for k, svc in services.items():
            for dep in svc.depends_on:
                self._dependants[dep].add(k)
        for k in services:
            if k in self.blast_radius(k):
                raise ValueError(f"dependency cycle through {k!r}")

    @classmethod
    def from_yaml(cls, path: Path | str | None = None) -> Topology:
        raw = yaml.safe_load(Path(path or DEFAULT_PATH).read_text())
        services = {k: Service.model_validate(v) for k, v in raw["services"].items()}
        return cls(services, list(raw["banks"]), list(raw["otp_providers"]))

    def _key(self, name: str) -> str:
        if name in self.services:
            return name
        if name in self._alias:
            return self._alias[name]
        raise KeyError(name)

    def upstream(self, svc: str) -> set[str]:
        """Direct dependencies of ``svc``."""
        return set(self.services[self._key(svc)].depends_on)

    def dependants(self, svc: str) -> set[str]:
        """Services that directly depend on ``svc``."""
        return set(self._dependants[self._key(svc)])

    def blast_radius(self, svc: str) -> set[str]:
        """Transitive dependants of ``svc`` (excluding itself unless in a cycle)."""
        seen: set[str] = set()
        stack = [self._key(svc)]
        while stack:
            for nxt in self._dependants[stack.pop()]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return seen

    def linked(self, a: str, b: str) -> bool:
        """True if one service is a transitive dependant of the other."""
        ka, kb = self._key(a), self._key(b)
        return kb in self.blast_radius(ka) or ka in self.blast_radius(kb)

    def owner(self, svc: str) -> str:
        return self.services[self._key(svc)].owner

    def tier(self, svc: str) -> int:
        return self.services[self._key(svc)].tier

    def csv_to_novapay(self, name: str) -> str:
        return self.services[name].novapay_name
