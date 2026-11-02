"""Keep the main goal and its sub-goals straight when one result leads to more runs.

  python -m bench.goals list
  python -m bench.goals add "Check the missed filings" --parent g3 --run my-run
  python -m bench.goals set g4 done
"""
from __future__ import annotations

import argparse
import json
import os
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILE = Path(os.environ.get("EVAL_GOALS_FILE", ROOT / "results" / "goals.json"))
STATES = ("planned", "running", "done", "stopped")
_lock = threading.Lock()


def load(path: Path = FILE, seed: Path | None = None) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    if seed and seed.exists():
        return json.loads(seed.read_text())
    return {"goals": []}


def save(data: dict, path: Path = FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(path)


def add(title: str, parent: str | None = None, run: str | None = None, status: str = "planned", path: Path = FILE, seed: Path | None = None) -> dict:
    with _lock:
        d = load(path, seed)
        if parent and parent not in {g["id"] for g in d["goals"]}:
            raise ValueError(f"no goal {parent}")
        nums = [int(g["id"][1:]) for g in d["goals"] if g["id"][1:].isdigit()]
        g = {"id": f"g{max(nums, default=0) + 1}", "title": title, "parent": parent, "status": status, "run": run}
        d["goals"].append(g)
        save(d, path)
        return g


def set_status(goal_id: str, status: str, run: str | None = None, path: Path = FILE, seed: Path | None = None) -> dict:
    if status not in STATES:
        raise ValueError(f"status must be one of {STATES}")
    with _lock:
        d = load(path, seed)
        for g in d["goals"]:
            if g["id"] == goal_id:
                g["status"] = status
                g["run"] = run or g.get("run")
                save(d, path)
                return g
    raise ValueError(f"no goal {goal_id}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    a_ = sub.add_parser("add")
    a_.add_argument("title")
    a_.add_argument("--parent")
    a_.add_argument("--run")
    s = sub.add_parser("set")
    s.add_argument("goal")
    s.add_argument("status", choices=STATES)
    s.add_argument("--run")
    a = ap.parse_args()
    if a.cmd == "add":
        print(add(a.title, a.parent, a.run))
    elif a.cmd == "set":
        print(set_status(a.goal, a.status, a.run))
    else:
        goals = load()["goals"]

        def show(parent, depth):
            for g in goals:
                if g["parent"] == parent:
                    print(f"{'  ' * depth}{g['id']} [{g['status']}] {g['title']}" + (f" (run {g['run']})" if g.get("run") else ""))
                    show(g["id"], depth + 1)
        show(None, 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
