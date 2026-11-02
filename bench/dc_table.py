"""The data center funding table, built only from what filings disclose. Python reads every number; nothing is typed by a model or a person.

  venv/bin/python -m bench.dc_table --in results/dc-funding-1101
Sources: XBRL for spending, cash flow, cash and debt; word-for-word quotes for commitments, or the filing's own table where a company reports them only in a table.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from . import dc_funding as d, sec

LEASE = re.compile(r"not yet commenced of|have not yet commenced with future|additional lease commitments|lease obligations were", re.I)
BUY = re.compile(r"material purchase commitments of|non-cancelable contractual commitments", re.I)


def row_total(text: str, label: str) -> float | None:
    """Last number in a filing table row (in millions), which is the Total column."""
    m = re.search(re.escape(label) + r"[^A-Za-z]*", text)
    if not m:
        return None
    nums = re.findall(r"\d[\d,]*", m.group(0))
    return float(nums[-1].replace(",", "")) * 1e6 if nums else None


def biggest(rows: list[dict], rx: re.Pattern) -> dict | None:
    hit = [c for c in rows if rx.search(c["quote"])]
    return max(hit, key=lambda c: c["usd"]) if hit else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="src", type=Path, required=True)
    a = ap.parse_args()
    t = {n: json.load((a.src / f"table-{n}.json").open())["table"] for n in ("gptoss120_fw", "sonnet5")}
    out = []
    for co, cik in d.COMPANIES.items():
        r, s = t["gptoss120_fw"][co], t["sonnet5"][co]
        pool, n = r["commitments"] + s["commitments"], r["numbers"]
        lease, buy = biggest(pool, LEASE), biggest(pool, BUY)
        row = {"company": co, "as_of": n["capex"]["end"], "filing": f'{r["report"]["form"]} filed {r["report"]["filed"]}', "url": r["report"]["url"],
               "capex": n["capex"]["usd"], "op_cash": n["operating_cash_flow"]["usd"], "cash_sec": n["cash"]["usd"] + (n["securities"] or {"usd": 0})["usd"],
               "debt": n["debt"]["usd"] if n["debt"] else None, "debt_as_of": n["debt"]["end"] if n["debt"] else None,
               "leases": lease["usd"] if lease else None, "lease_quote": lease["quote"] if lease else "", "purchases": buy["usd"] if buy else None, "purchase_quote": buy["quote"] if buy else ""}
        if row["leases"] is None or row["purchases"] is None:
            _, text = d.latest_report(cik)
            if row["leases"] is None:
                row["leases"], row["lease_quote"] = row_total(text, "Leases not yet commenced"), "filing table row: Leases not yet commenced, Total column"
            if row["purchases"] is None:
                p, q = row_total(text, "Property and equipment (2)"), row_total(text, "Unconditional purchase obligations (3)")
                if p and q:
                    row["purchases"], row["purchase_quote"] = p + q, "filing table rows: Property and equipment + Unconditional purchase obligations, Total column"
        if row["purchases"] is None and n["xbrl_commitments"]:
            x = max(n["xbrl_commitments"].values(), key=lambda v: v["end"])
            row["purchases"], row["purchase_quote"] = x["usd"], f'XBRL {x["concept"]} as of {x["end"]}'
        row["forward"] = (row["leases"] or 0) + (row["purchases"] or 0)
        row["years_of_cash_flow"] = round(row["forward"] / row["op_cash"], 1)
        out.append(row)
    (a.src / "funding-table.json").write_text(json.dumps(out, indent=1))
    b = lambda v: "not found" if v is None else f"{v / 1e9:,.1f}"
    lines = ["| Company | 12 months to | Capital spending $B | Operating cash flow $B | Cash + securities $B | Debt $B | Leases not yet started $B | Purchase commitments $B | Forward total ÷ cash flow, years |", "|---|---|---|---|---|---|---|---|---|"]
    lines += [f'| {r["company"]} | {r["as_of"]} | {b(r["capex"])} | {b(r["op_cash"])} | {b(r["cash_sec"])} | {b(r["debt"])} | {b(r["leases"])} | {b(r["purchases"])} | {r["years_of_cash_flow"]} |' for r in out]
    lines += ["", "Sources:"] + [f'- {r["company"]}: {r["url"]}\n  - Leases: {r["lease_quote"][:220]}\n  - Purchases: {r["purchase_quote"][:220]}' for r in out]
    (a.src / "funding-table.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:7]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
