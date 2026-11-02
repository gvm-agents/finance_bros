"""Score 8-K triage runs: accuracy, recall and precision on high-priority items, cost, speed. Python only; no model is called.

  venv/bin/python -m bench.triage_eval --runs swarm-triage-1031,screen-1101 --task triage_8k
Also works out cascades from saved answers: a first reader sees everything; items it is unsure about go to a second reader.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

from . import collect, tasks, triage, triage_rune

RUNS = Path(__file__).resolve().parent.parent / "results" / "runs"


def verdict(lane: str, reply: str) -> dict | None:
    """Reply -> {"type", "priority", "p_high"(optional)}."""
    if lane.startswith("rune"):
        return triage_rune.parse(reply)
    got = tasks.parse_json(reply or "")
    return got if isinstance(got, dict) and got.get("priority") in ("high", "normal") else None


def load(runs: list[str], task_names: list[str]) -> dict[str, dict[str, dict]]:
    """lane -> item id -> call."""
    out: dict[str, dict[str, dict]] = {}
    for run in runs:
        path = RUNS / run / "calls.jsonl"
        if not path.exists():
            continue
        for c in map(json.loads, path.open()):
            if c["task"] in task_names and not c.get("error"):
                c["v"] = verdict(c["lane"], c.get("reply", ""))
                out.setdefault(c["lane"], {})[c["item"]] = c
    return out


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return (0.0, 0.0)
    p, d = k / n, 1 + z * z / n
    c, h = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(100 * (c - h), 1), round(100 * (c + h), 1))


def metrics(flags: dict[str, bool], key: dict[str, dict]) -> dict:
    """flags: item id -> did we flag it high."""
    ids = [i for i in flags if i in key]
    pos = [i for i in ids if key[i]["priority"] == "high"]
    tp, fp = sum(flags[i] for i in pos), sum(flags[i] for i in ids if key[i]["priority"] != "high")
    rec, prec = tp / len(pos) if pos else 0, tp / (tp + fp) if tp + fp else 0
    return {"n": len(ids), "high": len(pos), "caught": tp, "false_alarms": fp, "recall": round(100 * rec, 1), "recall_95": wilson(tp, len(pos)),
            "precision": round(100 * prec, 1), "f1": round(100 * 2 * prec * rec / (prec + rec), 1) if prec + rec else 0,
            "priority_acc": round(100 * sum(flags[i] == (key[i]["priority"] == "high") for i in ids) / len(ids), 1) if ids else 0}


def table(calls: dict, key: dict) -> list[dict]:
    rows = []
    for lane, cs in calls.items():
        ok = {i: c for i, c in cs.items() if i in key}
        if not ok:
            continue
        flags = {i: bool(c["v"]) and c["v"]["priority"] == "high" for i, c in ok.items()}
        m = metrics(flags, key)
        m.update(lane=lane, valid=sum(bool(c["v"]) for c in ok.values()),
                 type_acc=round(100 * sum(bool(c["v"]) and c["v"].get("type") == key[i]["type"] for i, c in ok.items()) / len(ok), 1),
                 usd_per_1000=round(1000 * statistics.mean(c["usd"] for c in ok.values()), 3),
                 p50_s=round(statistics.median(c["seconds"] for c in ok.values()), 2))
        rows.append(m)
    return sorted(rows, key=lambda r: (-r["recall"], r["usd_per_1000"]))


def cascade(first: dict, second: dict, key: dict, low: float, high: float = 1.1) -> dict:
    """Rune first on every item. p_high >= high: flagged, done. p_high < low: normal, done. Between: the second reader decides."""
    flags, usd, up = {}, 0.0, 0
    for i, c in first.items():
        if i not in key or i not in second or not c["v"]:
            continue
        p = c["v"]["p_high"]
        usd += c["usd"]
        if p >= high:
            flags[i] = True
        elif p < low:
            flags[i] = False
        else:
            up += 1
            usd += second[i]["usd"]
            v = second[i]["v"]
            flags[i] = bool(v) and v["priority"] == "high" or p >= 0.5
    m = metrics(flags, key)
    m.update(low=low, sent_up_pct=round(100 * up / len(flags), 1) if flags else 0, usd_per_1000=round(1000 * usd / len(flags), 3) if flags else 0)
    return m


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", required=True)
    ap.add_argument("--task", default="triage_8k")
    ap.add_argument("--first", default="rune_fw")
    ap.add_argument("--second", default="")
    a = ap.parse_args()
    key = {i["id"]: i["key"] for i in collect.load(a.task)}
    calls = load(a.runs.split(","), [a.task, a.task + "_rune", "triage_8k_s60"])
    cols = ["lane", "n", "valid", "high", "caught", "recall", "recall_95", "precision", "false_alarms", "f1", "priority_acc", "type_acc", "usd_per_1000", "p50_s"]
    print(" | ".join(cols))
    for r in table(calls, key):
        print(" | ".join(str(r[c]) for c in cols))
    if a.second:
        print("\nCascade: first", a.first)
        for s in a.second.split(","):
            for high in (1.1, 0.95, 0.8):
                for low in (0.005, 0.02, 0.1):
                    m = cascade(calls[a.first], calls[s], key, low, high)
                    print(s, {"sure_high": high, **{k: m[k] for k in ("low", "sent_up_pct", "caught", "high", "recall", "precision", "false_alarms", "usd_per_1000")}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
