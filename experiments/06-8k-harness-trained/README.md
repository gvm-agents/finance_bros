# 06 8-K harness, trained: rules + trained Muse + Inkling tiebreak

Question: does the harness from 05 (Python rules, Muse, Python check, Inkling tiebreak) still help once Muse Glimmer 30B is trained on 8-K sorting?

Status: simulated 2026-11-02 on saved answers only (LoRA run `triage-4`). $0 spent, no model was called. A second LoRA run (`type-1`) is training now; see "Pending" below.

## The task

Same as 05: one of 10 event types per 8-K; six types are urgent (bankruptcy, cyber_incident, acquisition_or_sale, delisting_notice, restatement, leadership_change), four are normal (material_agreement, earnings, regulation_fd, other_event). The key is the SEC item code (`bench/triage_prompt.py`, `bench/triage.py`).

## Data

| Set | Filings | Urgent | Use here |
|---|---:|---:|---|
| `data/items/triage_8k_train.jsonl` | 688 | 281 | rules written here; also the LoRA training data |
| `data/items/triage_8k_fresh.jsonl` | 181 | 82 | held-out set of run `triage-4`; one measurement of the harness |
| `data/items/triage_8k.jsonl` | 200 | 105 | held-out set of run `type-1` (pending) |

## Method

The same code and the same rules as 05 (`bench/harness_8k.py`). Only the Muse answers change: `results/training/triage-4/predictions_tuned.jsonl` instead of `predictions_base.jsonl`. Rules: 8 phrase rules, 100% precise on the 688 training filings. Check: valid type, priority set from the type. Dispute: rule vs Muse disagreement or invalid Muse goes to the saved Inkling answer, majority vote, rule wins with no majority. Routing all: Muse reads every filing. Routing skip: a firing rule settles the filing without Muse.

## Results on the 181 fresh filings (run `triage-4`)

| System | Type right (of 181) | Urgent caught (of 82) | False alarms | Invalid | To Muse | To Inkling | $ per 1,000 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Muse untrained alone (from 05) | 155 | 79 | 6 | 4 | 100% | 0% | ~3.31 (estimate) |
| Muse trained alone | 151 | **82** | **4** | 0 | 100% | 0% | not measured |
| Rules alone | 60 right of 61 fired (98.4%), 33.7% coverage | 50 fired on urgent filings | - | - | 0% | 0% | 0 |
| Harness, routing all | 151 | 82 | 4 | 0 | 100% | 0.6% (1) | Muse + 0.01 Inkling |
| Harness, routing skip | 150 | 82 | 4 | 0 | 66.3% (120) | 0% | about 2/3 of Muse |

The trained Muse never returns an invalid answer, and its priority always matches its type (0 fixes). On the 61 filings where a rule fires, it agrees with the rule on 60. The one dispute is the wrong cyber_incident rule on a delisting notice; Inkling's vote keeps Muse's right answer. In routing skip that wrong rule answer stands, which costs one type-right (150). Both types are urgent, so urgency is unchanged.

### McNemar on type right, against trained Muse alone

| Comparison | Only harness right | Only Muse right | p |
|---|---:|---:|---:|
| Harness all vs trained Muse alone | 0 | 0 | 1.00 |
| Harness skip vs trained Muse alone | 0 | 1 | 1.00 |

## What this means

- With trained Muse, the harness adds no accuracy on this set. Its only remaining value is cost: routing skip lets the rules settle a third of the filings, so Muse reads 66% of them, with the same urgent catch (82 of 82) and the same 4 false alarms.
- The rules agree with trained Muse almost everywhere they fire, so they catch none of its 30 type errors. Those errors sit in the types the rules do not cover or in filings without a clear phrase.

## Cost and speed

- Muse trained: **not measured** as an inference cost or latency. The training sampler number (about $0.60 per 181-filing pass, `docs/training.md`) is for the untrained model on the sampler; a deployed LoRA has its own price.
- Inkling: measured saved `usd`, $0.0018 for the one dispute (about $0.01 per 1,000 filings).
- Rules: $0, microseconds per filing.

## Caveats

- **Selection risk.** The fresh set is the held-out set of `triage-4`, and the training settings of `triage-4` were chosen after earlier runs on this same set. The rules were written on training data only and run once here, but two routings were scored on it. The pending `type-1` run on the 200 independent filings is the cleaner test.
- Designs tried on fresh: 1 rule set, 2 routings (shared with 05), both reported.
- The one rule error on fresh (cyber_incident on risk-factor boilerplate) shows up only in routing skip here.

## Pending: run type-1

A new LoRA run is training now in `results/training/type-1`, with eval set `triage_8k` (200 independent filings, not used to write the rules). Its numbers will be filled in here. There are no saved Inkling answers on `triage_8k`, so disputes have no tiebreak: the rule wins and the count shows as `no_tiebreak`, and an invalid Muse answer with no rule stays invalid.

When the run has written `predictions_base.jsonl`, `predictions_tuned.jsonl` and `holdout_ids.json`:

```
venv/bin/python -m bench.harness_8k sim --run type-1 --answers tuned --set triage_8k
venv/bin/python -m bench.harness_8k sim --run type-1 --answers base --set triage_8k --out experiments/06-8k-harness-trained/results
```

| System (type-1, 200 filings) | Type right | Urgent caught (of 105) | False alarms | Invalid | To Muse | No tiebreak |
|---|---:|---:|---:|---:|---:|---:|
| Muse untrained alone | pending | pending | pending | pending | 100% | - |
| Muse trained alone | pending | pending | pending | pending | 100% | - |
| Rules alone | 81 right of 82 fired (98.8%), 41.0% coverage | 64 fired on urgent filings | - | - | 0% | - |
| Harness all (trained) | pending | pending | pending | pending | 100% | pending |
| Harness skip (trained) | pending | pending | pending | pending | 59% | pending |

## Reproduce

```
venv/bin/python -m bench.harness_8k sim --run triage-4 --answers tuned
```

Raw per-filing output (`*-all.jsonl`, `*-skip.jsonl`) and the summary (`*.summary.json`) are in `results/`.

## Result: run type-1 (filled in)

New LoRA run `type-1`: Muse Glimmer 30B, 2 epochs, 688 training filings, scored on `triage_8k` (200 independent filings, 105 urgent, no overlap with training, fresh or final sets). Trained model: `muse-starter-sl-type-1`. Training $0 (free offer); scoring about $1.30 (docs rate, not checked on the billing page). Harness rules are v2 (narrative phrases only).

| System (200 independent filings) | Type right | Urgent caught (of 105) | False alarms (of 95) | Invalid | Read by Muse |
|---|---:|---:|---:|---:|---:|
| Muse untrained alone (baseline) | 157 | 93 | 2 | 11 | 100% |
| Harness v2, untrained Muse | 162 | 97 | 2 | 7 | 55.5% |
| Muse trained alone | 183 | 102 | 3 | 0 | 100% |
| Harness v2, trained Muse | 184 | 103 | 3 | 0 | 55.5% |

McNemar, trained vs untrained, same 200 filings: type right 33 to 7 (p = 0.00004); priority right 16 to 4 (p = 0.012). Harness vs model alone: small, not significant. The 11 invalid untrained answers were cut off at the length limit.

Reproduce: `venv/bin/python -m bench.harness_8k sim --run type-1 --answers tuned --set triage_8k`
