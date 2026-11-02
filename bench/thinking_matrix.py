"""Thinking off / on matrix from saved runs. Calls no model.

Usage: venv/bin/python -m bench.thinking_matrix <out_dir>   (repo root; copy the Mini runs into results/runs first)
Needs results/runs/{baseline-1030,deepseek-1030,gptoss-1030,nemotron-1030,thinking-1031-open,thinking-1031-claude}/calls.jsonl.
Each setting is compared with its own baseline on the SAME items (the Claude runs used the first 30 items per task).
"""
from __future__ import annotations

import collections
import json
import statistics
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from . import route_sim, scorecard

BASE_RUNS = ("baseline-1030", "gptoss-1030", "nemotron-1030", "deepseek-1030")
NEW_RUNS = ("thinking-1031-open", "thinking-1031-claude", "thinking-1031-rerun", "azure-baseline-1031", "openai-thinking-1031-luna", "openai-thinking-1031-terra")  # later runs replace earlier rows for the same lane/item (the rerun replaces rate-limited rows)
# (model label, setting label, lane name, baseline-or-new)
CELLS = [
    ("DeepSeek V4.1", "off", "deepseek41_fw_off"), ("DeepSeek V4.1", "on (default, 4k headroom) = baseline", "deepseek41_fw"), ("DeepSeek V4.1", "on, 16k headroom", "deepseek41_fw_on_big"),
    ("gpt-oss-120b", "low = baseline", "gptoss120_fw"), ("gpt-oss-120b", "medium", "gptoss120_fw_med"), ("gpt-oss-120b", "high", "gptoss120_fw_high"),
    ("Nemotron 3.5", "off = baseline", "nemotron35_fw"), ("Nemotron 3.5", "on, 4k headroom (many cut off)", "nemotron35_fw_on"), ("Nemotron 3.5", "on, 16k headroom", "nemotron35_fw_on_big"),
    ("Sonnet 5", "off", "sonnet5_off"), ("Sonnet 5", "adaptive, low effort = baseline", "sonnet5"), ("Sonnet 5", "adaptive, high effort", "sonnet5_high"),
    ("Haiku 4.5", "off = baseline", "haiku45"), ("Haiku 4.5", "on (3,000-token budget)", "haiku45_on"),
    ("OpenAI luna", "off", "gpt56luna_none"), ("OpenAI luna", "low = baseline", "gpt56luna"), ("OpenAI luna", "high", "gpt56luna_high"),
    ("OpenAI terra", "off", "gpt56terra_none"), ("OpenAI terra", "low = baseline", "gpt56terra"), ("OpenAI terra", "high", "gpt56terra_high"),
]
TASKS = ["adv_extract", "formd_extract", "sector", "name_match", "format_table", "snapshot", "longdoc"]


def main(out_dir: str) -> int:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    calls = [json.loads(l) for r in BASE_RUNS + NEW_RUNS if Path(f"results/runs/{r}/calls.jsonl").exists() for l in open(f"results/runs/{r}/calls.jsonl")]
    scored = route_sim.rescore(calls)
    by = collections.defaultdict(dict)  # lane -> (task,item) -> row
    for (lane, task, item), r in scored.items():
        by[lane][(task, item)] = r
    result = []
    for model, setting, lane in CELLS:
        rows = by.get(lane, {})
        # items shared by every setting of this model, so comparisons are like for like
        peers = [l for m, _, l in CELLS if m == model and by.get(l)]
        common = set.intersection(*[set(by[l]) for l in peers]) if peers else set()
        ks = [k for k in rows if k in common]
        if not ks:
            continue
        rs = [rows[k] for k in ks]
        d = {"model": model, "setting": setting, "lane": lane, "n": len(rs), "right_pct": round(100 * statistics.mean(r["score"] >= route_sim.GOOD for r in rs), 1),
             "mean_score": round(statistics.mean(r["score"] for r in rs), 3), "out_tokens": round(statistics.mean(r["tokens_out"] for r in rs)),
             "median_s": round(statistics.median(r["seconds"] for r in rs), 2), "usd_per_1000": round(1000 * statistics.mean(r["usd"] for r in rs), 2),
             "errors": sum(bool(r.get("error")) for r in rs), "tasks": {}}
        for t in TASKS:
            tk = [rows[k] for k in ks if k[0] == t]
            if tk:
                d["tasks"][t] = {"n": len(tk), "right_pct": round(100 * statistics.mean(r["score"] >= route_sim.GOOD for r in tk), 1)}
        base = next((l for m, s, l in CELLS if m == model and "baseline" in s), None)
        if base and base != lane and by.get(base):
            pairs = [(rows[k]["score"] >= route_sim.GOOD, by[base][k]["score"] >= route_sim.GOOD) for k in ks if k in by[base]]
            b = sum(x and not y for x, y in pairs)
            c = sum(y and not x for x, y in pairs)
            d["vs_baseline"] = {"better": b, "worse": c, "p": round(scorecard.mcnemar(b, c), 4)}
        result.append(d)
    json.dump(result, open(out / "matrix.json", "w"), indent=1)

    plt.rcParams.update({"text.parse_math": False, "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(9.6, 8.0))
    labels = [f'{d["model"]}: {d["setting"]}' for d in result]
    colors = {"DeepSeek V4.1": "#C55A11", "gpt-oss-120b": "#ED9B5C", "Nemotron 3.5": "#BF9000", "Sonnet 5": "#1F4E79", "Haiku 4.5": "#7F9FC6", "OpenAI luna": "#7030A0", "OpenAI terra": "#B07CC6"}
    y = range(len(result))
    ax.barh(list(y), [d["right_pct"] for d in result], color=[colors[d["model"]] for d in result])
    for i, d in enumerate(result):
        star = ""
        if "vs_baseline" in d and d["vs_baseline"]["p"] < 0.05:
            star = " *"
        ax.text(d["right_pct"] + 0.8, i, f'{d["right_pct"]:.1f}%{star}   {d["out_tokens"]} tok, ${d["usd_per_1000"]:.2f}/1,000, n={d["n"]}', va="center", fontsize=7.5)
    ax.set_yticks(list(y), labels, fontsize=8); ax.invert_yaxis(); ax.set_xlim(0, 130); ax.set_xlabel("Answers right, %")
    ax.set_title("Chart 4. Thinking off and on: right rate on the same items", loc="left", fontweight="bold")
    fig.text(0.01, 0.005, "Open-model settings: all 563 test answers each. Claude settings: first 30 items of each task (about 209 answers), compared on those same items. * = significantly different from that model's baseline (paired test, 5% level).\ntok = average tokens written per answer. Cost from list prices applied to measured tokens. 'Right' = score 0.90 or more. gpt-oss has no off setting.", fontsize=7, va="bottom")
    fig.tight_layout(rect=(0, 0.07, 1, 1)); fig.savefig(out / "chart9_thinking_matrix.png", dpi=170)
    print(json.dumps([{k: v for k, v in d.items() if k != "tasks"} for d in result], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
