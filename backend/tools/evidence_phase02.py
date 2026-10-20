"""Phase 2 evidence: generated ps02 episodes (RC-BANK with segment precursor, N1 surge, N5 spike) + summary."""

import json
import sys
from datetime import timedelta
from pathlib import Path

from sentinel.datagen.generator import INFRA_METRICS, alert_runs, build
from tools.charts import episode_lines

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
ds = build("ps02")


def window(e, before=60, after=40):
    i0, i1 = ds.loc(e.precursor_start - timedelta(minutes=before)), ds.loc(e.end + timedelta(minutes=after))
    return i0, i1, ds.index[i0:i1]


bank = next(e for e in ds.episodes if e.code == "RC-BANK" and not e.abrupt and e.onset.day >= 21)
i0, i1, x = window(bank)
seg = ("PaymentGateway", "issuer_timeout_rate", bank.segment)
episode_lines(
    out / "01-rc-bank-episode.png",
    f"{bank.id}: RC-BANK on {bank.segment} (test split)",
    f"Segment issuer timeouts climb {bank.lead_min} min before PaymentGateway {bank.metric} breaches at the CSV anchor",
    x,
    {
        f"PaymentGateway {bank.metric} (anchored)": ds.series[(bank.service, bank.metric, "*")].u[i0:i1],
        f"issuer_timeout_rate {bank.segment}": ds.series[seg].u[i0:i1],
        "PaymentGateway error_rate (coupled)": ds.series[("PaymentGateway", "error_rate", "*")].u[i0:i1],
    },
    {"precursor start": bank.precursor_start, "onset = CSV row": bank.onset},
)

n1 = next(e for e in ds.episodes if e.code == "N1")
i0, i1, x = window(n1)
episode_lines(
    out / "02-n1-surge-hard-negative.png",
    f"{n1.id}: N1 surge (hard negative), every signal ramps together",
    "Looks like an incident to a trend detector; the only benign evidence is the campaign calendar event",
    x,
    {f"{n1.service} {m}": ds.series[(n1.service, m, "*")].u[i0:i1] for m in INFRA_METRICS[:4]},
    {"campaign starts": n1.precursor_start - timedelta(minutes=10), "CSV row": n1.onset},
)

n5 = next(e for e in ds.episodes if e.code == "N5")
i0, i1, x = window(n5, 30, 30)
episode_lines(
    out / "03-n5-transient-spike.png",
    f"{n5.id}: N5 transient spike (hard negative)",
    "A one-minute touch of CRITICAL that is already recovering",
    x,
    {f"{n5.service} {n5.metric}": ds.series[(n5.service, n5.metric, "*")].u[i0:i1]},
    {"CSV row": n5.onset},
)

infra = [s for k, s in ds.series.items() if k[2] == "*" and k[1] in INFRA_METRICS]
summary = {
    "minutes": len(ds.index),
    "series": len(ds.series),
    "episodes": {"incidents": sum(e.kind == "incident" for e in ds.episodes), "negatives": sum(e.kind == "negative" for e in ds.episodes)},
    "codes": {c: sum(e.code == c for e in ds.episodes) for c in sorted({e.code for e in ds.episodes})},
    "abrupt": sum(e.abrupt for e in ds.episodes),
    "b1_alert_runs": sum(len(alert_runs(s.u)) for s in infra),
    "b0_alerts": int(sum((s.u >= 1.0).sum() for s in infra)),
    "events": ds.events.kind.value_counts().to_dict(),
    "log_rows": len(ds.logs),
}
(out / "summary.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary, indent=2))
