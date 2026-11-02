"""Quote check: each number must come with the exact sentence or row it was read from, and Python confirms both.

This is meant to catch plausible wrong answers that the plain number check lets through. It never sees the answer key.
"""
from __future__ import annotations

import json
import re

from . import tasks


def prompt(item: dict) -> str:
    return ("From the annual report (Form 10-K) excerpt below, give four numbers for the most recent fiscal year as reported: total "
            "revenue, net income (negative for a loss), total assets at year end, and common shares outstanding from the cover page. "
            "Convert to full units (if a table says 'in millions', multiply). For each, copy the exact short text from the report that shows "
            'it, at most 25 words, unchanged. Reply with JSON only, with keys revenue, net_income, total_assets, shares_outstanding, each like '
            '{"value": 123, "quote": "..."}; use null for value and quote if not found.\n\nREPORT:\n' + item["text"])


def flat(reply: str) -> dict | None:
    got = tasks.parse_json(reply)
    if not isinstance(got, dict):
        return None
    return {k: (v.get("value") if isinstance(v, dict) else v) for k, v in got.items()}


def score(item: dict, reply: str) -> dict:
    f = flat(reply)
    return tasks.longdoc_score(item, json.dumps(f)) if f is not None else {"score": 0.0, "valid": False, "invented": 0}


def squeeze(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def quote_ok(text: str, value, quote) -> bool:
    if value is None or not quote or squeeze(quote) not in squeeze(text):
        return False
    digits = re.sub(r"[^\d]", "", quote)
    v = abs(float(value))
    for d in (1, 1e3, 1e6):
        x = v / d
        for form in (f"{x:.0f}", f"{x:.1f}".replace(".", ""), f"{x:.2f}".replace(".", "")):
            if form != "0" and form in digits:
                return True
    return False


def gate(item: dict, reply: str) -> bool:
    got = tasks.parse_json(reply)
    if not isinstance(got, dict):
        return False
    return all(isinstance(got.get(k), dict) and quote_ok(item["text"], got[k].get("value"), got[k].get("quote")) for k in item["key"] if item["key"][k] not in (None, ""))
