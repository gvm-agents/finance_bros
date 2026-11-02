"""Run a Fireworks router on the 8-K sets and save answers in the usual run format.

  python -m bench.auto_compare --model auto --run auto-1101 --sets triage_8k,triage_8k_fresh --max-usd 1 --workers 3
Comparison only: public filings, no tools, answers treated as untrusted text. Resumes from saved answers.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import collect, triage

URL = "https://api.fireworks.ai/inference/v1/chat/completions"


def call(model: str, text: str, max_tokens: int) -> dict:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": text}], "max_tokens": max_tokens}).encode()
    head = {"Authorization": "Bearer " + os.environ["FIREWORKS_API_KEY"], "Content-Type": "application/json", "User-Agent": "open-model-eval"}
    wait = 2.0
    for attempt in range(7):
        try:
            with urllib.request.urlopen(urllib.request.Request(URL, data=body, headers=head), timeout=120) as r:
                return {**json.load(r), "_refused": attempt}
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500:
                return {"_error": f"{e.code} {e.read()[:150]!r}", "_refused": attempt}
        except (TimeoutError, OSError):
            pass
        time.sleep(wait)
        wait = min(wait * 2, 30)
    return {"_error": "gave up after retries", "_refused": 7}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="auto")
    ap.add_argument("--run", required=True)
    ap.add_argument("--sets", default="triage_8k,triage_8k_fresh")
    ap.add_argument("--max-usd", type=float, required=True)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--max-tokens", type=int, default=4000)
    a = ap.parse_args()
    out = Path("results/runs") / a.run
    out.mkdir(parents=True, exist_ok=True)
    path = out / "calls.jsonl"
    done = {(r["task"], r["item"]) for r in map(json.loads, path.open())} if path.exists() else set()
    spent = sum(r["usd"] for r in map(json.loads, path.open())) if path.exists() else 0.0
    lock = threading.Lock()
    todo = [(s, i) for s in a.sets.split(",") for i in collect.load(s, None) if (s, i["id"]) not in done]

    def one(job):
        nonlocal spent
        s, item = job
        with lock:
            if spent >= a.max_usd:
                return
        t = time.time()
        j = call(a.model, triage.prompt(item), a.max_tokens)
        u = j.get("usage") or {}
        reply = ((j.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        row = {"lane": "fw_" + a.model.replace("/", "_"), "task": s, "item": item["id"], "served_by": j.get("model"), "seconds": round(time.time() - t, 3),
               "tokens_in": u.get("prompt_tokens", 0), "tokens_out": u.get("completion_tokens", 0), "usd": u.get("cost") or 0.0,
               "error": j.get("_error", ""), "refused": j.get("_refused", 0), "reply": reply, **triage.score(item, reply), "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        with lock:
            spent += row["usd"]
            with path.open("a") as f:
                f.write(json.dumps(row) + "\n")

    with ThreadPoolExecutor(a.workers) as pool:
        list(pool.map(one, todo))
    rows = [json.loads(l) for l in path.open()]
    print(len(rows), "answers; $", round(spent, 4), "; served by", collections.Counter(r["served_by"] for r in rows), "; errors", sum(bool(r["error"]) for r in rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
