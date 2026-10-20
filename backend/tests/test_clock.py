from datetime import UTC, datetime, timedelta

from sentinel.clock import SimClock

T0 = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)


def test_sim_clock_scheduler():
    clock = SimClock(T0)
    fired = []
    clock.call_later(timedelta(minutes=3), lambda: fired.append("recheck"))
    clock.call_later(timedelta(minutes=1), lambda: fired.append("verify"))
    clock.advance(timedelta(minutes=2))
    assert fired == ["verify"]
    assert clock.now() == T0 + timedelta(minutes=2)
    clock.advance(timedelta(minutes=5))
    assert fired == ["verify", "recheck"]


def test_sim_clock_cancel():
    clock = SimClock(T0)
    fired = []
    h = clock.call_later(timedelta(seconds=10), lambda: fired.append(1))
    h.cancel()
    clock.advance(timedelta(minutes=1))
    assert fired == []
