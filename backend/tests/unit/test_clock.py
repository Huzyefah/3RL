from datetime import UTC, datetime, timedelta

import pytest

from sentinel.clock import TIMERS, ClockKind, EventClock, FrozenClock, WallClock

T0 = datetime(2026, 8, 1, 3, 0, tzinfo=UTC)


@pytest.mark.unit
def test_event_clock_monotonic():
    clock = EventClock()
    with pytest.raises(LookupError):
        clock.now()
    clock.advance_to(T0)
    clock.advance_to(T0)  # equal timestamps are fine
    clock.advance_to(T0 + timedelta(minutes=1))
    assert clock.now() == T0 + timedelta(minutes=1)
    with pytest.raises(ValueError):
        clock.advance_to(T0)  # going backwards is an error and leaves time untouched
    assert clock.now() == T0 + timedelta(minutes=1)


@pytest.mark.unit
def test_frozen_clock_advance():
    clock = FrozenClock(T0)
    assert clock.now() == T0
    clock.advance(timedelta(seconds=90))
    assert clock.now() == T0 + timedelta(seconds=90)


@pytest.mark.unit
def test_wall_clock_is_aware_utc():
    now = WallClock().now()
    assert now.tzinfo is not None
    assert abs(datetime.now(UTC) - now) < timedelta(seconds=5)


M = timedelta(minutes=1)
H = timedelta(hours=1)
E, W = ClockKind.EVENT, ClockKind.WALL

TABLE = {
    "holt_warmup": (E, 10 * M),
    "rising_streak": (E, 5 * M),
    "binomial_window": (E, 5 * M),
    "corroboration_window": (E, 5 * M),
    "grouping_window": (E, 10 * M),
    "cooldown": (E, 15 * M),
    "recheck": (E, 3 * M),
    "approval_expiry": (W, 10 * M),
    "containment_ttl_throttle": (W, 15 * M),
    "containment_ttl_mfa": (W, 30 * M),
    "post_action_verification": (W, timedelta(seconds=60)),
    "circuit_breaker": (W, H),
    "page_limit": (W, H),
    "feedback_half_life": (W, 24 * H),
    "ui_eta_countdown": (E, None),
}


@pytest.mark.unit
def test_timer_clock_assignment():
    assert set(TIMERS) == set(TABLE)
    for name, (kind, value) in TABLE.items():
        assert TIMERS[name].kind is kind, name
        assert TIMERS[name].value == value, name
    assert TIMERS["circuit_breaker"].limit == 5
    assert TIMERS["page_limit"].limit == 6
    assert TIMERS["recheck"].limit == 2


@pytest.mark.unit
def test_event_clock_rejects_naive_datetime():
    clock = EventClock()
    with pytest.raises(ValueError):
        clock.advance_to(datetime(2026, 8, 1, 3, 0))
    with pytest.raises(LookupError):
        clock.now()
    clock.advance_to(T0)
    with pytest.raises(ValueError):
        clock.advance_to(datetime(2026, 8, 1, 4, 0))
    assert clock.now() == T0
