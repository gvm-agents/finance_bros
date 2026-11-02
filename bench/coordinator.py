"""Run many items through one model at once, with a hard budget, resumable files and a live status file.

  python -m bench.coordinator --lane gptoss120_fw --task triage_8k --workers 6 --max-usd 1 --run my-run
  python -m bench.coordinator --lane fake --task triage_8k --workers 2 --max-usd 0 --run try-it     # no keys, no cost

Workers can only read text and return text: a worker calls lanes.Caller, which sends one prompt and
gets one reply. Workers have no tools, so a fooled worker can do nothing worse than give a wrong answer.

Files in results/runs/<run>/:
  answers.jsonl  one line per item, written as it finishes, so a crash loses nothing
  status.json    the numbers the platform dashboard reads
  STOP           create this file to stop cleanly; run the same command again to resume
"""
from __future__ import annotations

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Iterable

from . import collect, goals, tasks
from .lanes import Caller, cost, load_lanes

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "results" / "runs"
WORST_PROMPT_CHARS_PER_TOKEN = 3
THINK_ROOM = 4000


class Ledger:
    """One thread-safe record of a run: spending, counts and the status file."""

    def __init__(self, run_dir: Path, total: int, max_usd: float, context: dict | None = None):
        self.dir = Path(run_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "answers.jsonl"
        self.lock = threading.Lock()
        self.total, self.max_usd, self.context = total, max_usd, context or {}
        self.started = time.time()
        self.c = dict(done=0, refused=0, failed=0, checked=0, to_person=0, second_reads=0, deferred=0, audited=0, audit_agree=0, high=0, skipped=0)
        self.spent = 0.0
        self.reserved = 0.0
        self.stopped = ""
        self.extra = None  # a function giving live numbers from outside the ledger, such as queue depth
        self.seen = set()
        if self.path.exists():
            for r in map(json.loads, self.path.open()):
                self.seen.add(r["id"])
                self.spent += r.get("usd", 0.0)
                self._count(r)
        self.c["resumed"] = len(self.seen)

    def _count(self, r: dict) -> None:
        self.c["done"] += 1
        self.c["refused"] += r.get("retries", 0)
        self.c["failed"] += bool(r.get("error"))
        self.c["checked"] += bool(r.get("checked"))
        self.c["to_person"] += bool(r.get("to_person"))
        self.c["second_reads"] += bool(r.get("second_lane"))
        self.c["deferred"] += bool(r.get("deferred"))
        self.c["high"] += r.get("final") == "high"

    def stop_requested(self) -> bool:
        return (self.dir / "STOP").exists()

    def reserve(self, usd: float) -> bool:
        """Hold money for a call before making it. False means the call would pass the cap, so the run stops."""
        with self.lock:
            if self.stopped:
                return False
            if self.stop_requested():
                self.stopped = "stop file"
                return False
            if self.spent + self.reserved + usd > self.max_usd:
                self.stopped = f"budget: ${self.spent:.4f} spent of ${self.max_usd:.2f}"
                return False
            self.reserved += usd
            return True

    def settle(self, reserved: float, spent: float) -> None:
        with self.lock:
            self.reserved -= reserved
            self.spent += spent

    def add(self, row: dict) -> None:
        """Write one finished item at once. The status file follows."""
        with self.lock:
            with self.path.open("a") as f:
                f.write(json.dumps(row) + "\n")
            self.seen.add(row["id"])
            self._count(row)
            self._write_status()

    def bump(self, name: str, by: int = 1) -> None:
        with self.lock:
            self.c[name] = self.c.get(name, 0) + by
            self._write_status()

    def snapshot(self, extra: dict | None = None) -> dict:
        new = self.c["done"] - self.c.get("resumed", 0)
        secs = max(time.time() - self.started, 1e-6)
        per_item = self.spent / self.c["done"] if self.c["done"] else 0.0
        left = max(self.total - self.c["done"], 0)
        return {**self.c, "total": self.total, "pct_done": round(100 * self.c["done"] / self.total, 1) if self.total else 0.0,
                "cost_so_far": round(self.spent, 4), "cost_to_finish": round(left * per_item, 4), "cost_total_est": round(self.spent + left * per_item, 4),
                "max_usd": self.max_usd, "items_per_sec": round(new / secs, 3), "seconds": round(secs, 1), "stopped": self.stopped,
                "state": "stopped" if self.stopped else ("finished" if self.total and left == 0 else "running"),
                "updated": time.strftime("%Y-%m-%dT%H:%M:%S"), "context": self.context, **(extra or {})}

    def _write_status(self, extra: dict | None = None) -> None:
        tmp = self.dir / "status.json.tmp"
        tmp.write_text(json.dumps(self.snapshot({**(self.extra() if self.extra else {}), **(extra or {})}), indent=1))
        tmp.replace(self.dir / "status.json")

    def finish(self, extra: dict | None = None) -> dict:
        with self.lock:
            self._write_status(extra)
            return self.snapshot({**(self.extra() if self.extra else {}), **(extra or {})})


def worst_cost(lane: dict, prompt: str, max_out: int) -> float:
    return cost(lane, len(prompt) / WORST_PROMPT_CHARS_PER_TOKEN, max_out + THINK_ROOM)


def run_items(items: Iterable[dict], work: Callable[[dict], None], ledger: Ledger, workers: int) -> None:
    """Hand each item not yet done to a pool of workers. `work` returns nothing; it records through the ledger."""
    todo = [i for i in items if i["id"] not in ledger.seen]
    if workers < 1:
        raise ValueError("workers must be 1 or more")

    def guarded(item: dict) -> None:
        if ledger.stopped:
            return
        try:
            work(item)
        except Exception as exc:  # noqa: BLE001 - one bad item is recorded, never fatal to the run
            ledger.add({"id": item["id"], "error": f"{type(exc).__name__}: {str(exc)[:200]}", "usd": 0.0, "at": time.strftime("%Y-%m-%dT%H:%M:%S")})

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(guarded, todo))


def one_lane(lane_name: str, lane: dict, task: str, items: list[dict], run_dir: Path, max_usd: float, workers: int, fake: dict | None = None) -> dict:
    """The plain case: one model, one task, N workers, scored against the answer key."""
    prompt_fn, score_fn, max_out = tasks.TASKS[task]
    context = {"task": task, "models": [lane_name], "settings": {k: lane[k] for k in ("reasoning", "effort", "thinking") if k in lane},
               "host": lane["provider"], "workers": workers, "measures": ["score", "cost", "seconds", "refusals"]}
    ledger = Ledger(run_dir, len(items), max_usd, context)
    caller = Caller(lane, fake_answers=fake)
    size = 1 if lane["provider"] == "ollama" else workers

    def work(item: dict) -> None:
        prompt = prompt_fn(item)
        held = worst_cost(lane, prompt, max_out)
        if not ledger.reserve(held):
            return
        r = caller(prompt, max_out, item["id"])
        usd = cost(lane, r.tokens_in, r.tokens_out)
        ledger.settle(held, usd)
        s = score_fn(item, r.text) if not r.error else {"score": 0.0, "valid": False, "invented": 0}
        ledger.add({"id": item["id"], "lane": lane_name, "task": task, "seconds": round(r.seconds, 3), "tokens_in": r.tokens_in, "tokens_out": r.tokens_out,
                    "usd": round(usd, 6), "error": r.error, "retries": r.retries, **s, "reply": r.text[:4000], "at": time.strftime("%Y-%m-%dT%H:%M:%S")})

    run_items(items, work, ledger, size)
    return ledger.finish()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lane", required=True, help="a lane name from lanes.json, or 'fake' for a free trial with canned replies")
    ap.add_argument("--task", required=True, choices=sorted(tasks.TASKS))
    ap.add_argument("--split", default="test", choices=["test", "train", "all"])
    ap.add_argument("--n", type=int, help="items to use (default: all in the split)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--max-usd", type=float, required=True, help="hard spending cap for this run")
    ap.add_argument("--run", required=True, help="run id; use the same id to resume")
    ap.add_argument("--goal", help="goal id from bench.goals that this run serves; its status follows the run")
    a = ap.parse_args()
    items = collect.load(a.task, a.split)
    items = items[: a.n] if a.n else items
    lane = {"provider": "fake", "model": "fake", "price_in": 0.0, "price_out": 0.0, "group": "test"} if a.lane == "fake" else load_lanes()[a.lane]
    if a.goal:
        goals.set_status(a.goal, "running", a.run)
    out = one_lane(a.lane, lane, a.task, items, RUNS / a.run, a.max_usd, a.workers, fake={})
    if a.goal:
        goals.set_status(a.goal, "done" if out["state"] == "finished" else "stopped")
    print(json.dumps({k: out[k] for k in ("done", "total", "cost_so_far", "refused", "failed", "state", "stopped")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
