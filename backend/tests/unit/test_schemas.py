import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from sentinel import schemas
from sentinel.schemas import CES, RCA, ActionParams, ActionRequest

SNAPSHOT = Path(__file__).parents[1] / "fixtures" / "schema_snapshot.json"


def _ces(**kw: Any) -> CES:
    base: dict[str, Any] = {
        "event_id": "e1",
        "ts": "2026-08-01T10:31:00Z",
        "source": "ps02_replay",
        "kind": "metric",
        "service": "PaymentGateway",
        "metric": "issuer_timeout_rate",
        "value": 0.031,
        "threshold": 0.02,
        "direction": "higher_bad",
    }
    return CES.model_validate(base | kw)


@pytest.mark.unit
def test_schema_snapshot() -> None:
    expected = json.loads(SNAPSHOT.read_text())
    actual = json.loads(json.dumps(schemas.schema_snapshot()))
    assert actual == expected, (
        "Schema changed. If deliberate: uv run python -m sentinel.schemas --write-snapshot "
        "and note it in REPORT.md."
    )


@pytest.mark.unit
def test_snapshot_covers_all_public_models() -> None:
    names = {m.__name__ for m in schemas.PUBLIC_MODELS}
    for required in (
        "CES", "MetricPoint", "LogRecord", "ChangeEvent", "Candidate", "IncidentCandidate",
        "Hypothesis", "RCA", "ActionRequest", "ActionRecord", "GuardVerdict", "TraceStep",
        "IncidentResult", "ScorecardRow", "Approval", "PolicyState",
    ):  # fmt: skip
        assert required in names


def _open_objects(node: Any, path: str = "$") -> list[str]:
    """Paths of object schemas that are free-form (no properties) or allow extra keys."""
    bad: list[str] = []
    if isinstance(node, dict):
        if node.get("type") == "object" and "properties" not in node:
            bad.append(path)
        if node.get("type") == "object" and node.get("additionalProperties") is not False:
            bad.append(path + " (additionalProperties)")
        for k, v in node.items():
            bad += _open_objects(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            bad += _open_objects(v, f"{path}[{i}]")
    return bad


@pytest.mark.unit
def test_rca_schema_is_strict_compatible() -> None:
    assert _open_objects(RCA.model_json_schema()) == []


@pytest.mark.unit
def test_ces_defaults_and_validation() -> None:
    c = _ces()
    assert c.segment_key == "*" and c.redacted is True and c.attributes == {}
    with pytest.raises(ValidationError):
        _ces(direction="sideways")
    with pytest.raises(ValidationError):
        _ces(kind="nope")


@pytest.mark.unit
def test_ces_u_and_band_use_shared_formula() -> None:
    c = _ces(value=0.031, threshold=0.02)
    assert c.u == pytest.approx(1.55)
    assert c.band == "CRITICAL"


@pytest.mark.unit
def test_action_request_idempotency_key_deterministic() -> None:
    a = ActionRequest(
        incident_id="INC-0001",
        type="reroute_bank",
        params=ActionParams(bank="BANK_C", rail="RAAST"),
        rationale="r",
    )
    b = a.model_copy()
    assert a.idempotency_key == b.idempotency_key
    c = a.model_copy(update={"params": a.params.model_copy(update={"bank": "BANK_D"})})
    assert c.idempotency_key != a.idempotency_key


@pytest.mark.unit
def test_rca_roundtrip_and_root_cause_codes() -> None:
    rca = RCA.model_validate(
        {
            "incident_id": "INC-2026-1020-004",
            "goal": "g",
            "headline": "h",
            "severity": "P1",
            "root_cause_service": "PaymentGateway",
            "affected_segment": "bank=BANK_C",
            "eta_minutes": 11,
            "hypotheses": [
                {
                    "code": "RC-BANK",
                    "confidence": 0.82,
                    "statement": "s",
                    "evidence_ids": ["log:91ab02ee"],
                }
            ],
            "similar_incidents": [{"id": "INC-0007", "similarity": 0.84, "fix": "f"}],
            "runbook_steps": ["a"],
            "impact": {
                "customers_affected_est": 4100,
                "pkr_at_risk_per_min": 1.25e6,
                "label": "estimate",
            },
            "actions": [
                {
                    "type": "reroute_bank",
                    "params": {"bank": "BANK_C", "rail": "RAAST"},
                    "rationale": "x",
                }
            ],
            "summary_technical": "t",
            "summary_business": "b",
            "comms_draft": {"in_app_banner": "i", "bank_partner_note": "n"},
            "if_ignored": "x",
            "skeptic": {"verdict": "CONFIRMED", "confidence": 0.81},
            "plan_versions": 2,
            "generated_by": "llm",
            "low_confidence": False,
        }
    )
    assert RCA.model_validate_json(rca.model_dump_json()) == rca
    with pytest.raises(ValidationError):
        RCA.model_validate(
            rca.model_dump()
            | {"hypotheses": [{**rca.model_dump()["hypotheses"][0], "code": "RC-X"}]}
        )
