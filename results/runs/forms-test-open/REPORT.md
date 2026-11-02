# Benchmark report: run forms-test-open

Score: 0 to 1 against answer keys built by Python from SEC data. 'Invented' = numbers given that appear nowhere in the input. Cost per 1,000 items from published prices; local lanes show $0 per call (hardware and upkeep are in the economics section).

## Overall (equal weight per task)

| lane | group | tasks | mean_score | invented_per_100 | p50_s | usd_per_1000 |
|---|---|---|---|---|---|---|
| deepseek41_fw_off | open-cloud | 1 | 0.986 | 0.0 | 1.28 | 1.208 |
| gptoss120_fw | open-cloud | 1 | 0.899 | 0.0 | 1.73 | 0.771 |

## By task

| task | lane | n | score | valid_pct | errors | invented_per_100 | p50_s | p95_s | tok_per_s | usd_per_1000 |
|---|---|---|---|---|---|---|---|---|---|---|
| formd_extract | deepseek41_fw_off | 120 | 0.986 | 100.0 | 0 | 0.0 | 1.28 | 1.84 | 134.6 | 1.208 |
| formd_extract | gptoss120_fw | 120 | 0.899 | 100.0 | 0 | 0.0 | 1.73 | 2.99 | 237.2 | 0.771 |

## Is hosting an open model worth it? (assumptions in economics.json)

Monthly items: 20,000 (scenario multipliers: [1, 10, 100]). Upkeep: 6 hours a month at $150 an hour; dedicated GPU $8.0/hour x 730 hours.

| lane | mean score | 1x volume $/month | 10x volume $/month | 100x volume $/month |
|---|---|---|---|---|
| deepseek41_fw_off | 0.986 | 24 | 242 | 2,416 |
| gptoss120_fw | 0.899 | 15 | 154 | 1,542 |

A dedicated Fireworks GPU (needed only above serverless limits or for custom models without serverless support) adds about $5,840 a month plus upkeep ($900). Serverless open models need no hosting or upkeep: you pay per call, like Claude.
