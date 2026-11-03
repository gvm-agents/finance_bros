# Every system on the same 200 independent 8-K filings

Set `triage_8k`: 200 filings, 105 urgent, none used for training or design. Same prompt (`bench/triage_prompt.py`) for every row. Answer key: the filing's own SEC item code, hidden from the model. Built by `python -m bench.compare_8k` from saved answers only.

| System | Group | Event type right (of 200) | Urgent caught | False alarms | Invalid | $ per 1,000 | p50 s |
|---|---|---:|---:|---:|---:|---:|---:|
| Claude Sonnet 5 | frontier | 164 | 100 of 105 | 6 | 0 | 2.333 | 1.29 |
| GPT-5.6 Luna | frontier | 151 | 99 of 105 | 7 | 0 | 0.148 | 0.76 |
| DeepSeek V4.1 Flash | open, ready-made | 160 | 103 of 105 | 6 | 0 | 0.218 | 0.75 |
| GLM 5.3 Flash | open, ready-made | 168 | 100 of 105 | 6 | 0 | 0.186 | 1.26 |
| Harness + GLM 5.3 Flash | open, ready-made + harness | 173 | 103 of 105 | 5 | 0 | 0.103 | 1.26 |
| gpt-oss-120b | open, ready-made | 151 | 96 of 105 | 5 | 0 | 0.141 | 0.51 |
| Harness + gpt-oss-120b | open, ready-made + harness | 161 | 99 of 105 | 4 | 0 | 0.078 | 0.51 |
| Muse Glimmer 30B untrained (baseline) | open, ready-made | 157 | 93 of 105 | 2 | 11 | not measured | not measured |
| Harness + Muse Glimmer 30B untrained (baseline) | open, ready-made + harness | 162 | 97 of 105 | 2 | 7 | not measured | not measured |
| Muse Glimmer 30B trained (ours) | open, trained | 183 | 102 of 105 | 3 | 0 | not measured | not measured |
| Harness + Muse Glimmer 30B trained (ours) | open, trained + harness | 184 | 103 of 105 | 3 | 0 | not measured | not measured |

Harness rows: Python rules settle 44.5% of filings at $0; the model reads the rest, so its cost is scaled by the share it reads. Muse Glimmer runs on the Fireworks training sampler, so its price and speed per filing were not measured. Costs are tokens x list price, not checked against billing pages. Frontier runs: 2026-11-02, from this repo's lanes `sonnet5_or` (OpenRouter) and `gpt56luna_none_oa` (OpenAI).
