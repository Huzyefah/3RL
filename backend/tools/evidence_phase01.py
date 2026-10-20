"""Phase 1 evidence: CSV bench (sanity gate 1) → JSON + chart."""

import json
import sys
from pathlib import Path

from sentinel.eval.csv_bench import run_bench
from tools.charts import grouped_bars

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
res = run_bench()
(out / "csv_bench.json").write_text(json.dumps(res, indent=2))
grouped_bars(
    out / "01-csv-bench-b0-vs-b1.png",
    "Static rules on the raw PS-02 CSV (500 rows, 28 incidents)",
    f"B0 u≥1.0 catches {res['B0']['tp']}/28 · B1 u≥0.95 catches {res['B1']['tp']}/28 at precision "
    f"{res['B1']['precision']:.2f} ({res['B1']['fp']} false pages)",
    ["B0  (u ≥ 1.0)", "B1  (u ≥ 0.95)"],
    {"True positives": [res["B0"]["tp"], res["B1"]["tp"]], "False positives": [res["B0"]["fp"], res["B1"]["fp"]]},
)
print(json.dumps(res, indent=2))
