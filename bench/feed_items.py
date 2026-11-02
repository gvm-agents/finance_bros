"""Read every public feed once and save what it holds; measure how often each one updates. No model is called.

  SEC_CONTACT="Name email" venv/bin/python -m bench.feed_items --out results/feed-snapshot.jsonl --stats results/feed-stats.json
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import statistics
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from .feed_check import UA, parse_time

TAG = re.compile(r"<[^>]+>")


def _local(t: str) -> str:
    return t.rsplit("}", 1)[-1]


def rows_xml(body: bytes) -> list[dict]:
    out = []
    for el in ET.fromstring(body).iter():
        if _local(el.tag) not in ("item", "entry"):
            continue
        r = {"title": "", "link": "", "time": None, "summary": ""}
        for c in el:
            n = _local(c.tag)
            if n == "title":
                r["title"] = html.unescape(c.text or "").strip()
            elif n == "link":
                r["link"] = c.get("href") or (c.text or "").strip() or r["link"]
            elif n in ("pubDate", "published", "updated", "date") and r["time"] is None:
                r["time"] = parse_time(c.text or "")
            elif n in ("description", "summary", "content") and not r["summary"]:
                r["summary"] = TAG.sub(" ", html.unescape(c.text or "")).strip()[:500]
        out.append(r)
    return out


def rows_json(body: bytes, key: str) -> list[dict]:
    out = []
    for r in json.loads(body).get(key, []):
        out.append({"title": r.get("title") or r.get("story_title") or "", "link": r.get("url") or "", "summary": "",
                    "time": parse_time(r.get("created_at") or r.get("seendate") or "")})
    return out


def cadence(minutes: float | None) -> str:
    if minutes is None:
        return "Unknown"
    for lim, name in ((15, "Near real time (minutes)"), (120, "Hourly"), (720, "Several a day"), (2160, "Daily"), (12000, "Weekly")):
        if minutes <= lim:
            return name
    return "Less than weekly"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--stats", type=Path, required=True)
    a = ap.parse_args()
    feeds = json.load(open(Path(__file__).with_name("feeds.json")))["feeds"]
    now, stats = datetime.now(timezone.utc), []
    with a.out.open("w") as f:
        for fd in feeds:
            ua = os.environ.get("SEC_CONTACT", "public research") if fd.get("sec") else UA
            s = {"name": fd["name"], "group": fd["group"], "url": fd["url"], "status": "error", "items": 0}
            t0 = time.time()
            try:
                with urllib.request.urlopen(urllib.request.Request(fd["url"], headers={"User-Agent": ua}), timeout=20) as r:
                    body, s["status"] = r.read(), r.status
                rows = rows_json(body, fd["json"]) if fd.get("json") else rows_xml(body)
                ts = sorted((x["time"] for x in rows if x["time"]), reverse=True)[:40]
                gaps = [(ts[i] - ts[i + 1]).total_seconds() / 60 for i in range(len(ts) - 1)]
                gaps = [g for g in gaps if g >= 0]
                s["items"] = len(rows)
                s["newest_min"] = round((now - ts[0]).total_seconds() / 60) if ts else None
                s["median_gap_min"] = round(statistics.median(gaps), 1) if gaps else None
                s["cadence"] = cadence(s["median_gap_min"])
                for x in rows[:60]:
                    f.write(json.dumps({"source": fd["name"], "group": fd["group"], **x, "time": x["time"].isoformat() if x["time"] else None}) + "\n")
            except urllib.error.HTTPError as e:
                s["status"] = e.code
            except Exception as e:  # noqa: BLE001 - one bad feed must not stop the list
                s["error"] = f"{type(e).__name__}: {e}"[:80]
            s["seconds"] = round(time.time() - t0, 2)
            stats.append(s)
            print(f"{str(s['status']):6}{s['items']:5}  gap {str(s.get('median_gap_min')):>8}  {s.get('cadence', '-'):24} {s['name']}", flush=True)
            time.sleep(0.4 if "gdelt" not in fd["url"] else 6)
    a.stats.write_text(json.dumps(stats, indent=1))
    print(sum(s["status"] == 200 and s["items"] > 0 for s in stats), "of", len(stats), "working")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
