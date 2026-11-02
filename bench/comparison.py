"""One-page test comparison from saved answers: open models, Claude and OpenAI on the same 563 items. No model is called.

  venv/bin/python -m bench.comparison --chart <png> --out <json>
Uses scorer v2 through route_sim.rescore. OpenAI rows come from azure-baseline-1031b (rate-limited calls retried).
The "fair 10-K" count uses only items whose key numbers appear literally in the excerpt the model was given.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import collect, route_sim, scorecard, tasks

RUNS = scorecard.RUNS + ("azure-baseline-1031b", "thinking-1031-open", "thinking-1031-rerun")  # later runs replace earlier rows; the rerun replaces rate-limited rows
ROWS = [("sonnet5", "Claude Sonnet 5", "Claude"), ("opus48", "Claude Opus 4.8", "Claude"), ("haiku45", "Claude Haiku 4.5", "Claude"),
        ("deepseek41_fw_on_big", "DeepSeek V4.1 Flash, more thinking room", "Open, on Fireworks"), ("deepseek41_fw", "DeepSeek V4.1 Flash", "Open, on Fireworks"),
        ("deepseek41_fw_off", "DeepSeek V4.1 Flash, thinking off", "Open, on Fireworks"),
        ("gptoss120_fw_med", "gpt-oss-120b, medium thinking", "Open, on Fireworks"), ("gptoss120_fw", "gpt-oss-120b", "Open, on Fireworks"),
        ("nemotron35_fw_on_big", "Nemotron 3.5, thinking on", "Open, on Fireworks"),
        ("gpt56luna", "OpenAI GPT-5.6 luna", "OpenAI, on Azure"), ("gpt56terra", "OpenAI GPT-5.6 terra", "OpenAI, on Azure"),
        ("gemma4_26b_local", "Gemma 4 26B", "Open, on the MacBook"), ("gemma4_12b_local", "Gemma 4 12B", "Open, on the MacBook")]
COLOR = {"Claude": "#2a78d6", "OpenAI, on Azure": "#c98500", "Open, on Fireworks": "#eb6834", "Open, on the MacBook": "#1baf7a"}
TASK_ORDER = ("adv_extract", "formd_extract", "sector", "name_match", "snapshot", "format_table", "longdoc")


def findable(item: dict) -> bool:
    """Every key number appears in the excerpt, written in full, in thousands or in millions."""
    for v in item["key"].values():
        if v in (None, ""):
            continue
        forms = {f"{abs(float(v)) / d:,.{p}f}" for d in (1, 1e3, 1e6) for p in (0, 1, 2, 3)}
        if not any(s in item["text"] for s in forms if len(s.replace(",", "").replace(".", "")) >= 3):
            return False
    return True


def build() -> dict:
    calls = [json.loads(l) for r in RUNS for l in open(f"results/runs/{r}/calls.jsonl")]
    scored = route_sim.rescore(calls)
    by: dict = {}
    for (lane, _, _), row in scored.items():
        by.setdefault(lane, []).append(row)
    ref = {(r["task"], r["item"]): r for r in by[scorecard.REFERENCE]}
    fair = [i["id"] for i in collect.load("longdoc", "test") if findable(i)]
    out = []
    for lane, label, group in ROWS:
        rows = by[lane]
        s = scorecard.summary(rows, ref)
        t = {k: scorecard.summary([r for r in rows if r["task"] == k], ref) for k in TASK_ORDER}
        f = [r for r in rows if r["task"] == "longdoc" and r["item"] in fair]
        out.append({"lane": lane, "label": label, "group": group, **s, "tasks": {k: v["right_pct"] for k, v in t.items()},
                    "p_tasks": {k: v["p"] for k, v in t.items()}, "fair_10k": [sum(r["score"] >= route_sim.GOOD for r in f), len(f)]})
    return {"rows": out, "fair_items": len(fair), "total_longdoc": 39}


def chart(d: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = sorted(d["rows"], key=lambda r: r["right_pct"])
    fig, ax = plt.subplots(figsize=(7.4, 3.9), dpi=200)
    ys = range(len(rows))
    ax.barh(list(ys), [r["right_pct"] for r in rows], height=0.62, color=[COLOR[r["group"]] for r in rows])
    for y, r in zip(ys, rows):
        ax.plot(r["ci"], [y, y], color="#444444", lw=1)
        ax.text(101, y, f"${r['usd_per_1000']:.2f}" if r["usd_per_1000"] else "Free", va="center", fontsize=7.5, color="#333333")
    ax.text(101, len(rows) - 0.3, "$ per 1,000\nanswers", fontsize=7, color="#555555", va="bottom")
    ax.set_yticks(list(ys), [r["label"] for r in rows], fontsize=7.5)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of 563 answers right (score 0.90 or more), %. Line shows the 95% range.", fontsize=7.5)
    ax.tick_params(axis="x", labelsize=7.5, length=0)
    ax.tick_params(axis="y", length=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color="#e6e6e3", lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=c) for c in COLOR.values()], labels=list(COLOR), fontsize=7, frameon=False,
              loc="lower right", bbox_to_anchor=(1.0, 0.0))
    fig.tight_layout()
    fig.savefig(path, facecolor="white")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chart", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    d = build()
    if a.out:
        a.out.write_text(json.dumps(d, indent=1))
    if a.chart:
        chart(d, a.chart)
    for r in sorted(d["rows"], key=lambda r: -r["right_pct"]):
        print(f"{r['label']:42} {r['right_pct']:5} {r['ci']} p={r['p']:<7} ${r['usd_per_1000']:<6} {r['median_s']:>5}s", " ".join(f"{r['tasks'][t]:5}" for t in TASK_ORDER), r["fair_10k"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
