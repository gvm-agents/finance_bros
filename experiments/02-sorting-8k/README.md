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
| Trained open model, LoRA "triage-4" | final 568 | runs 15:30 | | | |

## What did not work
- Inkling (new US open model): cost more than the frontier model with no gain.
- No pairing of ready-made open models caught all 82 urgent practice filings.
- First training run (`results/training/triage-2`): fewer false alarms, but exact event type fell from 83.4% to 82.3%.

## Reproduce
See `docs/training.md` (training) and `bench/stats.py` (significance).
