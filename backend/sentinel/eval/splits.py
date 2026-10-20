"""Train/test split constants (FP 9). Printed in the scorecard header."""

from typing import Literal

TRAIN_PS02 = ("2026-08-01", "2026-08-20")  # inclusive, whole days
TEST_PS02 = ("2026-08-21", "2026-08-30")
TRAIN_SEEDS = range(0, 10)
TEST_SEEDS = range(100, 130)


def split_of(ts: str) -> Literal["train", "test"]:
    """Split of an ISO timestamp; the test window starts at TEST_PS02[0] 00:00:00."""
    return "test" if ts[:10] >= TEST_PS02[0] else "train"


def describe() -> str:
    return (
        f"train {TRAIN_PS02[0]}..{TRAIN_PS02[1]} seeds {TRAIN_SEEDS[0]}-{TRAIN_SEEDS[-1]}; "
        f"test {TEST_PS02[0]}..{TEST_PS02[1]} seeds {TEST_SEEDS[0]}-{TEST_SEEDS[-1]}"
    )
