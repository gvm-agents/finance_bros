"""8-K triage test set: the SEC's own item codes are the answer key. Free, no model is called here.

  SEC_CONTACT="Name email" venv/bin/python -m bench.triage collect --start 2026-10-01 --end 2026-10-30 --per-type 30
Each item is the text of one 8-K with a single substantive item (exhibit item 9.01 is ignored). Item headings are
removed from the text so the model must read the content. The priority rule below is our own judgment.
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import re
import time
import urllib.parse
from pathlib import Path

from . import sec
from .triage_prompt import TYPES, prompt  # noqa: F401

HIGH = {"bankruptcy", "cyber_incident", "acquisition_or_sale", "delisting_notice", "restatement", "leadership_change"}
OUT = Path(__file__).resolve().parent.parent / "data" / "items" / "triage_8k.jsonl"
LIMIT = 6000
SEARCH = "https://efts.sec.gov/LATEST/search-index?forms=8-K&dateRange=custom&startdt={s}&enddt={e}&from={o}&q={q}"
HEADING = re.compile(r"^\W*item\s*\d\.\d\d\b.*$", re.I | re.M)
INLINE = re.compile(r"\bitem\s*\d\.\d\d\b", re.I)


TITLES = ("Departure of Directors or Certain Officers", "Election of Directors", "Appointment of Certain Officers", "Compensatory Arrangements of Certain Officers",
          "Results of Operations and Financial Condition", "Entry into a Material Definitive Agreement", "Regulation FD Disclosure", "Other Events",
          "Bankruptcy or Receivership", "Material Cybersecurity Incidents", "Completion of Acquisition or Disposition of Assets",
          "Notice of Delisting or Failure to Satisfy a Continued Listing Rule or Standard", "Transfer of Listing",
          "Non-Reliance on Previously Issued Financial Statements or a Related Audit Report or Completed Interim Review")


def clean(text: str) -> str:
    """Drop item headings and the cover page, and blank any remaining item number."""
    i = text.lower().find("item ")
    m = HEADING.search(text)
    body = text[m.start():] if m else text[max(i, 0):]
    body = re.split(r"\bSIGNATURES?\b", HEADING.sub("", body))[0]
    body = re.sub(r"\s+", " ", INLINE.sub("[item]", body)).strip()
    for t in TITLES:
        body = re.sub(re.escape(t) + r"\.?", "", body, flags=re.I)
    return re.sub(r"^(certain officers|[;.,\s])+", "", body, flags=re.I).strip()


def candidates(start: str, end: str, code: str, pages: int = 5) -> list[dict]:
    out = []
    for p in range(pages):
        url = SEARCH.format(s=start, e=end, o=p * 100, q=urllib.parse.quote(f'"Item {code}"'))
        hits = None
        for attempt in range(4):  # SEC full-text search returns HTTP 500 at times, often on later pages
            try:
                hits = sec.get_json(url).get("hits", {}).get("hits", [])
                break
            except sec.SecError as exc:
                if "HTTP 5" not in str(exc):
                    raise
                time.sleep(2 * (attempt + 1))
        if hits is None:
            if p == 0:
                raise sec.SecError(f"SEC search kept failing for Item {code}, {start} to {end}")
            break  # keep the pages already read
        out += hits
        if len(hits) < 100:
            break
    return out


def item_from(hit: dict) -> dict | None:
    src = hit["_source"]
    items = [x for x in src.get("items", []) if x != "9.01"]
    if src.get("file_type") != "8-K" or len(items) != 1 or items[0] not in TYPES:
        return None
    acc, doc = hit["_id"].split(":", 1)
    if not doc.lower().endswith((".htm", ".html")) or not re.search(r"8-?k", doc, re.I):
        return None
    cik = str(int(src["ciks"][-1]))
    url = sec.ARCHIVE.format(cik=cik, acc=acc.replace("-", ""), doc=doc)
    text = clean(sec.html_to_text(sec.get(url)))
    if len(text) < 200:
        return None
    label = TYPES[items[0]]
    return {"id": acc, "text": text[:LIMIT], "key": {"type": label, "priority": "high" if label in HIGH else "normal"}, "source": url, "filed": src.get("file_date"), "split": "test"}


def score(item: dict, reply: str) -> dict:
    from .tasks import parse_json
    got = parse_json(reply)
    if not isinstance(got, dict):
        return {"score": 0.0, "valid": False, "invented": 0}
    k = item["key"]
    return {"score": 0.5 * (got.get("type") == k["type"]) + 0.5 * (got.get("priority") == k["priority"]), "valid": True, "invented": 0}


def collect(start: str, end: str, per_type: int, seed: int = 11, out: Path = OUT, exclude: tuple[Path, ...] = ()) -> dict:
    """Build a set. Filings already in any `exclude` file are skipped, so fresh and training sets never overlap a test set."""
    rng = random.Random(seed)
    rows, seen, counts = [], set(), collections.Counter()
    for path in exclude:
        seen |= {json.loads(l)["id"] for l in path.open()}
    for code, label in TYPES.items():
        hits = candidates(start, end, code)
        rng.shuffle(hits)
        for h in hits:
            if counts[label] >= per_type:
                break
            acc = h["_id"].split(":")[0]
            if acc in seen:
                continue
            seen.add(acc)
            try:
                it = item_from(h)
            except (sec.SecError, KeyError, ValueError, IndexError):
                continue
            if it and it["key"]["type"] == label:
                rows.append(it)
                counts[label] += 1
    with out.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return dict(counts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--start", required=True)
    c.add_argument("--end", required=True)
    c.add_argument("--per-type", type=int, default=30)
    c.add_argument("--name", default="triage_8k", help="output set name in data/items")
    c.add_argument("--exclude", default="", help="comma-separated set names whose filings are left out")
    c.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    ex = tuple(OUT.parent / f"{n}.jsonl" for n in a.exclude.split(",") if n)
    print(collect(a.start, a.end, a.per_type, a.seed, OUT.parent / f"{a.name}.jsonl", ex))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
