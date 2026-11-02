"""Charts and extra numbers for the Story and Scorecard. Reads saved runs only; calls no model.

Usage: venv/bin/python -m bench.story_charts <out_dir>
Writes eight PNG charts plus extras.json (task-balanced averages, threshold table, vote test).
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
import numpy as np
import textwrap
from matplotlib.ticker import FuncFormatter, NullFormatter

PLAIN = FuncFormatter(lambda v, _: f"{v:,.0f}" if v >= 1 else f"{v:g}")

from . import route_sim, scorecard, tasks

ORDER = ["sonnet5", "opus48", "haiku45", "deepseek41_fw", "gptoss120_fw", "nemotron35_fw", "gemma4_26b_local", "gemma4_12b_local", "gemma4_e2b_local"]
SHORT = {"sonnet5": "Sonnet 5", "opus48": "Opus 4.8", "haiku45": "Haiku 4.5", "deepseek41_fw": "DeepSeek V4.1", "gptoss120_fw": "gpt-oss-120b",
         "nemotron35_fw": "Nemotron 3.5", "gemma4_26b_local": "Gemma 26B", "gemma4_12b_local": "Gemma 12B", "gemma4_e2b_local": "Gemma E2B"}
GROUP = {"sonnet5": "Frontier (closed)", "opus48": "Frontier (closed)", "haiku45": "Frontier (closed)", "deepseek41_fw": "Open, hosted",
         "gptoss120_fw": "Open, hosted", "nemotron35_fw": "Open, hosted", "gemma4_26b_local": "Open, local", "gemma4_12b_local": "Open, local", "gemma4_e2b_local": "Open, local"}
COLOR = {"Frontier (closed)": "#1F4E79", "Open, hosted": "#C55A11", "Open, local": "#548235"}
TASKS = ["adv_extract", "formd_extract", "sector", "name_match", "format_table", "snapshot", "longdoc"]
TASK_LABEL = {"adv_extract": "Form ADV facts", "formd_extract": "Form D facts", "sector": "Sector tagging", "name_match": "Duplicate names",
              "format_table": "Table formatting", "snapshot": "Company snapshot", "longdoc": "Long 10-K facts"}
NOTE = "Public SEC filings. 'Right' = score of 0.90 or more. 95% range: Wilson interval. 'Different from Sonnet 5': exact paired McNemar test, 5% level."
plt.rcParams.update({"text.parse_math": False, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "font.family": "DejaVu Sans"})


def foot(fig, text):
    fig.text(0.01, 0.005, text, fontsize=7.5, color="#444", va="bottom", ha="left", wrap=True)


def load():
    calls = [json.loads(l) for run in scorecard.RUNS for l in open(f"results/runs/{run}/calls.jsonl")]
    return calls, route_sim.rescore(calls)


def vote_test(calls):
    """Majority vote of the six open models on the two yes/no style tasks, against Sonnet 5 alone. Different models, one run each."""
    open_lanes = ["deepseek41_fw", "gptoss120_fw", "nemotron35_fw", "gemma4_26b_local", "gemma4_12b_local", "gemma4_e2b_local"]
    keys = {}
    for t, f in (("name_match", "name_match"), ("sector", "sector")):
        for l in open(f"data/items/{f}.jsonl"):
            d = json.loads(l)
            keys[(t, d["id"])] = d["key"]
    ans = collections.defaultdict(dict)
    for c in calls:
        if c["task"] in ("name_match", "sector") and not c.get("error"):
            g = tasks.parse_json(c["reply"])
            if c["task"] == "name_match" and isinstance(g, dict) and isinstance(g.get("same"), bool):
                ans[(c["task"], c["item"])][c["lane"]] = g["same"]
            if c["task"] == "sector" and isinstance(g, dict) and g.get("division"):
                ans[(c["task"], c["item"])][c["lane"]] = str(g["division"]).strip().upper()[:1]
    out = {}
    for t in ("name_match", "sector"):
        items = [k for k in ans if k[0] == t and all(l in ans[k] for l in open_lanes + ["sonnet5"])]
        def truth(k):
            return keys[k]["same"] if t == "name_match" else keys[k]["division"]
        res = {"n": len(items)}
        res["sonnet5"] = round(100 * statistics.mean(ans[k]["sonnet5"] == truth(k) for k in items), 1)
        for lane in open_lanes:
            res[lane] = round(100 * statistics.mean(ans[k][lane] == truth(k) for k in items), 1)
        for name, group in (("vote3_top3", ["deepseek41_fw", "gptoss120_fw", "gemma4_26b_local"]), ("vote5_no_e2b", open_lanes[:5]), ("vote6_all_open", open_lanes)):
            hit = 0
            for k in items:
                cnt = collections.Counter(ans[k][l] for l in group)
                top = cnt.most_common(1)[0]
                hit += top[0] == truth(k)
            res[name] = round(100 * hit / len(items), 1)
        out[t] = res
    return out


def main(out_dir: str) -> int:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    calls, scored = load()
    by = collections.defaultdict(list)
    for (lane, _, _), r in scored.items():
        by[lane].append(r)
    ref = {(r["task"], r["item"]): r for r in by["sonnet5"]}
    summ = {l: scorecard.summary(by[l], ref) for l in ORDER}
    tsum = {l: {t: scorecard.summary([r for r in by[l] if r["task"] == t], ref) for t in TASKS} for l in ORDER}
    n_task = {t: tsum["sonnet5"][t]["n"] for t in TASKS}

    # 1 overall
    fig, ax = plt.subplots(figsize=(8.6, 5.4))
    for i, l in enumerate(ORDER):
        s = summ[l]
        ax.barh(i, s["right_pct"], color=COLOR[GROUP[l]], alpha=0.9)
        ax.errorbar(s["right_pct"], i, xerr=[[s["right_pct"] - s["ci"][0]], [s["ci"][1] - s["right_pct"]]], color="black", capsize=3, lw=1)
        sig = "reference" if l == "sonnet5" else ("significantly worse" if s["p"] < 0.05 and s["right_pct"] < summ["sonnet5"]["right_pct"] else "not significantly different")
        ax.text(s["ci"][1] + 1, i, f'{s["right_pct"]:.1f}%  ({sig})', va="center", fontsize=8.5)
    ax.set_yticks(range(len(ORDER)), [SHORT[l] for l in ORDER]); ax.invert_yaxis(); ax.set_xlim(0, 112)
    ax.set_xlabel("Answers right, % (bars show 95% range)")
    ax.set_title("Chart 1. Overall: how often each model was right", loc="left", fontweight="bold")
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=c) for c in COLOR.values()], labels=list(COLOR), loc="lower right", frameon=False)
    foot(fig, "Sample: 563 scored answers per model (7 tasks, same items for every model, mix 40-120 per task). " + NOTE + "\nThe overall figure blends tasks by their item counts; see Chart 2 for each task.")
    fig.tight_layout(rect=(0, 0.07, 1, 1)); fig.savefig(out / "chart1_overall.png", dpi=170); plt.close(fig)

    # 2 heatmap
    mat = np.array([[tsum[l][t]["right_pct"] for t in TASKS] for l in ORDER])
    fig, ax = plt.subplots(figsize=(9.2, 5.6))
    ax.imshow(mat, cmap="RdYlGn", vmin=0, vmax=100, aspect="auto")
    for i, l in enumerate(ORDER):
        for j, t in enumerate(TASKS):
            s = tsum[l][t]
            star = "*" if (l != "sonnet5" and s["p"] < 0.05) else ""
            ax.text(j, i, f'{s["right_pct"]:.0f}{star}', ha="center", va="center", fontsize=9, fontweight="bold" if star else "normal")
    ax.set_xticks(range(len(TASKS)), [f"{TASK_LABEL[t]}\n(n={n_task[t]})" for t in TASKS], fontsize=8.5)
    ax.set_yticks(range(len(ORDER)), [SHORT[l] for l in ORDER]); ax.xaxis.tick_top()
    ax.set_title("Chart 2. Right, %, by task and model", loc="left", fontweight="bold", pad=34)
    foot(fig, "* = significantly different from Sonnet 5 (paired test, 5% level). No star = cannot tell apart; with n of 39-42 that is not proof of equality.\nn = answers per model per task. " + NOTE)
    fig.tight_layout(rect=(0, 0.07, 1, 1)); fig.savefig(out / "chart2_by_task.png", dpi=170); plt.close(fig)

    # 3 cost vs right
    fig, ax = plt.subplots(figsize=(8.6, 5.4))
    for l in ORDER:
        s = summ[l]; x = max(s["usd_per_1000"], 0.05)
        ax.errorbar(x, s["right_pct"], yerr=[[s["right_pct"] - s["ci"][0]], [s["ci"][1] - s["right_pct"]]], fmt="o", color=COLOR[GROUP[l]], capsize=3, ms=8)
        ax.annotate(SHORT[l], (x, s["right_pct"]), textcoords="offset points", xytext=(7, 5), fontsize=8.5)
    ax.set_xscale("log"); ax.xaxis.set_major_formatter(PLAIN); ax.xaxis.set_minor_formatter(NullFormatter()); ax.set_xlabel("Model cost, $ per 1,000 answers (log scale; local models plotted at $0.05 because they have no per-answer charge)"); ax.set_ylabel("Answers right, %")
    ax.set_title("Chart 3. Quality against cost", loc="left", fontweight="bold")
    foot(fig, "Sample: 563 answers per model. Vertical bars = 95% range. Cost from list prices applied to measured tokens, not a bill. " + NOTE)
    fig.tight_layout(rect=(0, 0.07, 1, 1)); fig.savefig(out / "chart3_cost_quality.png", dpi=170); plt.close(fig)

    # 4 speed
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.6, 5.0), gridspec_kw={"width_ratios": [1.3, 1]})
    y = np.arange(len(ORDER))
    a1.barh(y - 0.2, [summ[l]["median_s"] for l in ORDER], 0.4, color="#2E75B6", label="Median")
    a1.barh(y + 0.2, [summ[l]["p95_s"] for l in ORDER], 0.4, color="#9DC3E6", label="95th percentile")
    a1.set_yticks(y, [SHORT[l] for l in ORDER]); a1.invert_yaxis(); a1.set_xlabel("Seconds per answer"); a1.legend(frameon=False); a1.set_title("Time to answer", loc="left", fontsize=10)
    a2.barh(y, [summ[l]["out_tokens"] for l in ORDER], color=[COLOR[GROUP[l]] for l in ORDER]); a2.set_yticks(y, [""] * len(ORDER)); a2.invert_yaxis(); a2.set_xlabel("Tokens written per answer")
    a2.set_title("Length of answer (thinking counts)", loc="left", fontsize=10)
    fig.suptitle("Chart 9. Speed (appendix)", x=0.01, ha="left", fontweight="bold")
    foot(fig, "Sample: 563 answers per model. 95th percentile: 95 of 100 answers finished in under this time. Local runs are not clean benchmarks (shared machine, one answer at a time).\nDeepSeek writes about 11x Sonnet 5's tokens because it thinks first.")
    fig.tight_layout(rect=(0, 0.08, 1, 0.95)); fig.savefig(out / "chart9_speed.png", dpi=170); plt.close(fig)

    # 5 bulk + reviewer minute
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.6, 4.6))
    per1000 = {"Sonnet 5": summ["sonnet5"]["usd_per_1000"], "DeepSeek": summ["deepseek41_fw"]["usd_per_1000"], "gpt-oss-120b": summ["gptoss120_fw"]["usd_per_1000"]}
    vals = [2.5 / (v / 1000) for v in per1000.values()]
    a1.bar(list(per1000), vals, color=["#1F4E79", "#C55A11", "#C55A11"]); a1.set_yscale("log"); a1.yaxis.set_major_formatter(PLAIN); a1.yaxis.set_minor_formatter(NullFormatter()); a1.set_ylabel("Answers (log scale)")
    for i, v in enumerate(vals): a1.text(i, v * 1.1, f"{v:,.0f}", ha="center", fontsize=9)
    a1.set_title("Answers that cost one reviewer minute\n($150/hour = $2.50/minute)", fontsize=10, loc="left")
    a2.bar(["One at a time\n(estimate)", "100 workers\n(measured)"], [150 * 1.3, 42], color=["#BFBFBF", "#C55A11"]); a2.set_ylabel("Seconds for 150 Form ADV filings")
    for i, v in enumerate([195, 42]): a2.text(i, v + 4, f"{v}", ha="center", fontsize=9)
    a2.set_title("gpt-oss-120b, 150 filings", fontsize=10, loc="left")
    fig.suptitle("Chart 5b. (superseded; see Chart 6)", x=0.01, ha="left", fontweight="bold")
    foot(fig, "Left: Sonnet 5, DeepSeek and gpt-oss-120b $ per 1,000 answers (563 answers each); the $150/hour reviewer is our assumption. Right: 150 filings (one run, 99.3% right, $0.26);\nthe 'one at a time' bar is 150 x 1.3 s median, an estimate, not a measured run.")
    fig.tight_layout(rect=(0, 0.1, 1, 0.92)); fig.savefig(out / "chart5b_superseded.png", dpi=170); plt.close(fig)

    # 6 threshold curves
    th = [0.5, 0.7, 0.8, 0.9, 0.95, 0.99]
    fig, ax = plt.subplots(figsize=(8.6, 5.2))
    table = {}
    for l in ORDER:
        sc = [r["score"] for r in by[l]]
        ys = [100 * sum(s >= t for s in sc) / len(sc) for t in th]
        table[l] = dict(zip(map(str, th), (round(v, 1) for v in ys)))
        ax.plot([int(t * 100) for t in th], ys, marker="o", color=COLOR[GROUP[l]], alpha=0.9 if l in ("sonnet5", "deepseek41_fw", "gptoss120_fw") else 0.45, lw=2 if l == "sonnet5" else 1.2)
        ax.annotate(SHORT[l], (99, ys[-1]), textcoords="offset points", xytext=(6, -3), fontsize=7.5)
    ax.axvline(90, color="grey", ls=":"); ax.set_xlabel("Bar for 'right': score at least this many percent"); ax.set_ylabel("Answers clearing the bar, %"); ax.set_xlim(48, 108)
    ax.set_title("Chart 10. Does the 90% line change the picture? Same data at 95% and 99% (appendix)", loc="left", fontweight="bold")
    foot(fig, "Sample: 563 answers per model. Dotted line = the 90% bar used elsewhere. Exact-or-nothing tasks (names, sector) do not move; partial-credit tasks do.")
    fig.tight_layout(rect=(0, 0.06, 1, 1)); fig.savefig(out / "chart10_thresholds.png", dpi=170); plt.close(fig)


    # 7 decision matrix (four questions + setup and upkeep). Data columns measured; setup/upkeep/data-rule columns are our judgment.
    cols = ["1. Right often\nenough?\n(overall right %)", "2. Cost of a mistake\n(invented numbers\nin 563)", "3. Fast enough?\n(median s; 95th pct s)", "Model cost\n($ per 1,000)", "4. May data go\nthere?", "Setup effort\n(our judgment)", "Upkeep effort\n(our judgment)"]
    rule = {"Frontier (closed)": ("Yes, existing approvals", "Low: done", "Low: vendor"), "Open, hosted": ("Public only, until vendor review", "Low: API key", "Low: vendor; review needed"),
            "Open, local": ("Yes, stays on our machine, after approval", "Medium: 7-16 GB download", "High: restart, update by hand")}
    lvl = {"Yes": 0, "Low": 0, "Medium": 1, "Public": 1, "High": 2}
    fig, ax = plt.subplots(figsize=(11.5, 5.8))
    ax.set_xlim(0, len(cols)); ax.set_ylim(len(ORDER), -1.9); ax.axis("off")
    for j, c in enumerate(cols):
        ax.text(j + 0.5, -0.95, c, ha="center", va="center", fontsize=8, fontweight="bold")
    green, amber, red = "#C6E0B4", "#FFE699", "#F4B183"
    for i, l in enumerate(ORDER):
        s = summ[l]; g = GROUP[l]
        right = s["right_pct"]; inv = s["invented"]; med, p95 = s["median_s"], s["p95_s"]
        vals = [(f"{right:.1f}", green if right >= 70 else amber if right >= 55 else red), (f"{inv}", green if inv == 0 else amber if inv <= 4 else red),
                (f"{med:.2f}; {p95:.1f}", green if p95 < 5 else amber if p95 < 20 else red), (f'{s["usd_per_1000"]:.2f}' if s["usd_per_1000"] else "0.00", green if s["usd_per_1000"] < 1 else amber if s["usd_per_1000"] < 5 else red),
                (rule[g][0], green if g != "Open, hosted" else amber), (rule[g][1], green if g != "Open, local" else amber), (rule[g][2], green if g == "Frontier (closed)" else amber if g == "Open, hosted" else red)]
        for j, (t, col) in enumerate(vals):
            ax.add_patch(plt.Rectangle((j, i - 0.5), 1, 1, facecolor=col, edgecolor="#555", lw=0.8))
            ax.text(j + 0.5, i, textwrap.fill(t, 22), ha="center", va="center", fontsize=7.5)
        ax.text(-0.05, i, SHORT[l], ha="right", va="center", fontsize=9)
    ax.set_title("Chart 7. The four questions, plus setup and upkeep, for each tested model", loc="left", fontweight="bold", x=-0.1)
    foot(fig, "Green = good, amber = watch, red = weak. Columns 1-4 cost and speed are measured on 563 answers per model; colour cut-offs are ours (right 70%+, no invented numbers, 95th percentile under 5 s, under $1 per 1,000).\nData rule, setup and upkeep are our judgment from the Models section, not measurements. Per task, see Chart 2 and the Outcome section.")
    fig.subplots_adjust(left=0.1, right=0.99, bottom=0.1, top=0.9); fig.savefig(out / "chart7_decision_matrix.png", dpi=170); plt.close(fig)

    # 8 monthly cost by volume
    vol = np.array([1e3, 1e4, 2e4, 5e4, 1e5, 1e6, 1e7])
    fig, ax = plt.subplots(figsize=(8.8, 5.3))
    for l, col, nm in (("sonnet5", "#1F4E79", "Sonnet 5"), ("deepseek41_fw", "#C55A11", "DeepSeek (hosted)"), ("gptoss120_fw", "#ED9B5C", "gpt-oss-120b (hosted)")):
        ax.plot(vol, vol / 1000 * summ[l]["usd_per_1000"], marker="o", color=col, label=nm)
    ax.plot(vol, np.full_like(vol, 900.0), color="#548235", marker="o", label="Local model: upkeep only (6 h x $150, assumed)")
    ax.plot(vol, np.full_like(vol, 5840.0), color="#7F7F7F", ls="--", label="Rented GPU, $8/hour (stays off)")
    ax.set_xscale("log"); ax.set_yscale("log"); ax.xaxis.set_major_formatter(PLAIN); ax.yaxis.set_major_formatter(PLAIN); ax.xaxis.set_minor_formatter(NullFormatter()); ax.yaxis.set_minor_formatter(NullFormatter()); ax.set_xlabel("Answers per month"); ax.set_ylabel("Dollars per month (model cost; local and GPU are fixed costs)"); ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.set_title("Chart 8. Monthly cost by volume", loc="left", fontweight="bold")
    foot(fig, "Hosted lines: measured average $ per 1,000 answers over 563 answers, list prices, straight-line (no volume discount, no rate-limit cost). Fixed lines are our assumptions, not bills.\nAccuracy is not equal across these options: see Charts 1 and 2.")
    fig.tight_layout(rect=(0, 0.07, 1, 1)); fig.savefig(out / "chart8_monthly_cost.png", dpi=170); plt.close(fig)

    # task-balanced average
    bal = {l: round(statistics.mean(tsum[l][t]["right_pct"] for t in TASKS), 1) for l in ORDER}
    extras = {"task_balanced_right_pct": bal, "threshold_table": table, "vote_test": vote_test(calls), "n_task": n_task}
    json.dump(extras, open(out / "extras.json", "w"), indent=1)
    print(json.dumps(extras, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
