"""Train/test splits (FINAL_PLAN §9). Printed in the scorecard header; never tune on TEST."""

from datetime import datetime

PS02_TRAIN = (datetime(2026, 8, 1), datetime(2026, 8, 21))  # tune τ here
PS02_TEST = (datetime(2026, 8, 21), datetime(2026, 8, 31, 1, 0))  # report here: 12 incidents, 9 hard negatives
SEEDED_TRAIN = range(10)
SEEDED_TEST = range(100, 130)


def describe() -> str:
    return (
        f"ps02: train {PS02_TRAIN[0]:%b %d}–{PS02_TRAIN[1]:%b %d}, test {PS02_TEST[0]:%b %d}–Aug 30 · "
        f"seeded: train seeds {SEEDED_TRAIN.start}–{SEEDED_TRAIN.stop - 1}, test {SEEDED_TEST.start}–{SEEDED_TEST.stop - 1}"
    )
