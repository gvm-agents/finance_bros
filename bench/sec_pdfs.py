"""PDF library of tech-company SEC filings (public data, MacBook only).

Picks companies by SEC industry code from every ticker on EDGAR plus every S-1 / F-1
filer in the window (so pre-IPO names such as Anthropic are included), lists their major
filings, and prints each filing's main document to PDF with headless Chrome. Exhibits and
images inside filings are left out (Chrome runs with the network blocked).

Every result goes into a CSV as it happens, so a stopped run resumes where it left off.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path

from . import sec

ROOT = Path("data/sec_pdfs")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TICKERS = "https://www.sec.gov/files/company_tickers.json"
BULK = "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip"
FORM_IDX = "https://www.sec.gov/Archives/edgar/full-index/{y}/QTR{q}/form.idx"
FORMS = {"10-K", "10-Q", "20-F", "40-F", "S-1", "S-1/A", "F-1", "F-1/A", "1-A", "1-A/A", "1-K", "10-12B", "10-12G"}
IPO_FORMS = ("S-1", "S-1/A", "F-1", "F-1/A", "1-A", "1-A/A", "10-12B", "10-12G")  # includes non-listed filers
FIELDS = ["cik", "name", "ticker", "sic", "sic_description", "category", "form", "filed",
          "accession", "source_url", "pdf", "pdf_bytes", "status", "detail"]
SIC_CATEGORIES = {
    "biotech and pharma": {"2833", "2834", "2835", "2836", "8731"},
    "computers and hardware": {"3570", "3571", "3572", "3575", "3576", "3577", "3578", "3579"},
    "chips and electronics": {"3559", "3670", "3672", "3674", "3677", "3678", "3679", "3827"},
    "communications equipment": {"3661", "3663", "3669", "3651", "3652"},
    "telecom and network services": {"4812", "4813", "4822", "4899"},
    "robotics and automation": {"3569", "3822", "3823", "3824", "3825", "3829"},
    "energy tech": {"3600", "3612", "3613", "3620", "3621", "3690", "3691", "3692"},
    "medical devices": {"3826", "3841", "3842", "3844", "3845"},
    "software and internet": {"7370", "7371", "7372", "7373", "7374", "7375", "7376", "7377", "7378", "7379", "7389", "5961"},
    "fintech and crypto": {"6199"},
    "autos and mobility": {"3711"},
    "defense and sensing": {"3812", "3721", "3724", "3728", "3760", "3761", "3764", "3769"},
}
EXTRA_TICKERS = {"TSLA": "energy tech", "RIVN": "energy tech", "LCID": "energy tech",  # coded as car makers
                 # Tech-dependent names whose SEC industry code is mostly non-tech
                 "EQIX": "data centers and power", "DLR": "data centers and power", "IRM": "data centers and power",
                 "AMT": "data centers and power", "ETN": "data centers and power", "CEG": "data centers and power",
                 "VST": "data centers and power", "TLN": "data centers and power", "OKLO": "data centers and power",
                 "SMR": "data centers and power", "NNE": "data centers and power", "LEU": "data centers and power",
                 "CCI": "data centers and power", "SBAC": "data centers and power", "GLXY": "data centers and power",
                 "FRMI": "data centers and power", "NVT": "data centers and power", "JCI": "data centers and power",
                 "PWR": "data centers and power", "EME": "data centers and power", "FIX": "data centers and power",
                 "BWXT": "data centers and power", "CCJ": "data centers and power", "NEE": "data centers and power",
                 "GLW": "chips and electronics", "TEL": "chips and electronics", "ENTG": "chips and electronics",
                 "SNX": "computers and hardware", "ZBRA": "robotics and automation", "AXON": "defense and sensing",
                 "HWM": "defense and sensing", "TXT": "defense and sensing", "CW": "defense and sensing",
                 "NFLX": "software and internet", "SPOT": "software and internet", "BKNG": "software and internet",
                 "ABNB": "software and internet", "EXPE": "software and internet", "SE": "software and internet",
                 "JD": "software and internet", "ROKU": "software and internet", "TME": "software and internet",
                 "CVNA": "software and internet", "AFRM": "fintech and crypto", "FUTU": "fintech and crypto",
                 "GD": "defense and sensing", "HII": "defense and sensing", "HOOD": "fintech and crypto", "SOFI": "fintech and crypto"}


def category(sic: str) -> str | None:
    return next((c for c, codes in SIC_CATEGORIES.items() if str(sic) in codes), None)


def window_start(today: dt.date | None = None) -> str:
    d = today or dt.date.today()
    y, m = (d.year - 1, d.month - 1) if d.month > 1 else (d.year - 2, 12)
    day = min(d.day, 28 if m == 2 else 30)
    return dt.date(y, m, day).isoformat()


def quarters(start: str, end: dt.date) -> list[tuple[int, int]]:
    y, q = int(start[:4]), (int(start[5:7]) - 1) // 3 + 1
    out = []
    while (y, q) <= (end.year, (end.month - 1) // 3 + 1):
        out.append((y, q))
        y, q = (y + 1, 1) if q == 4 else (y, q + 1)
    return out


def parse_form_idx(text: str, forms=IPO_FORMS) -> set[str]:
    """CIKs from an EDGAR form.idx listing (fixed columns: form first, CIK before the date)."""
    out = set()
    for line in text.splitlines():
        m = re.match(r"(\S+(?:/A)?)\s+.*?\s(\d{1,10})\s+\d{4}-\d{2}-\d{2}\s", line)
        if m and m.group(1) in forms:
            out.add(str(int(m.group(2))))
    return out


def ipo_ciks(start: str, log=print) -> set[str]:
    out: set[str] = set()
    for y, q in quarters(start, dt.date.today()):
        try:
            out |= parse_form_idx(sec.get(FORM_IDX.format(y=y, q=q)))
        except sec.SecError as exc:
            log(f"  index {y} Q{q}: {exc}")
    return out


def recent_filings(sub: dict, start: str, load=lambda name: sec.get_json("https://data.sec.gov/submissions/" + name)) -> list[dict]:
    """Major filings on or after start, including the older-filings file when the recent list stops short."""
    blocks = [sub.get("filings", {}).get("recent", {})]
    dates = blocks[0].get("filingDate") or []
    if dates and min(dates) > start:
        for extra in sub.get("filings", {}).get("files", []):
            if extra.get("filingTo", "") >= start:
                blocks.append(load(extra["name"]))
    out = []
    for b in blocks:
        for form, date, acc, doc in zip(b.get("form", []), b.get("filingDate", []),
                                        b.get("accessionNumber", []), b.get("primaryDocument", [])):
            if form in FORMS and date >= start and doc:
                out.append({"form": form, "filed": date, "acc": acc, "doc": doc})
    return out


def safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")[:60] or "unknown"


def pdf_path(rec: dict) -> Path:
    label = rec["ticker"] or safe(rec["name"])
    return ROOT / "pdfs" / f"{safe(label)}_{rec['cik']}" / f"{rec['filed']}_{safe(rec['form'])}_{rec['accession']}.pdf"


def clean_html(raw: bytes) -> bytes:
    """Drop scripts and SEC's hidden inline-XBRL header so the printed page is the filing itself."""
    text = raw.decode("utf-8", "replace")
    text = re.sub(r"<script\b.*?</script>", "", text, flags=re.S | re.I)
    return re.sub(r"<ix:header\b.*?</ix:header>", "", text, flags=re.S | re.I).encode("utf-8")


def render(raw: bytes, doc: str, out: Path, timeout: int = 240) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if doc.lower().endswith(".pdf"):
        out.write_bytes(raw)
        return
    with tempfile.TemporaryDirectory(prefix="secpdf") as tmp:
        page = Path(tmp) / "filing.html"
        body = clean_html(raw) if not doc.lower().endswith(".txt") else b"<pre>" + raw.replace(b"<", b"&lt;") + b"</pre>"
        page.write_bytes(body)
        part = out.with_suffix(".part")
        cmd = [CHROME, "--headless=new", "--disable-gpu", "--no-first-run", "--no-pdf-header-footer",
               f"--user-data-dir={tmp}/profile", '--host-resolver-rules=MAP * ~NOTFOUND',
               f"--print-to-pdf={part}", page.as_uri()]
        subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
        if not part.exists() or part.stat().st_size < 1000:
            part.unlink(missing_ok=True)
            raise RuntimeError("Chrome produced no PDF")
        part.replace(out)


def bulk_zip(log=print) -> zipfile.ZipFile:
    """SEC's nightly file of every company's filing list: far quicker than one request per company."""
    path = ROOT / "submissions.zip"
    if not path.exists() or time.time() - path.stat().st_mtime > 86400:
        log("downloading SEC bulk filing list")
        part = path.with_suffix(".part")
        req = urllib.request.Request(BULK, headers={"User-Agent": sec.contact(), "Accept-Encoding": "identity"})
        with urllib.request.urlopen(req, timeout=120) as r, part.open("wb") as fh:
            shutil.copyfileobj(r, fh, 1 << 20)
        part.replace(path)
    return zipfile.ZipFile(path)


def build_plan(start: str, only: set[str] | None, log=print) -> list[dict]:
    tick = sec.get_json(TICKERS)
    bulk = bulk_zip(log)
    members = set(bulk.namelist())

    def load(name: str) -> dict:
        return json.loads(bulk.read(name))

    tickers = {}
    for v in tick.values():
        tickers.setdefault(str(v["cik_str"]), v["ticker"])
    extra = {str(v["cik_str"]): EXTRA_TICKERS[v["ticker"]] for v in tick.values() if v["ticker"] in EXTRA_TICKERS}
    ciks = sorted(set(tickers) | ipo_ciks(start, log), key=int)
    if only is not None:
        ciks = [c for c in ciks if c in only]
    log(f"checking {len(ciks)} companies")
    plan, seen = [], 0
    for cik in ciks:
        seen += 1
        if seen % 500 == 0:
            log(f"  checked {seen}, {len(plan)} filings so far")
        try:
            member = f"CIK{int(cik):010d}.json"
            sub = load(member) if member in members else sec.submissions(cik)
            sic = str(sub.get("sic") or "")
            cat = extra.get(cik) or category(sic)
            if not cat:
                continue
            for f in recent_filings(sub, start, load):
                acc = f["acc"].replace("-", "")
                plan.append({"cik": cik, "name": sub.get("name", ""), "ticker": tickers.get(cik, ""), "sic": sic,
                             "sic_description": sub.get("sicDescription", ""), "category": cat, "form": f["form"],
                             "filed": f["filed"], "accession": f["acc"], "doc": f["doc"],
                             "source_url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{f['doc']}"})
        except Exception as exc:  # noqa: BLE001
            log(f"  skip {cik}: {exc}")
    return plan


def done_keys(manifest: Path) -> set[str]:
    if not manifest.exists():
        return set()
    with manifest.open(newline="") as fh:
        return {r["accession"] for r in csv.DictReader(fh) if r["status"] == "ok"}


_pace = threading.Lock()
_next_slot = [0.0]


def fetch_raw(url: str) -> bytes:
    """Same contact header as sec.get, shared across workers at under SEC's 10 requests a second."""
    with _pace:
        now = time.time()
        slot = max(now, _next_slot[0])
        _next_slot[0] = slot + 0.12
    if slot > now:
        time.sleep(slot - now)
    req = urllib.request.Request(url, headers={"User-Agent": sec.contact(), "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def fetch_and_render(rec: dict) -> None:
    render(fetch_raw(rec["source_url"]), rec["doc"], pdf_path(rec))


def run(args) -> int:
    sec.contact()
    ROOT.mkdir(parents=True, exist_ok=True)
    manifest = ROOT / "manifest.csv"
    only = {str(int(c)) for c in args.ciks.split(",")} if args.ciks else None
    start = args.start or window_start()
    plan_file = ROOT / ("plan.json" if only is None else "plan_test.json")
    if plan_file.exists() and only is None:
        plan = json.loads(plan_file.read_text())
    else:
        plan = build_plan(start, only)
        plan_file.write_text(json.dumps(plan))
    print(f"{len(plan)} filings across {len({p['cik'] for p in plan})} companies since {start}", flush=True)
    if args.plan_only:
        return 0
    done = done_keys(manifest)
    todo = [p for p in plan if p["accession"] not in done]
    new_file = not manifest.exists()
    ok = fail = 0
    with manifest.open("a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        if new_file:
            writer.writeheader()

        def finish(rec: dict, status: str, detail: str = "") -> None:
            nonlocal ok, fail
            path = pdf_path(rec)
            size = path.stat().st_size if status == "ok" else 0
            writer.writerow({**rec, "pdf": str(path), "pdf_bytes": size, "status": status, "detail": detail[:200]})
            fh.flush()
            ok, fail = ok + (status == "ok"), fail + (status != "ok")
            if (ok + fail) % 100 == 0:
                print(f"  {ok} ok, {fail} failed, {len(todo) - ok - fail} left", flush=True)

        with ThreadPoolExecutor(args.workers) as pool:
            pending: dict = {}

            def drain(limit: int) -> None:
                while len(pending) >= limit:
                    finished, _ = wait(pending, return_when=FIRST_COMPLETED)
                    for fut in finished:
                        rec = pending.pop(fut)
                        exc = fut.exception()
                        finish(rec, "failed" if exc else "ok", repr(exc) if exc else "")

            for rec in todo:
                drain(args.workers * 2)
                pending[pool.submit(fetch_and_render, rec)] = rec
            drain(1)
    print(f"finished: {ok} ok, {fail} failed", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", help="first filing date, YYYY-MM-DD (default: 13 months ago)")
    ap.add_argument("--ciks", help="comma-separated CIKs, for a test")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--plan-only", action="store_true", help="list the filings, render nothing")
    args = ap.parse_args(argv)
    if not shutil.which(CHROME) and not Path(CHROME).exists():
        print("Google Chrome not found", file=sys.stderr)
        return 1
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
