# Benchmark report: run forms-r1

Score: 0 to 1 against answer keys built by Python from SEC data. 'Invented' = numbers given that appear nowhere in the input. Cost per 1,000 items from published prices; local lanes show $0 per call (hardware and upkeep are in the economics section).

## Overall (equal weight per task)

| lane | group | tasks | mean_score | invented_per_100 | p50_s | usd_per_1000 |
|---|---|---|---|---|---|---|
| deepseek41_fw_on_big | open-cloud | 1 | 0.997 | 0.0 | 19.6 | 4.835 |
| gptoss120_fw_high | open-cloud | 1 | 0.404 | 0.0 | 20.16 | 3.022 |

## By task

| task | lane | n | score | valid_pct | errors | invented_per_100 | p50_s | p95_s | tok_per_s | usd_per_1000 |
|---|---|---|---|---|---|---|---|---|---|---|
| formd_extract | deepseek41_fw_on_big | 29 | 0.997 | 100.0 | 0 | 0.0 | 19.6 | 38.26 | 159.0 | 4.835 |
| formd_extract | gptoss120_fw_high | 40 | 0.404 | 42.5 | 0 | 0.0 | 20.16 | 29.51 | 223.7 | 3.022 |

## Is hosting an open model worth it? (assumptions in economics.json)

Monthly items: 20,000 (scenario multipliers: [1, 10, 100]). Upkeep: 6 hours a month at $150 an hour; dedicated GPU $8.0/hour x 730 hours.

| lane | mean score | 1x volume $/month | 10x volume $/month | 100x volume $/month |
|---|---|---|---|---|
| deepseek41_fw_on_big | 0.997 | 97 | 967 | 9,670 |
| gptoss120_fw_high | 0.404 | 60 | 604 | 6,044 |

A dedicated Fireworks GPU (needed only above serverless limits or for custom models without serverless support) adds about $5,840 a month plus upkeep ($900). Serverless open models need no hosting or upkeep: you pay per call, like Claude.
