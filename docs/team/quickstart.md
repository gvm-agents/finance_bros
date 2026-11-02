# Quick start

From nothing to your first result in about 10 minutes. Works on Mac, Windows and Linux. Needs Python 3.11 and git.

This is a private repo. Give the organizer your GitHub username, accept the repo invitation, then clone it. If the SSH clone below fails because your GitHub SSH key is not set up, use the HTTPS address from the repo's **Code** button instead.

## 1. Set up (about 1 minute)

Mac or Linux:

```bash
git clone git@github.com:gvm-agents/open-model-eval.git
cd open-model-eval
python3 -m venv venv
venv/bin/pip install -e '.[dev]'
venv/bin/python -m bench.starter
venv/bin/pytest -q
```

Windows PowerShell: use the same lines, with `python -m venv venv`, and `venv\Scripts\python` in place of `venv/bin/python`. Replace `venv/bin/pip install -e '.[dev]'` with `venv\Scripts\python -m pip install -e ".[dev]"`, and `venv/bin/pytest -q` with `venv\Scripts\python -m pytest -q`. The automatic checks pass on Windows; a real Windows PC has not been tried yet.

**Worked if:** the last line says all checks passed, and `data/items` holds 10 test sets.

The repo includes `starter/public-sec-items.zip`, with those 10 public SEC test sets and answer keys. `bench.starter` unpacks them locally. The larger collection, saved model runs, and the final event test set are not included in GitHub; ask the organizer if your track needs a specific additional file. Keep the final test set held back until the scheduled final evaluation.

## 2. See the dashboard (free, no key)

```bash
venv/bin/python -m bench.dashboard --demo
```

Open http://127.0.0.1:8765 in your browser.

## 3. Add your key

Use your own Fireworks key, from https://app.fireworks.ai/, or event credits. Keys stay in your terminal, never in a file in this repo.

```bash
export FIREWORKS_API_KEY="your key"
export SEC_CONTACT="Your Name you@email.com"
```

Windows PowerShell: `$env:FIREWORKS_API_KEY="your key"` and `$env:SEC_CONTACT="Your Name you@email.com"`. The SEC requires a contact on automated requests.

## 4. Run your first test (about a penny)

```bash
venv/bin/python -m bench estimate --lanes gptoss120_fw --tasks formd_extract --n 20
venv/bin/python -m bench run --lanes gptoss120_fw --tasks formd_extract --n 20 --max-usd 0.05 --run my-first-run
venv/bin/python -m bench report --run my-first-run
```

Your report is in `results/runs/my-first-run/REPORT.md`, with a chart beside it.

## House rules

- **Public data only.** No private or client documents.
- **Every paid run has `--max-usd`.**
- **Never commit a key.** `git status` before every commit.
- **Reading models get no tools.** See [data and news](data-and-news.md).
- **A person reviews anything that leaves the team.**
