from sentinel.eval.csv_bench import run_bench

# Expected values come from the EDA (FINAL_PLAN §9 sanity gate 1) and are hard-coded on purpose.


def test_csv_bench_matches_eda():
    res = run_bench()
    assert res["rows"] == 500 and res["incidents"] == 28
    assert res["B0"]["tp"] == 0 and res["B0"]["fp"] == 0
    assert res["B1"]["tp"] == 28 and res["B1"]["fp"] == 22 and res["B1"]["fn"] == 0
    assert round(res["B1"]["precision"], 2) == 0.56
    assert res["B1"]["recall"] == 1.0


def test_csv_bands_reproduce_alert_level():
    assert run_bench()["band_mismatches"] == 0
