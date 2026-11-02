# finance bros: a penny analyst on open models

**Fireworks Deploy Buildathon, San Francisco, 2026-11-02.**

**Result:** on 200 SEC 8-K filings it never saw, our system (Python rules first, then a small open model trained on 688 public filings) names the event type right on **184** filings and catches **103 of 105** urgent ones. The same model untrained: 157 and 93. Claude Sonnet 5: 164 and 100, at $2.33 per 1,000 filings. The gain over the untrained model is statistically real (McNemar: 33 filings won, 6 lost, p = 0.00001).

| System (200 unseen 8-Ks, 105 urgent) | Event type right | Urgent caught | False alarms | $ per 1,000 |
|---|---:|---:|---:|---:|
| Claude Sonnet 5 (frontier) | 164 | 100 | 6 | 2.33 |
| GPT-5.6 Luna (frontier) | 151 | 99 | 7 | 0.15 |
| DeepSeek V4.1 Flash (open) | 160 | 103 | 6 | 0.22 |
| GLM 5.3 Flash (open) / with our harness | 168 / 173 | 100 / 103 | 6 / 5 | 0.19 / 0.10 |
| gpt-oss-120b (open) / with our harness | 151 / 161 | 96 / 99 | 5 / 4 | 0.14 / 0.08 |
| Muse Glimmer 30B untrained (baseline) | 157 | 93 | 2 | not measured |
| **Harness + Muse Glimmer 30B trained (ours)** | **184** | **103** | **3** | not measured |

Full table and sources: [results/comparison-triage_8k](results/comparison-triage_8k/).

**Why the answers can be trusted:** every 8-K carries an SEC item code (for example 5.02 = leadership change). We hide it, the model reads only the narrative text, and Python compares the model's call with the code. No person labelled anything and no model graded another model.

## The problem
Finance analysts read thousands of SEC filings a week: fundraising forms to pull facts from, and event filings where missing an urgent one is costly. Frontier models can do this, but at volume they are expensive and the data leaves your control. Our question: can a small open model, trained for the job, match a frontier model's accuracy at a fraction of the price and time?

## What we measured
Every system is scored on the same fixed held-out test set, on three dimensions:

| Accuracy | Price | Speed |
|---|---|---|
| Score against the SEC's own structured data | $ per 1,000 items | Median and p95 seconds per item |

## Experiments
| # | Experiment | Result |
|---|---|---|
| 01 | [Forms extraction](experiments/01-forms-extraction/): 9 facts from a Form D | 0.999 trained vs 0.987 untrained |
| 02 | [Sorting 8-K filings](experiments/02-sorting-8k/): urgent or routine | Frontier reference and trained sorter |
| 05 | [8-K harness, no training](experiments/05-8k-harness-no-training/) | 157 > 162 event types; model reads 56% of filings |
| 06 | [8-K harness + trained Muse](experiments/06-8k-harness-trained/) | 157 > 184 event types, 93 > 103 urgent (p = 0.00001) |
| 07 | [8-K on GLM 5.3 Flash and gpt-oss](experiments/07-8k-glm-trained/) | Harness lifts gpt-oss 151 > 161 (p = 0.002); GLM training blocked by Fireworks |

Each folder has the task, the data, every system we tried (failures included), the significance tests and the commands to reproduce.

## Reproduce
```bash
python3 -m venv venv && venv/bin/pip install -e '.[dev]'
venv/bin/python -m bench.starter      # unpack the public SEC test sets
venv/bin/pytest -q                     # 65 checks
export FIREWORKS_API_KEY=...           # never commit it
```
Then follow the commands in each experiment folder. Every run saves one row per test item under `results/`, so every number can be checked without re-running a model. Data sources: [DATA.md](DATA.md).

## Team
finance bros, a team of four. Names are kept out of this repo on purpose.

## Disclosure
The scoring bench, the test sets and earlier runs were built before today in a team member's [open-model-eval](https://github.com/gvm-agents/open-model-eval) (full description: [docs/bench-overview.md](docs/bench-overview.md)). Built today: the trained Forms models, experiments 05 to 07, the frontier comparison, and this write-up. We used AI coding assistants (Claude Code) throughout. Public data only.

Demo video: link follows.
