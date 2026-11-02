# Benchmark report: run baseline-1030-rescored

Score: 0 to 1 against answer keys built by Python from SEC data. 'Invented' = numbers given that appear nowhere in the input. Cost per 1,000 items from published prices; local lanes show $0 per call (hardware and upkeep are in the economics section).

## Overall (equal weight per task)

| lane | group | tasks | mean_score | invented_per_100 | p50_s | usd_per_1000 |
|---|---|---|---|---|---|---|
| sonnet5 | frontier | 7 | 0.83 | 0.0 | 1.08 | 14.754 |
| opus48 | frontier | 7 | 0.829 | 0.0 | 1.4 | 36.999 |
| haiku45 | frontier | 7 | 0.773 | 0.5 | 1.02 | 5.585 |

## By task

| task | lane | n | score | valid_pct | errors | invented_per_100 | p50_s | p95_s | tok_per_s | usd_per_1000 |
|---|---|---|---|---|---|---|---|---|---|---|
| adv_extract | haiku45 | 40 | 0.961 | 100.0 | 0 | 0.0 | 1.3 | 1.53 | 72.5 | 12.793 |
| format_table | haiku45 | 120 | 0.505 | 100.0 | 0 | 0.0 | 0.62 | 0.96 | 81.3 | 0.392 |
| formd_extract | haiku45 | 120 | 0.927 | 100.0 | 0 | 0.0 | 2.07 | 3.17 | 103.1 | 5.489 |
| longdoc | haiku45 | 39 | 0.643 | 100.0 | 0 | 0.0 | 1.02 | 1.16 | 53.2 | 17.509 |
| name_match | haiku45 | 82 | 0.72 | 100.0 | 0 | 0.0 | 0.42 | 0.6 | 29.0 | 0.175 |
| sector | haiku45 | 42 | 0.786 | 100.0 | 0 | 0.0 | 0.56 | 0.75 | 24.5 | 1.637 |
| snapshot | haiku45 | 120 | 0.87 | 100.0 | 0 | 3.3 | 1.67 | 2.02 | 102.6 | 1.1 |
| adv_extract | opus48 | 40 | 0.961 | 100.0 | 0 | 0.0 | 1.71 | 3.18 | 49.5 | 84.668 |
| format_table | opus48 | 120 | 0.64 | 100.0 | 0 | 0.0 | 1.1 | 2.03 | 66.8 | 2.894 |
| formd_extract | opus48 | 120 | 0.919 | 100.0 | 0 | 0.0 | 2.75 | 4.62 | 93.2 | 34.68 |
| longdoc | opus48 | 39 | 0.62 | 97.4 | 0 | 0.0 | 1.4 | 1.71 | 49.0 | 115.229 |
| name_match | opus48 | 82 | 0.829 | 100.0 | 0 | 0.0 | 0.57 | 0.77 | 13.9 | 0.979 |
| sector | opus48 | 42 | 0.833 | 100.0 | 0 | 0.0 | 0.77 | 0.9 | 14.9 | 11.557 |
| snapshot | opus48 | 120 | 1.0 | 100.0 | 0 | 0.0 | 3.66 | 4.06 | 82.3 | 8.986 |
| adv_extract | sonnet5 | 40 | 0.961 | 100.0 | 0 | 0.0 | 1.32 | 1.71 | 76.1 | 33.991 |
| format_table | sonnet5 | 120 | 0.689 | 100.0 | 0 | 0.0 | 1.08 | 2.07 | 73.5 | 1.198 |
| formd_extract | sonnet5 | 120 | 0.891 | 100.0 | 0 | 0.0 | 2.19 | 3.45 | 114.1 | 13.851 |
| longdoc | sonnet5 | 39 | 0.613 | 100.0 | 0 | 0.0 | 1.08 | 1.45 | 47.3 | 45.705 |
| name_match | sonnet5 | 82 | 0.878 | 100.0 | 0 | 0.0 | 0.59 | 0.89 | 9.6 | 0.396 |
| sector | sonnet5 | 42 | 0.786 | 100.0 | 0 | 0.0 | 0.62 | 0.89 | 14.6 | 4.603 |
| snapshot | sonnet5 | 120 | 0.99 | 100.0 | 0 | 0.0 | 3.15 | 3.75 | 93.3 | 3.536 |

## Is hosting an open model worth it? (assumptions in economics.json)

Monthly items: 20,000 (scenario multipliers: [1, 10, 100]). Upkeep: 6 hours a month at $150 an hour; dedicated GPU $8.0/hour x 730 hours.

| lane | mean score | 1x volume $/month | 10x volume $/month | 100x volume $/month |
|---|---|---|---|---|
| sonnet5 | 0.83 | 295 | 2,951 | 29,508 |
| opus48 | 0.829 | 740 | 7,400 | 73,998 |
| haiku45 | 0.773 | 112 | 1,117 | 11,170 |

A dedicated Fireworks GPU (needed only above serverless limits or for custom models without serverless support) adds about $5,840 a month plus upkeep ($900). Serverless open models need no hosting or upkeep: you pay per call, like Claude.
