"""Acceptance test: run before any benchmark you will quote. Free, local, no model called.

  venv/bin/python -m bench.acceptance
Each line is PASS, REVIEW (a person must look) or FAIL (fix before quoting numbers).
Checks: item counts, answer keys against their source text, scorer self-test (the key must score 1.0),
keys the models disagree with (consensus audit), API error rate per run, and the spend cap.
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

from . import tasks

NEED = {"formd_extract": 30, "name_match": 60, "sector": 30, "snapshot": 30, "format_table": 30, "longdoc": 30, "adv_extract": 30}
BASE_RUNS = ("baseline-1030", "gptoss-1030", "nemotron-1030", "deepseek-1030", "local-1030b")
out: list[tuple[str, str, str]] = []


def add(status, name, detail):
    out.append((status, name, detail))


def load(t):
    return [json.loads(l) for l in open(f"data/items/{t}.jsonl")]


def main() -> int:
    items = {t: load(t) for t in NEED}
    for t, need in NEED.items():
        n = sum(1 for i in items[t] if i.get("split") == "test")
        add("PASS" if n >= need else "FAIL", f"held-back items: {t}", f"{n} test items (need {need})")
    # ADV key against the filing: label-proximate employee counts
    bad = []
    for it in items["adv_extract"]:
        m = re.search(r"Approximately how many employees do you have\?[^\n]*\n\s*([\d,]+)", it["text"])
        b = re.search(r"perform investment advisory functions \(including research\)\?\s*\n\s*([\d,]+)", it["text"])
        if m and int(m.group(1).replace(",", "")) != it["key"]["total_employees"]:
            bad.append((it["id"], "5.A", m.group(1), it["key"]["total_employees"]))
        if b and int(b.group(1).replace(",", "")) != it["key"]["advisory_employees"]:
            bad.append((it["id"], "5.B(1)", b.group(1), it["key"]["advisory_employees"]))
    add("PASS" if not bad else "FAIL", "Form ADV keys match the filing text (employee counts, read next to their question)", f"{len(items['adv_extract'])} filings checked, {len(bad)} mismatches {bad[:3]}")
    # every numeric ADV key number appears in the text
    miss = [it["id"] for it in items["adv_extract"] if any(str(it["key"][f]) not in re.sub(r",", "", it["text"]) for f in ("aum_discretionary", "aum_non_discretionary", "aum_total", "accounts_total") if it["key"].get(f) not in (None, ""))]
    add("PASS" if not miss else "REVIEW", "Form ADV money and account keys appear in the filing", f"{len(miss)} filings with a key number not found in the text")
    # Form D key placeholders
    ph = sum(1 for it in items["formd_extract"] for p in it["key"].get("related_persons", []) if re.search(r"(^|\s)n/a(\s|$)", p["name"].lower()))
    add("REVIEW" if ph else "PASS", "Form D key person names free of placeholders (N/A)", f"{ph} person names carry a placeholder; the scorer now ignores it (scorer v2)")
    # scorer self-test
    def perfect(t, it):
        k = it["key"]
        if t == "formd_extract": return json.dumps(k)
        if t == "adv_extract": return json.dumps(k)
        if t == "name_match": return json.dumps({"same": k["same"]})
        if t == "sector": return json.dumps({"division": k["division"]})
        if t == "longdoc": return json.dumps({q: k[q] for q in k})
    fails = collections.Counter()
    for t in ("formd_extract", "adv_extract", "name_match", "sector", "longdoc"):
        for it in items[t]:
            if tasks.TASKS[t][1](it, perfect(t, it))["score"] < 0.999:
                fails[t] += 1
    add("PASS" if not fails else "FAIL", "Scorer self-test: the answer key, given back as a reply, scores 1.0", f"failures by task: {dict(fails) or 'none'}")
    # consensus audit
    calls = [json.loads(l) for r in BASE_RUNS for l in open(f"results/runs/{r}/calls.jsonl")]
    idx = {(t, i["id"]): i for t in items for i in items[t]}
    wrong = collections.defaultdict(set)
    seen = collections.defaultdict(set)
    for c in calls:
        it = idx.get((c["task"], c["item"]))
        if it is None or c["task"] in ("snapshot", "format_table") or c["error"]:
            continue
        sc = tasks.TASKS[c["task"]][1](it, c["reply"])["score"]
        seen[(c["task"], c["item"])].add(c["lane"])
        if sc < 0.9:
            wrong[(c["task"], c["item"])].add(c["lane"])
    sus = [k for k, v in wrong.items() if len(v) >= 7 and len(seen[k]) >= 8]
    by_task = collections.Counter(k[0] for k in sus)
    add("PASS" if not sus else "REVIEW", "Consensus audit: items where 7+ of 9 models disagree with the key", f"{len(sus)} items to read against the source {dict(by_task)}; examples {[k[1] for k in sus[:4]]}")
    # API error rate in the final runs
    for r in sorted(Path("results/runs").iterdir()):
        if r.name.endswith("-rescored"):
            continue
        f = r / "calls.jsonl"
        if not f.exists():
            continue
        rows = [json.loads(l) for l in open(f)]
        e = sum(bool(x.get("error")) for x in rows)
        if rows and e / len(rows) > 0.05:
            add("REVIEW", f"API error rate in run {r.name}", f"{e} of {len(rows)} calls failed ({100*e/len(rows):.0f}%): rate limits or cut-offs; do not quote these rows (thinking-1031-open rows for the three re-run lanes are superseded by thinking-1031-rerun)")
    cap = json.load(open("spend_cap.json"))["total_usd"]
    spent = sum(x.get("usd", 0) for r in Path("results/runs").glob("*/calls.jsonl") if not r.parent.name.endswith("-rescored") and not (r.parent / "SUPERSEDED_BY").exists() for x in map(json.loads, open(r)))
    spent += sum(x.get("usd", 0) for x in json.load(open("spend_cap.json")).get("other_spend", []))
    add("PASS" if spent <= cap else "FAIL", "Spend within the total cap", f"${spent:.2f} on saved runs (cap ${cap}); injection and version tests are in spend_cap.json other_spend")
    w = max(len(o[1]) for o in out)
    for s, n, d in out:
        print(f"{s:7s} {n:{w}s}  {d}")
    return 1 if any(o[0] == "FAIL" for o in out) else 0


if __name__ == "__main__":
    raise SystemExit(main())
