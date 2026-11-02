# Benchmark report: run smoke-1030

Score: 0 to 1 against answer keys built by Python from SEC data. 'Invented' = numbers given that appear nowhere in the input. Cost per 1,000 items from published prices; local lanes show $0 per call (hardware and upkeep are in the economics section).

## Overall (equal weight per task)

| lane | group | tasks | mean_score | invented_per_100 | p50_s | usd_per_1000 |
|---|---|---|---|---|---|---|
| haiku55 | frontier | 7 | 0.0 | 0.0 | 0.0 | 0.0 |

## By task

| task | lane | n | score | valid_pct | errors | invented_per_100 | p50_s | p95_s | tok_per_s | usd_per_1000 |
|---|---|---|---|---|---|---|---|---|---|---|
| adv_extract | haiku55 | 5 | 0.0 | 0.0 | 5 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| format_table | haiku55 | 5 | 0.0 | 0.0 | 5 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| formd_extract | haiku55 | 5 | 0.0 | 0.0 | 5 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| longdoc | haiku55 | 5 | 0.0 | 0.0 | 5 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| name_match | haiku55 | 5 | 0.0 | 0.0 | 5 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| sector | haiku55 | 5 | 0.0 | 0.0 | 5 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| snapshot | haiku55 | 5 | 0.0 | 0.0 | 5 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## Is hosting an open model worth it? (assumptions in economics.json)

Monthly items: 20,000 (scenario multipliers: [1, 10, 100]). Upkeep: 6 hours a month at $150 an hour; dedicated GPU $8.0/hour x 730 hours.

| lane | mean score | 1x volume $/month | 10x volume $/month | 100x volume $/month |
|---|---|---|---|---|
| haiku55 | 0.0 | 0 | 0 | 0 |

A dedicated Fireworks GPU (needed only above serverless limits or for custom models without serverless support) adds about $5,840 a month plus upkeep ($900). Serverless open models need no hosting or upkeep: you pay per call, like Claude.
