# finance bros: a penny analyst on open models

**Fireworks Deploy Buildathon, San Francisco, 2026-11-02.**

**Result:** a small open model, trained on public SEC data, reads private-fundraising filings (Form D) at **0.999** accuracy on 120 forms it never saw, up from **0.987** for the same model untrained and above every ready-made open model we tested (DeepSeek V4.1 Flash 0.986, gpt-oss-120b 0.899). The gain is statistically real (McNemar p = 0.00002 against the untrained model; company bootstrap excludes zero).

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
| 01 | [Forms extraction](experiments/01-forms-extraction/): 9 facts from a Form D | 0.999 trained vs 0.987 untrained, two training runs |
| 02 | [Sorting 8-K filings](experiments/02-sorting-8k/): urgent or routine | Final run on 568 held-out filings at 15:30 |
| 03 | [Forms on GLM 5.3 Flash](experiments/03-forms-glm-lora/): fully serverless training and inference | Baseline 0.944, $1.16 per 1,000 |
| 04 | [Forms router](experiments/04-forms-router/): rules first, model as fallback | Planned |

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
Bryan Finkel, Anika, Furkan Imamoglu.

## Disclosure
The scoring bench, the test sets and earlier runs were built before today in a team member's [open-model-eval](https://github.com/gvm-agents/open-model-eval) (full description: [docs/bench-overview.md](docs/bench-overview.md)). Built today: the trained Forms models, the final Sorting run, experiments 03 and 04, and this write-up. We used AI coding assistants (Claude Code) throughout. Public data only.

Demo video: link follows.
