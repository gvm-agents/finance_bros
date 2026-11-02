"""Score a Forms LoRA training run's predictions with the same scorer every other model gets (bench.tasks.formd_score).

  python -m bench.train_forms_score --run forms-lora-1
Prints the mean score and invented numbers for the untrained and the trained model on the 120 test filings. Free.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import tasks

REPO = Path(__file__).resolve().parent.parent


def score(run_dir: Path, kind: str, items: dict) -> dict:
    ids = json.loads((run_dir / "holdout_ids.json").read_text())
    rows = [json.loads(l) for l in (run_dir / f"predictions_{kind}.jsonl").open()]
    out = []
    for r in rows:
        item = items[ids[r["index"]]]
        out.append(tasks.formd_score(item, r.get("answer_text") or ""))
    n = len(out)
    return {"model": kind, "n": n, "mean_score": round(sum(o["score"] for o in out) / n, 3) if n else None,
            "invented_per_100": round(100 * sum(o.get("invented", 0) for o in out) / n, 1) if n else None,
            "valid_pct": round(100 * sum(bool(o.get("valid")) for o in out) / n, 1) if n else None}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", type=Path, default=REPO / "results" / "training")
    a = ap.parse_args()
    items = {i["id"]: i for i in map(json.loads, (REPO / "data" / "items" / "formd_extract.jsonl").open())}
    for kind in ("base", "tuned"):
        print(json.dumps(score(a.out / a.run, kind, items)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
