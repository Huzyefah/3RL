"""Policy Guard (FINAL_PLAN §8): agents only *request* actions; this module decides AUTO / HITL / DENY (I6)."""

from __future__ import annotations

from functools import cache

import yaml

from sentinel.config import settings

FORBIDDEN_TYPES = {"modify_ledger_balance", "delete_data", "block_all_logins", "change_transaction_limits"}
SANDBOX_TARGETS = {"finpay-sim"}


@cache
def policies() -> dict:
    with (settings.config_dir / "policies.yaml").open() as f:
        return yaml.safe_load(f)


def decide(
    action_type: str, params: dict, severity: str, target_health_u: float | None = None
) -> tuple[str, str]:
    """Returns (mode, reason)."""
    p = policies()
    if action_type in FORBIDDEN_TYPES or action_type in p["forbidden"]:
        return "DENY", f"{action_type} is forbidden by policy"
    if params.get("target") and params["target"] not in SANDBOX_TARGETS:
        return "DENY", "only sandbox targets may be acted on"
    if action_type in p["auto"]:
        allowed = p["auto"][action_type].get("severities")
        if allowed and severity not in allowed:
            return "DENY", f"{action_type} not allowed for {severity}"
        return "AUTO", "low-risk, reversible"
    if action_type in p["hitl"]:
        rule = p["hitl"][action_type]
        if rule.get("require_healthy_target") and (
            target_health_u is None or target_health_u >= rule["healthy_u_max"]
        ):
            return (
                "DENY",
                f"target unhealthy (u={target_health_u}); failover to an unhealthy target is forbidden",
            )
        return (
            "HITL",
            f"needs approval; healthy target (u={target_health_u}); expires in {rule['approval_ttl_min']} min",
        )
    return "DENY", f"{action_type} is not in the policy"
