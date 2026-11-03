# 07 8-K harness with GLM 5.3 Flash: untrained baseline; LoRA training blocked

Question: the same 8-K test as 06, with GLM 5.3 Flash (Fireworks serverless) in place of Muse Glimmer 30B: untrained, then LoRA-trained on the same data. Also gpt-oss-120b untrained (Fireworks allows no LoRA on gpt-oss).

Status 2026-11-02: both baselines measured. **The GLM LoRA run did not start**: Fireworks refused the training data upload (see "Training: blocked"). No trained GLM rows exist yet.

## The task

Same as 05 and 06: one of 10 event types per 8-K; six types are urgent (bankruptcy, cyber_incident, acquisition_or_sale, delisting_notice, restatement, leadership_change). The key is the SEC item code (`bench/triage_prompt.py`, `bench/triage.py`).

## Data

| Set | Filings | Urgent | Use here |
|---|---:|---:|---|
| `data/items/triage_8k_train.jsonl` | 688 | 281 | planned LoRA training data (790 rows, rare types x3, = `results/training/type-1/train.jsonl`) |
| `data/items/triage_8k.jsonl` | 200 | 105 | test set, the same 200 filings as run `type-1` in 06; no overlap with training |

## Method

- Prompt: the training prompt, `bench/triage_prompt.py` on `text[:6000]`, one user message, no system prompt.
- Calls: `bench/score_8k.py` (new, small) through the bench's `Caller` (`bench/lanes.py`), lanes `glm53flash_fw` (`accounts/fireworks/models/glm-5p3-flash`) and `gptoss120_fw` (`accounts/fireworks/models/gpt-oss-120b`, reasoning low). Temperature 0, max_tokens 60 + 4000 thinking headroom, 8 calls in parallel.
- Saved answers: `results/training/glm-type-1/predictions_base.jsonl` and `results/training/gptoss-base-triage_8k/predictions_base.jsonl`, with `holdout_ids.json` (ids of `triage_8k` in file order). Each line holds index, gold, answer_text, seconds, tokens, usd.
- Harness: `bench/harness_8k.py` unchanged (rules v2, check, dispute). There are no saved Inkling answers on `triage_8k`, so a dispute has no tiebreak and the rule wins. Harness rows below are routing skip (a firing rule settles the filing; the model reads 55.5%). Routing all gives the same type and urgency counts here.
- Cost: measured tokens x the lane's list price (GLM 5.3 Flash $0.15 in / $0.50 out, gpt-oss-120b $0.15 / $0.60 per 1M). Not checked against the billing page.

## Results on the 200 filings

| System | Type right | Priority right | Urgent caught (of 105) | False alarms (of 95) | Invalid | Read by model | $ per 1,000 | p50 / p95 s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| GLM 5.3 Flash untrained alone | 168 | 189 | 100 | 6 | 0 | 100% | 0.19 | 1.26 / 5.59 |
| Harness v2 + GLM untrained | 173 | 193 | 103 | 5 | 0 | 55.5% | about 0.10 | same per model call; rules take microseconds |
| GLM 5.3 Flash trained alone | not run | - | - | - | - | - | - | - |
| Harness v2 + GLM trained | not run | - | - | - | - | - | - | - |
| gpt-oss-120b untrained alone | 151 | 186 | 96 | 5 | 0 | 100% | 0.14 | 0.51 / 0.79 |
| Harness v2 + gpt-oss untrained | 161 | 190 | 99 | 4 | 0 | 55.5% | about 0.08 | same per model call |
| Muse untrained alone (06) | 157 | - | 93 | 2 | 11 | 100% | - | - |
| Harness v2 + Muse untrained (06) | 162 | - | 97 | 2 | 7 | 55.5% | - | - |
| Muse trained alone (06) | 183 | - | 102 | 3 | 0 | 100% | - | - |
| Harness v2 + Muse trained (06) | 184 | - | 103 | 3 | 0 | 55.5% | - | - |

Harness $ per 1,000 is the model's measured cost times the share of filings it reads; the harness rows were simulated on the saved answers, not called again. Seconds are wall time per call with 8 calls in parallel.

Tokens: GLM 133,927 in, 34,410 out (it thinks first; about 170 output tokens per filing). gpt-oss 144,556 in, 10,751 out. No errors, no retries counted as errors.

### McNemar, same 200 filings (pairs: only first right / only second right)

| Comparison | Type right | p | Priority right | p |
|---|---:|---:|---:|---:|
| GLM untrained vs Muse untrained | 15 / 4 | 0.019 | 11 / 4 | 0.12 |
| GLM untrained vs Muse trained | 8 / 23 | 0.011 | 3 / 8 | 0.23 |
| GLM untrained vs gpt-oss untrained | 31 / 14 | 0.016 | 5 / 2 | 0.45 |
| Harness + GLM untrained vs GLM untrained alone | 5 / 0 | 0.063 | - | - |
| Harness + gpt-oss vs gpt-oss alone | 10 / 0 | 0.002 | - | - |

Trained vs untrained GLM: not available (no trained model).

## What this means

- Untrained GLM 5.3 Flash beats untrained Muse (168 vs 157 type right, p = 0.019) and gpt-oss-120b (168 vs 151, p = 0.016), with no invalid answers.
- Trained Muse from 06 still beats untrained GLM (183 vs 168, p = 0.011).
- The harness adds 5 type-right filings to GLM (not significant) and 10 to gpt-oss (p = 0.002), and halves the model calls.

## Training: blocked

Planned: Fireworks managed supervised fine-tuning of `accounts/fireworks/models/glm-5p3-flash` (model reports `supervisedLoraTunable: true`, `supportsServerlessLora: true`), 790 rows, 2 epochs, LoRA rank 8. Estimate: about 0.92M training tokens (2.07M characters at about 4.5 characters per GLM token, x2 epochs) x $10 per 1M (>300B tier) = about $9.2.

What happened (REST API, account `furkan-6eo1n9w47cuf`):
1. `POST /v1/accounts/<account>/datasets` created `triage-8k-train-790` (state UPLOADING).
2. `POST .../datasets/triage-8k-train-790:upload` (multipart): HTTP 403, `dataset uploads are temporarily disabled, please contact Fireworks AI to get access`.
3. `POST .../datasets/triage-8k-train-790:getUploadEndpoint` (signed-URL route): HTTP 400, code 9, same message.

No fine-tuning job was created; the empty dataset entry was deleted. Training cost $0.

Serving caveat for the next try: Fireworks docs (`fine-tuning/deploying-loras`) say LoRA models run on on-demand deployments only, while the model metadata says `supportsServerlessLora: true`. Check that a trained adapter can be called serverless before paying for training.

## Spend

| Item | $ |
|---|---:|
| GLM 5.3 Flash, 200 filings (+2 probe calls) | 0.037 |
| gpt-oss-120b, 200 filings | 0.028 |
| Training | 0 (not started) |
| Total | about 0.07 |

## Reproduce

```
set -a; . ~/.config/fluid/env; set +a
venv/bin/python -m bench.score_8k --lane glm53flash_fw --set triage_8k --out results/training/glm-type-1/predictions_base.jsonl
venv/bin/python -m bench.score_8k --lane gptoss120_fw --set triage_8k --out results/training/gptoss-base-triage_8k/predictions_base.jsonl
venv/bin/python -m bench.harness_8k sim --run glm-type-1 --answers base --set triage_8k --out experiments/07-8k-glm-trained/results
venv/bin/python -m bench.harness_8k sim --run gptoss-base-triage_8k --answers base --set triage_8k --out experiments/07-8k-glm-trained/results
```

When uploads work again, the trained run is: upload `results/training/type-1/train.jsonl` as a dataset, create a supervisedFineTuningJob (baseModel `accounts/fireworks/models/glm-5p3-flash`, epochs 2, loraRank 8), then score with `bench.score_8k --lane glm53flash_fw --model accounts/<account>/models/<output> --out results/training/glm-type-1/predictions_tuned.jsonl` and run the harness with `--answers tuned`.
