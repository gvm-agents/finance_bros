# Benchmark report: run fw-baseline-1030-rescored

Score: 0 to 1 against answer keys built by Python from SEC data. 'Invented' = numbers given that appear nowhere in the input. Cost per 1,000 items from published prices; local lanes show $0 per call (hardware and upkeep are in the economics section).

## Overall (equal weight per task)

| lane | group | tasks | mean_score | invented_per_100 | p50_s | usd_per_1000 |
|---|---|---|---|---|---|---|
| gptoss120_fw | open-cloud | 7 | 0.748 | 0.0 | 1.36 | 0.774 |

## By task

| task | lane | n | score | valid_pct | errors | invented_per_100 | p50_s | p95_s | tok_per_s | usd_per_1000 |
|---|---|---|---|---|---|---|---|---|---|---|
| adv_extract | gptoss120_fw | 40 | 0.961 | 100.0 | 0 | 0.0 | 1.36 | 1.9 | 108.1 | 1.721 |
| format_table | gptoss120_fw | 120 | 0.527 | 100.0 | 0 | 0.0 | 0.94 | 1.99 | 187.2 | 0.144 |
| formd_extract | gptoss120_fw | 120 | 0.855 | 100.0 | 0 | 0.0 | 2.09 | 3.22 | 211.5 | 0.775 |
| longdoc | gptoss120_fw | 39 | 0.558 | 100.0 | 0 | 0.0 | 1.68 | 2.54 | 100.3 | 2.271 |
| name_match | gptoss120_fw | 82 | 0.622 | 100.0 | 0 | 0.0 | 0.39 | 0.62 | 96.7 | 0.05 |
| sector | gptoss120_fw | 42 | 0.738 | 100.0 | 0 | 0.0 | 0.44 | 0.76 | 87.7 | 0.241 |
| snapshot | gptoss120_fw | 120 | 0.973 | 100.0 | 0 | 0.0 | 1.38 | 2.06 | 204.3 | 0.217 |

## Is hosting an open model worth it? (assumptions in economics.json)

Monthly items: 20,000 (scenario multipliers: [1, 10, 100]). Upkeep: 6 hours a month at $150 an hour; dedicated GPU $8.0/hour x 730 hours.

| lane | mean score | 1x volume $/month | 10x volume $/month | 100x volume $/month |
|---|---|---|---|---|
| gptoss120_fw | 0.748 | 15 | 155 | 1,548 |

A dedicated Fireworks GPU (needed only above serverless limits or for custom models without serverless support) adds about $5,840 a month plus upkeep ($900). Serverless open models need no hosting or upkeep: you pay per call, like Claude.
