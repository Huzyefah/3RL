from datetime import UTC, datetime
from typing import Literal

import pytest

from sentinel.schemas import ActionParams, ActionRecord, ActionRequest, Approval, Ticket
from sentinel.store import BigQueryStore, MemoryStore, Store

T0 = datetime(2026, 10, 20, 10, tzinfo=UTC)


def _record(
    key_bank: str = "BANK_C", status: Literal["PENDING", "EXECUTED"] = "PENDING"
) -> ActionRecord:
    req = ActionRequest(
        incident_id="INC-0001",
        type="reroute_bank",
        params=ActionParams(bank=key_bank, rail="RAAST"),
        rationale="r",
    )
    return ActionRecord(
        action_id=f"act-{key_bank}",
        request=req,
        idempotency_key=req.idempotency_key,
        mode="HITL",
        status=status,
        created_ts=T0,
    )


@pytest.mark.unit
def test_memory_store_satisfies_protocol() -> None:
    s: Store = MemoryStore()
    assert s.tickets.list() == []


@pytest.mark.unit
def test_roundtrip_get_list_update() -> None:
    s = MemoryStore()
    t = Ticket(ticket_id="T1", incident_id="INC-0001", team="payments", title="x", body="y")
    s.tickets.put("T1", t)
    assert s.tickets.get("T1") == t
    assert s.tickets.get("missing") is None
    updated = s.tickets.update("T1", status="CLOSED")
    assert updated.status == "CLOSED" and s.tickets.get("T1") == updated
    assert [x.ticket_id for x in s.tickets.list()] == ["T1"]
    assert s.tickets.list(lambda x: x.status == "OPEN") == []


@pytest.mark.unit
def test_update_missing_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        MemoryStore().tickets.update("nope", status="CLOSED")


@pytest.mark.unit
def test_returned_objects_are_copies() -> None:
    s = MemoryStore()
    s.tickets.put("T1", Ticket(ticket_id="T1", incident_id="I", team="t", title="x", body="y"))
    got = s.tickets.get("T1")
    assert got is not None
    got.status = "CLOSED"
    assert s.tickets.get("T1").status == "OPEN"  # pyright: ignore[reportOptionalMemberAccess]


@pytest.mark.unit
def test_claim_action_is_idempotent() -> None:
    s = MemoryStore()
    first, created1 = s.claim_action(_record())
    second, created2 = s.claim_action(_record())
    assert created1 is True and created2 is False
    assert second == first
    assert len(s.actions.list()) == 1
    _, created3 = s.claim_action(_record("BANK_D"))
    assert created3 is True and len(s.actions.list()) == 2


@pytest.mark.unit
def test_other_collections_exist() -> None:
    s = MemoryStore()
    s.approvals.put(
        "a1",
        Approval(
            approval_id="a1",
            action_id="x",
            approver="u",
            decision="APPROVED",
            ts=T0,
            expires_at=T0,
        ),  # pyright: ignore[reportArgumentType]
    )
    assert s.approvals.get("a1") is not None
    assert s.incidents.list() == [] and s.feedback.list() == [] and s.events.list() == []


@pytest.mark.unit
def test_bigquery_store_is_a_stub() -> None:
    with pytest.raises(NotImplementedError):
        BigQueryStore()
