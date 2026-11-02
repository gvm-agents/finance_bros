# Training a small triage model

Goal: teach a small open model to sort 8-K filings by importance, then check it on filings it never saw. Labels come from the SEC's own item codes, so no person or model wrote them.

## Data

| Set | Filings | Filed | Use |
|---|---|---|---|
| `triage_8k_train` | 688 | Jan to Jun 2026 | Training. Rare high-priority types repeat 3 times, giving 790 rows |
| `triage_8k_fresh` | 181 (82 high priority) | May to Oct 2026 | Held out. Never used in training |

`bench/train_triage.py` refuses to start if a held-out filing appears in the training rows.

## Rebuild from nothing (about 45 minutes, most of it waiting)

Run on the machine that holds the Fireworks key.

```bash
git clone --depth 1 https://github.com/fw-ai/cookbook fw-cookbook
python3.11 -m venv venv-train
venv-train/bin/pip install -e fw-cookbook/training
export FIREWORKS_API_KEY=...   # never print it
cd fw-cookbook/training
../../venv-train/bin/python ../../open-model-eval/bench/train_triage.py --run triage-3 --epochs 2
```

Options: `--epochs`, `--rare`, `--lora-rank`, `--learning-rate`, `--eval`, `--max-eval-tokens`, `--no-promote`, `--out`.

Muse Glimmer 30B LoRA training through the serverless training API is free until Nov 30, 2026 (Fireworks' terms). Reading the held-out filings is billed per token: about $0.60 for one pass of 181 filings. The script scores the untrained model, trains, then scores the trained model, and writes `summary.json`, `metrics.jsonl`, `predictions_base.jsonl` and `predictions_tuned.jsonl` under `results/training/<run>`.

If name lookup fails behind a VPN, the script already switches the SDK to the system resolver.

## Serving

Fireworks does not serve a trained adapter per token. It needs a rented GPU deployment, billed by the hour.

```bash
venv/bin/python -m bench.deploy_tuned --model accounts/<account>/models/muse-starter-sl-<run> --task triage_8k_fresh --n 181 --minutes 25 --out results/tuned-deploy.jsonl
```

Measured on one H200 GPU: ready in 223 seconds; 181 filings answered in 26 seconds at 6 workers, median 0.75 seconds. The script deletes the deployment at the end, on any error, and at `--minutes` at the latest. Confirm in the Fireworks console that nothing is left running.

A second training run starts only after the first session is closed: `DELETE /v1/accounts/<account>/trainingSessions/<session>`. Promote first; the script does this.
