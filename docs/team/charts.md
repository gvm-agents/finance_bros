# Charts to present results

Pick the chart that answers the question.

| Question | Chart | Where it comes from |
|---|---|---|
| Which model suits which job? | Grid of jobs against models, green high, red low | `python -m bench.heatmap --out chart.png` |
| What is the best trade of quality and cost? | Dots: quality up, cost left | `python -m bench.overview_chart --out chart.png` |
| How much did today's tuning help? | Before and after, same items | Two runs from `bench report` |
| How far can we push volume? | Items per second against agents | `python -m bench.ramp --lane gptoss120_fw --task triage_8k --workers 6,12,24 --n 100 --max-usd 0.5` |
| Is a story spreading? | Volume by hour and source | Dashboard, Global Sweep and By Source |

## Every chart states

- Models and settings
- Task and number of items
- Measure, and what higher means
- Date, and where the model ran
- What it does not prove

Avoid one blended score: any weighting hides a choice. Show the main quality measure by job, plus quality against cost.
