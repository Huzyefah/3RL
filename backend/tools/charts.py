"""Evidence charts (dev-only). Palette: dataviz reference categorical slots, light mode."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

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


def episode_lines(path, title, subtitle, x, lines: dict[str, list[float]], marks: dict[str, object], ylabel="u",
                  bands=True) -> None:
    """Small-multiples-free line chart on one axis (u), with PS-02 band lines and labelled event markers."""
    fig, ax = plt.subplots(figsize=(10, 4.6), dpi=150)
    for i, (name, ys) in enumerate(lines.items()):
        ax.plot(x, ys, color=SERIES[i % len(SERIES)], linewidth=2, label=name)
    if bands:
        for y, lab in ((0.95, "CRITICAL 0.95"), (0.75, "WARNING 0.75")):
            ax.axhline(y, color=TEXT_2, linewidth=1, linestyle=(0, (4, 3)))
            ax.text(x[0], y + 0.01, lab, color=TEXT_2, fontsize=8)
    for lab, xv in marks.items():
        ax.axvline(xv, color=TEXT_2, linewidth=1, linestyle=":")
        ax.text(xv, ax.get_ylim()[1] * 0.98, f" {lab}", color=TEXT, fontsize=8.5, va="top")
    ax.set_ylabel(ylabel, color=TEXT_2)
    style(ax, title, subtitle)
    ax.legend(frameon=False, loc="upper left", labelcolor=TEXT_2, ncols=2, bbox_to_anchor=(0, -0.12))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
