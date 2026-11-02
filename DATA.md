# Data in this repo

Everything here is public: SEC filings and public news feeds. Answer keys come from the SEC's own structured data.

| Folder | What it holds |
|---|---|
| `data/items/` | Every test set as JSON lines: one filing per line with its text, SEC link and answer key. Sorting: `triage_8k_train` (688, training), `triage_8k_fresh` (181, practice), `triage_8k_final99` (568, final; run once). Forms: `formd_extract` (400 Form D; `split` = train 280 / test 120). |
| `data/sft_formd_extract.jsonl` | The 280 Form D training examples used to train the Forms model. |
| `data/adv_history/` | Public Form ADV history used by the adviser tasks. |
| `results/runs/<run>/` | Every model run: `calls.jsonl` (each prompt's reply, tokens, cost, score), `REPORT.md`. |
| `results/training/<run>/` | Trained-model runs: answers before and after training (`predictions_base.jsonl`, `predictions_tuned.jsonl`), `summary.json`. |
| `results/scoreboard.jsonl`, `results/stats.jsonl` | Scored results and significance tests. |

Not in git because of size (ask the lead for a copy):

| Collection | Size | How to rebuild |
|---|---|---|
| `data/cache/` (raw SEC downloads the sets were built from) | 2.1 GB | Attached to this repo's first release as a zip, when available; otherwise rebuilt automatically by the collectors, which fetch from SEC EDGAR (set `SEC_CONTACT`). |
| `data/sec_pdfs/` | 33 GB | `python -m bench.sec_pdfs` |
| `data/adv_library/` | 50 GB | `python -m bench.adv_library` |
| `data/adv/`, `data/adv_screen/` | 120 MB | SEC's public adviser lists; pending approval to add. |
