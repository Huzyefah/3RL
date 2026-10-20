import pytest

from sentinel.utilisation import band, utilisation


@pytest.mark.unit
def test_u_higher_bad() -> None:
    assert utilisation(68.46, 71.39, "higher_bad") == pytest.approx(0.95896, abs=1e-5)


@pytest.mark.unit
def test_u_lower_bad() -> None:
    assert utilisation(0.955, 0.97, "lower_bad") == pytest.approx(1.5)


@pytest.mark.unit
def test_u_lower_bad_at_floor_is_exactly_one() -> None:
    assert utilisation(0.97, 0.97, "lower_bad") == pytest.approx(1.0)


@pytest.mark.unit
def test_u_rejects_degenerate_threshold() -> None:
    with pytest.raises(ValueError):
        utilisation(1.0, 0.0, "higher_bad")
    with pytest.raises(ValueError):
        utilisation(0.5, 1.0, "lower_bad")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("u", "expected"),
    [
        (0.0, "NORMAL"),
        (0.7499999, "NORMAL"),
        (0.75, "WARNING"),
        (0.9499999, "WARNING"),
        (0.95, "CRITICAL"),
        (3.0, "CRITICAL"),
    ],
)
def test_band_edges(u: float, expected: str) -> None:
    assert band(u) == expected


@pytest.mark.unit
def test_unknown_direction_raises() -> None:
    with pytest.raises(ValueError, match="direction"):
        utilisation(1.0, 2.0, "higher_is_bad")  # type: ignore[arg-type]
