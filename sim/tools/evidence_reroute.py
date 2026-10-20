"""Deterministic reroute evidence: BANK_C payment success rate through bank_c_slow → reroute via Raast.

Timeline (sim-seconds): healthy 0–60, ``bank_c_slow`` at 60, reroute BANK_C → RAAST at 300, end at 480.
Writes ``01-bank-c-success-rate.png`` and ``series.json`` to the phase-02 evidence folder.

    uv run python tools/evidence_reroute.py [out_dir]
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from finpay_sim.engine import SimEngine

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "docs/test-evidence/phase-02-generator-sim-ui/sim-reroute"
SEED = 7
START = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
T_CHAOS, T_REROUTE, T_END = 60, 300, 480
FLOOR = 0.97

SURFACE, TEXT, TEXT2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SERIES = "#2a78d6"


def run() -> dict:
    eng = SimEngine(seed=SEED, start=START)
    points: list[dict] = []

    def collect(envs: list[dict]) -> None:
        for env in envs:
            for ev in env["events"]:
                if ev["metric"] == "payment_success_rate" and ev["segment_key"] == "bank=BANK_C":
                    t = (datetime.fromisoformat(ev["ts"]) - START).total_seconds()
                    points.append(
                        {"t": t, "value": ev["value"], "n_total": ev["n_total"], "n_bad": ev["n_bad"]}
                    )

    collect(eng.step(T_CHAOS))
    eng.trigger("bank_c_slow")
    collect(eng.step(T_REROUTE - T_CHAOS))
    eng.set_routing("BANK_C", "RAAST")
    collect(eng.step(T_END - T_REROUTE))

    def agg(lo: float, hi: float) -> float:
        sel = [p for p in points if lo < p["t"] <= hi]
        tot = sum(p["n_total"] for p in sel)
        return round(1 - sum(p["n_bad"] for p in sel) / tot, 4)

    first_breach = next((p["t"] for p in points if p["t"] > T_CHAOS and p["value"] < FLOOR), None)
    recovered = next((p["t"] for p in points if p["t"] > T_REROUTE and p["value"] >= FLOOR), None)
    summary = {
        "seed": SEED,
        "window_s": 5,
        "slo_floor": FLOOR,
        "t_bank_c_slow": T_CHAOS,
        "t_reroute": T_REROUTE,
        "success_before_chaos_0_60": agg(0, T_CHAOS),
        "success_last_60s_before_reroute": agg(T_REROUTE - 60, T_REROUTE),
        "success_after_reroute_300_480": agg(T_REROUTE, T_END),
        "first_window_below_floor_t": first_breach,
        "first_window_recovered_t": recovered,
        "time_to_recover_s": None if recovered is None else recovered - T_REROUTE,
    }
    return {"summary": summary, "points": points}


def plot(data: dict, out: Path) -> None:
    pts = data["points"]
    xs = [p["t"] for p in pts]
    ys = [p["value"] for p in pts]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    ax.plot(xs, ys, color=SERIES, linewidth=2, solid_capstyle="round", label="BANK_C success rate (5 s)")
    ax.axhline(FLOOR, color=TEXT2, linestyle=(0, (5, 4)), linewidth=1.2)
    ax.text(T_END - 4, FLOOR - 0.008, "SLO floor 0.97", color=TEXT2, ha="right", va="top", fontsize=9)
    ymin = min(0.6, min(ys) - 0.03)
    ax.set_ylim(ymin, 1.02)
    ax.set_xlim(0, T_END)
    for t, label in ((T_CHAOS, "bank_c_slow"), (T_REROUTE, "reroute → Raast")):
        ax.axvline(t, color=TEXT2, linewidth=1, alpha=0.7)
        ax.text(t + 4, ymin + 0.015, label, color=TEXT, fontsize=9, ha="left", va="bottom")
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=TEXT2, length=0)
    ax.set_xlabel("simulated seconds", color=TEXT2)
    ax.set_ylabel("payment success rate", color=TEXT2)
    s = data["summary"]
    fig.suptitle(
        "Rerouting BANK_C via Raast restores payment success",
        x=0.065,
        y=0.965,
        ha="left",
        fontsize=14,
        fontweight="bold",
        color=TEXT,
    )
    fig.text(
        0.065,
        0.895,
        f"finpay-sim, seed {s['seed']}, 5 s windows · before {s['success_before_chaos_0_60']:.3f} · "
        f"last 60 s before reroute {s['success_last_60s_before_reroute']:.3f} · "
        f"after reroute {s['success_after_reroute_300_480']:.3f}",
        ha="left",
        fontsize=9.5,
        color=TEXT2,
    )
    fig.subplots_adjust(left=0.08, right=0.97, top=0.85, bottom=0.11)
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    data = run()
    (out_dir / "series.json").write_text(json.dumps(data, indent=2) + "\n")
    plot(data, out_dir / "01-bank-c-success-rate.png")
    print(json.dumps(data["summary"], indent=2))


if __name__ == "__main__":
    main()
