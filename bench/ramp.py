"""Worker ramp: same items at rising worker counts until refusals pass 2%. Plots filings per second against workers.

  venv/bin/python -m bench.ramp --lane gptoss120_fw --task triage_8k --workers 6,12,24,48 --n 200 --max-usd 1 --out results/ramp-1101.jsonl
"""
from __future__ import annotations

import argparse
import json
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import collect, tasks
from .lanes import Caller, cost, load_lanes

STOP_PCT = 2.0


def step(lane: dict, prompt_fn, max_out: int, items: list[dict], workers: int) -> dict:
    call, lock, s = Caller(lane), threading.Lock(), {"refused": 0, "errors": 0, "usd": 0.0, "secs": []}

    def one(item):
        r = call(prompt_fn(item), max_out, item["id"])
        with lock:
            s["refused"] += r.retries
            s["errors"] += bool(r.error)
            s["usd"] += cost(lane, r.tokens_in, r.tokens_out)
            s["secs"].append(r.seconds)

    t0 = time.time()
    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(one, items))
    wall = time.time() - t0
    secs = sorted(s["secs"])
    return {"workers": workers, "items": len(items), "wall_s": round(wall, 1), "items_per_s": round(len(items) / wall, 2), "refused": s["refused"],
            "refused_pct": round(100 * s["refused"] / (len(items) + s["refused"]), 1), "errors": s["errors"], "usd": round(s["usd"], 4),
            "p50_s": round(secs[len(secs) // 2], 2), "p95_s": round(secs[int(0.95 * len(secs))], 2)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lane", required=True)
    ap.add_argument("--task", default="triage_8k")
    ap.add_argument("--items", default="", help="take items from this set instead of the task's own")
    ap.add_argument("--workers", default="6,12,24,48")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--max-usd", type=float, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    lane = load_lanes()[a.lane]
    prompt_fn, _, max_out = tasks.TASKS[a.task]
    items = collect.load(a.items or a.task)
    random.Random(9).shuffle(items)
    items, spent = items[: a.n], 0.0
    for w in map(int, a.workers.split(",")):
        if spent >= a.max_usd:
            print("STOPPED at the cap")
            break
        row = {"lane": a.lane, **step(lane, prompt_fn, max_out, items, w)}
        spent += row["usd"]
        print(row, flush=True)
        with a.out.open("a") as f:
            f.write(json.dumps(row) + "\n")
        if row["refused_pct"] > STOP_PCT:
            print(f"Refusals above {STOP_PCT}%: stopping the ramp at {w} workers")
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
