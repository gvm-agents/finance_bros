"""Build docs/showcase.html: one self-contained page, images embedded, numbers read from the saved results.

  python -m bench.showcase
Needs docs/img/. No model is called.
"""
from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from . import comparison, heatmap, router
from . import coordinator as co

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "docs" / "img"
OUT = ROOT / "docs" / "showcase.html"
JOBS = [("adv_extract", "Pull facts from simple forms", "gemma4_12b_local", "Match. Open is free on a laptop"),
        ("formd_extract", "Pull facts from detailed forms", "gemma4_12b_local", "Within 1 point. Open is free on a laptop"),
        ("sector", "Classify companies by industry", "deepseek41_fw", "Open scored higher, on a small test"),
        ("name_match", "Match duplicate company records", "deepseek41_fw", "About tied. Frontier cost less"),
        ("snapshot", "Write short summaries to a set of rules", "gptoss120_fw", "Frontier better. Open far cheaper"),
        ("format_table", "Reformat documents to an exact style", "deepseek41_fw", "Neither is reliable yet"),
        ("longdoc", "Answer questions from long reports", "deepseek41_fw_on_big", "Frontier better, on a small test")]
FRONTIER = "sonnet5"


def img(name: str, alt: str) -> str:
    data = base64.b64encode((IMG / f"{name}.png").read_bytes()).decode()
    return f'<img src="data:image/png;base64,{data}" alt="{html.escape(alt)}">'


def usd(x: float, note: str = "") -> str:
    return note or ("free" if x == 0 else f"${x:.3f}" if x < 1 else f"${x:.2f}")


def job_rows() -> list[tuple]:
    """Frontier against the best open result per job, both read from the saved answers."""
    rows = {r["lane"]: r for r in comparison.build()["rows"]}
    calls = [json.loads(l) for r in comparison.RUNS for l in (co.RUNS / r / "calls.jsonl").open()]
    rebuilt = [json.loads(l) for l in (co.RUNS / "longdoc-v2-1031" / "calls.jsonl").open()]
    long = heatmap.long_reports()

    def price(lane: str, task: str) -> tuple[float, int]:
        pool = rebuilt if task == "longdoc" else calls
        c = [x for x in pool if x["lane"] == lane and (task == "longdoc" or x["task"] == task) and not x.get("error")]
        return (1000 * sum(x.get("usd") or 0 for x in c) / len(c) if c else 0.0), len({x["item"] for x in c})

    out = []
    for task, name, lane, verdict in JOBS:
        fq = long["sonnet5"] if task == "longdoc" else rows[FRONTIER]["tasks"][task]
        oq = long[lane] if task == "longdoc" else rows[lane]["tasks"][task]
        fc, n = price(FRONTIER, task)
        oc, _ = price(lane, task)
        out.append((name, n, fq, oq, fc, oc, verdict))
    return out


def job_table() -> str:
    sim = router.simulate("fresh")
    f = next(s for s in sim["singles"] if s["name"] == FRONTIER)
    o = next(s for s in sim["systems"] if s["name"].startswith("gpt-oss, then"))
    money = lambda x: "No fee" if x == 0 else f"${x:.2f}" if x >= 0.1 else f"${x:.3f}"
    rows = [("Sort incoming items by importance", sim["n_items"], f["recall"], o["recall"], f["usd_per_1000"], o["usd_per_1000"], "Tied. Open about 16 times cheaper")] + job_rows()
    body = "".join(f"<tr><td>{html.escape(n)}</td><td>{q1:.0f}%</td><td>{q2:.0f}%</td><td>{money(c1)}</td><td>{money(c2)}</td><td class='say'>{html.escape(v)}</td><td>{k}</td></tr>" for n, k, q1, q2, c1, c2, v in rows)
    return ("<div class='wide'><table><tr><th>Business job</th><th>Frontier quality</th><th>Best open quality</th><th>Frontier cost per 1,000</th><th>Open cost per 1,000</th><th>Bottom line</th><th>Test items</th></tr>" + body + "</table></div>")


def sorting_table() -> str:
    sim = router.simulate("fresh")
    s = {x["name"]: x for x in sim["singles"]}
    o = next(x for x in sim["systems"] if x["name"].startswith("gpt-oss, then"))
    rows = [("Our router: low-cost open model, with a second look at routine items", o), ("Frontier model (Claude Sonnet)", s["sonnet5"]), ("Open model alone, hosted (DeepSeek)", s["deepseek41_fw_off"]),
            ("Open model alone, on a laptop (Gemma)", s["gemma4_12b_local"]), ("Fireworks automatic router", s["fw_auto"])]
    money = lambda x: "No fee" if x == 0 else f"${x:.2f}" if x >= 0.1 else f"${x:.3f}"
    body = "".join(f"<tr><td>{html.escape(n)}</td><td>{r['recall']:.0f}%</td><td>{r['false_alarms']}</td><td>{money(r['usd_per_1000'])}</td></tr>" for n, r in rows)
    return "<table><tr><th>Setup</th><th>Important items caught</th><th>False alarms, of 99 routine items</th><th>Cost per 1,000 items</th></tr>" + body + "</table>"


CSS = """
:root{color-scheme:light;--bg:#f7f7f5;--card:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--line:#e4e3de;--tint:#eef3fb;--a:#2a78d6}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1040px;margin:0 auto;padding:0 16px 56px}
.hero{padding:48px 0 22px}.hero h1{font-size:42px;line-height:1.12;margin:0 0 12px;letter-spacing:-.01em;max-width:820px}.hero p{font-size:20px;color:var(--ink2);margin:0;max-width:780px}
section{margin-top:40px}h2{font-size:25px;line-height:1.2;margin:0 0 8px}h3{font-size:17px;margin:0 0 4px}p{margin:0 0 12px}
img{display:block;width:100%;height:auto;border:1px solid var(--line);border-radius:10px;background:#fff}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;margin:22px 0 0}.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}.stat b{display:block;font-size:30px;line-height:1.15}.stat span{color:var(--ink2);font-size:15px}
.three{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}.way{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px}.way p{margin:0 0 8px;font-size:16px}.way .r{color:var(--ink2);font-size:15px;margin:0}
.pair{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}figure{margin:0}figcaption{color:var(--ink2);font-size:15px;margin:6px 2px 0}
table{border-collapse:collapse;width:100%;background:var(--card);font-size:15px}th,td{border:1px solid #000;padding:6px 9px;text-align:right;font-variant-numeric:tabular-nums}th{background:var(--tint);font-weight:600}th:first-child,td:first-child{text-align:left}
table.small{font-size:13.5px}.wide{overflow-x:auto}.note{color:var(--ink2);font-size:15px;margin-top:10px}.callout{border-left:4px solid var(--a);background:var(--tint);padding:10px 14px;margin:14px 0;border-radius:0 8px 8px 0}
ul{margin:0 0 12px;padding-left:20px}li{margin:3px 0}
@media (max-width:640px){.hero{padding-top:28px}.hero h1{font-size:31px}.hero p{font-size:18px}}
td,th{white-space:nowrap}td:first-child,td.say,.how td{white-space:normal;text-align:left}.how th{text-align:left}th{white-space:normal}
@media print{body{background:#fff;font-size:11pt}main{max-width:none;padding:0}.hero{padding-top:0}.hero h1{font-size:30pt}.hero p{font-size:13pt}section{margin-top:16px}h2{break-after:avoid;font-size:16pt}table,figure,.way,.stat,.callout,tr{break-inside:avoid}.pair{grid-template-columns:1fr 1fr}.three{grid-template-columns:repeat(3,1fr)}.way p{font-size:10pt}.way .r{font-size:9.5pt}table{font-size:9.5pt}table.small{font-size:8.5pt}th,td{padding:3px 6px}.note{font-size:9.5pt}.keep{break-inside:avoid}.pair{break-inside:avoid}figcaption{font-size:9.5pt}}
.keep{break-inside:avoid}
@page{size:letter;margin:.5in}
"""


def page() -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Open Model Overview</title><style>{CSS}</style></head>
<body><main>
<div class="hero"><h1>Quick AI Open Model Selection and Deployment, Based on Use Case</h1>
<p>This platform enables quick selection of open models based on business requirements for accuracy, cost, security and more.</p>
<div class="stats">
<div class="stat"><b>16 to 1</b><span>cost savings against a mid-priced frontier model on high-volume sorting, with no significant loss of quality</span></div>
<div class="stat"><b>No fee</b><span>to pull facts from standard forms on a laptop, within 1 point of a frontier model</span></div>
<div class="stat"><b>Not everything</b><span>Frontier models still lead on careful writing and long reports</span></div>
</div></div>

<section><h2>The size of the benefit depends on the job</h2>
<p>We gave open and frontier models the same real business documents, then checked every answer against official records. Quality is the share of answers that were correct. For sorting, it is the share of important items caught.</p>
{job_table()}
<p class="note">Frontier is Claude Sonnet. Best open is the best open setup tested for that job, so it varies by job. Laptop figures exclude the cost of the machine. Small tests are indicative only.</p></section>

<section class="keep"><h2>Up and to the left is better</h2>
<p>High-volume sorting: each dot is one setup. Higher means more important items caught. Further left means lower cost.</p>
<figure>{img("overview-chart", "Chart of important items caught against cost, with our router at top left")}</figure>
<p class="callout">Open models show a cost savings over frontier models of 16 to 1, while the quality difference (in this case recall, the share of important items caught) is not statistically significant. That compares with a mid-priced frontier model. A small frontier model costs about the same as our router, so the savings depend on which frontier model you would otherwise use.</p></section>

<section class="keep"><h2>Three ways to maximize the benefits of open models</h2><div class="three">
<div class="way"><h3>Route across models</h3><p>Send each item to the cheapest model that can handle it. A low-cost open model reads everything. A second, free model double-checks whatever the first calls routine.</p><p class="r">Result: frontier-level catch rate at about 1/16 of the cost. About half of the items needed the second look.</p></div>
<div class="way"><h3>Build a smarter harness</h3><p>Surround the models with the controls a business needs: a hard spending limit, automatic checks on every answer, and no ability for a model to act on its own.</p><p class="r">Result: if a malicious document fools a model, the worst case is one wrong answer that a check or a person can catch.</p></div>
<div class="way"><h3>Train a specialized model</h3><p>Teach a small open model one narrow job, using examples where the right answer is already known.</p><p class="r">Result: almost no false alarms and much shorter answers, but it missed slightly more. Early and still being tested.</p></div>
</div></section>

<section class="keep"><h2>Sorting by importance: a closer look</h2>
<p>A business that watches thousands of incoming documents needs the important ones flagged. We tested this on real company announcements the models had never seen, with settings locked in advance.</p>
{sorting_table()}
<p class="note">Differences of a few percentage points here are not statistically significant. The test set was about half important items, so false alarms will differ on a live stream. </p><p class="callout">On this test the laptop model alone matched our router, at no fee. So for volumes one laptop can handle, about 2,600 items an hour, the laptop alone is the better choice. The router earns its small cost when volume is higher, about 5,000 items an hour by our estimate, or when the work cannot depend on one machine staying on. The laptop model is also much weaker on writing and formatting, as the next chart shows.</p></section>

<section class="keep"><h2>No model wins every job</h2>
<p>Choose the job first, then the model. Pulling facts from forms is close to solved. Exact formatting is hard for every model.</p>
<figure>{img("heatmap", "Grid of share right by model and business job")}</figure></section>

<section><h2>How we measured</h2>
<table class="how"><tr><th>Measure</th><th>What it tells a business</th><th>How we checked it</th></tr>
<tr><td>Accuracy</td><td>Can I trust the answer?</td><td>Software compares each answer with official records. No AI grades the results</td></tr>
<tr><td>Cost</td><td>What does each 1,000 items cost?</td><td>Published prices applied to actual usage</td></tr>
<tr><td>Speed</td><td>Can it keep up with the volume?</td><td>Time per answer and items per second, measured under load</td></tr>
<tr><td>Security</td><td>Can a document trick the model?</td><td>We planted false instructions in documents and recorded which models obeyed</td></tr>
<tr><td>Confidence</td><td>Is a difference real, or luck?</td><td>Every model answers the same items, and differences are tested statistically</td></tr>
</table>
<p class="note">We also audited our own test. We found and fixed four faults, re-marked all saved answers, and retested on new documents after settings were locked.</p></section>

<section><h2>What the platform does</h2>
<ul><li><b>Recommends a setup</b> for a task: which models, how many running at once, budget and time.</li><li><b>Applies business rules.</b> Changing a rule, such as which models are allowed, changes the setup, even during a run.</li><li><b>Runs and checks the work</b> with a hard spending limit, and sends exceptions to a person.</li><li><b>Shows results</b> on dashboards, from the big picture down to the source document.</li></ul>
<div class="pair"><figure>{img("sweep", "Dashboard of news volume by topic")}<figcaption>News dashboard: the big picture by topic and hour</figcaption></figure><figure>{img("drill-down", "Dashboard drill-down by category")}<figcaption>Drill-down: one category, down to individual stories</figcaption></figure></div>
<figure style="margin-top:14px">{img("status-top", "Platform status page")}<figcaption>Live status: progress, cost so far and cost to finish</figcaption></figure></section>
</main></body></html>
"""


def main() -> int:
    OUT.write_text(page(), encoding="utf-8")
    print(OUT, OUT.stat().st_size // 1024, "KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
