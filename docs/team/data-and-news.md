# Data, news and search

## Public documents

`python -m bench.starter` gives you these test sets. All are public SEC data, with answer keys from SEC structured data.
They are bundled in `starter/public-sec-items.zip` in the private GitHub repo; no separate Drive download is needed.

| Set | Items | What it is |
|---|---:|---|
| `formd_extract` | 400 | Form D private offerings |
| `adv_extract` | 40 | Form ADV adviser forms |
| `triage_8k` | 200 | Company event filings |
| `triage_8k_fresh` | 181 | Newer event filings for practice and tuning |
| `triage_8k_train` | 688 | Older event filings, for training |
| `sector` | 120 | Business descriptions, with industry codes |
| `name_match` | 300 | Pairs of company records |
| `snapshot` | 400 | Short summaries written to rules |
| `format_table` | 400 | Tables to reformat exactly |
| `longdoc_v2` | 39 | Pages from annual reports |

Each row is one JSON item, with its text and its answer `key`. The practice set `triage_8k_fresh` can be used for tuning; keep the separate final set unseen until the final evaluation.
The separate `triage_8k_final` event test set is not in the repo. The organizer keeps it for one final evaluation.

Collect more, free:

```bash
venv/bin/python -m bench.triage collect --start 2026-10-01 --end 2026-10-30 --per-type 20 --name my_8k
venv/bin/python -m bench collect --start 2026-07-01 --end 2026-09-30 --formd 100 --tenk 20
```

## News feeds

`bench/feeds.json` lists 66 public feeds, and most need no key. Read them all with `python -m bench.feed_items`. Most update within minutes to hours. Licensed outlets come through as headlines via Google News, with no full text.

The only truly real-time source is the Bluesky stream, at about 40 posts a second. `python -m bench.recorder --once` does one pass of the feeds; leave off `--once` to keep recording. The stream is recorded in the same run.

## Search

```bash
venv/bin/python -m bench.news_search "data center power deal" --hours 48 --out results/search.jsonl
```

This saves headlines, sources, links and times from Google News and Hacker News.

**Why models get no search tool.** Anyone can publish text, and a page can carry hidden instructions. So search runs in Python, and models only read the saved text. If a page fools a model, the worst case is one wrong answer that a check or a person can catch. Do not give reading models tools.

**Retrieval (RAG).** The same pattern applies: Python finds the passages, the model reads them, and every claim must quote its source.
