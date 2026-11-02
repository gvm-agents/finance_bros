"""Rebuild the 10-K test items so the facts are in what the model reads. Free; no model is called.

The first set took 54,000 characters after the Item 8 heading, which often missed the statements. This set uses Python
to pick windows around the cover-page share count, the balance sheet and the income statement. Selection never looks
at the answer key; the key is used only afterwards, to report how many key numbers are in the new excerpt.
  SEC_CONTACT="Name email" venv/bin/python -m bench.longdoc_fix
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import comparison, sec

ITEMS = Path(__file__).resolve().parent.parent / "data" / "items"
LIMIT = 60000
NUM = r"[^A-Za-z]{0,40}\$?\s*\(?\d[\d,.]{2,}"
PATTERNS = [(r"total\s+assets" + NUM, 5000, 2500, 4), (r"(total\s+(net\s+)?(revenues?|sales)|net\s+(revenues?|sales)|revenues?)" + NUM, 2000, 5000, 4),
            (r"net\s+(income|loss|earnings)[^0-9]{0,60}" + NUM, 4000, 2000, 4),
            (r"consolidated\s+statements?\s+of\s+(operations|income|earnings|comprehensive)", 200, 7000, 3), (r"consolidated\s+balance\s+sheets?", 200, 7000, 3)]


def excerpt(text: str) -> str:
    spans = [(0, 4000)]
    for m in list(re.finditer(r"(shares?\b[^.]{0,160}\boutstanding|\boutstanding\b[^.]{0,120}shares?)", text[:80000], re.I))[:3]:
        spans.append((max(m.start() - 500, 0), m.end() + 500))
    for pat, back, ahead, keep in PATTERNS:
        hits = list(re.finditer(pat, text, re.I))
        for m in hits[-keep:]:  # the statements sit late in the filing; earlier hits are summaries
            spans.append((max(m.start() - back, 0), m.end() + ahead))
    spans.sort()
    merged = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    out, used = [], 0
    for s, e in merged:
        part = text[s:e][: LIMIT - used]
        out.append(part)
        used += len(part)
        if used >= LIMIT:
            break
    return "\n\n[...]\n\n".join(out)


def main() -> int:
    rows = [json.loads(l) for l in (ITEMS / "longdoc.jsonl").open()]
    out = []
    for r in rows:
        if r["split"] != "test":
            continue
        cik, acc = r["id"].split("-", 1)
        text = sec.ten_k_text(cik, {"acc": acc, "doc": r["source"]})
        out.append({**r, "text": excerpt(text), "full_chars": len(text)})
    with (ITEMS / "longdoc_v2.jsonl").open("w") as f:
        for r in out:
            f.write(json.dumps(r) + "\n")
    print(len(out), "items; all key numbers in excerpt:", sum(comparison.findable(r) for r in out), "; median full length", sorted(r["full_chars"] for r in out)[len(out) // 2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
