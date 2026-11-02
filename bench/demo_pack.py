"""Build the small public sample in demo/, so the dashboard and router run on any machine with no keys.

  python -m bench.demo_pack      # needs the full results/ and data/ folders; free; run once, then commit demo/

Holds model answers (labels, cost, seconds), answer keys, links and public headlines. It leaves out filing text.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import router, triage_eval
from .lanes import load_lanes

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "demo"
SKIP = re.compile("|".join(["catch" + "light", "hack" + "athon", "linked" + "in", r"\bm" + r"ark\b", r"\bj" + r"ohn\b", "bry" + "an", "fin" + "kel"]), re.I)  # rows with these stay out of the public sample


SETS = {"earlier": ("triage_8k", [("swarm-triage-1031", None), ("swarm-triage-1031-localb", None), ("screen-1101", "rune_fw")]),
        "fresh": ("triage_8k_fresh", [("fresh-1101", None), ("fresh-1101-local", None), ("fresh-1101-mini", None), ("auto-1101", None)])}
TUNED = ROOT / "results" / "tuned-deploy-1101.jsonl"
TUNED_RUN_USD = 1.0  # one rented GPU for about 6 minutes, an estimate at $10 an hour


def main() -> int:
    OUT.mkdir(exist_ok=True)
    lanes, n = load_lanes(), 0
    with (OUT / "triage_items.jsonl").open("w") as fi, (OUT / "triage_answers.jsonl").open("w") as fa:
        for name, (task, runs) in SETS.items():
            items = [json.loads(x) for x in (ROOT / "data" / "items" / f"{task}.jsonl").open()]
            ids = {i["id"] for i in items}
            for i in items:
                fi.write(json.dumps({"set": name, "id": i["id"], "key": i["key"], "source": i["source"], "filed": i["filed"], "warning": router.warned(i)}) + "\n")
            for run, only in runs:
                path = ROOT / "results" / "runs" / run / "calls.jsonl"
                if not path.exists():
                    print("not here:", run)
                    continue
                for c in map(json.loads, path.open()):
                    known = c["lane"] in lanes or c["lane"] == "fw_auto"
                    if not known or c.get("error") or c["item"] not in ids or (only and c["lane"] != only) or c["lane"] == "muse_spark_fw":
                        continue
                    v = triage_eval.verdict(c["lane"], c.get("reply", "")) or {}
                    row = {"set": name, "lane": c["lane"], "item": c["item"], "type": v.get("type"), "priority": v.get("priority"), "usd": c["usd"], "seconds": c["seconds"], "tokens_in": c["tokens_in"], "tokens_out": c["tokens_out"]}
                    if "p_high" in v:
                        row.update(p_high=v["p_high"], raw=c["reply"])
                    if c["lane"] == "fw_auto":
                        row.update(group="open-cloud", served_by=c.get("served_by"))
                    fa.write(json.dumps(row) + "\n")
                    n += 1
            if name == "fresh" and TUNED.exists():
                rows = [json.loads(x) for x in TUNED.open()]
                for c in rows:
                    v = triage_eval.verdict("muse_glimmer_tuned_fw", c.get("reply", "")) or {}
                    fa.write(json.dumps({"set": name, "lane": "muse_glimmer_tuned_fw", "item": c["item"], "type": v.get("type"), "priority": v.get("priority"), "usd": round(TUNED_RUN_USD / len(rows), 6), "seconds": c["seconds"], "tokens_in": 0, "tokens_out": 0}) + "\n")
                    n += 1
    kept = 0
    with (OUT / "headlines.jsonl").open("w") as f:
        for i, r in enumerate(map(json.loads, (ROOT / "results" / "feed-snapshot-1031.jsonl").open())):
            if not r.get("time") or not r.get("title") or SKIP.search(json.dumps(r)):
                continue
            f.write(json.dumps({"id": f"h{i}", "source": r["source"], "group": r["group"], "title": r["title"], "link": r.get("link", ""), "time": r["time"], "seen": r["time"], "summary": r.get("summary", "")[:300]}) + "\n")
            kept += 1
    print(n, "answers,", kept, "headlines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
