# Where we are now (Nov 2, about 12:20 PT)

Read this first if you are joining late. It is newer than every other page; where they differ, this page wins.

## The two results we are submitting

| Experiment | Before | After | Is the gain real? |
|---|---|---|---|
| **Sorting** (headline): is an SEC 8-K filing urgent? | Frontier model (Claude Sonnet 5) on 568 held-out filings: caught 236 of 240 urgent, 21 false alarms, $1.80 per 1,000 | Trained open model (LoRA "triage-4"): runs once at 3:30 on the same 568 filings. On practice it caught 82 of 82 with 4 false alarms | Tested at 3:55 with `python -m bench.stats` |
| **Forms**: pull 9 facts out of an SEC Form D | gpt-oss-120b on 120 held-out forms: score 0.899; DeepSeek: 0.986 | Trained open model (LoRA) on the same 120 forms: **0.999** (twice, two training runs). Same model untrained, given enough answer space: 0.987 | Yes. vs gpt-oss: fully right on 90 more forms, 0 fewer (McNemar p = 2e-27); vs DeepSeek: 17 more, 1 fewer (p = 0.0001). Same model untrained vs trained: 17 more, 0 fewer (p = 0.00002). vs frontier (Claude Sonnet 5, 0.988, $13.87 per 1,000 forms): 15 more, 0 fewer (p = 0.00006). Bootstrap 95% ranges exclude zero for all three |

Target for Sorting, fixed before the final run: catch at least 99% of urgent filings (238 of 240) with no more false alarms than the frontier model (21), then lowest cost.

## What we dropped, and what did not work

- Dropped for time: data centers, algorithm effects. News is reported as is (agreed with a person on 16 of 20 headlines; our bar was 18).
- Did not work (report these): Inkling (new US open model) cost more than the frontier model with no gain; gpt-oss with extra thinking scored 0.40 on Forms (its reasoning used up the answer space); a cheaper model (Nemotron Lightning) scored 0.55 on Forms; no pairing of ready-made models caught all 82 urgent practice filings.

## Who does what until 4:15

| Role | Does |
|---|---|
| Lead | The story, talks to judges, gives the pitch; approves anything paid |
| Agent (on the lead's machines) | Runs every paid job, the 3:30 final, the significance tests, fills in the write-up |
| Forms owner | Turns the Forms result into one slide: before/after table, why the trained model wins, the field it fixed most |
| Presentation owner | Slides from the submission draft; rehearses the live news dashboard demo |

## If you just arrived: 15 minutes to useful

1. Clone the repo, make the venv, run `venv/bin/pytest -q` (65 passed). See [quick start](quickstart.md).
2. Unzip the shared test-data zip inside the repo folder, then run `venv/bin/python -m bench.router simulate` (free; replays saved answers).
3. Read the two tables above. Then pick one: check the slides against these numbers, or rehearse the demo with `venv/bin/python -m bench.dashboard --demo --replay demo/headlines.jsonl --speed 600` and open http://127.0.0.1:8765.

No keys are needed for any of this. Paid runs go through the lead.

## Fixed times

3:15 lock (no new ideas) · 3:30 final run, once · 3:55 significance tests · 4:15 submit (hard stop 4:30)
