# analysis

Standalone EDA of `data/ps02_system_telemetry.csv`. Does not import `sentinel`.

```
uv run python analysis/eda.py        # writes analysis/outputs/rule_baselines.csv and docs/DATA_DESCRIPTION.md
uv run pytest analysis/tests
```

Pinned literals (tests assert them): B0 TP 0 / FP 0; B1 TP 28 / FP 22 / precision 0.56; test split (Aug 21-30) 12 incidents and 9 false CRITICALs. Backend `csv_bench` must match these (`test_csv_bench_matches_eda`).
