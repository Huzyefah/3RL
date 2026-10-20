import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import eda  # noqa: E402

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def rows():
    return eda.load()


def test_counts(rows):
    assert len(rows) == 500
    assert sum(r["is_incident"] for r in rows) == 28
    crit = [r for r in rows if r["alert_level"] == "CRITICAL"]
    assert len(crit) == 50
    assert sum(r["is_incident"] for r in crit) == 28
    assert sum(1 for r in crit if not r["is_incident"]) == 22


def test_baselines(rows):
    full = {b["config"]: b for b in eda.baselines(rows)}
    assert (full["B0"]["tp"], full["B0"]["fp"]) == (0, 0)
    assert (full["B1"]["tp"], full["B1"]["fp"], full["B1"]["precision"]) == (28, 22, 0.56)
    assert full["B1"]["recall"] == 1.0


def test_test_split(rows):
    test = [r for r in rows if r["timestamp"] >= "2026-08-21"]
    assert sum(r["is_incident"] for r in test) == 12
    fc = [r for r in test if r["alert_level"] == "CRITICAL" and not r["is_incident"]]
    assert len(fc) == 9


def test_calendar_facts(rows):
    eda.verify_calendar(rows)
