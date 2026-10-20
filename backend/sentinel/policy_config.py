"""Typed view of ``data/policies.yaml`` (FP 8.3). Unknown keys are rejected."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "policies.yaml"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Verify(_Strict):
    after_s: int
    fail_rate_drop_gte: float
    legit_success_drop_lte: float


class HealthyTargetAction(_Strict):
    require_healthy_target: bool
    healthy_u_lt: float
    window_min: int
    revertible: bool


class HitlConfig(_Strict):
    reroute_bank: HealthyTargetAction
    otp_failover: HealthyTargetAction
    scale_service: dict[str, int]
    restart_service: dict[str, int]
    rollback_deploy: dict[str, int]
    disable_feature_flag: dict[str, int]
    close_ticket: dict[str, int]


class Throttle(_Strict):
    auth_fail_z_gte: float
    distinct_accounts_per_src_gte: int
    window_min: int
    max_sources: int
    max_login_share: float
    ttl_min: int
    never_allowlists: list[str]
    verify: Verify


class StepUpMfa(_Strict):
    fails_per_account_gte: int
    distinct_srcs_gte: int
    window_min: int
    ttl_min: int
    require_healthy: list[str]


class SecurityConfig(_Strict):
    throttle: Throttle
    step_up_mfa: StepUpMfa
    circuit_breaker_per_hour: int
    ttl_extensions_max: int


class PolicyConfig(_Strict):
    kill_switch: bool
    security_autonomy: Literal["off", "shadow", "enforce"]
    approval_expiry_minutes: int
    page_limit_per_team_per_hour: int
    auto: list[str]
    page_oncall: dict[str, list[str]]
    notify_channel: dict[str, list[str]]
    schedule_recheck: dict[str, int]
    hitl: HitlConfig
    security: SecurityConfig
    forbidden: list[str] = Field(min_length=1)


def load_policies(path: Path | str | None = None) -> PolicyConfig:
    return PolicyConfig.model_validate(yaml.safe_load(Path(path or DEFAULT_PATH).read_text()))
