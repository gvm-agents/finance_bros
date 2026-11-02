"""8-K triage harness, simulated on saved answers only: Python rules first, Muse Glimmer 30B for the rest, Inkling as tiebreak.

  python -m bench.harness_8k rules --set triage_8k_train             # rules alone on any set: coverage and precision, $0
  python -m bench.harness_8k sim --run triage-4 --answers base         # harness with the untrained Muse answers of a run
  python -m bench.harness_8k sim --run triage-4 --answers tuned        # same harness, trained answers swapped in
  python -m bench.harness_8k sim --run type-1 --answers tuned --set triage_8k

No model is called. Muse answers come from results/training/<run>/predictions_<answers>.jsonl (row order =
holdout_ids.json). Inkling answers come from a saved bench run (calls.jsonl, lane inkling_fw); filings with no saved
Inkling answer have no tiebreak, and the rule wins the dispute (counted as "no_tiebreak").

Steps per filing:
1. Rules: phrase rules learned on triage_8k_train only. A rule names one type. If rules name two different types, none fires.
2. Muse answer (saved).
3. Check: the type must be one of the 10 names; the priority is always set from the type (mismatches are counted).
4. Dispute: a firing rule disagrees with Muse, or Muse is invalid: take Inkling's saved answer, then the majority of rule,
   Muse and Inkling. With no majority the rule wins (rules fire only on clear cases); with no rule, Inkling wins.
Two routings are scored: "all" (Muse reads every filing, so disputes can be seen) and "skip" (a firing rule settles the
filing and Muse is not asked; only an invalid Muse answer goes to Inkling).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .scorecard import mcnemar
from .tasks import parse_json
from .triage import HIGH
from .triage_prompt import TYPES

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / "data" / "items"
TRAINING = ROOT / "results" / "training"
INKLING = ROOT / "results" / "runs" / "inkling-1102" / "calls.jsonl"
INKLING_LANE = "inkling_fw"
NAMES = set(TYPES.values())
OUT = {"base": ROOT / "experiments" / "05-8k-harness-no-training" / "results",
       "tuned": ROOT / "experiments" / "06-8k-harness-trained" / "results"}

# Each rule: (type, pattern). Learned on the 688 training filings; every rule is 100% precise there (see README).
# Some patterns match heading words that the set's cleaning step left in the text ("Listing Rule or Standard").
RULES = [  # narrative phrases only; no leftover item headings (e.g. "Departure of Directors", "Listing Rule or Standard")
    ("earnings", r"press release (announcing|reporting|regarding) (its |the Company.s )?(preliminary |final |unaudited )?(financial|operating|earnings)"),
    ("earnings", r"(announc|report)\w* (its |the Company.s )?(financial|operating) results for the (quarter|three months|fiscal)"),
    ("regulation_fd", r"^(?!.*financial results).*(furnish|pursuant to|in accordance with|purposes of|subject to)\W+(\w+\W+){0,4}Regulation FD\b"),
    ("regulation_fd", r"investor presentation"),
    ("delisting_notice", r"Listing Qualifications.{0,400}(not in compliance|deficien|notif|did not comply|no longer (meets|complies))"),
    ("delisting_notice", r"received a (written )?(deficiency )?(letter|notice|notification) from (the )?(Nasdaq|NYSE|New York Stock Exchange)"),
    ("leadership_change", r"\bresign"),
    ("leadership_change", r"\bwill (step down|retire)\b"),
    ("leadership_change", r"notified the (Company|Board).{0,80}(decision|intention) (to|not to)"),
    ("leadership_change", r"\b(appointed|elected|named|promoted)\b.{0,160}\b(as|to the position of|to serve as|to the Board|as a (member|director))\b.{0,40}(President|Chief|Officer|director|Director|Board)"),
    ("leadership_change", r"ceased (serving|to serve) as"),
    ("leadership_change", r"\bpassing of\b"),
    ("restatement", r"should no longer be relied upon"),
    ("bankruptcy", r"^(?!.*(Nasdaq|NYSE|listing)).*(chapter 11|voluntary petition)"),
    ("cyber_incident", r"(detected|identified|discovered|experienced) (a |an )?(cybersecurity incident|ransomware)"),
    ("acquisition_or_sale", r"completed (the|its) (previously announced )?(acquisition|sale|merger|disposition)"),
]
COMPILED = [(t, re.compile(p, re.I | re.S)) for t, p in RULES]


def rule(text: str) -> str | None:
    """The one type the rules agree on, or None."""
    hits = {t for t, rx in COMPILED if rx.search(text[:6000])}
    return hits.pop() if len(hits) == 1 else None


def prio(t: str) -> str:
    return "high" if t in HIGH else "normal"


def answer(reply: str) -> tuple[str | None, str | None]:
    """(type, priority) from a reply; type None when it is not one of the 10 names."""
    got = parse_json(reply)
    if not isinstance(got, dict):
        return None, None
    t = got.get("type")
    return (t if t in NAMES else None), got.get("priority")


def load(name: str) -> list[dict]:
    return [json.loads(l) for l in (ITEMS / f"{name}.jsonl").open()]


def muse(run: str, which: str, items: list[dict]) -> dict:
    d = TRAINING / run
    ids = json.loads((d / "holdout_ids.json").read_text())
    if ids != [i["id"] for i in items]:
        raise SystemExit(f"{d}/holdout_ids.json is not the order of this set")
    return {ids[r["index"]]: r["answer_text"] for r in map(json.loads, (d / f"predictions_{which}.jsonl").open())}


def inkling(path: Path, task: str) -> dict:
    if not path.exists():
        return {}
    return {c["item"]: c for c in map(json.loads, path.open()) if c["lane"] == INKLING_LANE and c["task"] == task}


def decide(r: str | None, m: str | None, ink: dict | None, routing: str) -> tuple[str | None, str]:
    """Final type and how it was reached."""
    if routing == "skip" and r:
        return r, "rule"
    if m and (r is None or r == m):
        return m, "rule+muse" if r else "muse"
    if ink is None:
        return (r, "no_tiebreak") if r else (None, "invalid")
    i = answer(ink["reply"])[0]
    votes = [v for v in (r, m, i) if v]
    for v in votes:
        if votes.count(v) >= 2:
            return v, "inkling_vote"
    return (r, "inkling_vote") if r else (i, "inkling")


def simulate(items: list[dict], answers: dict, inks: dict, routing: str) -> list[dict]:
    rows = []
    for it in items:
        k = it["key"]
        r = rule(it["text"])
        mt, mp = answer(answers[it["id"]])
        ink = inks.get(it["id"])
        t, how = decide(r, mt, ink, routing)
        used_ink = how in ("inkling_vote", "inkling")
        rows.append({"item": it["id"], "key_type": k["type"], "key_priority": k["priority"], "rule": r, "muse_type": mt, "muse_priority": mp,
                     "muse_asked": not (routing == "skip" and r), "muse_priority_fixed": bool(mt) and mp != prio(mt),
                     "inkling_type": answer(ink["reply"])[0] if used_ink else None, "inkling_usd": ink["usd"] if used_ink else 0.0,
                     "inkling_s": ink["seconds"] if used_ink else 0.0, "how": how, "type": t, "priority": prio(t) if t else None})
    return rows


def metrics(rows: list[dict], tkey: str = "type", pkey: str = "priority") -> dict:
    n = len(rows)
    return {"n": n, "type_right": sum(r[tkey] == r["key_type"] for r in rows),
            "urgent": sum(r["key_priority"] == "high" for r in rows),
            "urgent_caught": sum(r["key_priority"] == "high" and r[pkey] == "high" for r in rows),
            "false_alarms": sum(r["key_priority"] == "normal" and r[pkey] == "high" for r in rows),
            "invalid": sum(r[tkey] is None for r in rows)}


def harness_summary(rows: list[dict]) -> dict:
    n = len(rows)
    s = metrics(rows)
    ink = [r for r in rows if r["how"] in ("inkling_vote", "inkling")]
    usd = sum(r["inkling_usd"] for r in ink)
    s.update({"to_muse": sum(r["muse_asked"] for r in rows), "to_muse_pct": round(100 * sum(r["muse_asked"] for r in rows) / n, 1),
              "to_inkling": len(ink), "to_inkling_pct": round(100 * len(ink) / n, 1), "no_tiebreak": sum(r["how"] == "no_tiebreak" for r in rows),
              "rule_fired": sum(bool(r["rule"]) for r in rows), "muse_priority_fixed": sum(r["muse_priority_fixed"] and r["muse_asked"] for r in rows),
              "inkling_usd_total": round(usd, 6), "inkling_usd_per_1000_filings": round(1000 * usd / n, 4),
              "inkling_seconds_total": round(sum(r["inkling_s"] for r in rows), 2), "how": {h: sum(r["how"] == h for r in rows) for h in sorted({r["how"] for r in rows})}})
    return s


def rules_summary(items: list[dict]) -> dict:
    fired = [(rule(i["text"]), i["key"]["type"]) for i in items]
    per = {}
    for t, _ in RULES:
        got = [k for r, k in fired if r == t]
        per[t] = {"fired": len(got), "right": sum(k == t for k in got), "wrong_types": sorted({k for k in got if k != t})}
    f = [(r, k) for r, k in fired if r]
    return {"n": len(items), "fired": len(f), "coverage_pct": round(100 * len(f) / len(items), 1), "right": sum(r == k for r, k in f),
            "precision_pct": round(100 * sum(r == k for r, k in f) / max(len(f), 1), 1),
            "urgent_fired": sum(prio(k) == "high" for r, k in f), "per_rule": per}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rules")
    r.add_argument("--set", required=True)
    r.add_argument("--out", type=Path, default=OUT["base"])
    s = sub.add_parser("sim")
    s.add_argument("--run", required=True, help="folder under results/training, e.g. triage-4 or type-1")
    s.add_argument("--answers", choices=["base", "tuned"], required=True)
    s.add_argument("--set", default="triage_8k_fresh", help="the run's eval set (its holdout_ids.json must match)")
    s.add_argument("--inkling", type=Path, default=INKLING)
    s.add_argument("--out", type=Path)
    a = ap.parse_args()
    items = load(a.set)
    if a.cmd == "rules":
        a.out.mkdir(parents=True, exist_ok=True)
        res = rules_summary(items)
        with (a.out / f"rules-{a.set}.jsonl").open("w") as f:
            for i in items:
                f.write(json.dumps({"item": i["id"], "key_type": i["key"]["type"], "rule": rule(i["text"])}) + "\n")
        (a.out / f"rules-{a.set}.summary.json").write_text(json.dumps(res, indent=1))
        print(json.dumps(res, indent=1))
        return 0
    out = a.out or OUT[a.answers]
    out.mkdir(parents=True, exist_ok=True)
    answers, inks = muse(a.run, a.answers, items), inkling(a.inkling, a.set)
    name = f"{a.run}-{a.answers}-{a.set}"
    res = {"run": a.run, "answers": a.answers, "set": a.set, "inkling_answers": len(inks), "rules": rules_summary(items)}
    for routing in ("all", "skip"):
        rows = simulate(items, answers, inks, routing)
        with (out / f"{name}-{routing}.jsonl").open("w") as f:
            for x in rows:
                f.write(json.dumps(x) + "\n")
        if routing == "all":
            res["muse_alone"] = metrics(rows, "muse_type", "muse_priority")
            res["muse_alone"]["priority_not_matching_type"] = sum(x["muse_priority_fixed"] for x in rows)
            if inks:
                ik = [{"key_type": i["key"]["type"], "key_priority": i["key"]["priority"], "t": answer(inks[i["id"]]["reply"])[0],
                       "p": answer(inks[i["id"]]["reply"])[1]} for i in items if i["id"] in inks]
                res["inkling_alone"] = metrics(ik, "t", "p")
                res["inkling_alone"]["usd_per_1000"] = round(1000 * sum(inks[i]["usd"] for i in inks) / len(inks), 4)
        h = harness_summary(rows)
        b = sum(x["type"] == x["key_type"] != x["muse_type"] for x in rows)
        c = sum(x["muse_type"] == x["key_type"] != x["type"] for x in rows)
        h["vs_muse_alone"] = {"only_harness_right": b, "only_muse_right": c, "mcnemar_p": round(mcnemar(b, c), 4)}
        res[f"harness_{routing}"] = h
    (out / f"{name}.summary.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
