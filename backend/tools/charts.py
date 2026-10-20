"""Evidence charts (dev-only). Palette: dataviz reference categorical slots, light mode."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]


def style(ax, title: str, subtitle: str = "") -> None:
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=TEXT_2, length=0)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", color=TEXT, fontsize=13, fontweight="bold", pad=22)
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, color=TEXT_2, fontsize=9.5)


def grouped_bars(path, title, subtitle, groups, series: dict[str, list[float]], fmt="{:.0f}") -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    n = len(series)
    width = 0.8 / n
    for i, (name, vals) in enumerate(series.items()):
        xs = [g + (i - (n - 1) / 2) * width for g in range(len(groups))]
        bars = ax.bar(xs, vals, width * 0.92, color=SERIES[i], label=name, edgecolor=SURFACE, linewidth=2)
        ax.bar_label(bars, labels=[fmt.format(v) for v in vals], color=TEXT, fontsize=9, padding=3)
    ax.set_xticks(range(len(groups)), groups, color=TEXT)
    style(ax, title, subtitle)
    ax.legend(frameon=False, loc="upper left", labelcolor=TEXT_2, ncols=n, bbox_to_anchor=(0, -0.08))
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
