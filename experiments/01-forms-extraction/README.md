# 01 Forms extraction: read an SEC Form D

## The job
When a private company raises money it files a Form D with the SEC. An analyst wants 9 facts from it as clean data: issuer name, state and year of incorporation, industry group, total offering amount, amount sold, date of first sale, number of investors, related persons.

**Who needs it:** VC and private-market analysts, data vendors and deal-flow tools read thousands of these a month.

## Data
- `data/items/formd_extract.jsonl`: 400 Form D filings, `split` = train 280 / test 120.
- Answer key: the SEC's own structured Form D data. Scored by Python (`bench/tasks.py`), an answer at 0.90 or more counts as fully right.
- Training file: `data/sft_formd_extract.jsonl` (the 280 training forms only). No company appears in both training and test; 10 test forms come from fund families also seen in training, and removing them changes the result from 0.999 to 0.998.

## Results on the 120 held-out test forms

| System | Score | $ per 1,000 | Median s | Run |
|---|---:|---:|---:|---|
| gpt-oss-120b (open, ready-made) | 0.899 | 0.77 | 1.73 | `results/runs/forms-test-open` |
| GLM 5.3 Flash (open, untrained) | 0.944 | 1.16 | 5.98 | `results/glm-base-formd-test` (this folder) |
| DeepSeek V4.1 Flash (open, ready-made) | 0.986 | 1.21 | 1.28 | `results/runs/forms-test-open` |
| Claude Sonnet 5 (frontier) | 0.988 | 13.87 | 2.16 | `results/runs/forms-test-frontier` |
| Muse Glimmer 30B, untrained (enough answer space) | 0.987 | to measure | to measure | `results/training/forms-lora-2/predictions_base.jsonl` |
| **Muse Glimmer 30B + LoRA (ours)** | **0.999** | to measure | to measure | `results/training/forms-lora-1`, `forms-lora-2` |

Same score in two separate training runs.

## Is the gain real?

| Comparison | Trained right, other wrong | Other right, trained wrong | McNemar p |
|---|---:|---:|---:|
| vs the same model untrained | 17 | 0 | 0.00002 |
| vs Claude Sonnet 5 (frontier) | 15 | 0 | 0.00006 |
| vs gpt-oss-120b | 90 | 0 | 2e-27 |
| vs DeepSeek V4.1 Flash | 17 | 1 | 0.0001 |

Bootstrap (resampling companies): the 95% range of the gain excludes zero in all three comparisons. Code: `bench/stats.py`.

## What did not work (we report these on purpose)

| Try | Score | Why |
|---|---:|---|
| gpt-oss-120b with extra thinking | 0.404 | Its reasoning used up the answer space: 57% of answers were cut off |
| Nemotron Lightning 30B (cheapest) | 0.553 | Invalid answers on 35% of forms, very slow (141 s median) |
| DeepSeek with long thinking | 0.997 on 29 forms | Accurate but 4x the price and 15x slower |
| Muse Glimmer untrained, default answer space | 0.117 | Ran out of answer space on 106 of 120 forms; not a fair "before", so we re-ran it with enough space (0.987) |

## Reproduce
```bash
venv/bin/python -m bench.starter                     # unpack test sets
venv/bin/python -m bench run --lanes gptoss120_fw,deepseek41_fw_off --tasks formd_extract --split test --max-usd 0.30 --run forms-test-open
venv/bin/python -m bench run --lanes glm53flash_fw --tasks formd_extract --split test --max-usd 0.30 --workers 8 --run glm-base-formd-test
# serverless LoRA training on Fireworks, from the Fireworks cookbook's training folder:
cd <cookbook>/training && <env>/bin/python <repo>/bench/train_forms.py --run forms-lora-2
venv/bin/python -m bench.train_forms_score --run forms-lora-2   # same scorer as every other model, free
venv/bin/python -m bench.stats --help                           # McNemar + company bootstrap
```
Cost of the open-model test runs: about $0.25 (gpt-oss + DeepSeek) and $0.14 (GLM).

## Open
- Price and speed of the trained model on the 120 forms (it ran on a rented GPU; convert to $ per 1,000).
