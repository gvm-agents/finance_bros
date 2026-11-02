# Evidence test: does open-model evidence improve a frontier model's answer?

Fixed before any answer was generated. Changes after the first run are listed at the end of this file with a reason.

## Design

One frontier model (Claude Sonnet 5) answers each question twice, with the same reply format.

- **Arm A, no extra facts:** the question alone.
- **Arm B, with evidence:** the question plus a fact pack. Python pulled the numbers from SEC data; open-model workers found passages, and a passage counts only if its quote is in the filing word for word.

## Questions

1. **Funding gap, data center set.** Which of these companies have disclosed forward commitments that are largest compared with their operating cash flow and cash, and where is the gap widest?
2. **Algorithm effects, algorithm set.** When AI models get cheaper or better, who in this group gains, who loses, and do these companies' filings show total spending rising or falling?
3. **Backlog concentration, data center set.** How much of the contracted backlog (remaining performance obligations) depends on a few AI customers?
4. **Chip life, data center set.** What server and network useful lives do these companies use, and what is the earnings effect if chips last 3 to 4 years instead of 6?

## Reply format

JSON: a short answer, then a list of claims. Each claim names the company, metric, value in US dollars, period and source. A claim with no dollar value is not a cited fact.

## Checklist

All marks come from `bench/evidence.py`. The same checker reads both arms against the same SEC data.

| Measure | Definition |
|---|---|
| Cited facts | Claims with a company and a dollar value |
| Verified current | Value within 1% of an SEC figure for that company dated within the 12 months before the question |
| Verified older | Value within 1% of an SEC figure for that company from an earlier period |
| Verified share | (Verified current + verified older) ÷ cited facts |
| Wrong | Metric is one the checker can read, and the value is more than 5% from every SEC figure for that metric |
| Unverified | Anything else. Not counted as right or wrong |
| Added cost | Worker cost plus the extra Sonnet tokens in arm B |

## What counts as helping

Evidence helps on a question only if arm B has more cited facts, a verified share at least 10 points higher, and no more wrong claims than arm A. It helps overall only if that holds on at least 3 of the 4 questions. Otherwise the report says it did not help.

## Known limits, stated before the run

- **Part of this test is circular.** Arm B's facts come from the same SEC data the checker reads, so a high verified share is expected. The measures that carry weight are wrong claims, how current the facts are, and whether arm B stays honest beyond its pack.
- Each question is asked once per arm, so one run cannot show how much answers vary.
- The checker tests facts, not reasoning. A better-sourced answer can still reach a poor conclusion.
- A person checks the top rows before anything is quoted.

## Changes after the first run

1. Checker fix: it compared a stated value with a negative SEC figure by sign, so a correct TeraWulf cash flow in arm B was marked wrong. It now compares sizes. This helps arm B by one claim and does not change any verdict.
