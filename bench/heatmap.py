"""Model-by-task heatmap from saved scores. Python only: no model is called.

  python -m bench.heatmap --out docs/img/heatmap.png
Each cell is the share of answers right on that task. The last column is the share of 8-K filings sorted right on priority,
from the 181 fresh filings. Long reports use the rebuilt excerpts. A dash means the model was not run on that task. Every cell shows its number, so color is never the only signal.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import comparison, router
from . import coordinator as co

MODELS = [("sonnet5", "Sonnet 5", "Frontier"), ("gpt56luna", "GPT-5.6 luna", "Frontier"), ("haiku45", "Haiku 4.5", "Frontier"),
          ("gptoss120_fw", "gpt-oss-120b", "Open, hosted"), ("deepseek41_fw", "DeepSeek V4.1 Flash", "Open, hosted"),
          ("gemma4_12b_local", "Gemma 4 12B", "Open, on a laptop"), ("gemma4_26b_local", "Gemma 4 26B", "Open, on a laptop")]
LONG = {"sonnet5": "sonnet5", "gpt56luna": "gpt56luna", "gptoss120_fw": "gptoss120_fw_med", "deepseek41_fw": "deepseek41_fw_on_big"}  # rebuilt long-report test; only these ran it
FRESH = {"gpt56luna": "gpt56luna_none", "deepseek41_fw": "deepseek41_fw_off"}  # the setting run on the fresh filings
TASKS = [("adv_extract", "Pull facts:\nsimple\nforms"), ("formd_extract", "Pull facts:\ndetailed\nforms"), ("sector", "Classify\ncompanies"), ("name_match", "Match\nduplicate\nrecords"),
         ("snapshot", "Write to\na rule"), ("format_table", "Format\nexactly"), ("longdoc", "Answer from\nlong reports"), ("triage", "Sort by\nimportance")]
LOW, MID, HIGH = 40.0, 75.0, 100.0  # red at 40, pale gray at 75, green at 100


def long_reports() -> dict[str, float]:
    """Share right on the rebuilt excerpts. The first long-report test left numbers out of the excerpts, so it is not shown."""
    best: dict[tuple, dict] = {}
    for run in ("longdoc-v2-1031", "longdoc-v2-1031-luna"):  # the second run replaces rate-limited calls in the first
        for c in map(json.loads, (co.RUNS / run / "calls.jsonl").open()):
            if not c.get("error"):
                best[(c["lane"], c["item"])] = c
    out: dict[str, list[int]] = {}
    for (lane, _), c in best.items():
        n = out.setdefault(lane, [0, 0])
        n[0] += c.get("score", 0) >= 0.9
        n[1] += 1
    return {k: 100 * a / b for k, (a, b) in out.items()}


def matrix() -> tuple[list[str], list[list[float | None]]]:
    rows = {r["lane"]: r for r in comparison.build()["rows"]}
    long = long_reports()
    fresh = {s["name"]: s for s in router.simulate("fresh")["singles"]}
    labels, out = [], []
    for lane, label, kind in MODELS:
        if lane not in rows:
            continue
        cells: list[float | None] = [rows[lane]["tasks"].get(t) for t, _ in TASKS[:-2]]
        cells.append(long.get(LONG.get(lane, "")))
        f = fresh.get(FRESH.get(lane, lane))
        cells.append(f["accuracy"] if f else None)
        labels.append(f"{label}\n{kind}")
        out.append(cells)
    return labels, out


def draw(labels: list[str], data: list[list[float | None]], path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
    cmap = LinearSegmentedColormap.from_list("rg", ["#c23a39", "#ec9a8a", "#f0efec", "#8fd0a0", "#0a7d4f"])
    norm = TwoSlopeNorm(vmin=LOW, vcenter=MID, vmax=HIGH)
    fig, ax = plt.subplots(figsize=(9.4, 0.62 * len(labels) + 1.55), dpi=200)
    for y, row in enumerate(data):
        for x, v in enumerate(row):
            face = "#ffffff" if v is None else cmap(norm(max(LOW, min(HIGH, v))))
            ax.add_patch(plt.Rectangle((x, y), 1, 1, facecolor=face, edgecolor="#000000", linewidth=1))
            dark = v is not None and (v >= 95 or v <= 50)
            ax.text(x + 0.5, y + 0.5, "-" if v is None else f"{v:.0f}", ha="center", va="center", fontsize=13, color="#ffffff" if dark else "#1a1a19" if v is not None else "#8a8a86", fontweight="bold" if v is not None else "normal")
    ax.set_xlim(0, len(TASKS))
    ax.set_ylim(len(labels), 0)
    ax.set_xticks([i + 0.5 for i in range(len(TASKS))], [t for _, t in TASKS], fontsize=10.5)
    ax.set_yticks([i + 0.5 for i in range(len(labels))], labels, fontsize=11)
    ax.xaxis.tick_top()
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.text(0.01, 0.012, "Share of answers right, %. Green is high, red is low. A dash means not tested. 30 to 181 test items per job.\nSort by importance counts every item sorted correctly, important or routine.", fontsize=10, color="#52514e")
    fig.tight_layout(rect=(0, 0.09, 1, 1))
    fig.savefig(path, facecolor="white")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--today", action="store_true", help="add an empty row to fill in during the day")
    a = ap.parse_args()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    labels, data = matrix()
    if a.today:
        order = [i for i, l in enumerate(labels) if "Frontier" in l] + [i for i, l in enumerate(labels) if "laptop" in l] + [i for i, l in enumerate(labels) if "hosted" in l]
        labels, data = [labels[i].replace("Open, hosted", "Fireworks, starting point") for i in order] + ["Today's best\nFireworks, tuned"], [data[i] for i in order] + [[None] * len(TASKS)]
    draw(labels, data, a.out)
    for l, r in zip(labels, data):
        print(l.replace("\n", " / "), r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
