"""Version-sorting test on public SEC filings: which of two versions of the same filing is the newer one?

Stand-in for document-registry version sorting. SEC records the truth: an original Form D and a later amendment (D/A)
from the same issuer, each with a filing date. Python builds the key from SEC's filing index, never from a model.

Two modes per pair, to separate "reads the content" from "trusts the file name":
  neutral  - files called Document A and Document B.
  trap     - the OLDER file is named like a final version, the NEWER like a draft (misleading names; the content still tells the truth).

  collect: SEC_CONTACT="Name email" venv/bin/python -m bench.versions collect --n 40
  run:     venv/bin/python -m bench.versions run --lanes sonnet5,haiku45 --max-usd 1 --out results/versions-1031
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import random
import re
from pathlib import Path

from . import lanes as L
from . import sec, tasks

ITEMS = Path("data/items/versions.jsonl")


def pairs_for(cik: str) -> list[tuple[dict, dict]]:
    sub = sec.submissions(cik)
    r = sub.get("filings", {}).get("recent", {})
    rows = [{"acc": r["accessionNumber"][i].replace("-", ""), "form": f, "date": r["filingDate"][i]} for i, f in enumerate(r.get("form", [])) if f in ("D", "D/A")]
    orig = [x for x in rows if x["form"] == "D"]
    amend = [x for x in rows if x["form"] == "D/A"]
    out = []
    for o in orig:
        for a in amend:
            if a["date"] > o["date"]:
                out.append((o, a))
                break
    return out[:1]


def doc_text(cik: str, acc: str) -> str:
    try:
        return sec.html_to_text(sec.get(sec.ARCHIVE.format(cik=cik, acc=acc, doc="xslFormDX01/primary_doc.xml")))
    except sec.SecError:
        return sec.render_form_d_text(sec.parse_form_d(sec.get(sec.ARCHIVE.format(cik=cik, acc=acc, doc="primary_doc.xml"))))


def collect(n: int) -> int:
    rng = random.Random(1031)
    ciks = sorted({json.loads(l)["id"].split("-")[0] for l in open("data/items/formd_extract.jsonl")})
    rng.shuffle(ciks)
    items = []
    for cik in ciks:
        if len(items) >= n:
            break
        try:
            for o, a in pairs_for(cik):
                to, ta = doc_text(cik, o["acc"]), doc_text(cik, a["acc"])
                if to.strip() == ta.strip() or len(to) < 200 or len(ta) < 200:
                    continue
                items.append({"id": f"ver-{cik}-{o['acc'][-6:]}", "older": {"acc": o["acc"], "date": o["date"], "text": to[:6000]}, "newer": {"acc": a["acc"], "date": a["date"], "text": ta[:6000]},
                              "cik": cik, "split": "test", "source": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=D"})
        except Exception as e:  # noqa: BLE001 - one issuer failing is not fatal
            print("skip", cik, type(e).__name__, str(e)[:80])
    ITEMS.parent.mkdir(parents=True, exist_ok=True)
    ITEMS.write_text("".join(json.dumps(i) + "\n" for i in items))
    print(len(items), "pairs written to", ITEMS)
    return 0


def prompt(item: dict, mode: str, swap: bool) -> tuple[str, str]:
    """Return (prompt, correct letter). Letter order is shuffled by `swap`."""
    first, second = (item["newer"], item["older"]) if swap else (item["older"], item["newer"])
    correct = "A" if swap else "B"
    if mode == "neutral":
        na, nb = "Document A", "Document B"
    else:  # trap: the older version carries the 'final' name
        older_name, newer_name = "Filing FINAL v3.html", "Filing draft v1.html"
        na, nb = (newer_name, older_name) if swap else (older_name, newer_name)
    p = ("Two files are versions of the same SEC filing by the same issuer: one is the original, the other a later amendment. "
         "Decide which file is the NEWER version, using the content (dates, amendment notices, changed figures), not just the file names. "
         'Answer {"newer": "A"} or {"newer": "B"}. Answer with JSON only.\n\n'
         f"=== A: {na} ===\n{first['text']}\n\n=== B: {nb} ===\n{second['text']}")
    return p, correct


def one(name: str, lane: dict, item: dict, mode: str, swap: bool) -> dict:
    p, correct = prompt(item, mode, swap)
    r = L.Caller(lane)(p, 60, item["id"])
    got = tasks.parse_json(r.text) if not r.error else None
    ans = str(got.get("newer", "")).strip().upper()[:1] if isinstance(got, dict) else ""
    return {"lane": name, "mode": mode, "item": item["id"], "swap": swap, "right": ans == correct, "answered": bool(ans), "usd": L.cost(lane, r.tokens_in, r.tokens_out), "error": r.error}


def run(lanes_arg: str, max_usd: float, out_dir: str) -> int:
    items = [json.loads(l) for l in ITEMS.open()]
    lanes = L.load_lanes()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    spent, rows = 0.0, []
    rng = random.Random(7)
    plan = [(it, mode, rng.random() < 0.5) for it in items for mode in ("neutral", "trap")]
    with open(out / "calls.jsonl", "w") as f:
        for name in lanes_arg.split(","):
            with cf.ThreadPoolExecutor(4) as ex:
                for row in ex.map(lambda j: one(name, lanes[name], *j) if spent <= max_usd else None, plan):
                    if row is None:
                        continue
                    spent += row["usd"]
                    rows.append(row)
                    f.write(json.dumps(row) + "\n")
    summ = {}
    for r in rows:
        s = summ.setdefault(r["lane"], {}).setdefault(r["mode"], {"n": 0, "right": 0, "unanswered": 0})
        s["n"] += 1
        s["right"] += r["right"]
        s["unanswered"] += not r["answered"]
    json.dump({"n_pairs": len(items), "spent_usd": round(spent, 4), "summary": summ}, open(out / "summary.json", "w"), indent=1)
    print(json.dumps(summ, indent=1), "spent", round(spent, 4))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("collect")
    c.add_argument("--n", type=int, default=40)
    r = sp.add_parser("run")
    r.add_argument("--lanes", required=True)
    r.add_argument("--max-usd", type=float, required=True)
    r.add_argument("--out", required=True)
    a = ap.parse_args()
    return collect(a.n) if a.cmd == "collect" else run(a.lanes, a.max_usd, a.out)


if __name__ == "__main__":
    raise SystemExit(main())
