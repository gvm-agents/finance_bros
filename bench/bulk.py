"""Fresh Form D filings for the scale test. Free; no model is called. Filings already in formd_extract are skipped.

  SEC_CONTACT="Name email" venv/bin/python -m bench.bulk --start 2026-10-01 --end 2026-10-30 --n 1000
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import collect

OUT = Path(__file__).resolve().parent.parent / "data" / "items" / "formd_bulk.jsonl"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--n", type=int, default=1000)
    a = ap.parse_args()
    seen = {i["id"] for i in collect.load("formd_extract")}
    rows = [dict(r, split="test") for r in collect.form_d_items(a.start, a.end, a.n + len(seen), print) if r["id"] not in seen][: a.n]
    with OUT.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(len(rows), "items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
