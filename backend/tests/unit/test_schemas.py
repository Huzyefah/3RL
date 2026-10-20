import json
from collections.abc import Iterator
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
    actual = schemas.normalise_schema(json.loads(json.dumps(schemas.schema_snapshot())))
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


def _walk(node: Any, path: str = "$") -> Iterator[tuple[str, dict[str, Any]]]:
    if isinstance(node, dict):
        yield path, node  # pyright: ignore[reportUnknownVariableType]
        for k, v in node.items():  # pyright: ignore[reportUnknownVariableType]
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):  # pyright: ignore[reportUnknownVariableType]
            yield from _walk(v, f"{path}[{i}]")


@pytest.mark.unit
def test_rca_schema_is_strict_compatible() -> None:
    schema = RCA.model_json_schema()
    problems: list[str] = []
    n_objects = 0
    for path, node in _walk(schema):
        if node.get("type") == "object" or "properties" in node:
            n_objects += 1
            props = set(node.get("properties", {}))
            if not props:
                problems.append(f"{path}: free-form object")
            if props != set(node.get("required", [])):
                problems.append(f"{path}: required != properties")
            if node.get("additionalProperties") is not False:
                problems.append(f"{path}: additionalProperties not false")
        if "default" in node and path.split(".")[-1] != "properties":
            problems.append(f"{path}: has default")
        if "$ref" in node and set(node) != {"$ref"}:
            problems.append(f"{path}: $ref with siblings {sorted(set(node) - {'$ref'})}")
    assert n_objects > 5
    assert problems == []


@pytest.mark.unit
def test_rca_schema_accepted_by_openai_sdk() -> None:
    from openai.lib._parsing import type_to_response_format_param
    from openai.lib._pydantic import to_strict_json_schema

    to_strict_json_schema(RCA)
    fmt: Any = type_to_response_format_param(RCA)
    assert fmt["type"] == "json_schema"


@pytest.mark.unit
def test_action_params_nullable_but_constructible_without_args() -> None:
    p = ActionParams()
    assert p.bank is None
    assert ActionParams.model_validate({"bank": "BANK_C"}).rail is None
    assert ActionRequest(incident_id="i", type="escalate").params == ActionParams()


@pytest.mark.unit
def test_policy_actions_are_valid_action_types() -> None:
    from typing import get_args

    from sentinel.policy_config import load_policies

    p = load_policies()
    named = {*p.auto, *p.forbidden, *p.hitl.model_dump(), "throttle_source", "step_up_mfa"}
    named |= {"page_oncall", "notify_channel", "schedule_recheck"}
    assert named <= set(get_args(schemas.ActionType))


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
