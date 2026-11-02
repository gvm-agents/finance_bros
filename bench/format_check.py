"""House-style check for Word tables (OUTPUT_FORMAT_STANDARDS section 5). Free, no model.

  venv/bin/python -m bench.format_check FILE.docx
Checks per table: borders on every cell, shaded header row, rows kept together, no skinny columns,
and number cells that mix a number with text. Page splits need a rendered file and are not checked here.
"""
from __future__ import annotations

import re
import sys

import docx
from docx.oxml.ns import qn

MIN_COL_IN = 0.55
NUM_TEXT = re.compile(r"^\$?\d[\d,.]*%?\s+[A-Za-z]{3,}")


def check(path: str) -> dict:
    d = docx.Document(path)
    res = {"tables": len(d.tables), "no_border": 0, "no_header_shade": 0, "rows_can_split": 0, "skinny_cols": 0, "mixed_number_cells": 0, "examples": []}
    for ti, t in enumerate(d.tables):
        pr = t._tbl.tblPr
        if pr.find(qn("w:tblBorders")) is None:
            res["no_border"] += 1
        hdr = t.rows[0].cells
        if not all(c._tc.tcPr is not None and c._tc.tcPr.find(qn("w:shd")) is not None for c in hdr):
            res["no_header_shade"] += 1
        if any(r._tr.trPr is None or r._tr.trPr.find(qn("w:cantSplit")) is None for r in t.rows):
            res["rows_can_split"] += 1
        widths = [int(g.get(qn("w:w"))) / 1440 for g in t._tbl.tblGrid.findall(qn("w:gridCol"))]
        if len(widths) > 1 and min(widths) < MIN_COL_IN:
            res["skinny_cols"] += 1
            res["examples"].append(f"table {ti + 1}: narrowest column {min(widths):.2f} in")
        for r in t.rows[1:]:
            for c in r.cells:
                if NUM_TEXT.match(c.text.strip()) and len(c.text) < 40:
                    res["mixed_number_cells"] += 1
    return res


if __name__ == "__main__":
    r = check(sys.argv[1])
    print(r)
    sys.exit(1 if (r["no_border"] or r["no_header_shade"] or r["rows_can_split"]) else 0)
