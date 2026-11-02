# Benchmark report: run smoke-1030c

Score: 0 to 1 against answer keys built by Python from SEC data. 'Invented' = numbers given that appear nowhere in the input. Cost per 1,000 items from published prices; local lanes show $0 per call (hardware and upkeep are in the economics section).

## Overall (equal weight per task)

| lane | group | tasks | mean_score | invented_per_100 | p50_s | usd_per_1000 |
|---|---|---|---|---|---|---|
| sonnet5 | frontier | 7 | 0.894 | 14.3 | 1.31 | 14.674 |
| opus48 | frontier | 7 | 0.887 | 14.3 | 3.01 | 36.89 |

## By task

| task | lane | n | score | valid_pct | errors | invented_per_100 | p50_s | p95_s | tok_per_s | usd_per_1000 |
|---|---|---|---|---|---|---|---|---|---|---|
| adv_extract | opus48 | 2 | 1.0 | 100.0 | 0 | 50.0 | 3.01 | 3.01 | 39.0 | 85.645 |
| format_table | opus48 | 2 | 0.5 | 100.0 | 0 | 0.0 | 3.23 | 3.23 | 51.3 | 3.792 |
| formd_extract | opus48 | 2 | 0.956 | 100.0 | 0 | 0.0 | 3.64 | 3.64 | 64.5 | 31.772 |
| longdoc | opus48 | 2 | 0.75 | 100.0 | 0 | 50.0 | 1.46 | 1.46 | 33.6 | 114.987 |
| name_match | opus48 | 2 | 1.0 | 100.0 | 0 | 0.0 | 1.1 | 1.1 | 8.3 | 1.058 |
| sector | opus48 | 2 | 1.0 | 100.0 | 0 | 0.0 | 0.88 | 0.88 | 11.4 | 11.607 |
| snapshot | opus48 | 2 | 1.0 | 100.0 | 0 | 0.0 | 4.1 | 4.1 | 82.6 | 9.368 |
| adv_extract | sonnet5 | 2 | 1.0 | 100.0 | 0 | 50.0 | 1.32 | 1.32 | 82.7 | 34.408 |
| format_table | sonnet5 | 2 | 0.55 | 100.0 | 0 | 0.0 | 1.18 | 1.18 | 53.8 | 0.887 |
| formd_extract | sonnet5 | 2 | 0.956 | 100.0 | 0 | 0.0 | 3.07 | 3.07 | 74.5 | 12.679 |
| longdoc | sonnet5 | 2 | 0.75 | 100.0 | 0 | 50.0 | 1.31 | 1.31 | 41.2 | 46.065 |
| name_match | sonnet5 | 2 | 1.0 | 100.0 | 0 | 0.0 | 0.6 | 0.6 | 13.6 | 0.423 |
| sector | sonnet5 | 2 | 1.0 | 100.0 | 0 | 0.0 | 0.67 | 0.67 | 15.2 | 4.643 |
| snapshot | sonnet5 | 2 | 1.0 | 100.0 | 0 | 0.0 | 3.08 | 3.08 | 96.9 | 3.612 |

## Is hosting an open model worth it? (assumptions in economics.json)

Monthly items: 20,000 (scenario multipliers: [1, 10, 100]). Upkeep: 6 hours a month at $150 an hour; dedicated GPU $8.0/hour x 730 hours.

| lane | mean score | 1x volume $/month | 10x volume $/month | 100x volume $/month |
|---|---|---|---|---|
| sonnet5 | 0.894 | 293 | 2,935 | 29,348 |
| opus48 | 0.887 | 738 | 7,378 | 73,780 |

A dedicated Fireworks GPU (needed only above serverless limits or for custom models without serverless support) adds about $5,840 a month plus upkeep ($900). Serverless open models need no hosting or upkeep: you pay per call, like Claude.
