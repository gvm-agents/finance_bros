"""Rent one GPU for a trained model, answer filings through it, and always delete the deployment. Billed by the hour.

  venv/bin/python -m bench.deploy_tuned --model accounts/<account>/models/<id> --task triage_8k_fresh --n 181 --minutes 45 --out results/tuned-deploy.jsonl
The deployment is deleted when the run ends, on any error, and at --minutes at the latest. Check the Fireworks console afterwards.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import collect, tasks

API = "https://api.fireworks.ai/v1"
USD_PER_HOUR = 10.0  # rough H200 rate; check the console, the bill is by the second


def call(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + os.environ["FIREWORKS_API_KEY"], "Content-Type": "application/json", "User-Agent": "open-model-eval"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    return json.loads(raw) if raw else {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True)
    ap.add_argument("--task", default="triage_8k_fresh")
    ap.add_argument("--n", type=int, default=181)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--minutes", type=float, required=True, help="delete the deployment by this time at the latest")
    ap.add_argument("--shape", default="default")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    account = a.model.split("/")[1]
    t0, name = time.time(), ""
    limit = t0 + a.minutes * 60
    prompt_fn, score_fn, max_out = tasks.TASKS[a.task]
    try:
        d = call("POST", f"/accounts/{account}/deployments", {"baseModel": a.model, "deploymentShape": a.shape, "minReplicaCount": 1, "maxReplicaCount": 1,
                                                              "description": "evaluation, delete after use"})
        name = d["name"]
        print("created", name, flush=True)
        while True:
            d = call("GET", "/" + name)
            state = d.get("state")
            print(int(time.time() - t0), "s", state, (d.get("status") or {}).get("message", "")[:100], flush=True)
            if state == "READY":
                break
            if state in ("FAILED", "DELETED", "DELETING") or time.time() > limit - 300:
                raise SystemExit(f"not ready: {state}")
            time.sleep(20)
        ready = time.time() - t0
        from openai import OpenAI
        client = OpenAI(base_url="https://api.fireworks.ai/inference/v1", api_key=os.environ["FIREWORKS_API_KEY"])
        items = collect.load(a.task)
        random.Random(3).shuffle(items)

        def one(item):
            if time.time() > limit - 60:
                return None
            s = time.time()
            r = client.chat.completions.create(model=a.model + "#" + name, temperature=0, max_tokens=800, messages=[{"role": "user", "content": prompt_fn(item)}])
            text = r.choices[0].message.content or ""
            return {"item": item["id"], "reply": text, "seconds": round(time.time() - s, 2), **score_fn(item, text)}

        with ThreadPoolExecutor(a.workers) as pool, a.out.open("w") as f:
            for row in pool.map(one, items[: a.n]):
                if row:
                    f.write(json.dumps(row) + "\n")
                    f.flush()
        print("ready after", int(ready), "s; finished after", int(time.time() - t0), "s")
    finally:
        if name:
            call("DELETE", "/" + name + "?ignoreChecks=true")  # a plain delete is refused after recent requests
            gone = int(time.time() - t0)
            print("deleted", name, "after", gone, "s; rough cost $", round(gone / 3600 * USD_PER_HOUR, 2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
