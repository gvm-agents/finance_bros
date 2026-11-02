"""Train a small open model (LoRA) to pull facts out of SEC Form D filings, then compare it with the untrained model
on the 120 held-out test filings it never saw.

Answer keys come from the SEC's own structured Form D data, so no person or model wrote them. Same Fireworks
serverless LoRA training as bench/train_triage.py; run with the cookbook's environment, from its training folder:

  cd <cookbook>/training && <env>/bin/python <repo>/bench/train_forms.py --run forms-lora-1 [--epochs 2]
Writes train.jsonl, holdout.jsonl, predictions_base.jsonl, predictions_tuned.jsonl, summary.json under --out.
Score the predictions with our own scorer afterwards: python -m bench.train_forms_score --run <run>.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from bench import tasks  # noqa: E402

FIELDS = ["issuer_name", "state_of_incorporation", "year_of_incorporation", "industry_group", "total_offering_amount",
          "total_amount_sold", "date_of_first_sale", "number_of_investors", "related_persons"]  # the keys the prompt asks for


def row(item: dict) -> dict:
    gold = json.dumps({k: item["key"].get(k) for k in FIELDS})
    return {"messages": [{"role": "user", "content": tasks.formd_prompt(item)}, {"role": "assistant", "content": gold}]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", required=True)
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--lora-rank", type=int, default=8)
    ap.add_argument("--learning-rate", type=float, default=1e-4)
    ap.add_argument("--max-seq-len", type=int, default=8192)
    ap.add_argument("--max-eval-tokens", type=int, default=1200)
    ap.add_argument("--no-promote", action="store_true")
    ap.add_argument("--out", type=Path, default=REPO / "results" / "training")
    a = ap.parse_args()
    sys.path.insert(0, ".")
    import pyqwest  # the SDK's network library has its own name lookup, which fails behind Tailscale; use the system's

    transport = pyqwest.HTTPTransport
    pyqwest.HTTPTransport = lambda **k: transport(**{**k, "use_system_dns": True})
    from examples.sft import muse_glimmer_starter as m

    items = [json.loads(l) for l in (REPO / "data" / "items" / "formd_extract.jsonl").open()]
    train = [i for i in items if i["split"] == "train"]
    held = [i for i in items if i["split"] == "test"]
    assert not {i["id"] for i in train} & {i["id"] for i in held}, "test filings leaked into training"
    train_rows = [row(i) for i in train for _ in range(1)]
    random.Random(7).shuffle(train_rows)
    eval_rows = [row(i) for i in held]
    run_dir = a.out / a.run
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "holdout_ids.json").write_text(json.dumps([i["id"] for i in held]))
    combined = run_dir / "all.jsonl"
    combined.write_text("".join(json.dumps(r) + "\n" for r in train_rows + eval_rows))

    original = m._prepare

    def fixed_split(args):
        """The cookbook picks a random holdout; we need exactly the 120 test filings, in order."""
        out = list(original(args))
        out[1], out[2] = train_rows, eval_rows
        for name, split in (("train.jsonl", train_rows), ("holdout.jsonl", eval_rows)):
            (run_dir / name).write_text("".join(json.dumps(r) + "\n" for r in split))
        out[-1]["train_rows"], out[-1]["holdout_rows"] = len(train_rows), len(eval_rows)
        print(json.dumps({k: v for k, v in out[-1].items() if k != "example_rendered"}), flush=True)
        return tuple(out)

    m._prepare = fixed_split
    args = m.parse_args(["launch", "--surface", "serverless", "--file", str(combined), "--run-id", a.run, "--epochs", str(a.epochs),
                         "--lora-rank", str(a.lora_rank), "--learning-rate", str(a.learning_rate), "--n-eval", str(len(eval_rows)),
                         "--max-seq-len", str(a.max_seq_len), "--max-eval-tokens", str(a.max_eval_tokens), "--log-path", str(run_dir)]
                        + (["--no-promote"] if a.no_promote else []))
    return m.main.__wrapped__(args) if hasattr(m.main, "__wrapped__") else m.cmd_launch_serverless(args)


if __name__ == "__main__":
    raise SystemExit(main())
