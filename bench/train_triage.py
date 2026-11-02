"""Train a small open model on 8-K importance, then compare it with the untrained model on filings it never saw.

Labels come from the SEC's own item codes, so no person or model wrote them. Uses Fireworks' serverless LoRA training
through the public cookbook; run with its environment, from its training folder:

  cd <cookbook>/training && <env>/bin/python <repo>/bench/train_triage.py --run triage-1 [--epochs 2] [--rare 3] [--no-promote]
Writes train.jsonl, holdout.jsonl, predictions_base.jsonl, predictions_tuned.jsonl, summary.json under --out.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ITEMS = REPO / "data" / "items"
TEXT_LIMIT = 6000
RARE = {"bankruptcy", "cyber_incident", "restatement", "acquisition_or_sale"}


def load_triage():
    spec = importlib.util.spec_from_file_location("triage_prompt", REPO / "bench" / "triage_prompt.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def row(item: dict, prompt_fn) -> dict:
    gold = json.dumps({"type": item["key"]["type"], "priority": item["key"]["priority"]})
    return {"messages": [{"role": "user", "content": prompt_fn({"text": item["text"][:TEXT_LIMIT]})}, {"role": "assistant", "content": gold}]}


def read(name: str) -> list[dict]:
    return [json.loads(l) for l in (ITEMS / f"{name}.jsonl").open()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", required=True)
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--rare", type=int, default=3, help="repeat rare high-priority types this many times in training")
    ap.add_argument("--high", type=int, default=1, help="repeat every high-priority filing this many times, to trade false alarms for fewer misses")
    ap.add_argument("--lora-rank", type=int, default=8)
    ap.add_argument("--learning-rate", type=float, default=1e-4)
    ap.add_argument("--eval", default="triage_8k_fresh", help="held-out set")
    ap.add_argument("--max-eval-tokens", type=int, default=1024)
    ap.add_argument("--no-promote", action="store_true")
    ap.add_argument("--out", type=Path, default=REPO / "results" / "training")
    a = ap.parse_args()
    sys.path.insert(0, ".")
    import pyqwest  # the SDK's network library has its own name lookup, which fails behind Tailscale; use the system's

    transport = pyqwest.HTTPTransport
    pyqwest.HTTPTransport = lambda **k: transport(**{**k, "use_system_dns": True})
    from examples.sft import muse_glimmer_starter as m

    prompt_fn = load_triage().prompt
    train, held = read("triage_8k_train"), read(a.eval)
    assert not {i["id"] for i in train} & {i["id"] for i in held}, "held-out filings leaked into training"
    copies = lambda i: max(a.rare if i["key"]["type"] in RARE else 1, a.high if i["key"]["priority"] == "high" else 1)
    train_rows = [row(i, prompt_fn) for i in train for _ in range(copies(i))]
    random.Random(7).shuffle(train_rows)
    eval_rows = [row(i, prompt_fn) for i in held]
    run_dir = a.out / a.run
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "holdout_ids.json").write_text(json.dumps([i["id"] for i in held]))
    combined = run_dir / "all.jsonl"
    combined.write_text("".join(json.dumps(r) + "\n" for r in train_rows + eval_rows))

    original = m._prepare

    def fixed_split(args):
        """The cookbook picks a random holdout; we need exactly the filings in the held-out set, in order."""
        out = list(original(args))
        out[1], out[2] = train_rows, eval_rows
        for name, split in (("train.jsonl", train_rows), ("holdout.jsonl", eval_rows)):
            (run_dir / name).write_text("".join(json.dumps(r) + "\n" for r in split))
        out[-1]["train_rows"], out[-1]["holdout_rows"] = len(train_rows), len(eval_rows)
        print(json.dumps({k: v for k, v in out[-1].items() if k != "example_rendered"}), flush=True)
        print(out[-1]["example_rendered"][-400:], flush=True)
        return tuple(out)

    m._prepare = fixed_split
    args = m.parse_args(["launch", "--surface", "serverless", "--file", str(combined), "--run-id", a.run, "--epochs", str(a.epochs),
                         "--lora-rank", str(a.lora_rank), "--learning-rate", str(a.learning_rate), "--n-eval", str(len(eval_rows)),
                         "--max-seq-len", "2600", "--max-eval-tokens", str(a.max_eval_tokens), "--log-path", str(run_dir)] + (["--no-promote"] if a.no_promote else []))
    return m.main.__wrapped__(args) if hasattr(m.main, "__wrapped__") else m.cmd_launch_serverless(args)


if __name__ == "__main__":
    raise SystemExit(main())
