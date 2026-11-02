"""Form ADV task: read a long adviser filing (Part 1A report) and pull seven facts.

Stand-in for compliance document review. Answer keys come from SEC's monthly
registered-adviser data file (Python reads the CSV), and an item is kept only if
Python finds every key number in the filing text too, so the key matches the
version of the filing the model reads. Free and public; needs SEC_CONTACT and
`pdftotext` (Homebrew poppler) on the machine that collects.
"""
from __future__ import annotations

import csv
import io
import random
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

from . import sec

DATA_FILE = ("https://www.sec.gov/files/investment/data/other/"
             "information-about-registered-investment-advisers-exempt-reporting-advisers/ia100226.zip")
REPORT = "https://reports.adviserinfo.sec.gov/reports/ADV/{crd}/PDF/{crd}.pdf"
COLUMNS = {  # answer key field -> SEC data file column
    "total_employees": "5A",
    "advisory_employees": "5B(1)",
    "aum_discretionary": "5F(2)(a)",
    "aum_non_discretionary": "5F(2)(b)",
    "aum_total": "5F(2)(c)",
    "accounts_total": "5F(2)(f)",
    "main_office_state": "Main Office State",
}
NUMERIC = [f for f in COLUMNS if f != "main_office_state"]


def _int(v: str):
    v = (v or "").strip().replace(",", "")
    try:
        return int(float(v))
    except ValueError:
        return None


def advisers(data_zip: bytes) -> list[dict]:
    """Registered advisers with assets under management, from SEC's monthly data file."""
    with zipfile.ZipFile(io.BytesIO(data_zip)) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        text = z.read(name).decode("latin-1")
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        key = {f: (_int(row.get(c)) if f in NUMERIC else (row.get(c) or "").strip()) for f, c in COLUMNS.items()}
        if row.get("Firm Type", "").strip() != "Registered" or not key["aum_total"] or None in key.values():
            continue
        out.append({"crd": row["Organization CRD#"].strip(), "name": row.get("Primary Business Name", "").strip(),
                    "filed": row.get("Latest ADV Filing Date", "").strip(), "key": key})
    return out


def pdf_text(pdf: bytes) -> str:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "adv.pdf"
        p.write_bytes(pdf)
        r = subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, timeout=120)
    if r.returncode:
        raise sec.SecError("pdftotext failed")
    return r.stdout.decode("utf-8", "replace")


def window(text: str, limit: int = 60000) -> str | None:
    """Cover pages plus a long stretch that contains Item 5 (employees and assets); None if Item 5 is missing."""
    m = re.search(r"Item 5 Information About Your Advisory Business - Employees", text)
    f = re.search(r"Discretionary:.*\n.*Non-Discretionary:.*\n.*Total:", text)
    if not m or not f:
        return None
    cover = text[:8000]
    start = max(8000, m.start() - 25000)
    body = text[start:start + limit - 8000]
    return cover + "\n\n[...]\n\n" + body if f.end() <= start + len(body) else None


def key_in_text(key: dict, text: str) -> bool:
    nums = {int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", text) if n.replace(",", "").isdigit()}
    return all(key[f] in nums for f in NUMERIC if key[f])  # zeros are often printed as blanks


def adv_items(n: int = 150, log=print, seed: int = 17) -> list[dict]:
    rows = advisers(sec.get(DATA_FILE, binary=True))
    random.Random(seed).shuffle(rows)
    items = []
    for r in rows:
        if len(items) >= n:
            break
        try:
            text = pdf_text(sec.get(REPORT.format(crd=r["crd"]), binary=True))
        except (sec.SecError, Exception) as exc:  # noqa: BLE001 - one bad filing must not stop the batch
            log(f"  skip CRD {r['crd']}: {str(exc)[:80]}")
            continue
        doc = window(text)
        if not doc or not key_in_text(r["key"], doc):
            continue  # filing changed after the data file, or Item 5 outside the window: key would not match
        items.append({"id": f"adv-{r['crd']}", "text": doc, "key": r["key"], "name": r["name"], "filed": r["filed"],
                      "source": REPORT.format(crd=r["crd"])})
        if len(items) % 25 == 0:
            log(f"  form adv: {len(items)}/{n}")
    return items
