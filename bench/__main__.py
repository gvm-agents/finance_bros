"""Benchmark command line.

  python -m bench collect --start 2026-08-01 --end 2026-09-30 --formd 400 --tenk 120   # free; needs SEC_CONTACT
  python -m bench estimate --lanes all --tasks all                                      # cost forecast, no calls
  python -m bench run --lanes haiku55,gptoss120_fw --tasks formd_extract --n 50 --max-usd 5
  python -m bench report --run <run id>                                                 # tables, chart, economics
  python -m bench export-sft --task formd_extract                                       # Fireworks training file

Every paid run needs --max-usd; it stops before a call would pass the cap.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import collect, tasks
from .lanes import Caller, cost, load_lanes

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "results" / "runs"


def pick(names: str, universe) -> list[str]:
    if names == "all":
        return list(universe)
    out = [n.strip() for n in names.split(",") if n.strip()]
    bad = [n for n in out if n not in universe]
    if bad:
        raise SystemExit(f"unknown: {', '.join(bad)} (choose from {', '.join(universe)})")
    return out


def items_for(task: str, split: str, n: int | None) -> list[dict]:
    its = collect.load(task, split)
    return its[:n] if n else its


def estimate(lane_names, task_names, split, n) -> list[dict]:
    lanes, rows = load_lanes(), []
    for t in task_names:
        prompt_fn, _, max_out = tasks.TASKS[t]
        its = items_for(t, split, n)
        if not its:
            continue
        tin = sum(len(prompt_fn(i)) for i in its) / 4
        for ln in lane_names:
            lane = lanes[ln]
            think = 1500 if lane["provider"] == "vertex" or "gpt-oss" in lane["model"] else 0
            tout = len(its) * (max_out * 0.5 + think)
            rows.append({"lane": ln, "task": t, "items": len(its), "est_usd": round(cost(lane, tin, tout), 2)})
    return rows


def run(lane_names, task_names, split, n, max_usd, run_id, workers, fake=None) -> Path:
    lanes = load_lanes()
    gpu = [ln for ln in lane_names if lanes[ln].get("gpu_usd_per_hour")]
    if gpu:  # billed per GPU-second, so --max-usd cannot protect these lanes
        print(f"WARNING: {', '.join(gpu)} run on a rented GPU billed by the hour; --max-usd does not cover it. "
              "Delete the Fireworks deployment as soon as this run ends.")
    out_dir = RUNS / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "calls.jsonl"
    done = {(c["lane"], c["task"], c["item"]) for c in map(json.loads, path.open())} if path.exists() else set()
    spent = sum(c["usd"] for c in map(json.loads, path.open())) if path.exists() else 0.0
    lock = threading.Lock()
    state = {"spent": spent, "stopped": False}
    for ln in lane_names:
        lane = lanes[ln]
        caller = Caller(lane, fake_answers=fake)
        for t in task_names:
            prompt_fn, score_fn, max_out = tasks.TASKS[t]
            todo = [i for i in items_for(t, split, n) if (ln, t, i["id"]) not in done]

            def one(item, lane=lane, ln=ln, t=t, prompt_fn=prompt_fn, score_fn=score_fn, max_out=max_out, caller=caller):
                prompt = prompt_fn(item)
                worst = cost(lane, len(prompt) / 3, max_out + 4000)
                with lock:
                    if state["stopped"] or state["spent"] + worst > max_usd:
                        state["stopped"] = True
                        return
                r = caller(prompt, max_out, item["id"])
                s = score_fn(item, r.text) if not r.error else {"score": 0.0, "valid": False, "invented": 0}
                row = {"lane": ln, "task": t, "item": item["id"], "group": lane["group"], "model": lane["model"],
                       "seconds": round(r.seconds, 3), "tokens_in": r.tokens_in, "tokens_out": r.tokens_out,
                       "usd": round(cost(lane, r.tokens_in, r.tokens_out), 6), "error": r.error, **s,
                       "retries": r.retries, "reply": r.text[:4000], "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
                with lock:
                    state["spent"] += row["usd"]
                    state["done"] = state.get("done", 0) + 1
                    state["refused"] = state.get("refused", 0) + r.retries
                    state["errors"] = state.get("errors", 0) + bool(r.error)
                    if state["done"] % 50 == 0:  # live monitor: refusals are seen during the run, not afterwards
                        print(f"  live: {state['done']} answered, {state['refused']} refused and retried, {state['errors']} failed, ${state['spent']:.2f}", flush=True)
                    with path.open("a") as f:
                        f.write(json.dumps(row) + "\n")

            pool_size = 1 if lane["provider"] == "ollama" else workers
            with ThreadPoolExecutor(pool_size) as pool:
                list(pool.map(one, todo))
            print(f"{ln:<18} {t:<14} {len(todo):>4} items  spent so far ${state['spent']:.2f}")
            if state["stopped"]:
                print(f"STOPPED: the next call could pass the ${max_usd:.2f} cap")
                return path
    return path


def merge(run_id: str, other: Path) -> int:
    """Add another machine's calls (same run id) to this run, skipping rows already here."""
    path = RUNS / run_id / "calls.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    have = {(c["lane"], c["task"], c["item"]) for c in map(json.loads, path.open())} if path.exists() else set()
    new = [l for l in other.open() if l.strip() and (lambda c: (c["lane"], c["task"], c["item"]))(json.loads(l)) not in have]
    with path.open("a") as f:
        f.writelines(l if l.endswith("\n") else l + "\n" for l in new)
    return len(new)


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else 0.0


def summarize(path: Path) -> list[dict]:
    calls = [json.loads(l) for l in path.open()]
    groups: dict[tuple, list[dict]] = {}
    for c in calls:
        groups.setdefault((c["lane"], c["task"]), []).append(c)
    rows = []
    for (ln, t), cs in sorted(groups.items()):
        ok = [c for c in cs if not c["error"]]
        secs = [c["seconds"] for c in ok]
        out_tok = sum(c["tokens_out"] for c in ok)
        rows.append({"lane": ln, "task": t, "group": cs[0]["group"], "n": len(cs),
                     "score": round(statistics.mean(c["score"] for c in cs), 3),
                     "valid_pct": round(100 * sum(bool(c.get("valid")) for c in cs) / len(cs), 1),
                     "errors": len(cs) - len(ok),
                     "invented_per_100": round(100 * sum(c.get("invented", 0) for c in cs) / len(cs), 1),
                     "p50_s": round(pct(secs, 0.5), 2), "p95_s": round(pct(secs, 0.95), 2),
                     "tok_per_s": round(out_tok / sum(secs), 1) if secs and sum(secs) else 0.0,
                     "usd_per_1000": round(1000 * sum(c["usd"] for c in cs) / len(cs), 3)})
    return rows


def md_table(rows: list[dict], cols: list[str]) -> str:
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in rows]
    return "\n".join(out)


def report(run_id: str) -> Path:
    path = RUNS / run_id / "calls.jsonl"
    rows = summarize(path)
    by_lane: dict[str, list[dict]] = {}
    for r in rows:
        by_lane.setdefault(r["lane"], []).append(r)
    overall = [{"lane": ln, "group": rs[0]["group"], "tasks": len(rs),
                "mean_score": round(statistics.mean(r["score"] for r in rs), 3),
                "invented_per_100": round(statistics.mean(r["invented_per_100"] for r in rs), 1),
                "p50_s": round(statistics.median(r["p50_s"] for r in rs), 2),
                "usd_per_1000": round(statistics.mean(r["usd_per_1000"] for r in rs), 3)} for ln, rs in by_lane.items()]
    overall.sort(key=lambda r: -r["mean_score"])
    md = [f"# Benchmark report: run {run_id}", "",
          "Score: 0 to 1 against answer keys built by Python from SEC data. 'Invented' = numbers given that appear "
          "nowhere in the input. Cost per 1,000 items from published prices; local lanes show $0 per call (hardware "
          "and upkeep are in the economics section).", "", "## Overall (equal weight per task)", "",
          md_table(overall, ["lane", "group", "tasks", "mean_score", "invented_per_100", "p50_s", "usd_per_1000"]),
          "", "## By task", "",
          md_table(rows, ["task", "lane", "n", "score", "valid_pct", "errors", "invented_per_100", "p50_s", "p95_s",
                          "tok_per_s", "usd_per_1000"])]
    econ_file = ROOT / "economics.json"
    if econ_file.exists():
        md += ["", economics(json.loads(econ_file.read_text()), overall)]
    out = RUNS / run_id / "REPORT.md"
    out.write_text("\n".join(md) + "\n")
    chart(overall, RUNS / run_id / "score_vs_cost.png")
    return out


def economics(e: dict, overall: list[dict]) -> str:
    """Monthly cost per lane at our volume, plus the fixed cost of hosting an open model ourselves."""
    lines = ["## Is hosting an open model worth it? (assumptions in economics.json)", "",
             f"Monthly items: {e['monthly_items']:,} (scenario multipliers: {e['scenarios']}). "
             f"Upkeep: {e['upkeep_hours_per_month']} hours a month at ${e['hour_value_usd']} an hour; "
             f"dedicated GPU ${e['dedicated_gpu_usd_per_hour']}/hour x {e['dedicated_hours_per_month']} hours.", "",
             "| lane | mean score | " + " | ".join(f"{m}x volume $/month" for m in e["scenarios"]) + " |",
             "|---|---|" + "---|" * len(e["scenarios"])]
    upkeep = e["upkeep_hours_per_month"] * e["hour_value_usd"]
    gpu = e["dedicated_gpu_usd_per_hour"] * e["dedicated_hours_per_month"]
    for r in overall:
        cells = []
        for m in e["scenarios"]:
            variable = r["usd_per_1000"] * e["monthly_items"] * m / 1000
            fixed = upkeep if r["group"] == "open-local" else 0
            cells.append(f"{variable + fixed:,.0f}")
        lines.append(f"| {r['lane']} | {r['mean_score']} | " + " | ".join(cells) + " |")
    lines += ["", f"A dedicated Fireworks GPU (needed only above serverless limits or for custom models without serverless "
              f"support) adds about ${gpu:,.0f} a month plus upkeep (${upkeep:,.0f}). Serverless open models need no "
              "hosting or upkeep: you pay per call, like Claude."]
    return "\n".join(lines)


def chart(overall: list[dict], out: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    colors = {"frontier": "#1F497D", "open-cloud": "#C0504D", "open-cloud-tuned": "#F79646", "open-local": "#4F9D69"}
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for r in overall:
        x = max(r["usd_per_1000"], 0.01)
        ax.scatter(x, r["mean_score"], s=80, color=colors.get(r["group"], "grey"))
        ax.annotate(r["lane"], (x, r["mean_score"]), textcoords="offset points", xytext=(6, 4), fontsize=9)
    ax.set_xscale("log")
    ax.set_xlabel("Cost per 1,000 items (USD, log scale; local shown at $0.01)")
    ax.set_ylabel("Mean score (0-1)")
    ax.set_title("Accuracy vs cost: frontier vs open models")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=160)


def export_sft(task: str) -> Path:
    """Fireworks supervised fine-tuning file (chat format) from the TRAIN split only."""
    prompt_fn = tasks.TASKS[task][0]
    answer = {
        "formd_extract": lambda i: json.dumps({**{f: i["key"].get(f) for f in tasks.FORMD_FIELDS},
                                               "related_persons": i["key"]["related_persons"]}),
        "name_match": lambda i: json.dumps({"same": i["key"]["same"]}),
        "sector": lambda i: json.dumps({"division": i["key"]["division"]}),
        "longdoc": lambda i: json.dumps({q: i["key"].get(q) for q in ("revenue", "net_income", "total_assets", "shares_outstanding")}),
        "adv_extract": lambda i: json.dumps(i["key"]),
        "format_table": lambda i: "| Name | Relationships |\n|---|---|\n" + "\n".join(
            f"| {p['name']} | {'; '.join(sorted(r.title() for r in p['relationships']))} |" for p in i["key"]["related_persons"]),
    }.get(task)
    if not answer:
        raise SystemExit(f"no exact gold answer for {task}; cannot export training examples")
    out = ROOT / "data" / f"sft_{task}.jsonl"
    with out.open("w") as f:
        for i in collect.load(task, "train"):
            f.write(json.dumps({"messages": [{"role": "user", "content": prompt_fn(i)},
                                             {"role": "assistant", "content": answer(i)}]}) + "\n")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="bench", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--start", required=True)
    c.add_argument("--end", required=True)
    c.add_argument("--formd", type=int, default=400)
    c.add_argument("--tenk", type=int, default=120)
    cn = sub.add_parser("collect-names", help="rebuild only the name_match items (free; needs SEC_CONTACT)")
    cn.add_argument("--pairs", type=int, default=150, help="same-company pairs (an equal number of different pairs is added)")
    ca = sub.add_parser("collect-adv", help="build the Form ADV items (free; needs SEC_CONTACT and pdftotext)")
    ca.add_argument("--n", type=int, default=150, help="advisers to keep")
    for name in ("estimate", "run"):
        p = sub.add_parser(name)
        p.add_argument("--lanes", default="all")
        p.add_argument("--tasks", default="all")
        p.add_argument("--split", default="test", choices=["test", "train", "all"])
        p.add_argument("--n", type=int, help="items per task (default: all in the split)")
        if name == "run":
            p.add_argument("--max-usd", type=float, required=True, help="hard spending cap for this run")
            p.add_argument("--run", default=time.strftime("%Y%m%d-%H%M"), help="run id (re-use to resume)")
            p.add_argument("--workers", type=int, default=4)
    m = sub.add_parser("merge", help="add another machine's calls.jsonl to a run (e.g. copied from the Mini)")
    m.add_argument("--run", required=True)
    m.add_argument("--calls", type=Path, required=True, help="the other machine's results/runs/<run>/calls.jsonl")
    r = sub.add_parser("report")
    r.add_argument("--run", required=True)
    e = sub.add_parser("export-sft")
    e.add_argument("--task", default="formd_extract")
    a = ap.parse_args(argv)

    if a.cmd == "collect":
        print(collect.collect_all(a.start, a.end, a.formd, a.tenk))
    elif a.cmd == "collect-adv":
        print(collect.collect_adv(a.n))
    elif a.cmd == "collect-names":
        print(collect.collect_names(a.pairs))
    elif a.cmd == "estimate":
        rows = estimate(pick(a.lanes, load_lanes()), pick(a.tasks, tasks.TASKS), a.split, a.n)
        print(md_table(rows, ["lane", "task", "items", "est_usd"]))
        print(f"\nTotal estimate: ${sum(r['est_usd'] for r in rows):.2f} (rough: chars/4 tokens, half of max output)")
    elif a.cmd == "run":
        p = run(pick(a.lanes, load_lanes()), pick(a.tasks, tasks.TASKS), a.split, a.n, a.max_usd, a.run, a.workers)
        print(f"calls: {p}\nnext: python -m bench report --run {a.run}")
    elif a.cmd == "merge":
        print(f"added {merge(a.run, a.calls)} calls to run {a.run}")
    elif a.cmd == "report":
        print(report(a.run))
    elif a.cmd == "export-sft":
        print(export_sft(a.task))
    return 0


if __name__ == "__main__":
    sys.exit(main())
