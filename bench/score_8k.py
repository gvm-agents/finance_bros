"""Score one lane on an 8-K set with the training prompt, and save the answers in the format bench.harness_8k reads.

  venv/bin/python -m bench.score_8k --lane glm53flash_fw --set triage_8k --out results/training/glm-type-1/predictions_base.jsonl
  venv/bin/python -m bench.score_8k --lane glm53flash_fw --model accounts/<account>/models/<id> --set triage_8k --out .../predictions_tuned.jsonl
Same prompt as training (bench/triage_prompt.py, text[:6000]). Writes holdout_ids.json (the set's ids in file order) next to --out.
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .lanes import Caller, cost, load_lanes
from .tasks import parse_json
from .triage_prompt import prompt

ITEMS = Path(__file__).resolve().parent.parent / "data" / "items"
TEXT_LIMIT = 6000


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lane", required=True)
    ap.add_argument("--model", help="call this model instead of the lane's (a trained LoRA); the lane's price is used")
    ap.add_argument("--set", default="triage_8k")
    ap.add_argument("--max-out", type=int, default=60)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    lane = load_lanes()[a.lane]
    if a.model:
        lane = {**lane, "model": a.model}
    items = [json.loads(l) for l in (ITEMS / f"{a.set}.jsonl").open()]
    call = Caller(lane)

    def one(i: int) -> dict:
        it = items[i]
        r = call(prompt({"text": it["text"][:TEXT_LIMIT]}), a.max_out, it["id"])
        gold = {"type": it["key"]["type"], "priority": it["key"]["priority"]}
        got = parse_json(r.text)
        got = got if isinstance(got, dict) else {}
        fields = {k: got.get(k) == v for k, v in gold.items()}
        return {"index": i, "gold": json.dumps(gold), "exact": all(fields.values()), "fields": fields, "truncated": not got,
                "answer_text": r.text, "seconds": round(r.seconds, 3), "tokens_in": r.tokens_in, "tokens_out": r.tokens_out,
                "usd": round(cost(lane, r.tokens_in, r.tokens_out), 7), "error": r.error, "model": lane["model"]}

    with ThreadPoolExecutor(a.workers) as pool:
        rows = list(pool.map(one, range(len(items))))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    (a.out.parent / "holdout_ids.json").write_text(json.dumps([i["id"] for i in items]))
    n = len(rows)
    print(json.dumps({"n": n, "type_right": sum(r["fields"]["type"] for r in rows), "priority_right": sum(r["fields"]["priority"] for r in rows),
                      "unparsed": sum(r["truncated"] for r in rows), "errors": sum(bool(r["error"]) for r in rows),
                      "usd": round(sum(r["usd"] for r in rows), 4)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
