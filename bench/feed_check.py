"""Read-only test of the public news feeds in bench/feeds.json. No key, no model call, nothing stored.

  SEC_CONTACT="Name email" venv/bin/python -m bench.feed_check [--out results/feed-check.json]
Prints: status, items, age of the newest item in minutes, and fetch time.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import email.utils
import json
import os
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (feed check; public research)"


def parse_time(s: str) -> datetime | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        d = email.utils.parsedate_to_datetime(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        pass
    if re.fullmatch(r"\d{8}T\d{6}Z", s):
        return datetime.strptime(s, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def times_xml(body: bytes) -> tuple[int, list[datetime]]:
    root = ET.fromstring(body)
    n, out = 0, []
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1] in ("item", "entry"):
            n += 1
            for c in el:
                if c.tag.rsplit("}", 1)[-1] in ("pubDate", "published", "updated", "date"):
                    t = parse_time(c.text or "")
                    if t:
                        out.append(t)
                        break
    return n, out


def times_json(body: bytes, key: str) -> tuple[int, list[datetime]]:
    rows = json.loads(body).get(key, [])
    out = []
    for r in rows:
        t = r.get("created_at") or r.get("seendate") or r.get("indexedAt")
        t = parse_time(t) if t else None
        if t:
            out.append(t)
    return len(rows), out


def check(f: dict) -> dict:
    ua = os.environ.get("SEC_CONTACT", "public research") if f.get("sec") else UA
    start = time.time()
    r = {"name": f["name"], "group": f["group"], "url": f["url"]}
    try:
        with urllib.request.urlopen(urllib.request.Request(f["url"], headers={"User-Agent": ua}), timeout=25) as resp:
            body, r["status"] = resp.read(), resp.status
        n, ts = times_json(body, f["json"]) if f.get("json") else times_xml(body)
        r["items"] = n
        if ts:
            r["newest_min"] = round((datetime.now(timezone.utc) - max(ts)).total_seconds() / 60)
    except urllib.error.HTTPError as e:
        r["status"], r["items"] = e.code, 0
    except Exception as e:  # one bad feed must not stop the list
        r["status"], r["items"], r["error"] = "error", 0, f"{type(e).__name__}: {e}"[:100]
    r["seconds"] = round(time.time() - start, 2)
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    feeds = json.load(open(Path(__file__).with_name("feeds.json")))["feeds"]
    with cf.ThreadPoolExecutor(1) as ex:  # one at a time; GDELT allows one request every 5 seconds
        rows = list(ex.map(check, feeds))
    for r in rows:
        print(f"{str(r['status']):6} {r['items']:4} items  newest {str(r.get('newest_min', '-')):>7} min  {r['seconds']:5}s  {r['name']}  {r.get('error', '')}")
    print(f"{sum(r['status'] == 200 and r['items'] > 0 for r in rows)} of {len(rows)} working")
    if a.out:
        a.out.write_text(json.dumps(rows, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
