# Test results, Sunday Nov 1, 2026
Runs: screen-1101, fresh-1101, fresh-1101-local, fresh-1101-mini, inject-rune-1101, ramp-1101.jsonl, live-news-1101-*, dc-funding-1101, adv-vintage-1101, training/triage-2, tuned-deploy-1101.

## Fresh 8-K test: 181 filings never used before, 82 high priority
Rune thresholds were picked on the earlier 200 filings, then frozen.
| Reader | Caught of 82 | Recall % | 95% range | False alarms | Priority right % | $ per 1,000 | Median s |
|---|---|---|---|---|---|---|---|
| Rune, then Gemma 12B on unsure 15-20% | 81 | 98.8 | 93.4-99.8 | 11 | | 0.025 | 0.19 / 0.96 |
| Gemma 12B alone | 81 | 98.8 | 93.4-99.8 | 10 | 93.9 | 0 | 0.96 |
| Rune or trained Muse Glimmer (combination picked after seeing this set) | 81 | 98.8 | 93.4-99.8 | 7 | 95.6 | GPU hours | |
| Sonnet 5 | 80 | 97.6 | 91.5-99.3 | 11 | 92.8 | 1.897 | 0.58 |
| DeepSeek off | 80 | 97.6 | 91.5-99.3 | 9 | 93.9 | 0.176 | 0.53 |
| luna | 80 | 97.6 | 91.5-99.3 | 13 | 91.7 | 0.12 | 1.17 |
| Untrained Muse Glimmer | 79 | 96.3 | 89.8-98.7 | 5 | 95.6 | | |
| Rune, then Muse Spark on unsure | 79 | 96.3 | 89.8-98.7 | 9 | 93.4 | 1.388 | |
| gpt-oss | 78 | 95.1 | 88.1-98.1 | 8 | 93.4 | 0.119 | 0.41 |
| Gemma E2B on Mini | 78 | 95.1 | 88.1-98.1 | 23 | 85.1 | 0 | 0.57 |
| Rune alone | 77 | 93.9 | 86.5-97.4 | 7 | 93.4 | 0.025 | 0.19 |
| Trained Muse Glimmer, deployed | 77 | 93.9 | 86.5-97.4 | 0 | 97.2 | GPU hours | 0.75 |
Sets are stratified, about half high priority, so false-alarm rates in a real stream will differ. Differences of 1 to 3 filings here are not significant.

## Earlier 200 filings, 105 high priority
Rune 97, Sonnet 96, gpt-oss 95, DeepSeek off 104, Gemma 12B 104, GLM 5.3 Flash 98, MiniMax M3 98. Rune then Gemma 12B: 105 of 105, 18.5% sent up.

## Random 60 of those filings, 31 high priority (comparison only)
Kimi K3 31, Ember 1 31, Qwen 3.8 Max 31, Muse Spark Open 30, GLM 5.3 25 of 25 (45 filings; stopped, some calls hung for 6 minutes).

## Worker ramp, no refusals up to 192 workers on gpt-oss
48 workers: 78 filings a second. 96: one stall of about 90 seconds. 192: 68.5 a second, slowest 5% over 8 seconds. Rune: 9.8% refused at 6 workers, about 11 a second.

## Live news, 500 headlines, stricter importance rule
gpt-oss: 394 routine, 93 notable, 13 breaking, $0.045. DeepSeek: 386, 106, 8, $0.045. Agreed on 424 of 500. No answer key.

## Five-company data center test
Planned table: 66% blank on gpt-oss, 68% on Sonnet. Over the one-third gate, so the table now uses what filings disclose: results/dc-funding-1101/funding-table.md. gpt-oss $0.007, Sonnet $0.085. Both wrongly listed AWS customer commitments as Amazon's own spending; a person must check the top rows.

## Form ADV
results/adv-vintage-1101/vintage.json: venture exempt advisers 675 (Jan 2013) to 2,312 (Oct 2026).

## Trained model, second run (high-priority filings weighted 3 times)
82 of 82 caught, 7 false alarms, type right 77.3%. First run: 77 of 82, 1 false alarm (in session), type right 82.3%. Training moved the trade-off on purpose. Adapter: muse-starter-sl-triage-3.

## Evidence test, Sonnet alone (A) against Sonnet with open-model evidence (B)
Checklist fixed first: docs/evidence-test.md. Scores: results/evidence-1101/scores.json.
| Question | Arm | Cited facts | Verified current | Verified older | Verified % | Wrong | Unverified | Sonnet $ |
|---|---|---|---|---|---|---|---|---|
| Funding gap | A | 11 | 6 | 1 | 63.6 | 1 | 3 | 0.015 |
| Funding gap | B | 19 | 19 | 0 | 100 | 0 | 0 | 0.037 |
| Algorithm effects | A | 8 | 5 | 2 | 87.5 | 0 | 1 | 0.011 |
| Algorithm effects | B | 25 | 25 | 0 | 100 | 0 | 0 | 0.040 |
| Backlog | A | 5 | 2 | 0 | 40.0 | 1 | 2 | 0.008 |
| Backlog | B | 8 | 7 | 0 | 87.5 | 0 | 1 | 0.033 |
| Chip life | A | 0 | 0 | 0 | 0 | 0 | 0 | 0.011 |
| Chip life | B | 11 | 11 | 0 | 100 | 0 | 0 | 0.041 |
Passes the fixed rule on 4 of 4. Added cost for all four: $0.105 Sonnet plus $0.061 workers.
Limits: partly circular (B's facts come from the data the checker reads); one run per arm; chip-life A gave useful lives with no dollar values, so its zero understates it; the checker confirms a value, not its label (B called Alphabet's $924.4B leases and Amazon's $883.6B total commitments purchase commitments).
Conclusion changed: A named neoclouds as the widest gap, from memory; B named Alphabet, Amazon, Meta and Oracle from disclosed figures. A still had Amazon's servers at 6 years; B had the later change to 5.

## Question chain, replayable
results/evidence-1101/chain.jsonl, goals.json. Replay: venv/bin/python -m bench.evidence replay. Funding (68 new facts), backlog (9 new, 68 reused), chip life (14 new, 77 reused). Each answer named the next question.

## All approved sets: results/sets-1101/completeness.md
Fields found: data center 79%, algorithm 84%, healthcare 67%, Nebius and TSMC 75%. Latest structured data: Nebius Dec 2025, TSMC Dec 2024.

## Form ADV
Monthly lists: 172 files, 2012 to Oct 2026. Jan 2019 and a few other months missing; first readable list of each year is used. Venture flag starts Mar 2012; fund counts only from 2024. 2024 dip: 283 firms left the exempt list between Feb and May 2024, against 25 to 45 in the same months of 2021, 2022, 2023, 2025 and 2026. Of 323 gone from the venture count, 4 became registered advisers, 40 unticked venture, 279 left both lists. Cause not confirmed.
