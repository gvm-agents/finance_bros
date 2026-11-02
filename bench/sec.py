"""Public SEC EDGAR data: fetch with a declared contact, cache on disk, parse.

SEC requires every automated request to name a contact ("Name email") and
allows about 10 requests a second. Set SEC_CONTACT before collecting.
Answer keys come from SEC's own structured fields (Form D XML, company
records, XBRL facts) by Python, never from a model.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

CACHE = Path(__file__).resolve().parent.parent / "data" / "cache"
SEARCH = "https://efts.sec.gov/LATEST/search-index?forms={form}&dateRange=custom&startdt={start}&enddt={end}&from={offset}"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik10}.json"
FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"
_last = [0.0]


class SecError(RuntimeError):
    pass


def contact() -> str:
    c = os.environ.get("SEC_CONTACT", "").strip()
    if "@" not in c:
        raise SecError('set SEC_CONTACT to "Name email" (SEC requires a contact for automated requests)')
    return c


def get(url: str, binary: bool = False) -> str | bytes:
    """GET with SEC's contact header, polite pacing and an on-disk cache."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / hashlib.sha256(url.encode()).hexdigest()[:32]
    if path.exists():
        data = path.read_bytes()
        return data if binary else data.decode("utf-8", "replace")
    wait = 0.12 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": contact(), "Accept-Encoding": "identity"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
    except urllib.error.HTTPError as exc:
        raise SecError(f"HTTP {exc.code} for {url}") from exc
    finally:
        _last[0] = time.time()
    if b"Undeclared Automated Tool" in data[:3000]:
        raise SecError("SEC refused the request: SEC_CONTACT must include a real email")
    path.write_bytes(data)
    return data if binary else data.decode("utf-8", "replace")


def get_json(url: str) -> dict:
    return json.loads(get(url))


# ---------------------------------------------------------------- text

class _Text(HTMLParser):
    BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table", "section"}

    def __init__(self):
        super().__init__()
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in self.BLOCK:
            self.out.append("\n")
        elif tag in ("td", "th"):
            self.out.append(" | ")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_to_text(page: str) -> str:
    p = _Text()
    p.feed(page)
    text = html.unescape("".join(p.out)).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


# ---------------------------------------------------------------- Form D

def _t(root: ET.Element, path: str) -> str:
    el = root.find(path)
    return (el.text or "").strip() if el is not None and el.text else ""


def _num(text: str):
    try:
        f = float(text)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return text or None


def parse_form_d(xml_text: str) -> dict:
    """The answer key for one Form D, straight from SEC's XML fields."""
    root = ET.fromstring(xml_text)
    persons = []
    for rp in root.findall(".//relatedPersonInfo"):
        name = " ".join(x for x in (_t(rp, "relatedPersonName/firstName"), _t(rp, "relatedPersonName/middleName"),
                                    _t(rp, "relatedPersonName/lastName")) if x)
        rels = sorted(r.text.strip() for r in rp.findall(".//relationship") if r.text)
        persons.append({"name": name, "relationships": rels})
    return {
        "issuer_name": _t(root, "primaryIssuer/entityName"),
        "state_of_incorporation": _t(root, "primaryIssuer/jurisdictionOfInc"),
        "year_of_incorporation": _num(_t(root, "primaryIssuer/yearOfInc/value")),
        "industry_group": _t(root, ".//industryGroup/industryGroupType"),
        "total_offering_amount": _num(_t(root, ".//offeringSalesAmounts/totalOfferingAmount")),
        "total_amount_sold": _num(_t(root, ".//offeringSalesAmounts/totalAmountSold")),
        "date_of_first_sale": _t(root, ".//dateOfFirstSale/value") or None,
        "number_of_investors": _num(_t(root, ".//investors/totalNumberAlreadyInvested")),
        "is_amendment": _t(root, ".//newOrAmendment/isAmendment") == "true",
        "related_persons": persons,
    }


def render_form_d_text(key: dict) -> str:
    """Plain-text stand-in for SEC's rendered page (used only when the page is unavailable, and in tests)."""
    lines = [f"FORM D  Notice of Exempt Offering of Securities", f"Name of Issuer: {key['issuer_name']}",
             f"Jurisdiction of Incorporation/Organization: {key['state_of_incorporation']}",
             f"Year of Incorporation/Organization: {key['year_of_incorporation']}",
             "Related Persons:"]
    for p in key["related_persons"]:
        lines.append(f"  {p['name']} | Relationship: {', '.join(p['relationships'])}")
    lines += [f"Industry Group: {key['industry_group']}", f"Date of First Sale: {key['date_of_first_sale']}",
              f"Total Offering Amount: ${key['total_offering_amount']} USD",
              f"Total Amount Sold: ${key['total_amount_sold']} USD",
              f"Total number of investors who already have invested: {key['number_of_investors']}"]
    return "\n".join(lines)


def search_form_d(start: str, end: str, offset: int = 0) -> list[dict]:
    d = get_json(SEARCH.format(form="D", start=start, end=end, offset=offset))
    out = []
    for h in d.get("hits", {}).get("hits", []):
        s = h["_source"]
        out.append({"cik": str(int(s["ciks"][0])), "acc": s["adsh"].replace("-", ""), "form": s["form"],
                    "filed": s["file_date"], "name": re.sub(r"\s*\(CIK \d+\)\s*$", "", s["display_names"][0]).strip()})
    return out


def form_d_item(hit: dict) -> dict:
    xml_text = get(ARCHIVE.format(cik=hit["cik"], acc=hit["acc"], doc="primary_doc.xml"))
    key = parse_form_d(xml_text)
    try:
        text = html_to_text(get(ARCHIVE.format(cik=hit["cik"], acc=hit["acc"], doc="xslFormDX01/primary_doc.xml")))
    except SecError:
        text = render_form_d_text(key)
    return {"id": f"{hit['cik']}-{hit['acc']}", "text": text, "key": key, "source": ARCHIVE.format(
        cik=hit["cik"], acc=hit["acc"], doc="xslFormDX01/primary_doc.xml")}


# ---------------------------------------------------------------- companies, 10-K, XBRL

def submissions(cik: str) -> dict:
    return get_json(SUBMISSIONS.format(cik10=f"{int(cik):010d}"))


def latest_10k(sub: dict) -> dict | None:
    r = sub.get("filings", {}).get("recent", {})
    for i, form in enumerate(r.get("form", [])):
        if form == "10-K":
            return {"acc": r["accessionNumber"][i], "doc": r["primaryDocument"][i], "date": r["reportDate"][i]}
    return None


def ten_k_text(cik: str, filing: dict) -> str:
    return html_to_text(get(ARCHIVE.format(cik=int(cik), acc=filing["acc"].replace("-", ""), doc=filing["doc"])))


def item_1(text: str, limit: int = 6000) -> str:
    """Business description: text after the last 'Item 1. Business' heading (skips the table of contents)."""
    hits = [m.end() for m in re.finditer(r"item\s*1\.?\s*[\-–—:]?\s*business\b", text, re.I)]
    start = hits[-1] if hits else 0
    body = text[start:]
    stop = re.search(r"item\s*1a\.?\s*[\-–—:]?\s*risk\s+factors", body, re.I)
    return body[: stop.start() if stop else limit][:limit].strip()


SIC_DIVISIONS = [  # SEC/OSHA SIC divisions by major-group range
    ("A", 1, 9, "Agriculture, Forestry and Fishing"), ("B", 10, 14, "Mining"), ("C", 15, 17, "Construction"),
    ("D", 20, 39, "Manufacturing"), ("E", 40, 49, "Transportation, Communications, Electric, Gas and Sanitary Services"),
    ("F", 50, 51, "Wholesale Trade"), ("G", 52, 59, "Retail Trade"), ("H", 60, 67, "Finance, Insurance and Real Estate"),
    ("I", 70, 89, "Services"), ("J", 91, 99, "Public Administration"),
]


def sic_division(sic: str | int) -> str | None:
    major = int(str(sic)[:2]) if str(sic).strip() else -1
    return next((d for d, lo, hi, _ in SIC_DIVISIONS if lo <= major <= hi), None)


XBRL_QUESTIONS = {  # question key -> (taxonomy, concepts tried in order, unit)
    "revenue": ("us-gaap", ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"], "USD"),
    "net_income": ("us-gaap", ["NetIncomeLoss"], "USD"),
    "total_assets": ("us-gaap", ["Assets"], "USD"),
    "shares_outstanding": ("dei", ["EntityCommonStockSharesOutstanding"], "shares"),
}


def xbrl_answers(facts: dict, acc: str) -> dict:
    """Values reported in one 10-K (matched by accession number), from SEC's XBRL company facts."""
    out = {}
    for q, (tax, concepts, unit) in XBRL_QUESTIONS.items():
        for c in concepts:
            rows = facts.get("facts", {}).get(tax, {}).get(c, {}).get("units", {}).get(unit, [])
            rows = [r for r in rows if r.get("accn") == acc and r.get("form") == "10-K"]
            if q in ("revenue", "net_income"):
                rows = [r for r in rows if r.get("fp") == "FY" and r.get("start")]
                rows.sort(key=lambda r: (r["end"], r["end"] > r["start"]), reverse=True)
            else:
                rows.sort(key=lambda r: r["end"], reverse=True)
            if rows:
                out[q] = rows[0]["val"]
                break
    return out
