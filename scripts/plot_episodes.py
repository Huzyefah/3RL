"""Render Phase 2 datagen evidence PNGs to backend/.cache/plots/ (anchors, episode gallery, CSV bench)."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from sentinel.datagen.episode_map import load_episode_map  # noqa: E402
from sentinel.datagen.generator import build  # noqa: E402
from sentinel.eval.csv_bench import csv_bench  # noqa: E402

OUT = ROOT / "backend/.cache/plots"
INK, MUTED = "#1f2933", "#52606d"
SERIES, ANCHOR = "#1f5fa8", "#b45309"
BAND = {"NORMAL (u < 0.75)": "#e6f2e6", "WARNING (0.75 to 0.95)": "#fdf1cf", "CRITICAL (u >= 0.95)": "#f9d6d2"}
plt.rcParams.update({"font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "text.color": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "figure.facecolor": "white"})


def shade(ax) -> None:
    ax.axhspan(0, 0.75, color=BAND["NORMAL (u < 0.75)"], zorder=0)
    ax.axhspan(0.75, 0.95, color=BAND["WARNING (0.75 to 0.95)"], zorder=0)
    ax.axhspan(0.95, 1.05, color=BAND["CRITICAL (u >= 0.95)"], zorder=0)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("utilisation u")


def band_legend(fig, extra=()) -> None:
    h = [Patch(facecolor=c, edgecolor=MUTED, label=k) for k, c in BAND.items()] + list(extra)
    fig.legend(handles=h, loc="lower center", ncol=len(h), frameon=False)


def series(m: pd.DataFrame, svc: str, metric: str) -> pd.DataFrame:
    s = m[(m.service == svc) & (m.metric == metric) & (m.segment_key == "*")]
    return s.sort_values("ts")


def anchors_plot(ds) -> Path:
    m = ds.metrics
    m = m[m.ts < "2026-08-04"]
    pairs = [("PaymentGateway", "connection_pool"), ("AuthService", "connection_pool"),
             ("SearchAPI", "connection_pool")]
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    for ax, (svc, met) in zip(axes, pairs, strict=True):
        shade(ax)
        s = series(m, svc, met)
        ax.plot(s.ts, s.u, color=SERIES, lw=1.0, zorder=2)
        a = s[s.is_anchor]
        ax.scatter(a.ts, a.u, s=70, marker="D", color=ANCHOR, edgecolor="black", zorder=4)
        for _, r in a.iterrows():
            ax.annotate(f"{r.u:.2f}", (r.ts, r.u), xytext=(0, 9), textcoords="offset points",
                        ha="center", fontsize=8, color=INK)
        ax.set_title(f"{svc}  {met}   ({len(a)} pinned CSV anchors)", loc="left", fontsize=11, fontweight="bold")
    t1, t2 = pd.Timestamp("2026-08-01 10:38"), pd.Timestamp("2026-08-01 10:59")
    axes[1].annotate("08-01 10:38 INC-0001 (root cause)", (t1, 0.97), xytext=(t1 + pd.Timedelta(hours=2), 0.5),
                     arrowprops={"arrowstyle": "->", "color": INK}, fontsize=9, bbox={"fc": "white", "ec": MUTED})
    axes[0].annotate("08-01 10:59 INC-0002 (cascade, +21 min)", (t2, 0.98), xytext=(t2 + pd.Timedelta(hours=2), 0.45),
                     arrowprops={"arrowstyle": "->", "color": INK}, fontsize=9, bbox={"fc": "white", "ec": MUTED})
    for ax in axes:
        ax.axvline(t1, color="#7a3e9d", ls="--", lw=1)
        ax.axvline(t2, color="#7a3e9d", ls=":", lw=1)
    axes[-1].set_xlabel("time, 2026-08-01 to 2026-08-03 (1-minute series)")
    fig.suptitle("Pinned CSV anchors are preserved verbatim inside the dense series (annotation = anchor u)",
                 fontsize=13, fontweight="bold")
    band_legend(fig, [Line2D([], [], color=SERIES, label="dense u series"),
                      Line2D([], [], marker="D", ls="", color=ANCHOR, mec="black", label="pinned CSV anchor"),
                      Line2D([], [], color="#7a3e9d", ls="--", label="08-01 cascade (10:38 / 10:59)")])
    fig.tight_layout(rect=(0, 0.05, 1, 0.96))
    p = OUT / "anchors-preserved.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    return p


def gallery_plot(ds) -> Path:
    emap = {a.episode_id: a for a in load_episode_map()}
    want = ["RC-BANK", "RC-DBPOOL", "RC-OTP-PROVIDER", "RC-QUEUE", "RC-AUTH-ATTACK", "RC-MEMLEAK", "RC-ABRUPT",
            "N1", "N3", "N4", "N5", "N6"]
    first = {}
    for e in sorted(ds.ground_truth, key=lambda e: e.episode_id):
        first.setdefault(e.code, e)
    codes = [c for c in want if c in first]
    cols = 4
    rows = -(-len(codes) // cols)
    fig, axes = plt.subplots(rows, cols, figsize=(18, 3.6 * rows + 1), squeeze=False)
    m = ds.metrics
    for ax in axes.flat[len(codes):]:
        ax.axis("off")
    for ax, code in zip(axes.flat, codes, strict=False):
        e = first[code]
        met = emap[e.episode_id].metric
        pad = pd.Timedelta(minutes=30)
        lo, hi = e.precursor_start - pad, e.end + pad
        s = series(m, e.service, met)
        s = s[(s.ts >= lo) & (s.ts <= hi)]
        shade(ax)
        ax.plot(s.ts, s.u, color=SERIES, lw=1.4, zorder=2)
        a = s[s.is_anchor]
        ax.scatter(a.ts, a.u, s=60, marker="D", color=ANCHOR, edgecolor="black", zorder=4)
        ax.axvline(e.onset, color=INK, ls="--", lw=1)
        if not e.abrupt or code == "RC-ABRUPT":
            ax.axvline(e.precursor_start, color="#7a3e9d", ls=":", lw=1)
        ax.set_title(f"{code}  {e.episode_id}\n{e.service} {met}", loc="left", fontsize=10, fontweight="bold")
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%m-%d\n%H:%M"))
        ax.tick_params(labelsize=8)
        if code.startswith("N"):
            ax.text(0.98, 0.06, "false alarm", transform=ax.transAxes, ha="right", fontsize=9,
                    bbox={"fc": "white", "ec": MUTED})
    fig.suptitle("Episode gallery: dense u around each onset, real ground truth (first episode per code)",
                 fontsize=14, fontweight="bold")
    band_legend(fig, [Line2D([], [], color=SERIES, label="dense u"),
                      Line2D([], [], marker="D", ls="", color=ANCHOR, mec="black", label="CSV anchor"),
                      Line2D([], [], color=INK, ls="--", label="onset"),
                      Line2D([], [], color="#7a3e9d", ls=":", label="precursor start")])
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    p = OUT / "episode-gallery.png"
    fig.savefig(p, dpi=110)
    plt.close(fig)
    return p


def bench_plot() -> Path:
    rows = {sp: csv_bench(split=sp) for sp in ("all", "test")}
    fig, (ax, tx) = plt.subplots(1, 2, figsize=(15, 6), gridspec_kw={"width_ratios": [1.2, 1]})
    labels, tps, fps = [], [], []
    for sp, rs in rows.items():
        for r in rs:
            labels.append(f"{r.system}\n{sp}")
            tps.append(r.tp)
            fps.append(r.fp)
    x = range(len(labels))
    ax.bar(x, tps, color="#1b7f5c", label="TP (real incidents caught)", edgecolor="white", linewidth=2)
    ax.bar(x, fps, bottom=tps, color="#c2410c", hatch="//", label="FP (false alarms)", edgecolor="white", linewidth=2)
    for i, (t, f) in enumerate(zip(tps, fps, strict=True)):
        ax.text(i, t + f + 0.6, f"TP {t}\nFP {f}", ha="center", fontsize=10)
    ax.set_xticks(list(x), labels)
    ax.set_ylabel("alert minutes on the 500 raw CSV rows")
    ax.set_ylim(0, max(t + f for t, f in zip(tps, fps, strict=True)) * 1.25 + 2)
    ax.set_title("B0 (u >= 1.0) vs B1 (u >= 0.95)", loc="left", fontweight="bold")
    ax.legend(frameon=False, loc="upper left")
    tx.axis("off")
    cells = [[r.system, sp, r.tp, r.fp, r.fn, "n/a" if r.precision is None else f"{r.precision:.2f}",
              "n/a" if r.recall is None else f"{r.recall:.2f}"] for sp, rs in rows.items() for r in rs]
    t = tx.table(cellText=cells, colLabels=["rule", "split", "TP", "FP", "FN", "precision", "recall"],
                 loc="upper center", cellLoc="center")
    t.auto_set_font_size(False)
    t.set_fontsize(10)
    t.scale(1, 1.8)
    b0, b1 = rows["all"]
    tx.text(0.5, 0.35, f"B0 static threshold: {b0.tp} of {b0.tp + b0.fn}\n"
            f"B1 95% rule: {b1.tp} of {b1.tp + b1.fn} @ {b1.precision:.2f}  ({b1.fp} false alarms)",
            ha="center", fontsize=14, fontweight="bold", transform=tx.transAxes)
    fig.suptitle("Raw PS-02 CSV bench: a static threshold catches 0 of 28; the 95% rule catches 28 of 28 @ 0.56",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    p = OUT / "csv-bench.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    return p


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ds = build("ps02", seed=0)
    for p in (anchors_plot(ds), gallery_plot(ds), bench_plot()):
        print(p)


if __name__ == "__main__":
    main()
