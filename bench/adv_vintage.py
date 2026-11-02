"""Who is entering venture? Yearly counts of venture capital advisers from the SEC's own monthly exempt reporting adviser lists. Python only; free.

  SEC_CONTACT="Name email" venv/bin/python -m bench.adv_vintage --out results/adv-vintage-1101
A venture adviser here is an exempt reporting adviser that ticks Form ADV item 2B(1). Venture firms that register fully are not counted, so this is a floor.
Each snapshot is the first list published in that year. Entrants and exits come from comparing firm numbers year to year.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path

from . import adv_library, sec

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "adv_history"
NAME = re.compile(r"ia(\d{2})(\d{2})(\d{2,4})-?exempt", re.I)


def snapshots(page: str) -> dict[int, list[tuple[str, str]]]:
    """year -> every exempt list of that year, earliest first; key 9999 holds the newest list overall. The first readable one is used."""
    found = []
    for href in re.findall(r'href="([^"]+\.(?:zip|xlsx?|csv))"', page):
        m = NAME.search(href.rsplit("/", 1)[-1])
        if m:
            yr = int(m.group(3)) if len(m.group(3)) == 4 else 2000 + int(m.group(3))
            found.append((f"{yr}-{m.group(1)}-{m.group(2)}", href))
    out: dict[int, list[tuple[str, str]]] = {}
    for d, h in sorted(set(found)):
        out.setdefault(int(d[:4]), []).append((d, h))
    out[9999] = [max(found)]
    return out


def xlsx_rows(handle):
    import openpyxl
    ws = openpyxl.load_workbook(handle, read_only=True, data_only=True).worksheets[0]
    head = None
    for r in ws.iter_rows(values_only=True):
        vals = ["" if v is None else str(v).strip() for v in r]
        if head is None:
            if any("CRD" in v for v in vals):
                head = vals
            continue
        yield dict(zip(head, vals))


def rows(path: Path):
    if path.suffix.lower() == ".xlsx":
        yield from xlsx_rows(path)
        return
    z = zipfile.ZipFile(path)
    name = z.namelist()[0]
    if name.lower().endswith(".xlsx"):
        yield from xlsx_rows(io.BytesIO(z.read(name)))
        return
    text = z.read(name).decode("latin-1", "replace")
    delimiter = "|" if text[:3000].count("|") > text[:3000].count(",") else ","
    yield from csv.DictReader(io.StringIO(text), delimiter=delimiter)


def pick(row: dict, *names) -> str:
    for n in names:
        if row.get(n) not in (None, ""):
            return row[n].strip()
    return ""


def num(s: str) -> float:
    try:
        return float(re.sub(r"[^\d.]", "", s) or 0)
    except ValueError:
        return 0.0


def venture(row: dict) -> str:
    for k, v in row.items():
        if k and re.fullmatch(r"(item\s*)?2\.?\s*B\.?\s*\(?1\)?", k.strip(), re.I):
            return str(v or "")
    return ""


def read(path: Path) -> dict:
    out = {}
    for r in rows(path):
        if venture(r).upper() not in ("Y", "YES"):
            continue
        crd = next((str(v).strip() for k, v in r.items() if k and "CRD" in k and "Organization" in k), "") or pick(r, "CRD#", "CRD Number")
        funds = num(next((str(v) for k, v in r.items() if k and "Count of Private Funds" in k and "7B(1)" in k), ""))
        since = pick(r, "SEC Status Effective Date", "Status Effective Date")
        out[crd] = {"funds": funds, "since": since, "name": pick(r, "Primary Business Name")}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    snaps = snapshots(sec.get(adv_library.LISTS_PAGE))
    table, prev, skipped = [], None, []
    for yr in sorted(snaps):
        now = None
        for d, href in snaps[yr]:
            path = CACHE / href.rsplit("/", 1)[-1]
            if not path.exists():
                path.write_bytes(sec.get("https://www.sec.gov" + href, binary=True))
            try:
                now = read(path)
            except (ValueError, zipfile.BadZipFile, KeyError, IndexError) as e:
                skipped.append([d, str(e)[:80]])
                continue
            if now:
                break
            skipped.append([d, "no venture rows found"])
        if not now:
            continue
        row = {"as_of": d, "venture_advisers": len(now), "funds": int(sum(v["funds"] for v in now.values())) or None}  # the lists gave fund counts only from about 2024
        if prev is not None:
            row["new"], row["gone"] = len(set(now) - set(prev)), len(set(prev) - set(now))
        table.append(row)
        prev = now
        print(row, flush=True)
    cohort: dict[str, dict] = {}
    for v in prev.values():
        y = (re.search(r"(19|20)\d{2}", v["since"]) or [""])[0]
        c = cohort.setdefault(y or "unknown", {"advisers": 0, "funds": 0})
        c["advisers"] += 1
        c["funds"] += int(v["funds"])
    (a.out / "vintage.json").write_text(json.dumps({"snapshots": table, "cohort_of_latest_list": dict(sorted(cohort.items())), "skipped": skipped}, indent=1))
    print("cohorts", dict(sorted(cohort.items())))
    print("skipped", skipped)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
