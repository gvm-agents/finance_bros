# Benchmark report: run azure-baseline-1031b

Score: 0 to 1 against answer keys built by Python from SEC data. 'Invented' = numbers given that appear nowhere in the input. Cost per 1,000 items from published prices; local lanes show $0 per call (hardware and upkeep are in the economics section).

## Overall (equal weight per task)

| lane | group | tasks | mean_score | invented_per_100 | p50_s | usd_per_1000 |
|---|---|---|---|---|---|---|
| gpt56luna | frontier | 7 | 0.81 | 0.0 | 1.45 | 1.067 |
| gpt56terra | frontier | 7 | 0.793 | 0.7 | 1.52 | 10.282 |

## By task

| task | lane | n | score | valid_pct | errors | invented_per_100 | p50_s | p95_s | tok_per_s | usd_per_1000 |
|---|---|---|---|---|---|---|---|---|---|---|
| adv_extract | gpt56luna | 40 | 1.0 | 100.0 | 0 | 0.0 | 1.41 | 5.84 | 31.3 | 2.237 |
| format_table | gpt56luna | 120 | 0.643 | 100.0 | 0 | 0.0 | 1.45 | 2.56 | 67.0 | 0.147 |
| formd_extract | gpt56luna | 120 | 0.902 | 100.0 | 0 | 0.0 | 1.88 | 3.11 | 133.2 | 0.969 |
| longdoc | gpt56luna | 39 | 0.551 | 100.0 | 0 | 0.0 | 2.26 | 12.45 | 75.2 | 3.213 |
| name_match | gpt56luna | 82 | 0.854 | 100.0 | 0 | 0.0 | 1.16 | 3.15 | 58.1 | 0.119 |
| sector | gpt56luna | 42 | 0.762 | 100.0 | 0 | 0.0 | 0.93 | 1.64 | 23.1 | 0.303 |
| snapshot | gpt56luna | 120 | 0.961 | 100.0 | 0 | 0.0 | 2.54 | 4.06 | 132.1 | 0.482 |
| adv_extract | gpt56terra | 40 | 1.0 | 100.0 | 0 | 0.0 | 1.34 | 5.13 | 29.6 | 22.282 |
| format_table | gpt56terra | 120 | 0.625 | 100.0 | 0 | 0.0 | 1.52 | 4.26 | 17.9 | 1.686 |
| formd_extract | gpt56terra | 120 | 0.92 | 100.0 | 0 | 0.0 | 1.57 | 2.5 | 21.2 | 8.263 |
| longdoc | gpt56terra | 39 | 0.515 | 100.0 | 0 | 5.1 | 3.18 | 18.17 | 71.0 | 33.032 |
| name_match | gpt56terra | 82 | 0.878 | 100.0 | 0 | 0.0 | 1.22 | 4.2 | 49.2 | 1.136 |
| sector | gpt56terra | 42 | 0.786 | 100.0 | 0 | 0.0 | 1.13 | 1.73 | 30.0 | 3.172 |
| snapshot | gpt56terra | 120 | 0.825 | 100.0 | 0 | 0.0 | 1.71 | 3.75 | 87.2 | 2.401 |

## Is hosting an open model worth it? (assumptions in economics.json)

Monthly items: 20,000 (scenario multipliers: [1, 10, 100]). Upkeep: 6 hours a month at $150 an hour; dedicated GPU $8.0/hour x 730 hours.

| lane | mean score | 1x volume $/month | 10x volume $/month | 100x volume $/month |
|---|---|---|---|---|
| gpt56luna | 0.81 | 21 | 213 | 2,134 |
| gpt56terra | 0.793 | 206 | 2,056 | 20,564 |

A dedicated Fireworks GPU (needed only above serverless limits or for custom models without serverless support) adds about $5,840 a month plus upkeep ($900). Serverless open models need no hosting or upkeep: you pay per call, like Claude.
