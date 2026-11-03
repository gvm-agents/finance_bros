# Experiments

Team **finance bros**, Fireworks Deploy Buildathon, San Francisco, 2026-11-02.

**The question:** can a small open model, trained on public SEC data, do a finance analyst's routine reading as well as a frontier model, faster and for a fraction of the price?

We test two analyst jobs. Each experiment has its own folder with the task, the data, every system we tried (including the ones that failed), the results on a fixed held-out test set, and the significance tests.

| # | Experiment | Job | Status |
|---|---|---|---|
| 01 | [Forms extraction](01-forms-extraction/) | Pull 9 facts out of an SEC Form D (private fundraising) | Done: trained model 0.999 vs 0.987 untrained |
| 02 | [Sorting 8-K filings](02-sorting-8k/) | Decide if a company event filing is urgent | Done: 3 misses vs frontier 4, false alarms 9 vs 21, $0.37 vs $1.80 per 1,000 |

| 05 | [8-K harness, no training](05-8k-harness-no-training/) | Python rules first, untrained Muse for the rest | Type right 157 > 162 on 200 unseen 8-Ks; model reads 56% of filings |
| 06 | [8-K harness + trained Muse](06-8k-harness-trained/) | Same harness, Muse Glimmer LoRA on 688 filings | Type right 157 > 184, urgent 93 > 103 of 105 (p = 0.00001) |
| 07 | [8-K with GLM 5.3 Flash and gpt-oss](07-8k-glm-trained/) | Same test on two other open models | Harness lifts gpt-oss 151 > 161 (p = 0.002) |

All 8-K systems side by side on the 200 unseen filings, frontier included: [results/comparison-triage_8k](../results/comparison-triage_8k/).

## The three dimensions we report for every system

| Dimension | Measure |
|---|---|
| Accuracy | Score against the SEC's own structured data (no person or model wrote the keys) |
| Price | Dollars per 1,000 items, from tokens and published prices |
| Speed | Median and 95th-percentile seconds per item |

## Rules we kept

- One fixed held-out test set per task, used the same way for every system. Training never sees it.
- Same prompt and settings for every system we compare.
- Every run saves one row per test item (`calls.jsonl` or `predictions_*.jsonl`), so every number here can be re-checked without re-running a model.
- Significance: McNemar test on per-item right/wrong, and a bootstrap that resamples whole companies.

## Disclosure

Much of the bench (scoring code, test sets, earlier runs) was built before today by a team member in [open-model-eval](https://github.com/gvm-agents/open-model-eval). Built today: the trained Forms models, the final Sorting run, experiments 03 and 04, and this write-up. We used AI coding assistants (Claude Code) throughout.
