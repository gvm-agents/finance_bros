"""Build docs/kickoff.html: short slides to introduce the project to new teammates. Images embedded; no model is called.

  python -m bench.kickoff
"""
from __future__ import annotations

import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "docs" / "img"
OUT = ROOT / "docs" / "kickoff.html"


def img(name: str, alt: str) -> str:
    return f'<img alt="{alt}" src="data:image/png;base64,{base64.b64encode((IMG / f"{name}.png").read_bytes()).decode()}">'


CSS = """
:root{color-scheme:light;--ink:#0b0b0b;--ink2:#52514e;--a:#2a78d6;--tint:#eef3fb;--line:#d8d7d2}
*{box-sizing:border-box}body{margin:0;background:#fff;color:var(--ink);font:20px/1.35 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.s{width:11in;height:8.3in;padding:.45in .55in;break-after:page;display:flex;flex-direction:column;overflow:hidden}
.s:last-child{break-after:auto}h1{font-size:52px;line-height:1.1;margin:0 0 14px;letter-spacing:-.01em}h2{font-size:38px;line-height:1.15;margin:0 0 12px}
p{margin:0 0 10px}.lead{font-size:28px;color:var(--ink2)}ul{margin:0;padding-left:22px}li{margin:5px 0}
.g{display:grid;gap:12px;flex:1;min-height:0}.g2{grid-template-columns:1fr 1fr}.g3{grid-template-columns:1fr 1fr 1fr}
.c{border:1px solid var(--line);border-radius:10px;padding:13px 15px;background:#fcfcfb}.c h3{font-size:27px;margin:0 0 8px}.c p{font-size:24px;margin:0}
.fig{flex:1;min-height:0;display:flex;justify-content:center}.fig img{max-width:100%;max-height:100%;object-fit:contain}
.shots img{width:100%;height:auto;border:1px solid var(--line);border-radius:8px}.cap{font-size:16px;color:var(--ink2);margin-top:4px}
.big{background:var(--tint);border-left:5px solid var(--a);padding:12px 16px;border-radius:0 8px 8px 0;font-size:25px;margin-top:14px}
table{border-collapse:collapse;width:100%;font-size:23px}th,td{border:1px solid #000;padding:7px 10px;text-align:left;vertical-align:top}th{background:var(--tint)}
.note{font-size:15px;color:var(--ink2);margin-top:6px}
@page{size:11in 8.5in;margin:0}
"""


def page() -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Open Model Kickoff</title><style>{CSS}</style></head><body>
<section class="s"><h1>Which AI work can move off expensive models?</h1>
<p class="lead">A ready-made test bench for open models, on real work. Bring your own question, or take one of ours.</p>
<div class="g g3" style="margin-top:18px;flex:none"><div class="c"><h3>Skip the setup</h3><p>Test data, scoring, many agents at once and dashboards are ready.</p></div><div class="c"><h3>Learn something real</h3><p>See how open models compare with frontier models, in cost and quality.</p></div><div class="c"><h3>Take it with you</h3><p>Leave with a method you can use on your own work.</p></div></div>
<p class="big">Early result: on high-volume sorting, open models cost about 16 times less than a mid-priced frontier model, with no significant loss of quality. Frontier models still lead on careful writing and long reports.</p></section>

<section class="s"><h2>What is already set up</h2><div class="g g2">
<div class="c"><h3>Tasks</h3><p>Repeatable work that open models may suit: pull facts from forms, sort and tag items, track news. More mechanical, less open-ended reasoning.</p></div>
<div class="c"><h3>Public data</h3><p>SEC filings, which come with structured data we can use as an answer key. News feeds, which are messy narrative text.</p></div>
<div class="c"><h3>Standard measures</h3><p>Accuracy, recall, precision and F1, plus cost, speed, reliability and security. Software marks every answer; no AI grades the results.</p></div>
<div class="c"><h3>Three kinds of model</h3><p>Frontier for the targets, open models hosted on Fireworks, and small local models on a laptop, to show the tradeoffs.</p></div>
</div></section>

<section class="s"><h2>Same jobs, same data, every model</h2><p>Share of answers right. Green is high, red is low. The bottom row is ours to fill in today.</p>
<div class="fig">{img("grid-today", "Grid of models against jobs, with an empty row for today")}</div></section>

<section class="s shots"><h2>A platform for fast testing and drill-down</h2><div class="g g2" style="flex:none"><div>{img("sweep", "Dashboard home page")}<p class="cap">Home: the big picture</p></div><div>{img("drill-down", "Dashboard drill-down")}<p class="cap">Drill-down: from a category to the source</p></div></div>
<p class="big">Change a model or a setting, rerun, and compare. Every run has a hard spending limit.</p></section>

<section class="s"><h2>Today: four experiments</h2><table><tr><th>Experiment</th><th>The question</th><th>What we use</th></tr>
<tr><td>Form extraction</td><td>Can open models pull facts as reliably as frontier models?</td><td>Form D and Form ADV, with SEC data as the answer key</td></tr>
<tr><td>Data centers</td><td>Are AI commitments funded, and do the resources exist?</td><td>Company filings, with a quote for every claim</td></tr>
<tr><td>Algorithm effects</td><td>How do new algorithms change suppliers and customers?</td><td>Filings across chips, clouds, software and end users</td></tr>
<tr><td>Real-time news</td><td>Can we see a story start, spread and fade?</td><td>66 public feeds and a live stream</td></tr></table>
<p class="big">First comparison: gpt-oss-120b against DeepSeek V4.1 Flash on Fireworks. Then tune: route across models, build a smarter harness, or train a small model.</p></section>

<section class="s"><h2>How we work together</h2><div class="g g2"><div class="c"><h3>Pick a track</h3><p>Forms, deep research, news, router and training, or your own task.</p></div><div class="c"><h3>Goal for today</h3><p>Improve one number against a baseline frozen at the start, and show what it cost.</p></div><div class="c"><h3>Stop times</h3><p>10:30 baseline. 12:30 working entry. 3:30 freeze. 4:15 submit. 7:00 demos.</p></div><div class="c"><h3>Ground rules</h3><p>Public data only. Your own key. A spending limit on every run. Prepared work is disclosed.</p></div></div>
<p class="big">Everything is in the repo: quick start, experiment steps, data, charts and glossary. Setup takes about a minute.</p></section>
</body></html>"""


def main() -> int:
    OUT.write_text(page(), encoding="utf-8")
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
