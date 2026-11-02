# Benchmark report: run local-probe-1030

Score: 0 to 1 against answer keys built by Python from SEC data. 'Invented' = numbers given that appear nowhere in the input. Cost per 1,000 items from published prices; local lanes show $0 per call (hardware and upkeep are in the economics section).

## Overall (equal weight per task)

| lane | group | tasks | mean_score | invented_per_100 | p50_s | usd_per_1000 |
|---|---|---|---|---|---|---|
| gemma4_e2b_local | open-local | 7 | 0.784 | 14.3 | 5.06 | 0.0 |

## By task

| task | lane | n | score | valid_pct | errors | invented_per_100 | p50_s | p95_s | tok_per_s | usd_per_1000 |
|---|---|---|---|---|---|---|---|---|---|---|
| adv_extract | gemma4_e2b_local | 2 | 1.0 | 100.0 | 0 | 50.0 | 6.47 | 6.47 | 135.6 | 0.0 |
| format_table | gemma4_e2b_local | 2 | 0.55 | 100.0 | 0 | 0.0 | 2.22 | 2.22 | 225.9 | 0.0 |
| formd_extract | gemma4_e2b_local | 2 | 0.912 | 100.0 | 0 | 0.0 | 5.82 | 5.82 | 182.0 | 0.0 |
| longdoc | gemma4_e2b_local | 2 | 0.625 | 100.0 | 0 | 50.0 | 7.82 | 7.82 | 118.0 | 0.0 |
| name_match | gemma4_e2b_local | 2 | 0.5 | 100.0 | 0 | 0.0 | 1.87 | 1.87 | 206.9 | 0.0 |
| sector | gemma4_e2b_local | 2 | 1.0 | 100.0 | 0 | 0.0 | 5.06 | 5.06 | 182.2 | 0.0 |
| snapshot | gemma4_e2b_local | 2 | 0.9 | 100.0 | 0 | 0.0 | 3.15 | 3.15 | 224.9 | 0.0 |

## Is hosting an open model worth it? (assumptions in economics.json)

Monthly items: 20,000 (scenario multipliers: [1, 10, 100]). Upkeep: 6 hours a month at $150 an hour; dedicated GPU $8.0/hour x 730 hours.

| lane | mean score | 1x volume $/month | 10x volume $/month | 100x volume $/month |
|---|---|---|---|---|
| gemma4_e2b_local | 0.784 | 900 | 900 | 900 |

A dedicated Fireworks GPU (needed only above serverless limits or for custom models without serverless support) adds about $5,840 a month plus upkeep ($900). Serverless open models need no hosting or upkeep: you pay per call, like Claude.
