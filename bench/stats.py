"""Is the gain real? Two tests on the same filings, as the judges' sample asks: McNemar and a cluster bootstrap.

  python -m bench.stats --set triage_8k_final99 --before run:frontier-final99:sonnet5 --after run:final-system
  python -m bench.stats --set triage_8k_final99 --before run:base-final99 --after file:results/tuned-final.jsonl

A system is one of:
  run:<run>          a router run (answers.jsonl) in results/runs
  run:<run>:<lane>   one model in a `bench run` run (calls.jsonl)
  file:<path>        a jsonl of {"item", "reply"} rows, as bench.deploy_tuned writes
Right or wrong per filing = the urgent/routine call matches the SEC item code. McNemar counts the filings where exactly one
system is right. The bootstrap redraws whole companies (all of a company's filings move together, because they look
alike), 5,000 times, and reports the middle 95% of each gap. Call a gain real only when both agree. Free; no model calls.
"""
from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

from . import collect, coordinator as co
from .lanes import load_lanes
from .router import read
from .scorecard import mcnemar

ROOT = Path(__file__).resolve().parent.parent


def preds(spec: str) -> dict[str, str]:
    kind, _, rest = spec.partition(":")
    if kind == "file":
        return {r["item"]: (read(r.get("reply") or "", None)["priority"] or "normal") for r in map(json.loads, Path(rest).open())}
    run, _, lane = rest.partition(":")
    d = co.RUNS / run
    if (d / "answers.jsonl").exists():
        return {a["id"]: a.get("final") or "normal" for a in map(json.loads, (d / "answers.jsonl").open())}
    lanes = load_lanes()
    out = {}
    for c in map(json.loads, (d / "calls.jsonl").open()):
        if c.get("task", "").startswith("triage_8k") and (not lane or c["lane"] == lane):
            out[c["item"]] = read(c.get("reply") or "", lanes.get(c["lane"]))["priority"] or "normal"
    return out


def company(item: dict) -> str:
    m = re.search(r"/data/(\d+)/", item.get("source", ""))
    return m.group(1) if m else item["id"]


def counts(rows: list[tuple[str, str, str]]) -> dict:
    """rows: (key, before, after). Returns right, caught and false-alarm counts for both systems."""
    out = {}
    for name, j in (("before", 1), ("after", 2)):
        out[name] = {"right": sum(r[j] == r[0] for r in rows), "caught": sum(r[j] == "high" == r[0] for r in rows),
                     "false_alarms": sum(r[j] == "high" != r[0] for r in rows)}
    out["urgent"] = sum(r[0] == "high" for r in rows)
    return out


def compare(task: str, before: str, after: str, reps: int = 5000, seed: int = 7) -> dict:
    items = {i["id"]: i for i in collect.load(task)}
    b, a = preds(before), preds(after)
    ids = [i for i in items if i in b and i in a]
    rows = {i: (items[i]["key"]["priority"], b[i], a[i]) for i in ids}
    c = counts(list(rows.values()))
    only_after = sum(r[2] == r[0] != r[1] for r in rows.values())
    only_before = sum(r[1] == r[0] != r[2] for r in rows.values())
    groups: dict[str, list[str]] = {}
    for i in ids:
        groups.setdefault(company(items[i]), []).append(i)
    keys, rng = list(groups), random.Random(seed)
    gaps = {"right": [], "caught": [], "false_alarms": []}
    for _ in range(reps):
        sample = [rows[i] for g in (rng.choice(keys) for _ in keys) for i in groups[g]]
        s = counts(sample)
        n, urgent = len(sample), s["urgent"] or 1
        gaps["right"].append(100 * (s["after"]["right"] - s["before"]["right"]) / n)
        gaps["caught"].append(100 * (s["after"]["caught"] - s["before"]["caught"]) / urgent)
        gaps["false_alarms"].append(s["after"]["false_alarms"] - s["before"]["false_alarms"])
    ci = {k: (round(sorted(v)[int(0.025 * reps)], 2), round(sorted(v)[int(0.975 * reps) - 1], 2)) for k, v in gaps.items()}
    p = mcnemar(only_after, only_before)
    n = len(ids)
    return {"set": task, "n": n, "companies": len(keys), "urgent": c["urgent"], "before": before, "after": after,
            "before_counts": c["before"], "after_counts": c["after"],
            "accuracy_before": round(100 * c["before"]["right"] / n, 1), "accuracy_after": round(100 * c["after"]["right"] / n, 1),
            "only_after_right": only_after, "only_before_right": only_before, "mcnemar_p": p,
            "bootstrap_95": {"accuracy_points": ci["right"], "catch_rate_points": ci["caught"], "false_alarm_change": ci["false_alarms"]},
            "real_gain": p < 0.05 and ci["right"][0] > 0}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", required=True, help="item set in data/items, e.g. triage_8k_final99")
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--reps", type=int, default=5000)
    a = ap.parse_args()
    r = compare(a.set, a.before, a.after, a.reps)
    print(json.dumps(r, indent=1))
    out = ROOT / "results" / "stats.jsonl"
    with out.open("a") as f:
        f.write(json.dumps(r) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
