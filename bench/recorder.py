"""Keep watching public feeds and save each new headline once, with its source and the time we first saw it.

  SEC_CONTACT="Name email" python -m bench.recorder                     # runs until stopped
  python -m bench.recorder --once --out results/recorder-test           # one pass, then exit

Files in results/recorder/:
  headlines-YYYY-MM-DD.jsonl   one line per new headline, grouped by the day we saw it (UTC)
  feeds.json                   last check of each feed: status, items, new items, last error
Feeds are read from bench/feeds.json on every pass, so a new feed needs no restart. One bad feed never stops the rest.
Live streams (the `streams` list) run alongside the feeds and reconnect by themselves. A stream carries far more than anyone
should keep, so only posts in English that match a watched topic are saved, at most KEEP_PER_MINUTE a stream; a count of the rest is kept.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .feed_check import UA
from .feed_items import rows_json, rows_xml
from .live_news import tag

ROOT = Path(__file__).resolve().parent.parent
FEEDS = Path(__file__).with_name("feeds.json")
OUT = ROOT / "results" / "recorder"
EVERY = {"sec": 120, "gdelt": 900, "default": 300}  # seconds between looks at one feed; SEC and GDELT ask for restraint
SPACE = re.compile(r"\W+")
KEEP_PER_MINUTE = 5


def key(title: str, link: str = "") -> str:
    """Same story text means same row, whatever the feed's tracking link. Trailing ' - Publisher' is ignored."""
    t = SPACE.sub(" ", title.rsplit(" - ", 1)[0].lower()).strip()
    return hashlib.sha1((t or link).encode()).hexdigest()[:16]


def wait_for(feed: dict) -> int:
    if feed.get("every"):
        return int(feed["every"])
    if feed.get("sec"):
        return EVERY["sec"]
    return EVERY["gdelt"] if "gdelt" in feed["url"] else EVERY["default"]


def read(feed: dict, timeout: int = 20) -> list[dict]:
    ua = os.environ.get("SEC_CONTACT", "public research") if feed.get("sec") else UA
    with urllib.request.urlopen(urllib.request.Request(feed["url"], headers={"User-Agent": ua}), timeout=timeout) as r:
        body = r.read()
    return rows_json(body, feed["json"]) if feed.get("json") else rows_xml(body)


def post_row(raw: str | bytes) -> dict | None:
    """A new English Bluesky post -> a row like a feed's. Anything else -> None."""
    try:
        m = json.loads(raw)
        c = m["commit"]
        r = c["record"]
        if c.get("operation") != "create" or "en" not in (r.get("langs") or []) or "reply" in r or not r.get("text"):
            return None
        return {"title": r["text"][:240], "summary": "", "link": f"https://bsky.app/profile/{m['did']}/post/{c['rkey']}",
                "time": datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00"))}
    except (ValueError, KeyError, TypeError, AttributeError):
        return None


def load_seen(out: Path) -> set[str]:
    seen: set[str] = set()
    for f in sorted(out.glob("headlines-*.jsonl")):
        for line in f.open():
            try:
                seen.add(json.loads(line)["id"])
            except (ValueError, KeyError):
                continue
    return seen


class Recorder:
    def __init__(self, out: Path, reader=read):
        self.out, self.reader = Path(out), reader
        self.out.mkdir(parents=True, exist_ok=True)
        self.seen = load_seen(self.out)
        self.next: dict[str, float] = {}
        self.state: dict[str, dict] = {}
        self.streams: dict[str, dict] = {}
        self.lock = threading.Lock()

    def save(self, feed: dict, rows: list[dict]) -> int:
        now = datetime.now(timezone.utc)
        path = self.out / f"headlines-{now:%Y-%m-%d}.jsonl"
        new = 0
        with self.lock, path.open("a") as f:
            for r in rows:
                if not r.get("title"):
                    continue
                k = key(r["title"], r.get("link", ""))
                if k in self.seen:
                    continue
                self.seen.add(k)
                new += 1
                f.write(json.dumps({"id": k, "source": feed["name"], "group": feed["group"], "title": r["title"], "link": r.get("link", ""),
                                    "time": r["time"].isoformat() if r.get("time") else None, "seen": now.isoformat(timespec="seconds"), "summary": r.get("summary", "")}) + "\n")
        return new

    def stream_message(self, feed: dict, raw: str | bytes) -> bool:
        """One message from a stream: keep it only if it is English, on a watched topic and within this minute's allowance."""
        s = self.streams.setdefault(feed["name"], {"read": 0, "matched": 0, "kept": 0, "minute": 0, "this_minute": 0})
        s["read"] += 1
        row = post_row(raw)
        if not row or not tag(row["title"]):
            return False
        s["matched"] += 1
        minute = int(time.time() // 60)
        if minute != s["minute"]:
            s.update(minute=minute, this_minute=0)
        if s["this_minute"] >= int(feed.get("keep_per_minute", KEEP_PER_MINUTE)):
            return False
        s["this_minute"] += 1
        got = self.save(feed, [row])
        s["kept"] += got
        return bool(got)

    def stream_loop(self, feed: dict, connect=None, forever: bool = True) -> None:
        """Stay connected. A dropped stream waits a little longer each time, up to 2 minutes, then reconnects."""
        if connect is None:
            from websockets.sync.client import connect
        wait = 5
        while True:
            try:
                with connect(feed["url"], open_timeout=20, close_timeout=5, max_size=2 ** 20) as ws:
                    self.streams.setdefault(feed["name"], {"read": 0, "matched": 0, "kept": 0, "minute": 0, "this_minute": 0})["status"] = "ok"
                    wait = 5
                    for raw in ws:
                        self.stream_message(feed, raw)
            except Exception as e:  # noqa: BLE001 - any drop means reconnect, never stop the recorder
                self.streams.setdefault(feed["name"], {"read": 0, "matched": 0, "kept": 0, "minute": 0, "this_minute": 0})["status"] = f"{type(e).__name__}: {e}"[:120]
            if not forever:
                return
            time.sleep(wait)
            wait = min(wait * 2, 120)

    def start_streams(self, feeds: list[dict]) -> None:
        for feed in feeds:
            if feed["name"] not in self.streams:
                self.streams[feed["name"]] = {"read": 0, "matched": 0, "kept": 0, "minute": 0, "this_minute": 0, "status": "starting"}
                threading.Thread(target=self.stream_loop, args=(feed,), daemon=True).start()

    def one_pass(self, feeds: list[dict]) -> int:
        total = 0
        for feed in feeds:
            now = time.time()
            if now < self.next.get(feed["name"], 0):
                continue
            self.next[feed["name"]] = now + wait_for(feed)
            s = {"checked": datetime.now(timezone.utc).isoformat(timespec="seconds"), "group": feed["group"]}
            try:
                rows = self.reader(feed)
                new = self.save(feed, rows)
                total += new
                s.update(status="ok", items=len(rows), new=new)
            except urllib.error.HTTPError as e:
                s.update(status=e.code)
            except Exception as e:  # noqa: BLE001 - one bad feed must not stop the rest
                s.update(status="error", error=f"{type(e).__name__}: {e}"[:120])
            old = self.state.get(feed["name"], {})
            s["total_new"] = old.get("total_new", 0) + s.get("new", 0)
            self.state[feed["name"]] = s
            time.sleep(0.3)
        tmp = self.out / "feeds.json.tmp"
        tmp.write_text(json.dumps({**self.state, **{k: {"stream": True, **v} for k, v in self.streams.items()}}, indent=1))
        tmp.replace(self.out / "feeds.json")
        return total


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--once", action="store_true", help="one pass, then exit")
    ap.add_argument("--pause", type=int, default=30, help="seconds between passes")
    a = ap.parse_args()
    rec = Recorder(a.out)
    while True:
        conf = json.loads(FEEDS.read_text(encoding="utf-8"))
        if not a.once:
            rec.start_streams(conf.get("streams", []))
        new = rec.one_pass(conf["feeds"])
        ok = sum(s.get("status") == "ok" for s in rec.state.values())
        live = "; ".join(f"{k}: read {v['read']}, matched {v['matched']}, kept {v['kept']}" for k, v in rec.streams.items())
        print(f"{time.strftime('%H:%M:%S')} new {new}, total {len(rec.seen)}, feeds answering {ok} of {len(rec.state)}. {live}", flush=True)
        if a.once:
            return 0
        time.sleep(a.pause)


if __name__ == "__main__":
    raise SystemExit(main())
