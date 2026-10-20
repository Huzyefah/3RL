import pytest

from sentinel.eval import splits


@pytest.mark.unit
def test_split_constants() -> None:
    assert splits.TRAIN_PS02 == ("2026-08-01", "2026-08-20")
    assert splits.TEST_PS02 == ("2026-08-21", "2026-08-30")
    assert list(splits.TRAIN_SEEDS) == list(range(0, 10))
    assert list(splits.TEST_SEEDS) == list(range(100, 130))


@pytest.mark.unit
def test_split_of_boundaries() -> None:
    assert splits.split_of("2026-08-20T23:59:59") == "train"
    assert splits.split_of("2026-08-21T00:00:00") == "test"
    assert splits.split_of("2026-08-01T00:00:00") == "train"
    assert splits.split_of("2026-08-30T23:59:59") == "test"


@pytest.mark.unit
def test_split_constants_printed() -> None:
    text = splits.describe()
    assert "2026-08-01" in text and "2026-08-20" in text
    assert "2026-08-21" in text and "2026-08-30" in text
    assert "0-9" in text and "100-129" in text
