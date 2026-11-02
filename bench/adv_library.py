"""Download SEC's monthly Form ADV files for a window of months (public data, MacBook only).

Sources: reports.adviserinfo.sec.gov monthly files for Part 1 filing data, Part 2 brochures,
Part 3 Firm CRS (data and documents) and ADV-W, plus sec.gov's monthly adviser lists for both
registered and exempt reporting advisers. Each result goes into a CSV as it happens, and a
file already on disk at the listed size is skipped, so a stopped run resumes.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import re
import time
import urllib.request
from pathlib import Path

from . import sec

ROOT = Path("data/adv_library")
BASE = "https://reports.adviserinfo.sec.gov/reports/foia"
META = BASE + "/reports_metadata.json"
LISTS_PAGE = ("https://www.sec.gov/data-research/sec-markets-data/"
              "information-about-registered-investment-advisers-exempt-reporting-advisers")
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
FIELDS = ["section", "file", "url", "bytes", "status", "detail"]


def month_of(name: str) -> str | None:
    """YYYY-MM a monthly file covers, from its name: the last date in it, or a month word."""
    dates = re.findall(r"20\d{6}", name)
    if dates:
        return f"{dates[-1][:4]}-{dates[-1][4:6]}"
    m = re.search(r"(20\d\d)_([A-Za-z]+)", name)
    if m and m.group(2) in MONTHS:
        return f"{m.group(1)}-{MONTHS.index(m.group(2)) + 1:02d}"
    return None


def month_window(today: dt.date, n: int = 13) -> list[str]:
    """The n most recent complete months."""
    y, m = today.year, today.month
    out = []
    for _ in range(n):
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
        out.append(f"{y}-{m:02d}")
    return out


def adviser_files(meta: dict, months: set[str]) -> list[dict]:
    out = []
    for section, years in meta.items():
        for year, block in years.items():
            if not str(year).isdigit():
                continue
            for f in block.get("files") or []:
                if month_of(f["fileName"]) in months:
                    out.append({"section": section, "file": f["fileName"], "bytes": f.get("size") or 0,
                                "url": f"{BASE}/{section}/{year}/{f['fileName']}"})
    return out


def list_files(page: str, months: set[str]) -> list[dict]:
    """SEC's monthly adviser lists; names carry mmddyy or mmyyyy, and two months published none."""
    out = []
    for href in sorted(set(re.findall(r'href="(/files/investment/data/[^"]+\.zip)"', page))):
        name = href.rsplit("/", 1)[-1]
        m = re.match(r"ia(\d{2})(\d{2})(\d{2,4})", name)
        if not m:
            continue
        mm, rest, yy = m.group(1), m.group(2), m.group(3)
        year = 2000 + int(yy) if len(yy) == 2 else int(yy)
        month = f"{year}-{mm}"
        if len(yy) == 2 and int(rest) > 31:  # ia122025.zip: month, then a four-digit year
            month = f"20{rest}-{mm}"
        if month in months:
            out.append({"section": "adviserLists", "file": name, "bytes": 0, "url": "https://www.sec.gov" + href})
    return out


def download(url: str, dest: Path) -> int:
    part = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": sec.contact(), "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=120) as r, part.open("wb") as fh:
        while chunk := r.read(1 << 20):
            fh.write(chunk)
    part.replace(dest)
    return dest.stat().st_size


def part1_pdfs(cutoff: str, workers: int = 6) -> None:
    """Each adviser's current Form ADV (Parts 1 and 3 as filed) as a PDF, for registered advisers filing since cutoff."""
    import csv as _csv
    import glob
    import threading
    import zipfile
    from concurrent.futures import ThreadPoolExecutor

    from . import adv
    newest = sorted(glob.glob(str(ROOT / "adviserLists" / "ia09012026-registered.zip")))[-1]
    with zipfile.ZipFile(newest) as z:
        rows = list(_csv.DictReader(io_text(z)))
    crds = sorted({r["Organization CRD#"].strip() for r in rows if iso(r.get("Latest ADV Filing Date", "")) >= cutoff})
    out = ROOT / "part1Pdfs"
    out.mkdir(exist_ok=True)
    manifest = (ROOT / "part1_manifest.csv").open("a", newline="")
    writer = csv.writer(manifest)
    lock = threading.Lock()
    slot = [0.0]
    todo = [c for c in crds if not (out / f"{c}.pdf").exists()]
    print(f"{len(crds)} advisers, {len(todo)} to fetch", flush=True)

    def one(crd: str) -> None:
        with lock:
            now = time.time()
            at = max(now, slot[0])
            slot[0] = at + 0.15
        if at > now:
            time.sleep(at - now)
        try:
            size = download(adv.REPORT.format(crd=crd), out / f"{crd}.pdf")
            row = [crd, size, "ok", ""]
        except Exception as exc:  # noqa: BLE001 - one bad filing must not stop the batch
            row = [crd, 0, "failed", repr(exc)[:150]]
        with lock:
            writer.writerow(row)
            manifest.flush()

    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(one, todo))
    print("finished part 1 PDFs", flush=True)


def io_text(z) -> "io.StringIO":
    name = next(n for n in z.namelist() if n.lower().endswith(".csv"))
    return io.StringIO(z.read(name).decode("latin-1"))


def iso(date: str) -> str:
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", date.strip())
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--months", type=int, default=13)
    ap.add_argument("--plan-only", action="store_true", help="list the files, download nothing")
    ap.add_argument("--part1-pdfs", metavar="YYYY-MM-DD", help="instead, fetch each adviser's Part 1 PDF, filed since this date")
    args = ap.parse_args(argv)
    sec.contact()
    ROOT.mkdir(parents=True, exist_ok=True)
    if args.part1_pdfs:
        part1_pdfs(args.part1_pdfs)
        return 0
    months = set(month_window(dt.date.today(), args.months))
    meta = json.loads(sec.get(META))
    plan = adviser_files(meta, months) + list_files(sec.get(LISTS_PAGE), months)
    total = sum(p["bytes"] for p in plan)
    print(f"{len(plan)} files for {min(months)} to {max(months)}, {total / 1e9:.1f} GB listed", flush=True)
    if args.plan_only:
        for p in plan:
            print(f"  {p['section']:16} {p['file']} {p['bytes'] / 1e6:.0f} MB")
        return 0
    manifest = ROOT / "manifest.csv"
    new_file = not manifest.exists()
    with manifest.open("a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        for p in sorted(plan, key=lambda x: x["bytes"]):
            dest = ROOT / p["section"] / p["file"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and (not p["bytes"] or dest.stat().st_size == p["bytes"]):
                continue
            try:
                size = download(p["url"], dest)
                writer.writerow({**p, "bytes": size, "status": "ok", "detail": ""})
                print(f"  ok {p['file']} {size / 1e6:.0f} MB", flush=True)
            except Exception as exc:  # noqa: BLE001 - one bad file must not stop the batch
                writer.writerow({**p, "status": "failed", "detail": repr(exc)[:200]})
                print(f"  FAILED {p['file']}: {exc}", flush=True)
            fh.flush()
    print("finished", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
