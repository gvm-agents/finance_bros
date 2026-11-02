"""One table of every system on the 200 independent 8-K filings (triage_8k), built from saved answers only.

  python -m bench.compare_8k            # writes results/comparison-triage_8k/{comparison.json,README.md}

No model is called. Rows: frontier and ready-made open models (results/runs), untrained and trained models
(results/training), and the harness (bench.harness_8k, routing "skip") on top of each saved model.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

from . import harness_8k
from .tasks import parse_json

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "results" / "comparison-triage_8k"
SET = "triage_8k"
RUNS = [  # (label, group, run folder, lane)
    ("Claude Sonnet 5", "frontier", "frontier-1102-sonnet", "sonnet5_or"),
    ("GPT-5.6 Luna", "frontier", "frontier-1102-oa", "gpt56luna_none_oa"),
    ("DeepSeek V4.1 Flash", "open, ready-made", "frontier-1102", "deepseek41_fw_off"),
]
E = "experiments/"
TRAINED = [  # (label, group, training run, answers, saved harness summary from bench.harness_8k sim)
    ("GLM 5.3 Flash", "open, ready-made", "glm-type-1", "base", E + "07-8k-glm-trained/results/glm-type-1-base-triage_8k.summary.json"),
    ("gpt-oss-120b", "open, ready-made", "gptoss-base-triage_8k", "base", E + "07-8k-glm-trained/results/gptoss-base-triage_8k-base-triage_8k.summary.json"),
    ("Muse Glimmer 30B untrained (baseline)", "open, ready-made", "type-1", "base", E + "06-8k-harness-trained/results/type-1/sim-base/type-1-base-triage_8k.summary.json"),
    ("Muse Glimmer 30B trained (ours)", "open, trained", "type-1", "tuned", E + "06-8k-harness-trained/results/type-1/sim-tuned/type-1-tuned-triage_8k.summary.json"),
]


def score(items: list[dict], answers: dict[str, dict], usd: float | None, secs: list[float]) -> dict:
    key = {i["id"]: i["key"] for i in items}
    got = lambda i, f: (answers.get(i) or {}).get(f)
    urgent = [i for i in key if key[i]["priority"] == "high"]
    return {
        "type_right": sum(got(i, "type") == key[i]["type"] for i in key),
        "urgent_caught": sum(got(i, "priority") == "high" for i in urgent),
        "urgent_total": len(urgent),
        "false_alarms": sum(got(i, "priority") == "high" for i in key if key[i]["priority"] != "high"),
        "invalid": sum(not answers.get(i) for i in key),
        "usd_per_1000": None if usd is None else round(1000 * usd / len(key), 3),
        "p50_s": round(statistics.median(secs), 2) if secs else None,
    }


def main() -> int:
    items = harness_8k.load(SET)
    rows = []
    for label, group, run, lane in RUNS:
        calls = [json.loads(l) for l in (REPO / "results" / "runs" / run / "calls.jsonl").open()]
        calls = [c for c in calls if c["lane"] == lane and c["task"] == SET]
        ans = {c["item"]: parse_json(c.get("reply") or "") if isinstance(parse_json(c.get("reply") or ""), dict) else {} for c in calls}
        rows.append({"system": label, "group": group, "source": f"results/runs/{run}", **score(items, ans, sum(c.get("usd") or 0 for c in calls), [c.get("seconds") or 0 for c in calls])})
    for label, group, run, which, summary in TRAINED:
        d = REPO / "results" / "training" / run
        lines = [json.loads(l) for l in (d / f"predictions_{which}.jsonl").open()]
        ids = json.loads((d / "holdout_ids.json").read_text())
        ans = {i: (parse_json(r.get("answer_text") or "") if isinstance(parse_json(r.get("answer_text") or ""), dict) else {}) for i, r in zip(ids, lines)}
        has_usd = all("usd" in r for r in lines)
        base = score(items, ans, sum(r["usd"] for r in lines) if has_usd else None, [r["seconds"] for r in lines if "seconds" in r])
        rows.append({"system": label, "group": group, "source": f"results/training/{run}/predictions_{which}.jsonl", **base})
        h = json.loads((REPO / summary).read_text())["harness_skip"]
        if h:
            rows.append({"system": f"Harness + {label}", "group": group.replace("ready-made", "ready-made + harness").replace("trained", "trained + harness"),
                         "source": summary,
                         "type_right": h["type_right"], "urgent_caught": h["urgent_caught"], "urgent_total": base["urgent_total"],
                         "false_alarms": h["false_alarms"], "invalid": h["invalid"],
                         "usd_per_1000": None if base["usd_per_1000"] is None else round(base["usd_per_1000"] * h["to_muse_pct"] / 100, 3),
                         "p50_s": base["p50_s"], "read_by_model_pct": h["to_muse_pct"]})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "comparison.json").write_text(json.dumps({"set": SET, "filings": len(items), "rows": rows}, indent=1) + "\n")
    fmt = lambda v, suf="": "not measured" if v is None else f"{v}{suf}"
    md = ["# Every system on the same 200 independent 8-K filings", "",
          f"Set `{SET}`: 200 filings, {rows[0]['urgent_total']} urgent, none used for training or design. Same prompt (`bench/triage_prompt.py`) for every row. "
          "Answer key: the filing's own SEC item code, hidden from the model. Built by `python -m bench.compare_8k` from saved answers only.", "",
          "| System | Group | Event type right (of 200) | Urgent caught | False alarms | Invalid | $ per 1,000 | p50 s |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        md.append(f"| {r['system']} | {r['group']} | {r['type_right']} | {r['urgent_caught']} of {r['urgent_total']} | {r['false_alarms']} | {r['invalid']} | {fmt(r['usd_per_1000'])} | {fmt(r['p50_s'])} |")
    md += ["", "Harness rows: Python rules settle 44.5% of filings at $0; the model reads the rest, so its cost is scaled by the share it reads. "
           "Muse Glimmer runs on the Fireworks training sampler, so its price and speed per filing were not measured. "
           "Costs are tokens x list price, not checked against billing pages. Frontier runs: 2026-11-02, from this repo's lanes `sonnet5_or` (OpenRouter) and `gpt56luna_none_oa` (OpenAI)."]
    (OUT / "README.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
