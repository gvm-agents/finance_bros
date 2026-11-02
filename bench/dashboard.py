"""The local dashboard: a page in your browser, served by this one Python process. Stop it with Ctrl+C.

  python -m bench.dashboard --demo                                   # saved data, no keys; works on any machine
  python -m bench.dashboard --demo --replay demo/headlines.jsonl --speed 600    # headlines arrive as if live
  python -m bench.dashboard --run my-run                             # live: recorder files plus one run
  python -m bench.dashboard --run my-run --replay results/recorder/headlines-2026-11-02.jsonl --speed 60   # no network needed

Then open http://127.0.0.1:8765. It holds no keys and listens on this machine only unless you pass --host.
"""
from __future__ import annotations

import argparse
import collections
import html
import ipaddress
import json
import re
import socket
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import coordinator as co
from . import goals as G
from . import router, triage_eval
from .feed_check import UA
from .live_news import TOPICS, tag

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "dashboard" / "index.html"
DEMO = ROOT / "demo"
RECORDER = ROOT / "results" / "recorder"
MAX_ROWS = 6000
RADAR = {"Site announcements": ("campus", "breaks ground", "groundbreaking", "new data center", "site selection", "to build"),
         "Power deals": ("power purchase", "ppa", "nuclear", "gas turbine", "megawatt", "gigawatt", " mw ", " gw ", "power deal", "electricity supply"),
         "Permits and zoning": ("permit", "zoning", "rezoning", "approval", "planning commission", "county board"),
         "Local opposition": ("oppose", "opposition", "residents", "moratorium", "protest", "lawsuit", "ban on data"),
         "Competitor capacity": ("capacity", "expansion", "coreweave", "digital realty", "equinix", "nebius", "neocloud", "lease"),
         "Utility filings": ("utility", "utilities", "rate case", "ferc", "pjm", "ercot", "interconnection", "grid"),
         "Customer commitments": ("signed", "contract", "commitment", "agreement", "backlog", "billion deal")}
TAGS = re.compile(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", re.S | re.I)


def parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(ts)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def radar_tags(text: str) -> list[str]:
    t = f" {text.lower()} "
    return [k for k, ws in RADAR.items() if any(w in t for w in ws)]


class Store:
    """Everything the page reads. Replay mode shows only what had arrived by the replay clock."""

    def __init__(self, demo: bool, run: str | None, replay: Path | None, speed: float, runs: Path = co.RUNS, recorder: Path = RECORDER):
        self.demo, self.run, self.replay, self.speed, self.runs, self.recorder = demo, run, replay, speed, runs, recorder
        self.t0 = time.time()
        self.cache: tuple = (0.0, [])
        self.goals_file = (ROOT / "results" / "goals-demo.json") if demo else G.FILE
        self.sims: dict = {}
        self.sim_lock = threading.Lock()

    def source_files(self) -> list[Path]:
        if self.replay:
            return [self.replay]
        return [DEMO / "headlines.jsonl"] if self.demo else sorted(self.recorder.glob("headlines-*.jsonl"))[-3:]

    def rows(self) -> list[dict]:
        stamp = sum(f.stat().st_mtime + f.stat().st_size for f in self.source_files() if f.exists())
        if stamp != self.cache[0]:
            out = []
            for f in self.source_files():
                if not f.exists():
                    continue
                for line in f.open():
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    text = r.get("title", "") + " " + r.get("summary", "")
                    r["topics"], r["radar"] = tag(text), radar_tags(text)
                    r["ts"] = (parse(r.get("time")) or parse(r.get("seen")) or datetime.fromtimestamp(0, timezone.utc)).timestamp()
                    r["seen_ts"] = (parse(r.get("seen")) or datetime.fromtimestamp(r["ts"], timezone.utc)).timestamp()
                    if r["ts"] > time.time() + 3600:  # some feeds carry future dates
                        if r["seen_ts"] > time.time() + 3600:
                            continue
                        r["ts"] = r["seen_ts"]
                    out.append(r)
            out.sort(key=lambda r: r["ts"])
            self.cache = (stamp, out[-MAX_ROWS * 4:])
        return self.cache[1]

    def visible(self) -> tuple[list[dict], float]:
        rows = self.rows()
        if not rows:
            return [], time.time()
        if self.replay:
            start = max(rows[-1]["ts"] - 48 * 3600, rows[0]["ts"])
            clock = start + (time.time() - self.t0) * self.speed
            return [r for r in rows if r["ts"] <= clock], min(clock, rows[-1]["ts"])
        if self.demo:
            return rows, rows[-1]["ts"]
        return rows, time.time()

    def headlines(self) -> dict:
        rows, now = self.visible()
        return {"now": now, "rows": rows[-MAX_ROWS:], "topics": {k: [w.strip() for w in v] for k, v in TOPICS.items()}, "radar": list(RADAR), "replay": bool(self.replay)}

    def find(self, rid: str) -> dict | None:
        return next((r for r in self.rows() if str(r.get("id")) == rid), None)

    def run_dir(self) -> Path | None:
        if self.run:
            return self.runs / self.run
        return None

    def status(self) -> dict:
        d = self.run_dir()
        if d and (d / "status.json").exists():
            s = json.loads((d / "status.json").read_text())
            live = d / "control.json"
            if live.exists():
                s["requested_policy"] = json.loads(live.read_text()).get("policy")
            return s
        return {"state": "no run yet", "context": {}}

    def auto_point(self, which: str) -> dict | None:
        """The Fireworks auto router, read from its run as it fills. The sample in demo/ holds a copy once it is finished."""
        path = self.runs / "auto-1101" / "calls.jsonl"
        if not path.exists():
            return None
        items = {i["id"]: i for i in router.saved_rows(which)[0]}
        rows, served = [], collections.Counter()
        for c in map(json.loads, path.open()):
            if c["item"] in items and not c.get("error"):
                v = triage_eval.verdict("fw_auto", c.get("reply", "")) or {}
                rows.append({"pred": v.get("priority"), "key": items[c["item"]]["key"]["priority"], "usd": c["usd"], "seconds": c["seconds"]})
                served[c.get("served_by")] += 1
        if not rows:
            return None
        return {"name": "fw_auto", "kind": "single", "group": "open-cloud", "origin": "mixed", "per_hour": 0, "note": "Served by " + ", ".join(f"{k} {v}" for k, v in served.most_common(3)) + f"; {len(rows)} of {len(items)} filings so far", **router.measure(rows)}

    def compare(self, which: str = "fresh") -> dict:
        which = which if which in router.SETS else "fresh"
        with self.sim_lock:
            if which not in self.sims:
                sim = router.simulate(which)
                sim["policies"] = router.policies(sim)
                self.sims[which] = sim
        out = dict(self.sims[which])
        auto = self.auto_point(which)
        if auto:
            out["singles"] = [s for s in out["singles"] if s["name"] != "fw_auto"] + [auto]
        d = self.run_dir()
        if d and (d / "answers.jsonl").exists() and not self.demo:
            rows = [r for r in map(json.loads, (d / "answers.jsonl").open()) if r.get("key") and r.get("final")]
            if rows:
                m = router.measure([{"pred": r["final"], "key": r["key"], "usd": r["usd"], "seconds": r["seconds"]} for r in rows])
                out = {**out, "systems": out["systems"] + [{"name": f"This run: {self.run}", "kind": "system", "group": "system", "per_hour": 0, **m}]}
        return out

    def context(self) -> dict:
        s = self.status()
        return {"mode": "replay" if self.replay else ("saved data" if self.demo else "live"), "run": self.run, "context": s.get("context", {}), "updated": s.get("updated"),
                "state": s.get("state"), "now": time.strftime("%Y-%m-%d %H:%M:%S %Z")}

    def set_policy(self, name: str) -> dict:
        routes = router.load_routes()
        if name not in routes["policies"]:
            raise ValueError("unknown policy")
        d = self.run_dir()
        if d:
            d.mkdir(parents=True, exist_ok=True)
            tmp = d / "control.json.tmp"
            tmp.write_text(json.dumps({"policy": name}))
            tmp.replace(d / "control.json")
        return {"policy": name, "label": routes["policies"][name]["label"]}


def public_host(url: str) -> bool:
    """Links come from outside, so only public web addresses are fetched."""
    u = urllib.parse.urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        return False
    try:
        return all(ipaddress.ip_address(x[4][0]).is_global for x in socket.getaddrinfo(u.hostname, None))
    except (OSError, ValueError):
        return False


def article(row: dict) -> dict:
    """Plain text of the page behind a headline, for reading only. It never goes to a model from here."""
    fallback = {"text": row.get("summary", ""), "full": False}
    link = row.get("link", "")
    if not public_host(link):
        return fallback
    try:
        with urllib.request.urlopen(urllib.request.Request(link, headers={"User-Agent": UA}), timeout=8) as r:
            body = r.read(2_000_000).decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001 - offline or blocked: show the summary we hold
        return fallback
    text = re.sub(r"\s+", " ", html.unescape(TAGS.sub(" ", body))).strip()
    return {"text": text[:12000], "full": True} if len(text) > len(fallback["text"]) else fallback


def handler(store: Store):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet terminal; the page shows state
            pass

        def send(self, body: bytes, kind: str = "application/json", code: int = 200) -> None:
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def js(self, data, code: int = 200) -> None:
            self.send(json.dumps(data).encode(), code=code)

        def do_GET(self):  # noqa: N802
            u = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(u.query)
            try:
                if u.path == "/":
                    return self.send(PAGE.read_bytes(), "text/html; charset=utf-8")
                if u.path == "/api/headlines":
                    return self.js(store.headlines())
                if u.path == "/api/compare":
                    return self.js(store.compare(q.get("set", ["fresh"])[0]))
                if u.path == "/api/status":
                    return self.js(store.status())
                if u.path == "/api/context":
                    return self.js(store.context())
                if u.path == "/api/goals":
                    return self.js(G.load(store.goals_file, DEMO / "goals.json" if store.demo else None))
                if u.path == "/api/article":
                    r = store.find(q.get("id", [""])[0])
                    return self.js({"row": r, **article(r)} if r else {"error": "not found"}, 200 if r else 404)
                return self.js({"error": "not found"}, 404)
            except (OSError, ValueError) as e:
                return self.js({"error": str(e)[:200]}, 500)

        def do_POST(self):  # noqa: N802
            if "application/json" not in self.headers.get("Content-Type", ""):
                return self.js({"error": "json only"}, 415)
            origin = self.headers.get("Origin")
            if origin and urllib.parse.urlparse(origin).netloc != self.headers.get("Host"):
                return self.js({"error": "other sites may not change this"}, 403)
            try:
                body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 20000)) or b"{}")
                seed = DEMO / "goals.json" if store.demo else None
                if self.path == "/api/policy":
                    return self.js(store.set_policy(body.get("policy", "")))
                if self.path == "/api/goals":
                    return self.js(G.add(str(body.get("title", ""))[:200] or "Untitled", body.get("parent"), body.get("run"), path=store.goals_file, seed=seed))
                if self.path == "/api/goal":
                    return self.js(G.set_status(body.get("id", ""), body.get("status", ""), path=store.goals_file, seed=seed))
                return self.js({"error": "not found"}, 404)
            except ValueError as e:
                return self.js({"error": str(e)[:200]}, 400)
    return H


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--demo", action="store_true", help="saved data only: no keys, no network, nothing paid")
    ap.add_argument("--run", help="run id to show on the platform page")
    ap.add_argument("--replay", type=Path, help="a headlines file to play back as if live")
    ap.add_argument("--speed", type=float, default=60.0, help="replay speed: 60 means one real minute shows one hour")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 only to share on a trusted network")
    a = ap.parse_args()
    run = a.run
    if a.demo and not run:
        run = "demo-router"
        d = co.RUNS / run
        d.mkdir(parents=True, exist_ok=True)
        for name in ("answers.jsonl", "status.json", "control.json", "audit.jsonl"):
            (d / name).unlink(missing_ok=True)
        (ROOT / "results" / "goals-demo.json").unlink(missing_ok=True)
        threading.Thread(target=router.saved_router, args=(d,), kwargs={"speed": 0.5, "workers": 3}, daemon=True).start()
    store = Store(a.demo, run, a.replay, a.speed)
    print(f"Open http://{a.host}:{a.port}  ({'saved data' if a.demo else 'live'}{', replay' if a.replay else ''}). Ctrl+C stops it.", flush=True)
    try:
        ThreadingHTTPServer((a.host, a.port), handler(store)).serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
