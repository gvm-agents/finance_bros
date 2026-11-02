"""Benchmark tasks that stand in for routine research work, on public SEC data.

Each task gives: a prompt for one item, and a Python scorer against an answer
key that came from SEC's structured data (never from a model).

  formd_extract  entity database upkeep: messy filing -> structured facts, people, amounts
  name_match     entity database upkeep: are two company records the same company?
  sector         news tagging / sector taxonomy: business description -> SIC division
  snapshot       CheatSheet text: facts -> short summary + table, no invented numbers
  format_table   document formatting: prose -> exact house-style table
  longdoc        memo-style reading: long 10-K -> four reported numbers (hard control task)
  adv_extract    compliance document review: long Form ADV filing -> seven adviser facts
"""
from __future__ import annotations

import json
import re

from . import adv, sec

JSON_ONLY = "Reply with JSON only, no other text."


def parse_json(text: str):
    """First JSON object in a reply (tolerates code fences and stray words)."""
    if not text:
        return None
    t = re.sub(r"```(?:json)?", "", text)
    start = t.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(t)):
            depth += {"{": 1, "}": -1}.get(t[i], 0)
            if depth == 0:
                try:
                    return json.loads(t[start:i + 1])
                except ValueError:
                    break
        start = t.find("{", start + 1)
    return None


def norm(s) -> str:
    s = str(s or "").lower()
    s = re.sub(r"\b(inc|incorporated|corp|corporation|co|company|llc|l\.l\.c|ltd|limited|lp|l\.p|plc)\b\.?", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def to_number(v):
    """'$12,250,000', '12.25 million', 12250000 -> 12250000.0; words like 'Indefinite' -> the word."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().lower().replace(",", "").replace("$", "").replace("usd", "").strip()
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*(k|thousand|m|mm|million|b|bn|billion)?", s)
    if not m:
        return s or None
    mult = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mm": 1e6, "million": 1e6, "b": 1e9, "bn": 1e9, "billion": 1e9}
    return float(m.group(1)) * mult.get(m.group(2) or "", 1)


def same_value(got, want, rel: float = 0.0) -> bool:
    g, w = to_number(got), to_number(want)
    if isinstance(w, float) and isinstance(g, float):
        return abs(g - w) <= max(rel * abs(w), 0.5)
    return norm(g) == norm(w) and w is not None


NUM_RE = re.compile(r"\$?\d[\d,]*(?:\.\d+)?\s*(?:million|billion|thousand|[mbk]\b)?", re.I)


def numbers_in(text: str) -> set[float]:
    out = set()
    for m in NUM_RE.finditer(text or ""):
        n = to_number(m.group(0))
        if isinstance(n, float):
            out.add(round(n, 2))
        bare = re.match(r"\$?\d[\d,]*(?:\.\d+)?", m.group(0))  # a label letter after a number is not a unit
        if bare:
            out.add(round(float(bare.group(0).lstrip("$").replace(",", "")), 2))
    return out


def invented(values, source_numbers: set[float]) -> int:
    """How many numbers the model gave that appear nowhere in its input."""
    bad = 0
    for v in values:
        n = to_number(v)
        if not isinstance(n, float) or n == 0:  # forms print zeros as blanks
            continue
        tries = [n] + ([n / 1e3, n / 1e6] if abs(n) >= 1e5 else [])  # filings state amounts in thousands or millions
        if not any(abs(abs(v) - s) <= max(0.005 * abs(s), 0.5) for v in tries for s in source_numbers):
            bad += 1
    return bad


# ---------------------------------------------------------------- 1. formd_extract

FORMD_FIELDS = ["issuer_name", "state_of_incorporation", "year_of_incorporation", "industry_group",
                "total_offering_amount", "total_amount_sold", "date_of_first_sale", "number_of_investors"]


def formd_prompt(item: dict) -> str:
    return ("Extract these facts from the SEC Form D filing below. Use exactly these JSON keys: "
            + ", ".join(FORMD_FIELDS) + ", related_persons (a list of {\"name\": full name, \"relationships\": list}). "
            "Amounts as plain numbers in US dollars, or the word in the filing (for example \"Indefinite\"). "
            "Dates as YYYY-MM-DD. Use null when the filing does not say. Do not guess. "
            + JSON_ONLY + "\n\nFILING:\n" + item["text"])


def _pname(s: str) -> str:
    # scorer v3 (2026-10-31): SEC's key carries "N/A" placeholder name parts ("N/A ENCAP ... GP, LLC"). Drop them before norm(),
    # which splits "N/A" into "n a" (v2 tested for "n/a" after that split, so the placeholder was never removed).
    parts = [w for w in norm(re.sub(r"\bN/A\b", " ", s or "", flags=re.I)).split() if w != "na"]
    return f"{parts[0]} {parts[-1]}" if len(parts) >= 2 else " ".join(parts)


def formd_score(item: dict, reply: str) -> dict:
    key, got = item["key"], parse_json(reply)
    if not isinstance(got, dict):
        return {"score": 0.0, "valid": False, "invented": 0}
    def field_ok(f):
        if key.get(f) is None:
            return got.get(f) in (None, "", "null")
        if f == "industry_group" and isinstance(got.get(f), str):  # scorer v2: a more specific label that starts with the key's label is correct
            return norm(got[f]).startswith(norm(key[f]))
        return same_value(got.get(f), key.get(f))
    fields = sum(field_ok(f) for f in FORMD_FIELDS) / len(FORMD_FIELDS)
    want = {_pname(p["name"]): p for p in key["related_persons"]}
    gotp = {_pname(p.get("name", "")): p for p in (got.get("related_persons") or []) if isinstance(p, dict)}
    hit = len(set(want) & set(gotp))
    f1 = 1.0 if not want and not gotp else (2 * hit / (len(want) + len(gotp)) if (want or gotp) else 0.0)
    nums = [got.get(f) for f in ("total_offering_amount", "total_amount_sold", "number_of_investors", "year_of_incorporation")]
    bad = invented(nums, numbers_in(item["text"]))
    return {"score": round(0.7 * fields + 0.3 * f1, 4), "valid": True, "invented": bad,
            "field_accuracy": round(fields, 4), "person_f1": round(f1, 4)}


# ---------------------------------------------------------------- 2. name_match

def name_prompt(item: dict) -> str:
    a, b = item["a"], item["b"]
    return ("Two company records from an investment database. Is record B the same legal company as record A "
            "(for example renamed, or a different spelling), or a different company? "
            'Answer {"same": true} or {"same": false}. ' + JSON_ONLY +
            f"\n\nA: {a['name']} (state: {a.get('state') or 'unknown'}; industry: {a.get('industry') or 'unknown'})"
            f"\nB: {b['name']} (state: {b.get('state') or 'unknown'}; industry: {b.get('industry') or 'unknown'})")


def name_score(item: dict, reply: str) -> dict:
    got = parse_json(reply)
    if not isinstance(got, dict) or not isinstance(got.get("same"), bool):
        return {"score": 0.0, "valid": False, "invented": 0}
    return {"score": float(got["same"] == item["key"]["same"]), "valid": True, "invented": 0}


# ---------------------------------------------------------------- 3. sector

def sector_prompt(item: dict) -> str:
    divisions = "; ".join(f"{d} = {name}" for d, _, _, name in sec.SIC_DIVISIONS)
    return ("Classify the company by its main business into one Standard Industrial Classification division: "
            + divisions + '. Answer {"division": "<letter>"}. ' + JSON_ONLY + "\n\nBUSINESS DESCRIPTION:\n" + item["text"])


def sector_score(item: dict, reply: str) -> dict:
    got = parse_json(reply)
    if not isinstance(got, dict) or not got.get("division"):
        return {"score": 0.0, "valid": False, "invented": 0}
    return {"score": float(str(got["division"]).strip().upper()[:1] == item["key"]["division"]), "valid": True, "invented": 0}


# ---------------------------------------------------------------- 4. snapshot

SNAP_ROWS = [("Issuer", "issuer_name"), ("Industry", "industry_group"), ("Amount sold", "total_amount_sold"),
             ("Offering size", "total_offering_amount"), ("First sale", "date_of_first_sale"), ("Investors", "number_of_investors")]


def snapshot_facts(key: dict) -> dict:
    return {k: key.get(k) for k in ("issuer_name", "state_of_incorporation", "year_of_incorporation", "industry_group",
                                     "total_offering_amount", "total_amount_sold", "date_of_first_sale", "number_of_investors")}


def snapshot_prompt(item: dict) -> str:
    return ("Write a company snapshot for an investment team from ONLY these facts. First a paragraph of 60 to 120 words "
            "starting with 'SNAPSHOT:'. Then a markdown table with columns | Field | Value | and exactly these rows in "
            "order: " + ", ".join(r for r, _ in SNAP_ROWS) + ". Do not add any number, date or name that is not in the "
            "facts. Write 'Not disclosed' for a missing fact.\n\nFACTS:\n" + json.dumps(item["facts"], indent=1))


def table_rows(reply: str) -> dict[str, str]:
    rows = {}
    for line in (reply or "").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and not set(cells[0]) <= set("-: "):
            rows[cells[0].strip("* ").lower()] = cells[1]
    return rows


def snapshot_score(item: dict, reply: str) -> dict:
    key, rows = item["key"], table_rows(reply)
    if not rows:
        return {"score": 0.0, "valid": False, "invented": 0}
    ok = 0
    for label, field in SNAP_ROWS:
        cell = rows.get(label.lower())
        want = key.get(field)
        if cell is None:
            continue
        ok += (want is None and "not disclosed" in cell.lower()) or (want is not None and (
            same_value(cell, want, rel=0.01) or norm(want) in norm(cell)))
    table = ok / len(SNAP_ROWS)
    para = (reply.split("|", 1)[0] if "|" in reply else reply)
    m = re.search(r"snapshot:(.*)", para, re.I | re.S)
    words = len(m.group(1).split()) if m else 0
    fact_numbers = numbers_in(json.dumps(item["facts"]))
    fact_numbers |= {round(n / 1e6, 2) * 1e6 for n in fact_numbers} | {round(n / 1e6, 1) * 1e6 for n in fact_numbers}
    bad = invented([x.group(0) for x in NUM_RE.finditer(m.group(1) if m else "")], fact_numbers)
    length_ok = 60 <= words <= 130
    return {"score": round(0.5 * table + 0.3 * (bad == 0) + 0.2 * length_ok, 4), "valid": True, "invented": bad,
            "table_accuracy": round(table, 4), "words": words}


# ---------------------------------------------------------------- 5. format_table

def format_prose(key: dict) -> str:
    """Python turns the answer key into plain sentences; the model must turn them back into the house table."""
    parts = [f"{p['name']} serves as {' and '.join(p['relationships']).lower() or 'a related person'}"
             for p in key["related_persons"]]
    return (f"{key['issuer_name']} filed a notice of an exempt offering. " + ". ".join(parts) + ". "
            f"The company reported {key.get('number_of_investors')} investors so far.")


def format_prompt(item: dict) -> str:
    return ("Convert the text into a markdown table in our house style: header exactly | Name | Relationships |, one "
            "row per person in the order they appear, relationships in Title Case, sorted A to Z, separated by '; '. "
            "Output only the table.\n\nTEXT:\n" + item["text"])


def format_score(item: dict, reply: str) -> dict:
    lines = [l.strip() for l in (reply or "").strip().splitlines() if l.strip().startswith("|")]
    if not lines:
        return {"score": 0.0, "valid": False, "invented": 0}
    header_ok = [c.strip() for c in lines[0].strip("|").split("|")] == ["Name", "Relationships"]
    body = [[c.strip() for c in l.strip("|").split("|")] for l in lines[2:]]
    want = [[p["name"], "; ".join(sorted(r.title() for r in p["relationships"]))] for p in item["key"]["related_persons"]]
    exact = sum(1 for i, w in enumerate(want) if i < len(body) and body[i][:2] == w) / max(len(want), 1)
    extra = max(0, len(body) - len(want))
    return {"score": round(0.2 * header_ok + 0.8 * exact - 0.1 * extra, 4), "valid": True, "invented": 0,
            "rows_exact": round(exact, 4)}


# ---------------------------------------------------------------- 6. longdoc

def longdoc_prompt(item: dict) -> str:
    return ("From the annual report (Form 10-K) excerpt below, give four numbers for the most recent fiscal year as "
            "reported: total revenue, net income (negative for a loss), total assets at year end, and common shares "
            "outstanding from the cover page. Convert to full units (if a table says 'in millions', multiply). "
            'Use keys revenue, net_income, total_assets, shares_outstanding; null if not found. ' + JSON_ONLY
            + "\n\nREPORT:\n" + item["text"])


def longdoc_score(item: dict, reply: str) -> dict:
    got = parse_json(reply)
    if not isinstance(got, dict):
        return {"score": 0.0, "valid": False, "invented": 0}
    key = item["key"]
    asked = [q for q in sec.XBRL_QUESTIONS if q in key]
    right = sum(same_value(got.get(q), key[q], rel=0.005) for q in asked)
    bad = invented([got.get(q) for q in asked], numbers_in(item["text"]) | {n * m for n in numbers_in(item["text"]) for m in (1e3, 1e6)})
    return {"score": round(right / max(len(asked), 1), 4), "valid": True, "invented": bad}


# ---------------------------------------------------------------- 7. adv_extract

def adv_prompt(item: dict) -> str:
    return ("From the investment adviser's Form ADV filing below, give: total employees (Item 5.A), employees who "
            "perform investment advisory functions (Item 5.B(1)), regulatory assets under management in US dollars "
            "(Item 5.F(2): discretionary, non-discretionary, total), total number of accounts (Item 5.F(2)(f)), and "
            "the two-letter state of the main office. Use keys " + ", ".join(adv.COLUMNS) + "; numbers as plain "
            "integers; null if not found. " + JSON_ONLY + "\n\nFILING:\n" + item["text"])


def adv_score(item: dict, reply: str) -> dict:
    got = parse_json(reply)
    if not isinstance(got, dict):
        return {"score": 0.0, "valid": False, "invented": 0}
    key = item["key"]
    fields = [f for f in adv.COLUMNS if key[f] not in ("", None)]  # a blank key field cannot be scored
    right = sum(same_value(got.get(f), key[f]) for f in fields)
    bad = invented([got.get(f) for f in adv.NUMERIC if got.get(f) not in (0, "0")], numbers_in(item["text"]))
    return {"score": round(right / len(fields), 4), "valid": True, "invented": bad}


def _quote():
    from . import quote  # imported late: quote needs parse_json from this module
    return quote


def _triage():
    from . import triage  # imported late: triage needs parse_json from this module
    return triage


def _rune():
    from . import triage_rune
    return triage_rune


TASKS = {
    "formd_extract": (formd_prompt, formd_score, 1200),
    "formd_bulk": (formd_prompt, formd_score, 1200),  # scale test: fresh filings from bench/bulk.py
    "name_match": (name_prompt, name_score, 50),
    "sector": (sector_prompt, sector_score, 50),
    "snapshot": (snapshot_prompt, snapshot_score, 700),
    "format_table": (format_prompt, format_score, 500),
    "longdoc": (longdoc_prompt, longdoc_score, 300),
    "adv_extract": (adv_prompt, adv_score, 300),
    "longdoc_v2": (longdoc_prompt, longdoc_score, 300),  # same job on excerpts rebuilt by bench/longdoc_fix.py
    "longdoc_quote": (lambda item: _quote().prompt(item), lambda item, reply: _quote().score(item, reply), 500),
    "triage_8k": (lambda item: _triage().prompt(item), lambda item, reply: _triage().score(item, reply), 60),
    "triage_8k_fresh": (lambda item: _triage().prompt(item), lambda item, reply: _triage().score(item, reply), 60),  # filings never used in any earlier test
    "triage_8k_final": (lambda item: _triage().prompt(item), lambda item, reply: _triage().score(item, reply), 60),  # final exam: collected Nov 2, run once at the end of the day
    "triage_8k_final99": (lambda item: _triage().prompt(item), lambda item, reply: _triage().score(item, reply), 60),  # final exam for the 99% target: triage_8k_final plus 310 more new filings (collected Nov 2), run once at the end
    "triage_8k_s60": (lambda item: _triage().prompt(item), lambda item, reply: _triage().score(item, reply), 60),  # random 60 of triage_8k, for costly models
    "triage_8k_rune": (lambda item: _rune().prompt(item), lambda item, reply: _rune().score(item, reply), 0),  # same items as triage_8k, decision model
    "triage_8k_fresh_rune": (lambda item: _rune().prompt(item), lambda item, reply: _rune().score(item, reply), 0),
    "triage_8k_up": (lambda item: _triage().prompt(item), lambda item, reply: _triage().score(item, reply), 60),  # the fresh filings the first reader was unsure about
    "triage_inject_rune": (lambda item: _rune().prompt(item), lambda item, reply: _rune().score(item, reply), 0),  # planted instructions, decision model
    "triage_inject": (lambda item: _triage().prompt(item), lambda item, reply: _triage().score(item, reply), 60),  # same job, hidden instruction planted
}  # name -> (prompt builder, scorer, max output tokens)
