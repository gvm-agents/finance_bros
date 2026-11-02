# Benchmark report: run smoke-1030b

Score: 0 to 1 against answer keys built by Python from SEC data. 'Invented' = numbers given that appear nowhere in the input. Cost per 1,000 items from published prices; local lanes show $0 per call (hardware and upkeep are in the economics section).

## Overall (equal weight per task)

| lane | group | tasks | mean_score | invented_per_100 | p50_s | usd_per_1000 |
|---|---|---|---|---|---|---|
| haiku45 | frontier | 7 | 0.777 | 11.4 | 1.09 | 5.864 |

## By task

| task | lane | n | score | valid_pct | errors | invented_per_100 | p50_s | p95_s | tok_per_s | usd_per_1000 |
|---|---|---|---|---|---|---|---|---|---|---|
| adv_extract | haiku45 | 5 | 0.943 | 100.0 | 0 | 40.0 | 1.42 | 1.43 | 71.2 | 12.809 |
| format_table | haiku45 | 5 | 0.46 | 100.0 | 0 | 0.0 | 0.75 | 0.87 | 75.4 | 0.382 |
| formd_extract | haiku45 | 5 | 0.95 | 100.0 | 0 | 0.0 | 2.89 | 3.8 | 70.4 | 5.305 |
| longdoc | haiku45 | 5 | 0.783 | 100.0 | 0 | 40.0 | 1.09 | 1.3 | 49.9 | 19.533 |
| name_match | haiku45 | 5 | 0.6 | 100.0 | 0 | 0.0 | 0.58 | 0.67 | 23.7 | 0.178 |
| sector | haiku45 | 5 | 0.8 | 100.0 | 0 | 0.0 | 0.63 | 0.7 | 21.9 | 1.75 |
| snapshot | haiku45 | 5 | 0.903 | 100.0 | 0 | 0.0 | 1.73 | 1.81 | 102.4 | 1.094 |

## Is hosting an open model worth it? (assumptions in economics.json)

Monthly items: 20,000 (scenario multipliers: [1, 10, 100]). Upkeep: 6 hours a month at $150 an hour; dedicated GPU $8.0/hour x 730 hours.

| lane | mean score | 1x volume $/month | 10x volume $/month | 100x volume $/month |
|---|---|---|---|---|
| haiku45 | 0.777 | 117 | 1,173 | 11,728 |

A dedicated Fireworks GPU (needed only above serverless limits or for custom models without serverless support) adds about $5,840 a month plus upkeep ($900). Serverless open models need no hosting or upkeep: you pay per call, like Claude.
