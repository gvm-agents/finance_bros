# Data in this repo

Everything here is public: SEC filings and public news feeds. Answer keys come from the SEC's own structured data.

| Folder | What it holds |
|---|---|
| `data/items/` | Every test set as JSON lines: one filing per line with its text, SEC link and answer key. Sorting: `triage_8k_train` (688, training), `triage_8k_fresh` (181, practice), `triage_8k` (200, independent test for experiments 05 to 07), `triage_8k_final99` (568, final; run once). Forms: `formd_extract` (400 Form D; `split` = train 280 / test 120). |
| `data/sft_formd_extract.jsonl` | The 280 Form D training examples used to train the Forms model. |
| `results/runs/<run>/` | Every model run: `calls.jsonl` (each prompt's reply, tokens, cost, score), `REPORT.md`. |
| `results/comparison-triage_8k/` | Every system on the 200 independent 8-K filings in one table (`python -m bench.compare_8k`). |
| `results/training/<run>/` | Trained-model runs: answers before and after training (`predictions_base.jsonl`, `predictions_tuned.jsonl`), `summary.json`. |
| `results/scoreboard.jsonl`, `results/stats.jsonl` | Scored results and significance tests. |

Not in git because of size. Copies are in the team's shared Google Drive folder **Github Additional Data**; put each one inside `data/` here:

| Collection | Size | How to rebuild |
|---|---|---|
| `data/cache/` (raw SEC downloads the sets were built from) | 2.1 GB (`cache.zip`, 480 MB) | Unzip inside `data/`. Or let the collectors re-fetch from SEC EDGAR (set `SEC_CONTACT`). |
| `data/sec_pdfs/` (SEC filings as PDFs) | 34 GB | Copy the `sec_pdfs` folder, or rebuild: `python -m bench.sec_pdfs` |
| `data/adv_library/`, `data/adv/`, `data/adv_screen/`, `data/adv_history/` (Form ADV, not used by the experiments here) | 50 GB + 255 MB | Copy the `adv_library` folder, or rebuild: `python -m bench.adv_library` |
