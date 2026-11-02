"""Search public news and community sources by keyword, with no model and no key. Saves one JSON row per story.

  python -m bench.news_search "data center power deal" --hours 48 --out results/search.jsonl
Search runs here, in Python, and never inside a model. Models only read the saved text, so a page cannot give a model tools to use.
Sources: Google News search feed and Hacker News. Headlines, sources, links and times only.
"""
from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

UA = {"User-Agent": "open-model-eval/0.1"}


def get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read()


def google_news(query: str, hours: int) -> list[dict]:
    q = urllib.parse.quote(f"{query} when:{max(1, hours)}h")
    root = ET.fromstring(get(f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"))
    rows = []
    for i in root.iter("item"):
        when = i.findtext("pubDate")
        rows.append({"title": i.findtext("title", ""), "source": i.findtext("source", "Google News"), "link": i.findtext("link", ""),
                     "published": parsedate_to_datetime(when).astimezone(timezone.utc).isoformat() if when else None, "via": "google_news"})
    return rows


def hacker_news(query: str, hours: int) -> list[dict]:
    since = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())
    url = "https://hn.algolia.com/api/v1/search_by_date?" + urllib.parse.urlencode({"query": query, "tags": "story", "numericFilters": f"created_at_i>{since}", "hitsPerPage": 50})
    return [{"title": h.get("title") or "", "source": "Hacker News", "link": h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}", "published": h.get("created_at"), "via": "hacker_news"}
            for h in json.loads(get(url)).get("hits", [])]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query")
    ap.add_argument("--hours", type=int, default=48)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    rows: list[dict] = []
    for name, fn in (("Google News", google_news), ("Hacker News", hacker_news)):
        try:
            found = fn(a.query, a.hours)
        except Exception as e:  # one source being down should not lose the other
            print(f"{name}: failed ({e})")
            continue
        print(f"{name}: {len(found)} stories")
        rows += found
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"{len(rows)} saved to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
