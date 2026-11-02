# 05 8-K harness, no training: rules + untrained Muse + Inkling tiebreak

Question: can plain Python rules and a cheap tiebreak lift the untrained Muse Glimmer 30B on 8-K sorting, with no training and no new model calls?

Status: simulated 2026-11-02 on saved answers only. $0 spent, no model was called.

## The task

Each 8-K is sorted into one of 10 event types. Six types are urgent (priority high): bankruptcy, cyber_incident, acquisition_or_sale, delisting_notice, restatement, leadership_change. The other four are normal: material_agreement, earnings, regulation_fd, other_event. The answer key is the SEC item code the company declared (`bench/triage_prompt.py`, `bench/triage.py`). Item numbers are removed from the text; models see the first 6,000 characters.

## Data

| Set | Filings | Urgent | Use here |
|---|---:|---:|---|
| `data/items/triage_8k_train.jsonl` | 688 | 281 | rules were written and checked on this set only |
| `data/items/triage_8k_fresh.jsonl` | 181 | 82 | one measurement of the finished harness (saved Muse and Inkling answers exist) |
| `data/items/triage_8k.jsonl` | 200 | 105 | rules alone, coverage and precision (no saved Muse answers yet) |

The final exam set was not opened.

## Method (`bench/harness_8k.py`)

1. **Rules ($0).** Eight phrase rules, one per type except material_agreement and other_event. Each fires only on a clear phrase, for example "press release announcing its financial results" (earnings), "Regulation FD" without "financial results" (regulation_fd), "Listing Qualifications" near "not in compliance" or "deficiency" (delisting_notice), "resign" (leadership_change), "should no longer be relied upon" (restatement). If two rules name different types, no rule fires. Some rules match heading words that the set's cleaning step left in the text, for example "Listing Rule or Standard" and "of Directors or Certain Officers". On the 688 training filings the rules fire on 246 (35.8%) and are right on all 246.
2. **Muse.** The saved untrained Muse Glimmer 30B answer (`results/training/triage-4/predictions_base.jsonl`).
3. **Check.** The type must be one of the 10 names. The priority is always set from the type. Muse's own priority never disagreed with its type here (0 fixes).
4. **Dispute.** When a firing rule and Muse disagree, or Muse's answer is invalid, the saved Inkling answer (`results/runs/inkling-1102/calls.jsonl`) is the tiebreak: majority of rule, Muse and Inkling. With no majority the rule wins. With no rule, Inkling's answer is used.

Two routings:
- **all**: Muse reads every filing, so a rule and Muse can disagree.
- **skip**: a firing rule settles the filing and Muse is not asked. Only an invalid Muse answer goes to Inkling.

## Results on the 181 fresh filings

| System | Type right (of 181) | Urgent caught (of 82) | False alarms | Invalid | To Muse | To Inkling | $ per 1,000 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Muse untrained alone | 155 | 79 | 6 | 4 | 100% | 0% | ~3.31 (estimate, see below) |
| Inkling alone (reference) | 155 | 80 | 7 | 8 | 0% | 100% | 2.87 (measured) |
| Rules alone | 60 right of 61 fired (98.4%), 33.7% coverage | 50 fired on urgent filings | - | - | 0% | 0% | 0 |
| **Harness, routing all** | **157** | 79 | 6 | 1 | 100% | 3.3% (6) | ~3.31 + 0.25 Inkling |
| **Harness, routing skip** | **157** | **80** | 6 | 1 | 66.3% (120) | 2.2% (4) | ~2.19 + 0.23 Inkling |

Rules alone, per type on fresh: earnings 9 of 9, regulation_fd 2 of 2, delisting_notice 19 of 19, leadership_change 12 of 12, restatement 16 of 16, acquisition_or_sale 1 of 1, cyber_incident 1 of 2, bankruptcy 0 fired.

Where Inkling was used (routing all): 4 filings with an invalid Muse answer (Inkling was right on 2, wrong on 1, invalid on 1) and 2 rule-vs-Muse disputes. In one dispute the rule was wrong (cyber_incident on a delisting notice) and the vote fixed it. In the other the rule was right (leadership_change), and Muse and Inkling both said other_event, so the vote took the wrong answer and lost one urgent catch. Routing skip keeps that rule answer, which is why it catches 80 instead of 79.

### Is the gain real? (McNemar on type right, same 181 filings, against Muse alone)

| Comparison | Only harness right | Only Muse right | p |
|---|---:|---:|---:|
| Harness all vs Muse alone | 2 | 0 | 0.50 |
| Harness skip vs Muse alone | 3 | 1 | 0.63 |

Neither difference is significant. In routing all, the whole gain comes from the 4 filings where Muse returned no answer: Inkling turns 2 of them into right answers. Routing skip adds one more right answer from a rule (leadership_change) and loses one to a wrong rule (cyber_incident).

### Rules alone on the 200 independent filings (`triage_8k`)

Fired on 82 (41.0%), right on 81 (98.8%). 64 of the fired filings are urgent. Per type: earnings 12 of 12, regulation_fd 6 of 6, delisting_notice 24 of 24, leadership_change 17 of 17, restatement 17 of 17, cyber_incident 2 of 2, bankruptcy 3 of 4. The one miss is a chapter 11 filing whose key says acquisition_or_sale (an asset sale inside the bankruptcy); both types are urgent.

## Cost and speed

- Inkling: measured. Saved `usd` from the bench run, $2.87 per 1,000 filings when it reads every filing. In the harness only 2-3% of filings reach it: $0.23-0.25 per 1,000. Saved Inkling time on those filings: 90-94 s in total, almost all of it on three of the invalid cases (23-40 s each).
- Muse untrained: **not measured** as an inference cost. The only number is from the training sampler: about $0.60 per 181-filing pass (`docs/training.md`), so about $3.31 per 1,000. Routing skip sends 66% of filings to Muse, about $2.19 per 1,000. Treat both as estimates.
- Rules: microseconds per filing, $0.
- Muse latency: not measured (the training sampler does not save per-filing time).

## Caveats

- **Selection risk.** The rules were written on the training set only, and the fresh set was measured once with this one rule set. But the fresh set is the same set on which Muse, Inkling and the other models were already compared, and two routings (all, skip) were scored on it. Picking the better routing after this is a choice made on the test data. The 200-filing `triage_8k` check of the rules is the cleaner number.
- Designs tried on fresh: 1 rule set, 2 routings, both reported. No rule was changed after the fresh run.
- The gain over Muse alone is small (2-3 filings) and not significant.
- Some rules lean on heading words left by the cleaning step. A cleaner text (or a different source) would lower coverage.
- The cyber rule fired on risk-factor boilerplate ("cybersecurity incidents" in forward-looking statements). A real deployment needs that phrase guarded.
- material_agreement has 0 training filings, so no rule exists for it and the other rules were never checked against it on training data.
- Only one filing stays invalid. The harness has no safe default for it (for example "send to a person"); it is counted as invalid.

## Reproduce

```
venv/bin/python -m bench.harness_8k rules --set triage_8k_train
venv/bin/python -m bench.harness_8k rules --set triage_8k
venv/bin/python -m bench.harness_8k sim --run triage-4 --answers base
```

Raw per-filing output (`*-all.jsonl`, `*-skip.jsonl`, `rules-*.jsonl`) and summaries (`*.summary.json`) are in `results/`.

## v2: rules without leftover item headings

The first rule set matched words that the cleaning step left from the removed item headings ("Departure of Directors or Certain Officers", "Listing Rule or Standard", "Non-Reliance", "Related Audit Report", "of Assets"). Those words carry part of the answer, so v2 drops them and uses narrative phrases only, written on the 688 training filings.

| Set | Rules fire | Right when they fire |
|---|---:|---:|
| triage_8k_train (688, design set) | 280 (40.7%) | 274 (97.9%) |
| triage_8k_fresh (181) | 72 (39.8%) | 70 (97.2%) |
| triage_8k (200, independent) | 89 (44.5%) | 88 (98.9%) |

Harness on the 181 fresh filings, routing "skip" (a firing rule settles the filing; Muse reads the rest; Inkling only for invalid Muse answers):

| System | Type right | Urgent caught (of 82) | False alarms | Invalid | Read by Muse |
|---|---:|---:|---:|---:|---:|
| Muse untrained alone | 155 | 79 | 6 | 4 | 100% |
| Harness v2, untrained Muse | 158 | 79 | 6 | 1 | 60.2% |
| Muse trained alone | 151 | 82 | 4 | 0 | 100% |
| Harness v2, trained Muse | 152 | 82 | 5 | 0 | 60.2% |

McNemar on type right, harness v2 untrained vs Muse alone: 4 to 1, p = 0.375 (not significant). Raw output: results/v2/.

## Check on 200 independent filings (triage_8k)

Untrained Muse answers from run `type-1` (results/training/type-1/predictions_base.jsonl), harness v2, routing skip:

| System | Type right | Urgent caught (of 105) | False alarms | Invalid | Read by Muse |
|---|---:|---:|---:|---:|---:|
| Muse untrained alone | 157 | 93 | 2 | 11 | 100% |
| Harness v2, untrained Muse | 162 | 97 | 2 | 7 | 55.5% |

Reproduce: `venv/bin/python -m bench.harness_8k sim --run type-1 --answers base --set triage_8k`
