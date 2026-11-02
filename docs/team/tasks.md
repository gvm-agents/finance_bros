# The experiments

Each one follows the same steps, so results compare cleanly.

1. **Claim it.** Say which experiment you are taking.
2. **Freeze a baseline.** Run the current setup before changing anything.
3. **Change one thing at a time:** a model, a setting or a route.
4. **Measure** with the same items and the same [measures](metrics.md).
5. **Retest the winner** on items not used for tuning.
6. **Record** what changed, what it cost, and what it did not fix.

All commands below were run from a clean copy of this repo.

## 1. Extract facts from forms

**The job:** read a government form and return the facts as clean data. Form D reports a private fundraising. Form ADV describes an investment adviser.

**The answer key:** the structured data filed with the SEC, so Python can mark each answer.

```bash
venv/bin/python -m bench run --lanes gptoss120_fw,deepseek41_fw_off --tasks formd_extract --n 40 --max-usd 0.25 --run forms-1
venv/bin/python -m bench report --run forms-1
```

Try next: `--tasks adv_extract`, thinking on and off, smaller models.

## 2. Data centers: are the commitments funded?

**The job:** compare what companies have committed to spend with their cash flow and debt.

**How it works:** Python reads spending, cash flow and debt from SEC data. Models find commitment passages, each with a word-for-word quote. Python reads the dollar amount from the quote, so a model never supplies a number.

```bash
venv/bin/python -m bench.dc_funding --max-usd 0.05 --out results/dc-1
```

Results are in `results/dc-1/table-gptoss120_fw.json`.

**Known limit:** a person must check the top rows. Companies rarely report spending by category, so a table split that way comes back about two-thirds blank.

## 3. How new algorithms affect AI suppliers and customers

**The job:** collect evidence across chip makers, clouds, software companies and end users on how cheaper or better algorithms change demand.

**The test:** ask a frontier model the same question with and without evidence collected by open models, and score both against a [checklist fixed in advance](../evidence-test.md).

```bash
venv/bin/python -m bench.sets --out results/sets-1
venv/bin/python -m bench.evidence armb --topic algo --pull results/sets-1 --out results/evidence-1 --max-usd 0.25
```

Fix the checklist before you run. The frontier step needs a frontier model account, so the team lead runs it; `bench.sets` is free. Report added cost and whether the gain was worth it.

## 4. Real-time news tracking

**The job:** read public news as it arrives, sort it by topic and importance, and show a story rising and fading across sources.

```bash
venv/bin/python -m bench.feed_items --out results/feeds.jsonl --stats results/feed-stats.json
venv/bin/python -m bench.live_news --snapshot results/feeds.jsonl --lane gptoss120_fw --n 30 --tight --out results/news-1 --max-usd 0.05
```

News has no answer key, so report behavior and cost, and mark a sample by hand if you need accuracy. Reading all feeds takes about a minute.

## 5. Sorting by importance (the headline experiment)

SEC event filings carry their own labels, which gives this job a real answer key. This is the sharpest test of the router.

**Target:** catch at least 99% of urgent filings, with no more false alarms than the frontier model. Among designs that hit it: lowest cost per 1,000 filings first, then most filings per hour.

| Set | Filings | Urgent | Use |
|---|---|---|---|
| `triage_8k_fresh` | 181 | 82 | Practice: tune on it as often as you like |
| `triage_8k_final` | 258 | 133 | First final set; part of `triage_8k_final99` |
| `triage_8k_final99` | 568 | 240 | Final exam for the 99% target (at most 2 misses): run once, at the end, after the design is locked |

```bash
venv/bin/python -m bench.router simulate                       # every saved model and the current router, free
venv/bin/python -m bench.router combos                         # every model and pair that hits the target, cheapest first, free
venv/bin/python -m bench.router live --job triage_8k --task triage_8k_fresh --n 20 --workers 6 --first-only --max-usd 0.02 --run router-1
```

Score each run against the answer key; every score is added to `results/scoreboard.jsonl`, which feeds the before-and-after chart:

```bash
venv/bin/python -m bench.router score --run router-1 --max-false-alarms 11 --note "baseline"
```

`--max-false-alarms` is the frontier model's count on the same set: 11 on the practice set. For a run of several models made with `bench run`, add `--lane <model>`.

`--first-only` needs no local model. Without it, a second reader runs through Ollama. To change the design, edit `routes.json` (which model reads first, which reads second, and `second_read`), preview with `combos`, then confirm live.
