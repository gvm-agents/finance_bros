"""Build the test items for all six tasks from public SEC data (free; needs SEC_CONTACT).

Every item is saved to data/items/<task>.jsonl with its answer key and a
fixed split: about 70% "train" (examples for fine-tuning) and 30% "test"
(scoring only; never used for training).
"""
from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path

from . import adv, sec, tasks

ITEMS = Path(__file__).resolve().parent.parent / "data" / "items"
TICKERS = "https://www.sec.gov/files/company_tickers.json"


def split_of(item_id: str) -> str:
    return "test" if int(hashlib.sha256(item_id.encode()).hexdigest(), 16) % 10 < 3 else "train"


def save(task: str, items: list[dict]) -> Path:
    ITEMS.mkdir(parents=True, exist_ok=True)
    path = ITEMS / f"{task}.jsonl"
    with path.open("w") as f:
        for it in items:
            it.setdefault("split", split_of(it["id"]))
            f.write(json.dumps(it) + "\n")
    return path


def load(task: str, split: str | None = None) -> list[dict]:
    path = ITEMS / f"{task}.jsonl"
    if not path.exists():
        return []
    items = [json.loads(l) for l in path.open()]
    return [i for i in items if split in (None, "all") or i["split"] == split]


def form_d_items(start: str, end: str, n: int, log=print) -> list[dict]:
    hits, offset = [], 0
    while len(hits) < n * 2 and offset < 2000:
        page = sec.search_form_d(start, end, offset)
        if not page:
            break
        hits += [h for h in page if h["form"] == "D"]
        offset += 100
    random.Random(7).shuffle(hits)
    items, seen = [], set()
    for h in hits:
        if len(items) >= n or h["cik"] in seen:
            continue
        seen.add(h["cik"])
        try:
            it = sec.form_d_item(h)
        except (sec.SecError, Exception) as exc:  # noqa: BLE001 - one bad filing must not stop the batch
            log(f"  skip {h['cik']}: {exc}")
            continue
        it["name"], it["filed"] = h["name"], h["filed"]
        items.append(it)
        if len(items) % 25 == 0:
            log(f"  form d: {len(items)}/{n}")
    return items


def derived_items(formd: list[dict]) -> tuple[list[dict], list[dict]]:
    snaps, fmts = [], []
    for it in formd:
        k = it["key"]
        snaps.append({"id": it["id"], "split": it["split"], "facts": tasks.snapshot_facts(k), "key": k, "source": it["source"]})
        if k["related_persons"]:
            fmts.append({"id": it["id"], "split": it["split"], "text": tasks.format_prose(k), "key": k, "source": it["source"]})
    return snaps, fmts


NAME_STOP = {"the", "inc", "corp", "co", "company", "group", "holdings", "holding", "trust", "fund", "capital",
             "international", "global", "partners", "and", "of", "new", "american", "first", "bancorp", "financial"}


def name_tokens(name: str) -> set[str]:
    return {w for w in tasks.norm(name).split() if len(w) > 2 and w not in NAME_STOP}


def _rec(cik: str, sub: dict, fallback_name: str = "") -> dict:
    return {"cik": cik, "name": sub.get("name") or fallback_name, "state": sub.get("stateOfIncorporation") or "",
            "industry": sub.get("sicDescription") or "",
            "former": [f["name"] for f in sub.get("formerNames", []) if f.get("name")]}


def name_items(formd: list[dict], log=print, pairs: int = 150, max_fetch: int = 1500) -> list[dict]:
    """Same company (current vs former SEC name, same SEC number) vs different companies with a shared name word.

    Sources: SEC's company list (public companies) plus the Form D issuers already collected. A 'same' pair
    must share at least one distinctive word (a rename nobody could guess from the names alone is noise,
    not a test). A 'different' pair shares the first distinctive word but has a different SEC number.
    Answer keys come from the SEC number (CIK), never from a model.
    """
    tick = sec.get_json(TICKERS)
    names = {str(v["cik_str"]): v["title"] for v in tick.values()}
    for it in formd:
        names.setdefault(it["id"].split("-")[0], it["key"]["issuer_name"])
    ciks = sorted(names)
    random.Random(11).shuffle(ciks)
    recs: dict[str, dict] = {}

    def rec(cik: str) -> dict | None:
        if cik not in recs:
            if len(recs) >= max_fetch:
                return None
            try:
                recs[cik] = _rec(cik, sec.submissions(cik), names.get(cik, ""))
            except sec.SecError as exc:
                log(f"  skip {cik}: {exc}")
                recs[cik] = None
        return recs[cik]

    def side(r: dict, name: str | None = None) -> dict:
        return {"name": name or r["name"], "state": r["state"], "industry": r["industry"]}

    pos = []
    for cik in ciks:
        if len(pos) >= pairs:
            break
        r = rec(cik)
        if r is None and len(recs) >= max_fetch:
            break
        for f in (r or {}).get("former", [])[:3]:
            if tasks.norm(f) != tasks.norm(r["name"]) and name_tokens(f) & name_tokens(r["name"]):
                pos.append({"id": f"pos-{cik}", "a": side(r), "b": side(r, f), "key": {"same": True}})
                break
        if len(recs) % 200 == 0 and recs:
            log(f"  name_match: {len(recs)} records read, {len(pos)} same-company pairs")
    by_word: dict[str, list[str]] = {}
    for cik in ciks:
        toks = [w for w in tasks.norm(names[cik]).split() if len(w) > 2 and w not in NAME_STOP]
        if toks:
            by_word.setdefault(toks[0], []).append(cik)
    neg, used = [], set()
    for word in sorted(by_word, key=lambda w: random.Random(w).random()):
        group = by_word[word]
        for a, b in zip(group[::2], group[1::2]):
            if len(neg) >= len(pos) or a in used or b in used:
                continue
            ra, rb = rec(a), rec(b)
            if ra and rb and tasks.norm(ra["name"]) != tasks.norm(rb["name"]):
                used |= {a, b}
                neg.append({"id": f"neg-{a}-{b}", "a": side(ra), "b": side(rb), "key": {"same": False}})
    items = pos + neg[: len(pos)]
    random.Random(13).shuffle(items)
    log(f"  name_match: {len(pos)} same + {min(len(neg), len(pos))} different pairs")
    return items


def ten_k_items(n: int, longdoc_chars: int = 60000, log=print) -> tuple[list[dict], list[dict]]:
    """Business descriptions (sector task) and long 10-K excerpts with XBRL answers (longdoc task)."""
    tick = sec.get_json(TICKERS)
    ciks = sorted({str(v["cik_str"]) for v in tick.values()})
    random.Random(5).shuffle(ciks)
    sectors, longdocs = [], []
    for cik in ciks:
        if len(sectors) >= n:
            break
        try:
            sub = sec.submissions(cik)
            div = sec.sic_division(sub.get("sic") or "")
            filing = sec.latest_10k(sub)
            if not div or not filing:
                continue
            text = sec.ten_k_text(cik, filing)
            desc = sec.item_1(text)
            if len(desc) < 800:
                continue
            sectors.append({"id": f"{cik}-{filing['acc']}", "text": desc, "source": filing["doc"],
                            "key": {"division": div, "sic": sub.get("sic"), "sic_description": sub.get("sicDescription")}})
            answers = sec.xbrl_answers(sec.get_json(sec.FACTS.format(cik10=f"{int(cik):010d}")), filing["acc"])
            if len(answers) >= 3:
                cover = text[:6000]
                hits = [m.start() for m in re.finditer(r"item\s*8\.?\s*[\-–—:]?\s*financial\s+statements", text, re.I)]
                body = text[hits[-1]:] if hits else text[len(text) // 2:]
                longdocs.append({"id": f"{cik}-{filing['acc']}", "text": cover + "\n\n[...]\n\n" + body[: longdoc_chars - 6000],
                                 "key": answers, "source": filing["doc"]})
        except (sec.SecError, Exception) as exc:  # noqa: BLE001
            log(f"  skip {cik}: {exc}")
        if len(sectors) % 20 == 0 and sectors:
            log(f"  10-K: {len(sectors)}/{n}")
    return sectors, longdocs


def collect_all(start: str, end: str, n_formd: int, n_10k: int, log=print) -> dict[str, int]:
    sec.contact()
    formd = form_d_items(start, end, n_formd, log)
    for it in formd:
        it["split"] = split_of(it["id"])
    save("formd_extract", formd)
    snaps, fmts = derived_items(formd)
    save("snapshot", snaps)
    save("format_table", fmts)
    save("name_match", name_items(formd, log))
    sectors, longdocs = ten_k_items(n_10k, log=log)
    save("sector", sectors)
    save("longdoc", longdocs)
    return {t: len(load(t)) for t in tasks.TASKS}


def collect_names(pairs: int = 150, log=print) -> dict[str, int]:
    sec.contact()
    items = name_items(load("formd_extract"), log, pairs=pairs)
    save("name_match", items)
    test = [i for i in load("name_match") if i["split"] == "test"]
    return {"name_match": len(items), "held_back": len(test), "held_back_same": sum(i["key"]["same"] for i in test)}


def collect_adv(n: int = 150, log=print) -> dict[str, int]:
    sec.contact()
    save("adv_extract", adv.adv_items(n, log))
    return {"adv_extract": len(load("adv_extract")), "held_back": len(load("adv_extract", "test"))}
