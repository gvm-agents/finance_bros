"""Work out the CCO Test routing result from saved replies. No model is called.

An open model answers first. A Python gate that never sees the answer key checks that the
reply parses, every required field is filled, and every number appears in the source. A
failed answer falls back to Claude. An answer that fails both gates needs a close human
look. The answer key is used only afterwards, to count wrong answers the gate let through.

Cost per signed-off answer = model cost + retry cost + close-look share x minutes x $150/hour.
Review minutes are an assumption, shown at 0.5, 1 and 3.
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from . import collect, tasks

HOUR_USD = 150
MINUTES = (0.5, 1, 3)
GOOD = 0.9  # score at or above this counts as a right answer
REQUIRED = {"formd_extract": ("issuer_name", "industry_group", "total_offering_amount"),
            "longdoc": ("revenue", "total_assets"), "adv_extract": ("total_employees", "aum_total")}


def rescore(calls: list[dict]) -> dict[tuple, dict]:
    """(lane, task, item) -> saved reply scored with the current scorer."""
    items = {t: {i["id"]: i for i in collect.load(t, "test")} for t in tasks.TASKS}
    out = {}
    for c in calls:
        item = items[c["task"]].get(c["item"])
        if item is None:
            continue
        s = tasks.TASKS[c["task"]][1](item, c.get("reply") or "") if not c.get("error") else \
            {"score": 0.0, "valid": False, "invented": 0}
        got = tasks.parse_json(c.get("reply") or "")
        filled = not isinstance(got, dict) or all(got.get(f) is not None for f in REQUIRED.get(c["task"], ()))
        out[(c["lane"], c["task"], c["item"])] = {**c, **s, "gate": bool(s["valid"]) and not s["invented"] and filled}
    return out


def strategy(rows: list[dict]) -> dict:
    """rows: one dict per item with cost, close (bool), right (bool), passed (bool)."""
    n = len(rows)
    out = {"n": n, "close_look_pct": round(100 * sum(r["close"] for r in rows) / n, 1),
           "wrong_passed_pct": round(100 * sum(r["passed"] and not r["right"] for r in rows) / n, 1),
           "right_pct": round(100 * sum(r["right"] for r in rows) / n, 1),
           "invented_passed": sum(r.get("invented", 0) for r in rows if r["passed"]),
           "model_usd_per_answer": round(statistics.mean(r["cost"] for r in rows), 6)}
    for m in MINUTES:
        out[f"usd_at_{m}_min"] = round(out["model_usd_per_answer"] + out["close_look_pct"] / 100 * m / 60 * HOUR_USD, 4)
    return out


def price_as(c: dict, price: tuple[float, float] | None) -> float:
    if price is None:
        return c["usd"]
    return (c["tokens_in"] * price[0] + c["tokens_out"] * price[1]) / 1e6


def compare(scored: dict, first: str, fallback: str, task: str, price=None) -> dict:
    keys = [k for k in scored if k[0] == first and k[1] == task and (fallback, task, k[2]) in scored]
    alone, claude, routed = [], [], []
    for k in keys:
        a, b = scored[k], scored[(fallback, task, k[2])]
        ca = price_as(a, price)
        alone.append({"cost": ca, "close": not a["gate"], "passed": a["gate"], "right": a["score"] >= GOOD,
                      "invented": a["invented"]})
        claude.append({"cost": b["usd"], "close": not b["gate"], "passed": b["gate"], "right": b["score"] >= GOOD,
                       "invented": b["invented"]})
        use = a if a["gate"] else b
        routed.append({"cost": ca + (0 if a["gate"] else b["usd"]), "close": not use["gate"], "passed": use["gate"],
                       "right": use["score"] >= GOOD, "invented": use["invented"]})
    if not keys:
        return {}
    return {"task": task, "first": first, "fallback": fallback,
            "fallback_pct": round(100 * sum(not scored[k]["gate"] for k in keys) / len(keys), 1),
            "open_alone": strategy(alone), "claude_alone": strategy(claude), "routed": strategy(routed)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--calls", nargs="+", required=True, help="calls.jsonl files")
    ap.add_argument("--first", default="gemma4_e2b_local")
    ap.add_argument("--fallback", default="sonnet5")
    ap.add_argument("--price-as", help="in,out per million tokens: price the first lane as if on a paid model")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    calls = [json.loads(l) for f in a.calls for l in Path(f).open()]
    scored = rescore(calls)
    price = tuple(float(x) for x in a.price_as.split(",")) if a.price_as else None
    rows = [r for t in tasks.TASKS if (r := compare(scored, a.first, a.fallback, t, price))]
    for r in rows:
        print(f"{r['task']:14} n={r['open_alone']['n']:3} fallback {r['fallback_pct']:5}%")
        for s in ("claude_alone", "open_alone", "routed"):
            x = r[s]
            print(f"   {s:13} right {x['right_pct']:5}%  close look {x['close_look_pct']:5}%  wrong passed {x['wrong_passed_pct']:5}%"
                  f"  invented passed {x['invented_passed']:3}  ${x['usd_at_0.5_min']:.4f} / ${x['usd_at_1_min']:.4f} / ${x['usd_at_3_min']:.4f}")
    if a.out:
        a.out.write_text(json.dumps(rows, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
