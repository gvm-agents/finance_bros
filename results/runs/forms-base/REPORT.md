# Benchmark report: run forms-base

Score: 0 to 1 against answer keys built by Python from SEC data. 'Invented' = numbers given that appear nowhere in the input. Cost per 1,000 items from published prices; local lanes show $0 per call (hardware and upkeep are in the economics section).

## Overall (equal weight per task)

| lane | group | tasks | mean_score | invented_per_100 | p50_s | usd_per_1000 |
|---|---|---|---|---|---|---|
| deepseek41_fw_off | open-cloud | 1 | 0.987 | 0.0 | 1.36 | 1.253 |
| gptoss120_fw | open-cloud | 1 | 0.906 | 0.0 | 1.88 | 0.796 |

## By task

| task | lane | n | score | valid_pct | errors | invented_per_100 | p50_s | p95_s | tok_per_s | usd_per_1000 |
|---|---|---|---|---|---|---|---|---|---|---|
| formd_extract | deepseek41_fw_off | 40 | 0.987 | 100.0 | 0 | 0.0 | 1.36 | 2.66 | 132.0 | 1.253 |
| formd_extract | gptoss120_fw | 40 | 0.906 | 100.0 | 0 | 0.0 | 1.88 | 3.58 | 233.6 | 0.796 |

## Is hosting an open model worth it? (assumptions in economics.json)

Monthly items: 20,000 (scenario multipliers: [1, 10, 100]). Upkeep: 6 hours a month at $150 an hour; dedicated GPU $8.0/hour x 730 hours.

| lane | mean score | 1x volume $/month | 10x volume $/month | 100x volume $/month |
|---|---|---|---|---|
| deepseek41_fw_off | 0.987 | 25 | 251 | 2,506 |
| gptoss120_fw | 0.906 | 16 | 159 | 1,592 |

A dedicated Fireworks GPU (needed only above serverless limits or for custom models without serverless support) adds about $5,840 a month plus upkeep ($900). Serverless open models need no hosting or upkeep: you pay per call, like Claude.
