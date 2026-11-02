# The evaluation platform

## Where it runs and how to reach it

The platform is not a website. It is this repo plus a small dashboard program, so it runs on whichever laptop starts it. Each person runs their own copy, so several people can work on different tasks in parallel without getting in each other's way.

| Question | Answer |
|---|---|
| How do I turn it on? | Follow the [quick start](quickstart.md): clone, set up, then `venv/bin/python -m bench.dashboard --demo` and open http://127.0.0.1:8765 |
| Where do runs happen? | On your laptop. Each command calls the models over the internet and saves results in `results/` |
| How does it reach Fireworks? | Through your `FIREWORKS_API_KEY` in your terminal. Every Fireworks model is a named entry in `lanes.json`; pass the name to `--lanes` or `--lane` |
| Can we work in parallel? | Yes. Each person has their own copy, own branch and own `--run` name. Results never collide |
| Where is the local model? | Ollama on your laptop (`ollama serve`), at http://127.0.0.1:11434. Optional: add `--first-only` to the router to skip it |
| How do I see someone else's results? | Ask them for the run report or a screen share. For a local dashboard view, ask the organizer for the required run files and baseline files; a code branch alone does not include them |
| How do I stop it? | Ctrl+C in the window running the dashboard. Runs stop at their `--max-usd` cap, or when you create a file named `STOP` in `results/runs/<run>/`; run the same command again to resume |

| Part | File | What it does |
|---|---|---|
| Tasks and scoring | `bench/tasks.py` | Prompts, and Python marking against answer keys |
| Models | `lanes.json` | Every model and setting; adding one is a config change |
| Routing | `routes.json`, `bench/router.py` | Which model reads what, and when a second reader looks |
| Coordinator | `bench/coordinator.py` | Runs many agents with a hard budget, retries and resume |
| Recorder | `bench/recorder.py` | Saves new headlines with source and time |
| Dashboard | `bench/dashboard.py` | Big picture, drill-downs, model comparison, live status |

## The pages

| Page | Use it to |
|---|---|
| Global Sweep | See news volume by topic and hour |
| By Source | See where a story is coming from |
| Data Center Radar | Drill into one category, down to the stories |
| Compare | Compare models on each measure |
| Frontier | See quality against cost |
| Platform | Watch progress, cost so far and cost to finish |
| Goals | Keep the main goal and sub-goals straight |

Every page shows its context: models, settings, task, measures, time and host. Charts download as images.

Code and the 10 starter test sets come from GitHub. New runs stay on the machine that made them because `results/` is excluded from GitHub. Share only the report or files another teammate needs; check them for keys or private material before sending. The final event test set stays with the organizer until the final evaluation.

```bash
venv/bin/python -m bench.dashboard --demo                      # saved data, no key
venv/bin/python -m bench.dashboard --run router-1              # one of your runs
venv/bin/python -m bench.goals add "Check the missed items" --run router-1
```

## Add a model

Add an entry to `lanes.json`, with its price and where it runs. Then pass its name to `--lanes`.
