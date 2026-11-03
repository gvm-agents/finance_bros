"""Train GLM 5.3 Flash on 8-K importance with Fireworks' serverless LoRA training, score it on the held-out filings, promote it.

Same data and settings as the Muse run in train_triage.py (results/training/type-1/train.jsonl and holdout.jsonl, LoRA rank 8,
2 epochs, learning rate 1e-4, batch 16, max length 2600). The untrained model was already scored through serverless inference
(bench.score_8k), so only the trained adapter is sampled here. Run from the cookbook's training folder:

  cd <cookbook>/training && <env>/bin/python <repo>/bench/train_glm.py --run glm-type-1
  cd <cookbook>/training && <env>/bin/python <repo>/bench/train_glm.py --run glm-type-1 --adapter accounts/<account>/models/<id>
The second form skips training: it loads a promoted adapter into a new session and only scores it (the sampler snapshot of an
ended session did not answer: requests hung without a reply).
Writes predictions_tuned.jsonl, metrics.jsonl and summary_tuned.json under --out/--run; deletes the training session at the end.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BASE_MODEL = "accounts/fireworks/models/glm-5p3-flash"
TOKENIZER_MODEL = "zai-org/GLM-5.3-Flash"
RENDERER_NAME = "glm53_flash"
TRAIN_USD_PER_M = 8.89  # Serverless Training API list prices for GLM 5.3 Flash
PREFILL_USD_PER_M = 2.96
SAMPLE_USD_PER_M = 7.41


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--data", type=Path, default=REPO / "results" / "training" / "type-1")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--lora-rank", type=int, default=8)
    ap.add_argument("--learning-rate", type=float, default=1e-4)
    ap.add_argument("--max-seq-len", type=int, default=2600)
    ap.add_argument("--max-eval-tokens", type=int, default=1024)
    ap.add_argument("--max-usd", type=float, default=13.0, help="stop before training if the token estimate costs more")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--adapter", help="skip training; load this promoted LoRA model into the session and score it")
    ap.add_argument("--no-promote", action="store_true")
    ap.add_argument("--out", type=Path, default=REPO / "results" / "training")
    a = ap.parse_args()
    sys.path.insert(0, ".")
    import pyqwest  # the SDK's network library has its own name lookup, which fails behind Tailscale; use the system's

    transport = pyqwest.HTTPTransport
    pyqwest.HTTPTransport = lambda **k: transport(**{**k, "use_system_dns": True})
    from examples.sft.muse_glimmer_starter import LORA_ALPHA, LORA_TARGETS, _connect, _score
    from fireworks.training import sdk
    from fireworks.training.sdk import FireworksClient, FiretitanServiceClient
    from training.renderer import TrainOnWhat, get_renderer, get_text_content
    from training.renderer.tokenizer import get_tokenizer
    from training.utils.serverless import enable_serverless_supervised_409_retry, serverless_base_url

    train_ex = [json.loads(l) for l in (a.data / "train.jsonl").open()]
    eval_ex = [json.loads(l) for l in (a.data / "holdout.jsonl").open()]
    tokenizer = get_tokenizer(TOKENIZER_MODEL)
    renderer = get_renderer(RENDERER_NAME, tokenizer)

    datums, train_tokens = [], 0
    for ex in train_ex:
        model_input, weights = renderer.build_supervised_example(ex["messages"], train_on_what=TrainOnWhat.LAST_ASSISTANT_TURN)
        tokens, w = [int(t) for t in model_input.to_ints()], [float(x) for x in weights.tolist()]
        if len(tokens) > a.max_seq_len:
            sys.exit(f"a train row has {len(tokens)} tokens, over --max-seq-len {a.max_seq_len}")
        train_tokens += len(tokens)
        datums.append(sdk.Datum(model_input=sdk.ModelInput.from_ints(tokens[:-1]), loss_fn_inputs={"target_tokens": tokens[1:], "weights": w[1:]}))
    prompts = [renderer.build_generation_prompt(ex["messages"][:-1]) for ex in eval_ex]
    prompt_tokens = sum(len(p.to_ints()) for p in prompts)
    estimate = (0 if a.adapter else train_tokens * a.epochs * TRAIN_USD_PER_M / 1e6) + prompt_tokens * PREFILL_USD_PER_M / 1e6
    print(json.dumps({"train_rows": len(datums), "train_tokens_per_epoch": train_tokens, "eval_rows": len(eval_ex),
                      "eval_prompt_tokens": prompt_tokens, "estimate_usd_before_sampling": round(estimate, 2)}), flush=True)
    if estimate > a.max_usd:
        sys.exit(f"estimate ${estimate:.2f} is over --max-usd {a.max_usd}")

    _, account = _connect()
    run_dir = a.out / a.run
    run_dir.mkdir(parents=True, exist_ok=True)
    service = FiretitanServiceClient(api_key=os.environ["FIREWORKS_API_KEY"],
                                     base_url=serverless_base_url(os.environ.get("FIREWORKS_BASE_URL", "https://api.fireworks.ai")))
    enable_serverless_supervised_409_retry(service)
    summary: dict = {"base_model": BASE_MODEL}
    try:
        training_client = service.create_lora_training_client(base_model=BASE_MODEL, rank=a.lora_rank, alpha=LORA_ALPHA, **LORA_TARGETS)
        session = service.training_session_name
        print(f"session={session} run={getattr(training_client, 'run_id', None)}", flush=True)
        if a.adapter:
            training_client.load_adapter(a.adapter).result()
            snapshot = training_client.save_weights_for_sampler("glm-tuned").result().path
            summary.update({"session": session, "adapter": a.adapter})
        else:
            adam = sdk.AdamParams(learning_rate=a.learning_rate, beta1=0.9, beta2=0.999, eps=1e-8, weight_decay=0.0, grad_clip_norm=1.0)
            rng, step, started = random.Random(a.seed), 0, time.monotonic()
            with (run_dir / "metrics.jsonl").open("a") as log:
                for epoch in range(a.epochs):
                    order = list(range(len(datums)))
                    rng.shuffle(order)
                    for start in range(0, len(order), a.batch_size):
                        fb = training_client.forward_backward([datums[i] for i in order[start:start + a.batch_size]], "cross_entropy").result()
                        opt = training_client.optim_step(adam, emit_grad_norm_metrics=True).result()
                        step += 1
                        metrics = dict(getattr(fb, "metrics", None) or {})
                        tokens = metrics.get("response_tokens") or metrics.get("num_loss_tokens") or 1.0
                        row = {"step": step, "epoch": epoch + 1, "loss": round(metrics.get("loss:sum", 0.0) / max(float(tokens), 1.0), 4),
                               **{k: v for k, v in (getattr(opt, "metrics", None) or {}).items() if "grad" in k}}
                        log.write(json.dumps(row) + "\n")
                        print(json.dumps(row), flush=True)
            snapshot = training_client.save_weights_for_sampler("glm-tuned").result().path
            print(f"snapshot={snapshot}", flush=True)
            # Promote first: the session's checkpoints are only promotable while the session exists.
            promoted = None
            if not a.no_promote:
                fw = FireworksClient(api_key=os.environ["FIREWORKS_API_KEY"], base_url=os.environ.get("FIREWORKS_BASE_URL", "https://api.fireworks.ai"))
                ckpts = [r for r in fw.list_training_session_checkpoints(session)
                         if r.get("promotable") and "glm-tuned" in (r.get("checkpointName") or r.get("name") or "")]
                if ckpts:
                    model_id = f"glm53flash-{a.run}"[:63]
                    fw.promote_session_checkpoint(name=max(ckpts, key=lambda r: r.get("createTime", ""))["name"], output_model_id=model_id, base_model=BASE_MODEL)
                    promoted = f"accounts/{account}/models/{model_id}"
                else:
                    print("no promotable checkpoint found; the adapter stays session-only", flush=True)
            summary.update({"session": session, "promoted_model": promoted, "steps": step, "epochs": a.epochs, "batch_size": a.batch_size,
                            "lora_rank": a.lora_rank, "learning_rate": a.learning_rate, "train_rows": len(datums),
                            "train_tokens": train_tokens * a.epochs, "train_seconds": round(time.monotonic() - started)})

        sampler = service.create_sampling_client(model_path=snapshot, tokenizer=tokenizer)
        params = sdk.SamplingParams(max_tokens=a.max_eval_tokens, temperature=0.0, stop=renderer.get_stop_sequences())
        rows, sampled_tokens, started = [], 0, time.monotonic()
        try:
            futures = [sampler.sample(prompt=p, num_samples=1, sampling_params=params) for p in prompts]
            for i, (ex, fut) in enumerate(zip(eval_ex, futures)):
                res = fut.result() if hasattr(fut, "result") else fut
                out_tokens = list(res.sequences[0].tokens)
                sampled_tokens += len(out_tokens)
                msg, termination = renderer.parse_response(out_tokens)
                clean = termination if isinstance(termination, bool) else termination.is_clean  # the GLM renderer returns a bool
                text = get_text_content(msg)
                gold = ex["messages"][-1]["content"]
                ok, fields = _score(text, gold)
                rows.append({"index": i, "gold": gold, "exact": ok, "fields": fields, "truncated": not clean, "answer_text": text,
                             "tokens_in": len(prompts[i].to_ints()), "tokens_out": len(out_tokens), "model": snapshot})
        finally:
            getattr(sampler, "close", lambda: None)()
        (run_dir / "predictions_tuned.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        summary.update({
            "snapshot": snapshot,
            "eval": {"n": len(rows), "type_right": sum(r["fields"].get("type", False) for r in rows),
                     "priority_right": sum(r["fields"].get("priority", False) for r in rows), "exact": sum(r["exact"] for r in rows),
                     "unterminated": sum(r["truncated"] for r in rows), "prompt_tokens": prompt_tokens, "sampled_tokens": sampled_tokens,
                     "seconds_all_200_in_parallel": round(time.monotonic() - started, 1)},
            "usd_list_price": {"training": 0 if a.adapter else round(train_tokens * a.epochs * TRAIN_USD_PER_M / 1e6, 2),
                               "prefill": round(prompt_tokens * PREFILL_USD_PER_M / 1e6, 3),
                               "sampling": round(sampled_tokens * SAMPLE_USD_PER_M / 1e6, 4)},
        })
        (run_dir / "summary_tuned.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2), flush=True)
    finally:
        if service.training_session_id:
            service.delete_training_session()
            print("training session deleted", flush=True)
        service.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
