"""Per-task scorecard from saved replies. No model is called.

Right = score of 0.9 or more, re-scored with the current scorer. Each lane is compared with
Claude Sonnet 5 on the same items: a Wilson 95% interval for the right rate, and an exact
McNemar test, which looks only at items where one was right and the other wrong.
"""
from __future__ import annotations

import collections
import json
import math
import statistics
import sys

from . import route_sim, tasks

RUNS = ("baseline-1030", "gptoss-1030", "nemotron-1030", "deepseek-1030", "local-1030b")
REFERENCE = "sonnet5"
LABELS = {"sonnet5": "Claude Sonnet 5", "opus48": "Claude Opus 4.8", "haiku45": "Claude Haiku 4.5", "gptoss120_fw": "gpt-oss-120b",
          "deepseek41_fw": "DeepSeek V4.1 Flash", "nemotron35_fw": "Nemotron 3.5 Lightning", "gemma4_26b_local": "Gemma 4 26B",
          "gemma4_12b_local": "Gemma 4 12B", "gemma4_e2b_local": "Gemma 4 E2B"}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p, d = k / n, 1 + z * z / n
    mid, half = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(100 * (mid - half), 1), round(100 * (mid + half), 1)


def mcnemar(b: int, c: int) -> float:
    """Exact two-sided p value from the b and c discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def percentile(v: list[float], q: float) -> float:
    s = sorted(v)
    return s[min(len(s) - 1, int(q * len(s)))]


def summary(rows: list[dict], ref: dict[tuple, dict]) -> dict:
    n = len(rows)
    right = sum(r["score"] >= route_sim.GOOD for r in rows)
    pairs = [(r["score"] >= route_sim.GOOD, ref[(r["task"], r["item"])]["score"] >= route_sim.GOOD) for r in rows if (r["task"], r["item"]) in ref]
    b = sum(a and not x for a, x in pairs)
    c = sum(x and not a for a, x in pairs)
    return {"n": n, "right_pct": round(100 * right / n, 1), "ci": wilson(right, n), "mean_score": round(statistics.mean(r["score"] for r in rows), 3),
            "invented": sum(bool(r["invented"]) for r in rows), "errors": sum(bool(r.get("error")) for r in rows), "open_better": b, "sonnet_better": c, "p": round(mcnemar(b, c), 4),
            "median_s": round(statistics.median(r["seconds"] for r in rows), 2), "p95_s": round(percentile([r["seconds"] for r in rows], 0.95), 2),
            "tokens_per_s": round(sum(r["tokens_out"] for r in rows) / max(sum(r["seconds"] for r in rows), 0.001)), "in_tokens": round(statistics.mean(r["tokens_in"] for r in rows)),
            "out_tokens": round(statistics.mean(r["tokens_out"] for r in rows)), "usd_per_1000": round(1000 * sum(r["usd"] for r in rows) / n, 2)}


def main() -> int:
    calls = [json.loads(l) for run in RUNS for l in open(f"results/runs/{run}/calls.jsonl")]
    scored = route_sim.rescore(calls)
    by = collections.defaultdict(list)
    for (lane, _, _), row in scored.items():
        by[lane].append(row)
    ref = {(r["task"], r["item"]): r for r in by[REFERENCE]}
    out = {}
    for lane, rows in by.items():
        out[lane] = {"label": LABELS.get(lane, lane), "all": summary(rows, ref), "tasks": {t: summary([r for r in rows if r["task"] == t], ref) for t in tasks.TASKS if any(r["task"] == t for r in rows)}}
    json.dump(out, open(sys.argv[1], "w"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
