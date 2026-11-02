# 03 Forms extraction with GLM 5.3 Flash, fully serverless

Same job, data and test set as [01](../01-forms-extraction/). Why a second model: GLM 5.3 Flash is on Fireworks serverless inference **and** serverless training, so the trained model gets a real price per 1,000 forms and a real speed, with no rented GPU.

| System | Score | $ per 1,000 | Median s | p95 s | Status |
|---|---:|---:|---:|---:|---|
| GLM 5.3 Flash, untrained | 0.944 | 1.16 | 5.98 | 28.79 | done, 5 of 120 answers invalid |
| GLM 5.3 Flash + LoRA on the 280 training forms | | | | | next |

Baseline run: `../01-forms-extraction/results/glm-base-formd-test`.
