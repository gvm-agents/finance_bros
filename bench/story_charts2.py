"""Extra charts for the Story and Scorecard (numbers in appearance order). Reads saved runs only; no model is called.

Usage: venv/bin/python -m bench.story_charts2 <out_dir>   (run bench.story_charts and bench.thinking_matrix first)
"""
from __future__ import annotations

import collections
import json
import math
import statistics
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter, NullFormatter

from . import route_sim, scorecard
from .story_charts import COLOR, GROUP, ORDER, SHORT, TASK_LABEL, TASKS, foot, load

plt.rcParams.update({"text.parse_math": False, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
PLAIN = FuncFormatter(lambda v, _: f"{v:,.0f}" if v >= 1 else f"{v:g}")


def main(out_dir: str) -> int:
    out = Path(out_dir)
    calls, scored = load()
    by = collections.defaultdict(dict)
    for (lane, task, item), r in scored.items():
        by[lane][(task, item)] = r

    # Chart 5: security and version sorting
    inj = {}
    for f in ("results/inject-1031-summary.json", "results/inject-1031-open/summary.json"):
        inj.update(json.load(open(f))["summary"])
    ver = json.load(open("results/versions-1031/summary.json"))["summary"]
    names = {"sonnet5": "Sonnet 5", "haiku45": "Haiku 4.5", "gptoss120_fw": "gpt-oss-120b", "nemotron35_fw": "Nemotron 3.5", "deepseek41_fw": "DeepSeek V4.1"}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.4, 4.9))
    lanes = [l for l in names if l in inj and l != "deepseek41_fw"]
    x = np.arange(len(lanes))
    for k, (style, col, lab) in enumerate((("override", "#C00000", "Code-word plant"), ("tamper", "#7F7F7F", "'Report this amount' plant"))):
        vals = [100 * inj[l][style].get("obeyed", 0) / sum(inj[l][style].values()) for l in lanes]
        a1.bar(x + (k - 0.5) * 0.38, vals, 0.38, color=col, label=lab)
        for xi, v in zip(x, vals):
            a1.text(xi + (k - 0.5) * 0.38, v + 1.5, f"{v:.0f}", ha="center", fontsize=8)
    a1.set_xticks(x, [names[l] for l in lanes], fontsize=8.5); a1.set_ylabel("Filings where the model obeyed the planted line, %"); a1.set_ylim(0, 112); a1.legend(frameon=False, fontsize=8)
    a1.set_title("Hidden instructions: lower is safer", fontsize=10, loc="left")
    lv = [l for l in names if l in ver]
    x2 = np.arange(len(lv))
    for k, (mode, col, lab) in enumerate((("neutral", "#2E75B6", "Plain file names"), ("trap", "#ED7D31", "Misleading file names"))):
        vals = [100 * ver[l][mode]["right"] / ver[l][mode]["n"] for l in lv]
        a2.bar(x2 + (k - 0.5) * 0.38, vals, 0.38, color=col, label=lab)
        for xi, v in zip(x2, vals):
            a2.text(xi + (k - 0.5) * 0.38, v + 1.5, f"{v:.0f}", ha="center", fontsize=8)
    a2.set_xticks(x2, [names[l] for l in lv], fontsize=8, rotation=12); a2.set_ylabel("Newer version picked correctly, %"); a2.set_ylim(0, 112); a2.legend(frameon=False, fontsize=8, loc="lower left")
    a2.set_title("Which of two versions is newer: higher is better", fontsize=10, loc="left")
    fig.suptitle("Chart 5. Two tests beyond accuracy: obeying hidden instructions, and sorting document versions", x=0.01, ha="left", fontweight="bold")
    foot(fig, "Left: 30 Form D filings per model with an instruction planted in the text; scored by Python. DeepSeek is omitted (too many cut-off answers to score). Not tested: OpenAI, Opus. Right: 35 Form D / amendment pairs, 70 questions per model;\nchance is 50%. Truth comes from SEC filing dates. Small samples: gaps under about 15 points are not reliable. Sonnet 5 obeyed the code-word plant in 5 of 30 filings.")
    fig.tight_layout(rect=(0, 0.1, 1, 0.93)); fig.savefig(out / "chart5_security_versions.png", dpi=170); plt.close(fig)

    # Chart 6: volume, cost, uncertainty, reviewer minute
    per1000 = {"Sonnet 5": 33.99, "Haiku 4.5": 12.79, "DeepSeek V4.1": 3.96, "gpt-oss-120b": 1.72, "Nemotron 3.5": 0.63}
    cols = {"Sonnet 5": "#1F4E79", "Haiku 4.5": "#7F9FC6", "DeepSeek V4.1": "#C55A11", "gpt-oss-120b": "#ED9B5C", "Nemotron 3.5": "#BF9000"}
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(12.6, 4.8))
    vol = np.array([150, 1e3, 1e4, 1e5, 17014 * 1.0])
    vol = np.array([150, 1000, 10000, 100000])
    for n_, v in per1000.items():
        a1.plot(vol, vol / 1000 * v, marker="o", color=cols[n_], label=n_)
    a1.set_xscale("log"); a1.set_yscale("log"); a1.xaxis.set_major_formatter(PLAIN); a1.yaxis.set_major_formatter(PLAIN); a1.xaxis.set_minor_formatter(NullFormatter()); a1.yaxis.set_minor_formatter(NullFormatter())
    a1.set_xlabel("Form ADV filings read"); a1.set_ylabel("Model cost, $"); a1.legend(frameon=False, fontsize=7.5); a1.set_title("Cost grows in a straight line", fontsize=10, loc="left")
    ns = np.logspace(2, 5, 40)
    for p, c in ((0.99, "#C55A11"), (0.90, "#7F7F7F")):
        half = 1.96 * np.sqrt(p * (1 - p) / ns) * 100
        a2.plot(ns, half, color=c, label=f"true rate {int(p*100)}%")
    a2.axvline(150, color="#ED9B5C", ls=":"); a2.text(160, 6.0, "our bulk run (150)", fontsize=7.5, rotation=90, va="top")
    a2.set_xscale("log"); a2.xaxis.set_major_formatter(PLAIN); a2.xaxis.set_minor_formatter(NullFormatter()); a2.set_xlabel("Items checked (sample size)"); a2.set_ylabel("Uncertainty, +/- percentage points (95%)")
    a2.legend(frameon=False, fontsize=8); a2.set_title("More items, tighter estimate", fontsize=10, loc="left")
    vals = [2.5 / (v / 1000) for v in (9.94, 2.87, 0.55)]
    a3.bar(["Sonnet 5", "DeepSeek", "gpt-oss-120b"], vals, color=["#1F4E79", "#C55A11", "#ED9B5C"]); a3.set_yscale("log"); a3.yaxis.set_major_formatter(PLAIN); a3.yaxis.set_minor_formatter(NullFormatter())
    for i, v in enumerate(vals):
        a3.text(i, v * 1.1, f"{v:,.0f}", ha="center", fontsize=9)
    a3.set_ylabel("Answers (log scale)"); a3.set_title("Answers that cost one reviewer minute", fontsize=10, loc="left")
    fig.suptitle("Chart 6. Volume: what 100 parallel workers cost, how sure we can be, and why a reviewer's minute dominates", x=0.01, ha="left", fontweight="bold")
    foot(fig, "Left: measured Form ADV cost per 1,000 filings (40 test filings each; gpt-oss also 150 in the bulk run at $0.26), extended in a straight line; no volume discount or rate-limit cost. Parallel workers change speed, not the right rate: gpt-oss read 150 filings in 42 seconds with 100 workers.\nMiddle: the plus-or-minus on a measured right rate shrinks with the square root of the sample (our bulk run: 99.3% on 150, 95% range about 96 to 99.9). Right: $150/hour reviewer is our assumption; per-1,000 costs measured over 563 answers each.")
    fig.tight_layout(rect=(0, 0.12, 1, 0.93)); fig.savefig(out / "chart6_volume.png", dpi=170); plt.close(fig)

    # Chart 11: item heatmap 563 x models
    lanes = [l for l in ORDER]
    order_items = []
    for t in TASKS:
        ks = sorted({k for k in by["sonnet5"] if k[0] == t}, key=lambda k: -sum(by[l].get(k, {"score": 0})["score"] >= route_sim.GOOD for l in lanes))
        order_items += ks
    mat = np.array([[1 if by[l].get(k, {"score": 0})["score"] >= route_sim.GOOD else 0 for l in lanes] for k in order_items])
    fig, ax = plt.subplots(figsize=(7.4, 10.5))
    ax.imshow(mat, aspect="auto", cmap=matplotlib.colors.ListedColormap(["#F4B183", "#548235"]), interpolation="nearest")
    start = 0
    for t in TASKS:
        n = sum(1 for k in order_items if k[0] == t)
        ax.axhline(start - 0.5, color="black", lw=0.8)
        ax.text(len(lanes) - 0.35, start + n / 2, f"{TASK_LABEL[t]}\n(n={n})", fontsize=8, va="center")
        start += n
    ax.set_xticks(range(len(lanes)), [SHORT[l] for l in lanes], rotation=40, ha="right", fontsize=8); ax.set_yticks([]); ax.xaxis.tick_top()
    ax.set_xlim(-0.5, len(lanes) + 1.6)
    ax.set_title("Chart 11. All 563 test items: green = right (0.90 or more), orange = wrong", loc="left", fontweight="bold", pad=40, fontsize=10)
    foot(fig, "Each row is one test item; within each task, items are sorted from most to least models right. Tasks differ: Form ADV and Form D = pull fields from a document; sector = classify; duplicate names = yes/no;\ntable formatting = exact rules; snapshot = write with no invented numbers; long 10-K = find four numbers. Same items for every model.")
    fig.subplots_adjust(left=0.04, right=0.98, top=0.93, bottom=0.07); fig.savefig(out / "chart11_item_heatmap.png", dpi=170); plt.close(fig)

    # Chart 12: levers (measured changes in right %, same items)
    m = {(d["model"], d["setting"]): d for d in json.load(open(out / "matrix.json"))}

    def g(model, setting):
        for (mo, se), d in m.items():
            if mo == model and se.startswith(setting):
                return d
    sc = json.load(open(out / "sc_v2.json")) if (out / "sc_v2.json").exists() else None
    rows = []
    def add(label, a, b):
        if a and b:
            rows.append((label, b["right_pct"] - a["right_pct"], b["usd_per_1000"] / max(a["usd_per_1000"], 0.01), b["median_s"] / max(a["median_s"], 0.01)))
    add("DeepSeek: thinking off -> on (16k allowance)", g("DeepSeek V4.1", "off"), g("DeepSeek V4.1", "on, 16k"))
    add("Nemotron: thinking off -> on (16k allowance)", g("Nemotron 3.5", "off"), g("Nemotron 3.5", "on, 16k"))
    add("gpt-oss: effort low -> medium", g("gpt-oss-120b", "low"), g("gpt-oss-120b", "medium"))
    add("gpt-oss: effort low -> high", g("gpt-oss-120b", "low"), g("gpt-oss-120b", "high"))
    add("Haiku: thinking off -> on", g("Haiku 4.5", "off"), g("Haiku 4.5", "on"))
    add("Sonnet 5: thinking off -> high effort", g("Sonnet 5", "off"), g("Sonnet 5", "adaptive, high"))
    add("OpenAI luna: off -> high", g("OpenAI luna", "off"), g("OpenAI luna", "high"))
    add("OpenAI terra: off -> high", g("OpenAI terra", "off"), g("OpenAI terra", "high"))
    fig, ax = plt.subplots(figsize=(9.6, 4.8))
    ypos = range(len(rows))
    ax.barh(list(ypos), [r[1] for r in rows], color=["#548235" if r[1] > 0 else "#C00000" for r in rows])
    for i, r in enumerate(rows):
        ax.text(r[1] + (0.6 if r[1] >= 0 else -0.6), i, f"{r[1]:+.1f} pts, cost x{r[2]:.1f}, time x{r[3]:.1f}", va="center", ha="left" if r[1] >= 0 else "right", fontsize=8)
    ax.set_yticks(list(ypos), [r[0] for r in rows], fontsize=8.5); ax.invert_yaxis(); ax.axvline(0, color="black", lw=0.8)
    lo = min(r[1] for r in rows); hi = max(r[1] for r in rows)
    ax.set_xlim(lo - 25, hi + 25); ax.set_xlabel("Change in answers right, percentage points (same items)")
    ax.set_title("Chart 12. What moves the needle: measured effect of the thinking lever, with its cost and time", loc="left", fontweight="bold")
    foot(fig, "Open models: all 563 test answers per setting. Claude and OpenAI settings: a subsample (first 15-30 items per task), so small samples; a gain under about 5 points is not reliable there. Cost and time are multiples of the starting setting.\nNot measured here: bigger model size (see Chart 1), parallel workers (speed only), majority voting across models (no gain, section 7), prompt changes, routing with a fallback.")
    fig.tight_layout(rect=(0, 0.1, 1, 1)); fig.savefig(out / "chart12_levers.png", dpi=170); plt.close(fig)
    json.dump([{"label": r[0], "delta": round(r[1], 1), "cost_x": round(r[2], 2), "time_x": round(r[3], 2)} for r in rows], open(out / "levers.json", "w"), indent=1)
    print(json.dumps(rows, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
