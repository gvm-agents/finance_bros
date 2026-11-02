# How we measure

Python marks every answer. No model grades a model.

| Measure | Question it answers | How |
|---|---|---|
| Accuracy | How often is it right? | Share of answers matching the key. A score of 0.90 or more counts as right |
| Recall | Of what mattered, how much did we catch? | Use when a miss is costly |
| Precision | Of what we flagged, how much was real? | Use when false alarms are costly |
| F1 | One score for both | Blends recall and precision |
| Cost | What does 1,000 items cost? | Tokens used times list price; not a bill |
| Speed | Can it keep up? | Median and slowest 5% of seconds; items per second |
| Reliability | Does it fail? | Blank, invalid and refused calls, counted separately |
| Security | Can a document trick it? | Plant false instructions, and count how often models obey |
| Confidence | Real, or luck? | Same items for every model; paired test; 95% range |

## Reading results

- **Compare on the same items.** It is far sharper than comparing two percentages.
- **"Not significant" means we cannot tell,** not that two results are equal.
- **To detect a 5-point gap, plan on about 400 paired items.** For a 10-point gap, about 100.
- **If you pick the best of many settings, retest on fresh items.**

## Public benchmarks

We use our own answer keys for every result. Public benchmarks help you make a shortlist; they do not test your work.

| Source | Good for |
|---|---|
| Artificial Analysis | Price, speed and an overall quality index |
| LMArena | Which answers people prefer |
| MLPerf | Hardware speed |

Check these before citing them; they change often.
