"""Render the NovaPay service dependency graph (owners, tiers, segments) to a PNG."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from sentinel.topology import Topology  # noqa: E402

OUT = ROOT / "backend/.cache/plots/topology.png"
TIER_COLOUR = {0: "#d95f02", 1: "#1b9e77", 2: "#7570b3"}
TIER_LABEL = {0: "Tier 0", 1: "Tier 1", 2: "Tier 2"}
# (x, y) layout: callers on top, shared dependencies below.
POS = {
    "PaymentGateway": (7.0, 4.2),
    "AuthService": (2.5, 2.6),
    "NotificationHub": (7.5, 2.6),
    "DataPipeline": (12.5, 2.6),
    "UserProfileService": (2.5, 0.8),
    "SearchAPI": (9.0, 0.8),
    "AnalyticsDashboard": (12.5, 0.8),
    "ReportGenerator": (16.0, 0.8),
}


def main() -> None:
    topo = Topology.from_yaml()
    fig, ax = plt.subplots(figsize=(16, 7))
    w, h = 3.2, 1.1
    for name, svc in topo.services.items():
        for dep in svc.depends_on:
            (x1, y1), (x2, y2) = POS[name], POS[dep]
            ax.annotate(
                "",
                xy=(x2, y2 + (h / 2 if y2 < y1 else -h / 2)),
                xytext=(x1, y1 + (-h / 2 if y2 < y1 else h / 2)),
                arrowprops=dict(arrowstyle="-|>", color="#333333", lw=1.5, shrinkA=2, shrinkB=2),
                zorder=2,
            )
    for name, svc in topo.services.items():
        x, y = POS[name]
        ax.add_patch(
            plt.Rectangle(
                (x - w / 2, y - h / 2), w, h, color=TIER_COLOUR[svc.tier], ec="black", zorder=3
            )
        )
        seg = "; ".join(f"{k}: {len(v)} ({v[0]}..{v[-1]})" for k, v in svc.segments.items())
        lines = [name]
        if svc.novapay_name != name:
            lines.append(f"({svc.novapay_name})")
        lines.append(f"{svc.owner} | {TIER_LABEL[svc.tier]}")
        if seg:
            lines.append(seg)
        ax.text(x, y, "\n".join(lines), ha="center", va="center", color="white", fontsize=8,
                fontweight="bold", zorder=4)  # fmt: skip
    ax.set_xlim(-0.5, 18.0)
    ax.set_ylim(-0.9, 5.0)
    ax.axis("off")
    ax.set_title("NovaPay service dependencies (arrow = depends on)", fontsize=13, loc="left")
    handles = [
        plt.Rectangle((0, 0), 1, 1, color=c, label=TIER_LABEL[t]) for t, c in TIER_COLOUR.items()
    ]
    ax.legend(handles=handles, loc="lower left", frameon=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=130, bbox_inches="tight", facecolor="white")
    print(OUT)


if __name__ == "__main__":
    main()
