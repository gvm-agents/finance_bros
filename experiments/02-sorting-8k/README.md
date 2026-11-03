# 02 Sorting 8-K filings: urgent or routine?

## The job
Companies file an 8-K when something material happens (a CEO leaves, an acquisition, a bankruptcy). An analyst must never miss an urgent one, and there are hundreds a day.

## Data
- `data/items/triage_8k_train.jsonl`: 688 filings (Jan to Jun 2026), training only.
- `data/items/triage_8k_fresh.jsonl`: 181 filings (82 urgent), practice. Tuned on as often as needed.
- `data/items/triage_8k_final99.jsonl`: 568 filings (240 urgent), the final exam. Run once, at 15:30, after the design is locked.
- Answer key: the SEC item code each company must declare on the filing.

## Target, fixed before the final run
Catch at least 99% of urgent filings (238 of 240) with no more false alarms than the frontier model (21), then lowest cost.

## Results

| System | Set | Caught urgent | False alarms | $ per 1,000 | Run |
|---|---|---:|---:|---:|---|
| Claude Sonnet 5 (frontier) | final 568 | 236 of 240 | 21 | 1.80 | see `docs/team/NOW.md` |
| Trained open model, LoRA "triage-4" | practice 181 | 82 of 82 | 4 | to measure | `results/training/triage-4` |
| Python keyword rule (no AI) | final 568 | 228 of 240 | 27 | 0 | rule in this folder's notes |
| Our starting open setup (gpt-oss + Gemma second reader) | final 568 | 234 of 240 | 21 | 0.13 | `results/runs/final-before` |
| **Trained open model, LoRA "triage-4"** | **final 568** | **237 of 240** | **9** | **0.37** | `results/tuned-final99.jsonl` |

**Final result (run once, after the design was locked):** fewer misses than the frontier model (3 vs 4), 57% fewer false alarms (9 vs 21), about a fifth of the cost. Overall right 97.9% vs 95.6%. McNemar vs frontier: 20 vs 7, p = 0.02; company bootstrap: accuracy gain +0.6 to +4.1 points, false alarms cut by 3 to 21, both excluding zero. The extra urgent filing caught is not significant on its own. Our pre-set target was at most 2 misses; we missed 3, one short. Cost: one rented GPU at about $10/hour answered 568 filings in 75 s once running (about $0.37 per 1,000; about 4 minutes of start-up).

## What did not work
- Inkling (new US open model): cost more than the frontier model with no gain.
- No pairing of ready-made open models caught all 82 urgent practice filings.
- First training run (`results/training/triage-2`): fewer false alarms, but exact event type fell from 83.4% to 82.3%.

## Reproduce
See `docs/training.md` (training) and `bench/stats.py` (significance).
