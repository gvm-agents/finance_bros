# FAQ and glossary

## FAQ

**Do I need a Mac?** No. Saved-data mode needs only Python.

**Do I need a powerful laptop?** Only for local models. Hosted models run on Fireworks.

**Whose key do I use?** Your own, or event credits.

**Can I test my own task?** Yes, on public or synthetic data. Add a prompt and a scorer in `bench/tasks.py`. Copy `sector`, the simplest.

**A call was refused (error 429).** You hit a rate limit. The code retries; lower `--workers`.

**A model has gone.** The Fireworks list changes. Change `lanes.json`. gpt-oss-120b shows a November 7, 2026 deprecation date.

**Was this prepared in advance?** Yes, and we say so. Results from today are marked against a baseline frozen at the start.

## Glossary

| Term | Meaning here |
|---|---|
| Frontier model | A top closed model from a big lab |
| Open model | Its weights are published, so anyone can run it |
| Hosted | Runs on someone else's machines, paid per call |
| Local | Runs on your own machine |
| Project > Task > Run > Item | The whole effort > one kind of job > one execution > one document |
| Answer | One model's reply to one item |
| Answer key | The correct answer, from official data |
| Lane | One model, in one place, on one setting |
| Agent, or swarm | One worker, or many at once on a task |
| Harness | The controls around models: budget, retries, checks |
| Router | Sends each item to the model that suits it |
| Second reader | Another model reading the same item, to catch misses |
| Thinking | Notes a model writes itself before answering |
| Token | A small piece of text; 100 tokens is about 75 words |
| Rate limit, or refusal | Too much work per minute; error 429 |
| Baseline | The result you must beat, frozen before tuning |
| Freeze the baseline | At the start, each experiment runs its current setup once on its practice set, saves the numbers, and the repo is tagged (`git tag baseline-1030`). Every later change is compared with those numbers, so nobody can say we moved the goalposts |
| Practice set and final exam | Tune on the practice set as often as you like. Run the final exam once, after the design is locked, so the result is not tuned to the test |
| Pairing search | `bench.router combos`: tries every model and pair of models on saved answers, free, and lists those that hit the target, cheapest first |
