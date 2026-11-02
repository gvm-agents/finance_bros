"""Pull what public filings disclose for every company set. Python only, free; no model reads a number.

  SEC_CONTACT="Name email" venv/bin/python -m bench.sets --out results/sets-1101
Writes pull.json (one row per company, with sources) and completeness.md (share of fields found, by group).
Companies that do not file with the SEC appear only through what partners say about them.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from . import dc_funding as d, sec

SETS = {
    "Data center spenders": {"Microsoft": "MSFT", "Alphabet": "GOOGL", "Amazon": "AMZN", "Meta": "META", "Oracle": "ORCL", "Apple": "AAPL", "Tesla": "TSLA", "CoreWeave": "CRWV",
                             "Nebius": "NBIS", "IREN": "IREN", "Applied Digital": "APLD", "Cipher Mining": "CIFR", "TeraWulf": "WULF", "Galaxy Digital": "GLXY", "Core Scientific": "CORZ",
                             "Hut 8": "HUT", "Digital Realty": "DLR", "Equinix": "EQIX", "Iron Mountain": "IRM", "American Tower": "AMT"},
    "Algorithm effects": {"NVIDIA": "NVDA", "AMD": "AMD", "Broadcom": "AVGO", "Micron": "MU", "TSMC": "TSM", "Microsoft": "MSFT", "Alphabet": "GOOGL", "Amazon": "AMZN", "Meta": "META", "Oracle": "ORCL",
                          "CoreWeave": "CRWV", "ServiceNow": "NOW", "Salesforce": "CRM", "Adobe": "ADBE", "Snowflake": "SNOW", "Datadog": "DDOG", "Palantir": "PLTR", "Accenture": "ACN", "JPMorgan": "JPM", "Walmart": "WMT"},
    "Healthcare AI": {"UnitedHealth": "UNH", "Elevance": "ELV", "CVS": "CVS", "HCA": "HCA", "Veeva": "VEEV", "Doximity": "DOCS", "Tempus AI": "TEM", "Hims & Hers": "HIMS", "Teladoc": "TDOC",
                      "Intuitive Surgical": "ISRG", "GE HealthCare": "GEHC", "Eli Lilly": "LLY"},
}
PRIVATE_LABS = ("OpenAI", "Anthropic", "xAI")
FLOW = {"capex": d.CONCEPTS["capex"] + ["PaymentsToDevelopRealEstateAssets", "PaymentsForCapitalImprovements", "PaymentsToAcquireOilAndGasPropertyAndEquipment",
                                         "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities", "PurchaseOfPropertyPlantAndEquipmentIntangibleAssetsOtherThanGoodwillInvestmentPropertyAndOtherNoncurrentAssets"],
        "operating_cash_flow": d.CONCEPTS["operating_cash_flow"] + ["NetCashProvidedByUsedInOperatingActivitiesContinuingOperations", "CashFlowsFromUsedInOperatingActivities"],
        "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "RevenueFromContractWithCustomerIncludingAssessedTax", "Revenue", "RevenuesNetOfInterestExpense"]}
POINT = {"cash": d.BALANCE["cash"] + ["CashAndCashEquivalents", "CashAndDueFromBanks"],
         "securities": d.BALANCE["securities"] + ["CurrentInvestments", "OtherCurrentFinancialAssets"],
         "debt": d.BALANCE["debt"] + ["LongTermDebtNoncurrent", "ConvertibleNotesPayableNoncurrent", "ConvertibleDebtNoncurrent", "SeniorNotes", "Borrowings", "NoncurrentPortionOfNoncurrentBondsIssued", "LongTermBorrowings"],
         "backlog_rpo": ["RevenueRemainingPerformanceObligation"]}
FIELDS = ("capex", "operating_cash_flow", "revenue", "cash", "debt", "backlog_rpo", "leases_not_started", "purchase_commitments", "server_useful_life", "customer_concentration")
SENT = re.compile(r"(?<=[.;])\s+(?=[A-Z(])")
LEASE_RX = re.compile(r"not yet commenced|additional lease commitments|lease obligations were|leases? that ha(?:ve|s) not", re.I)
BUY_RX = re.compile(r"material purchase commitments|non-cancelable contractual commitments|purchase (?:commitments|obligations) (?:of|were|totaled|for)|unconditional purchase", re.I)
LIFE_RX = re.compile(r"useful li[fv]es?", re.I)
HW_RX = re.compile(r"server|network|GPU|computer equipment|compute", re.I)
CONC_RX = re.compile(r"(\d{1,3}(?:\.\d)?)\s?%[^.]{0,120}(revenue|net sales|remaining performance|backlog|receivable)|(revenue|remaining performance|backlog|net sales)[^.]{0,120}?(\d{1,3}(?:\.\d)?)\s?%", re.I)
CUST_RX = re.compile(r"customers?", re.I)


def sentences(text: str) -> list[str]:
    return [d.squash(s) for s in SENT.split(text)]


def tickers() -> dict[str, str]:
    data = sec.get_json("https://www.sec.gov/files/company_tickers.json")
    return {v["ticker"]: str(v["cik_str"]) for v in data.values()}


def latest(cik: str) -> tuple[dict | None, str]:
    r = sec.submissions(cik)["filings"]["recent"]
    for i, form in enumerate(r["form"]):
        if form in ("10-Q", "10-K", "20-F", "40-F"):
            f = {"form": form, "accession": r["accessionNumber"][i], "doc": r["primaryDocument"][i], "filed": r["filingDate"][i]}
            f["url"] = sec.ARCHIVE.format(cik=str(int(cik)), acc=f["accession"].replace("-", ""), doc=f["doc"])
            return f, sec.html_to_text(sec.get(f["url"]))
    return None, ""


def annual(cik: str) -> tuple[dict | None, str]:
    """Latest annual report: the fuller notes (useful lives, customers) are usually only there."""
    r = sec.submissions(cik)["filings"]["recent"]
    for i, form in enumerate(r["form"]):
        if form in ("10-K", "20-F", "40-F"):
            f = {"form": form, "accession": r["accessionNumber"][i], "doc": r["primaryDocument"][i], "filed": r["filingDate"][i]}
            f["url"] = sec.ARCHIVE.format(cik=str(int(cik)), acc=f["accession"].replace("-", ""), doc=f["doc"])
            return f, sec.html_to_text(sec.get(f["url"]))
    return None, ""


def biggest(sents: list[str], rx: re.Pattern) -> dict | None:
    hit = [(d.amount(s), s) for s in sents if rx.search(s) and d.amount(s)]
    if not hit:
        return None
    usd, s = max(hit, key=lambda t: t[0])
    return {"usd": usd, "quote": s[:400]}


def table_lease(text: str) -> dict | None:
    from .dc_table import row_total
    v = row_total(text, "Leases not yet commenced")
    return {"usd": v, "quote": "filing table row: Leases not yet commenced, Total column"} if v else None


def life(sents: list[str]) -> dict | None:
    for s in sents:
        if LIFE_RX.search(s) and HW_RX.search(s) and re.search(r"\b\d{1,2}(\.\d)?\s*(to\s*\d{1,2}\s*)?(-\s*)?years?\b|\b(three|four|five|six|seven)\b[^.]{0,20}years?", s, re.I):
            return {"quote": s[:400]}
    return None


def concentration(sents: list[str]) -> dict | None:
    hits = [s for s in sents if CUST_RX.search(s) and CONC_RX.search(s)]
    named = [s for s in hits if re.search(r"OpenAI|Anthropic|Microsoft|Meta|Nvidia|largest customer|top (two|three|five|ten|\d+) customers|one customer|two customers|single customer|customers? (?:accounted|represented)", s)]
    pick = (named or hits)[:1]
    return {"quote": pick[0][:400]} if pick else None


def pull_one(name: str, ticker: str, ciks: dict[str, str]) -> dict:
    row: dict = {"company": name, "ticker": ticker, "cik": ciks.get(ticker)}
    if not row["cik"]:
        row["error"] = "ticker not on the SEC list"
        return row
    facts = sec.get_json(sec.FACTS.format(cik10=row["cik"].zfill(10)))
    row.update({k: d.ttm(facts, v) for k, v in FLOW.items()})
    row.update({k: d.point(facts, v) for k, v in POINT.items()})
    rep, text = latest(row["cik"])
    yr, ytext = annual(row["cik"])
    row["report"], row["annual_report"] = rep, yr
    s, y = sentences(text), sentences(ytext)
    row["leases_not_started"] = biggest(s, LEASE_RX) or table_lease(text) or biggest(y, LEASE_RX) or table_lease(ytext)
    row["purchase_commitments"] = biggest(s, BUY_RX) or biggest(y, BUY_RX)
    xbrl = {n: v for n, v in ((n, d.point(facts, [n])) for n in d.XBRL_COMMIT) if v}
    if not row["purchase_commitments"] and xbrl:
        x = max(xbrl.values(), key=lambda v: v["end"])
        row["purchase_commitments"] = {"usd": x["usd"], "quote": f'XBRL {x["concept"]} as of {x["end"]}'}
    row["server_useful_life"] = life(s) or life(y)
    row["customer_concentration"] = concentration(s) or concentration(y)
    row["labs"] = {lab: [q[:300] for q in s + y if re.search(rf"\b{lab}\b", q)][:6] for lab in PRIVATE_LABS}
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    ciks, done = tickers(), {}
    for names in SETS.values():
        for name, t in names.items():
            if name in done:
                continue
            try:
                done[name] = pull_one(name, t, ciks)
            except Exception as e:  # noqa: BLE001 - one company must never stop the set
                done[name] = {"company": name, "ticker": t, "error": f"{type(e).__name__}: {e}"[:160]}
            print(name, "ok" if "error" not in done[name] else done[name]["error"], sum(bool(done[name].get(f)) for f in FIELDS), flush=True)
            (a.out / "pull.json").write_text(json.dumps(done, indent=1))
    lines = ["| Group | Companies | Fields found | Of possible | Share |", "|---|---|---|---|---|"]
    groups = {g: list(n) for g, n in SETS.items()}
    groups["Limited data: Nebius, TSMC"] = ["Nebius", "TSMC"]
    for g, names in groups.items():
        got = sum(bool(done[n].get(f)) for n in names for f in FIELDS)
        lines.append(f"| {g} | {len(names)} | {got} | {len(names) * len(FIELDS)} | {100 * got // (len(names) * len(FIELDS))}% |")
    lines += ["", "| Field | Found | Companies |", "|---|---|---|"]
    uniq = list(done)
    lines += [f"| {f} | {sum(bool(done[n].get(f)) for n in uniq)} | {len(uniq)} |" for f in FIELDS]
    lines += ["", "Private labs, seen only through partners' filings (sentences found):"]
    for lab in PRIVATE_LABS:
        who = {n: len(r.get("labs", {}).get(lab, [])) for n, r in done.items() if r.get("labs", {}).get(lab)}
        lines.append(f"- {lab}: {who}")
    (a.out / "completeness.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
