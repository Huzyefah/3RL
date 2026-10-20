from datetime import datetime
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from sentinel.calendar import events_at, load_calendar
from sentinel.policy_config import PolicyConfig, load_policies

pytestmark = pytest.mark.unit

DATA = Path(__file__).resolve().parents[2] / "data"


def _names(ts: str) -> set[str]:
    return {e.id for e in events_at(datetime.fromisoformat(ts))}


def test_calendar_2026_08_01_is_salary_day():
    events = events_at(datetime.fromisoformat("2026-08-01T11:00"))
    salary = [e for e in events if e.kind == "salary_day"]
    assert salary and salary[0].tps_multiplier == 1.6


def test_calendar_salary_days_1_to_3_only():
    assert "salary_day" in {e.kind for e in events_at(datetime(2026, 8, 3, 12))}
    assert "salary_day" not in {e.kind for e in events_at(datetime(2026, 8, 4, 12))}


def test_calendar_cashback_covers_0822_2025():
    assert "cashback_weekend_0822" in _names("2026-08-22T20:25")


def test_calendar_azadi_covers_0814_1949():
    assert "azadi_sale_0814" in _names("2026-08-14T19:49")


def test_calendar_0814_0318_not_covered_by_azadi():
    assert "azadi_sale_0814" not in _names("2026-08-14T03:18")


def test_calendar_authored_flags():
    cal = load_calendar()
    flagged = {e.id for e in cal if e.authored_to_explain_anchor}
    assert flagged == {"azadi_sale_0814", "cashback_weekend_0822"}


def test_calendar_eod_settlement_cron():
    cal = load_calendar()
    eod = [e for e in cal if e.kind == "eod_settlement"]
    assert eod and eod[0].cron == "0 16 * * *" and eod[0].tz == "Asia/Karachi"


def test_policies_yaml_schema_valid():
    p = load_policies()
    assert isinstance(p, PolicyConfig)
    assert p.approval_expiry_minutes == 10
    assert p.page_limit_per_team_per_hour == 6
    assert p.hitl.reroute_bank.require_healthy_target is True
    assert p.hitl.otp_failover.require_healthy_target is True
    assert p.security.throttle.ttl_min == 15
    assert p.security.throttle.auth_fail_z_gte == 4
    assert p.security.throttle.distinct_accounts_per_src_gte == 20
    assert p.security.throttle.window_min == 5
    assert p.security.throttle.max_sources == 50
    assert p.security.throttle.max_login_share == 0.02
    assert p.security.step_up_mfa.ttl_min == 30
    assert p.security.circuit_breaker_per_hour == 5


def test_policies_forbidden_list():
    p = load_policies()
    assert "modify_payment_routing" not in p.forbidden
    for rule in (
        "change_ledger_balances",
        "delete_data",
        "block_all_logins",
        "change_limits",
        "failover_to_unhealthy_target",
        "act_on_non_sandbox_target",
    ):
        assert rule in p.forbidden


def test_policies_auto_and_forbidden_disjoint():
    p = load_policies()
    assert not set(p.auto) & set(p.forbidden)


def test_policy_schema_rejects_unknown_key():
    raw = yaml.safe_load((DATA / "policies.yaml").read_text())
    raw["surprise"] = 1
    with pytest.raises(ValidationError):
        PolicyConfig.model_validate(raw)


def test_allowlists_yaml_shape():
    raw = yaml.safe_load((DATA / "allowlists.yaml").read_text())
    assert {"corporate", "partner_banks", "processors"} <= set(raw)
    import ipaddress

    for group in ("corporate", "partner_banks", "processors"):
        for cidr in raw[group]["cidrs"]:
            ipaddress.ip_network(cidr)


def test_runbooks_exist_for_every_root_cause():
    codes = [
        "RC-BANK", "RC-DBPOOL", "RC-OTP-PROVIDER", "RC-QUEUE", "RC-AUTH-ATTACK",
        "RC-MEMLEAK", "RC-CERT", "RC-ABRUPT", "RC-BENIGN",
    ]  # fmt: skip
    for code in codes:
        text = (DATA / "runbooks" / f"{code}.md").read_text()
        assert len(text.splitlines()) <= 25
        assert "Preventive action" in text and "Steps" in text
