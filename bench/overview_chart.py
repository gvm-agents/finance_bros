"""Chart for the overview page: share of important items caught against cost. Python only, read from saved results.

  python -m bench.overview_chart --out docs/img/overview-chart.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

from . import router

FREE_X = 0.012  # where a no-fee model sits on the log axis
FRONTIER, OPEN, OURS = "#b4531a", "#2a78d6", "#0b0b0b"
# lane: (label, kind, label x, label y, horizontal alignment)
DOTS = {"sonnet5": ("Frontier model\n(Claude Sonnet)", FRONTIER, 1.9, 96.35, "center"),
        "gpt56luna_none": ("Small frontier model\n(OpenAI luna)", FRONTIER, 0.62, 98.75, "center"),
        "fw_auto": ("Fireworks automatic router", OPEN, 0.145, 96.8, "left"),
        "deepseek41_fw_off": ("DeepSeek alone", OPEN, 0.30, 98.05, "left"),
        "gptoss120_fw": ("gpt-oss alone", OPEN, 0.14, 94.9, "left"),
        "gemma4_12b_local": ("Gemma alone, on a laptop\n(no fee, one machine)", OPEN, 0.0125, 97.3, "left")}


def draw(path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sim = router.simulate("fresh")
    singles = {s["name"]: s for s in sim["singles"]}
    system = next(s for s in sim["systems"] if s["name"].startswith("gpt-oss, then"))
    fig, ax = plt.subplots(figsize=(10, 6.2), dpi=200)
    ax.set_xscale("log")
    ax.set_xlim(0.009, 7)
    ax.set_ylim(93, 100.4)
    ax.set_xticks([FREE_X, 0.1, 0.25, 1, 2, 5], ["no fee", "$0.10", "$0.25", "$1", "$2", "$5"], fontsize=14)
    ax.minorticks_off()
    ax.tick_params(axis="y", labelsize=14, length=0)
    ax.tick_params(axis="x", length=0)
    ax.set_yticks([94, 96, 98, 100], ["94%", "96%", "98%", "100%"])
    ax.grid(color="#e4e3de", linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.set_xlabel("Cost per 1,000 items (log scale)", fontsize=14, labelpad=10)
    ax.set_ylabel("Important items caught", fontsize=14, labelpad=10)
    for lane, (label, color, tx, ty, ha) in DOTS.items():
        s = singles[lane]
        x = max(s["usd_per_1000"], FREE_X)
        offset = {"gpt56luna_none": 1.09, "fw_auto": 0.92}.get(lane, 1.0)  # the same score and cost, so set side by side
        ax.scatter([x * offset], [s["recall"]], s=130, color=color, edgecolor="white", linewidth=1.5, zorder=3)
        ax.annotate(label, (x * offset, s["recall"]), (tx, ty), fontsize=13, ha=ha, va="center", color="#1a1a19",
                    arrowprops=dict(arrowstyle="-", color="#8a8a86", linewidth=0.8, shrinkB=6))
    ax.scatter([system["usd_per_1000"]], [system["recall"]], s=420, color=OURS, edgecolor="white", linewidth=2, zorder=5)
    ax.annotate("Our router", (system["usd_per_1000"], system["recall"]), (0.052, 99.75), fontsize=16, fontweight="bold", color=OURS, va="center",
                arrowprops=dict(arrowstyle="-", color=OURS, linewidth=1, shrinkB=9))
    h = [plt.Line2D([], [], marker="o", linestyle="", markersize=m, color=c, label=t) for c, t, m in
         ((OURS, "Our router", 12), (OPEN, "Open model or open-model service", 10), (FRONTIER, "Frontier model", 10))]
    ax.legend(handles=h, loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=3, frameon=True, edgecolor="#000000", fancybox=False, fontsize=13)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    draw(a.out)
    print(a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
