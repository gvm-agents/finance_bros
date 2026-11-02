import json
import re
import time
from pathlib import Path

import pytest

from bench import coordinator as co
from bench import router
from bench.lanes import Reply

LANES = {"cheap": {"provider": "fake", "model": "m", "price_in": 1.0, "price_out": 1.0, "group": "open-cloud", "origin": "US (A)"},
         "second": {"provider": "fake", "model": "m", "price_in": 1.0, "price_out": 1.0, "group": "open-cloud", "origin": "China (B)"},
         "third": {"provider": "fake", "model": "m", "price_in": 1.0, "price_out": 1.0, "group": "frontier", "origin": "US (C)"},
         "local": {"provider": "ollama", "model": "m", "price_in": 0.0, "price_out": 0.0, "group": "open-local", "origin": "US (D)"}}
ROUTES = {"jobs": {"triage_8k": {"first": ["cheap", "local"], "second": ["second", "third"], "stronger": ["third"], "auditor": ["local"], "private": ["local"]}},
          "policies": {"all_models": {"label": "All", "block_origins": []}, "no_china": {"label": "No", "block_origins": ["China"]},
                       "local_only": {"label": "Local", "block_origins": [], "local_only": True}},
          "default_policy": "all_models", "unsure_below": 0.8, "audit_rate": 0.0, "second_queue_cap": 50}


def fixed(reply):
    return lambda prompt, max_out, item_id="": Reply(reply if isinstance(reply, str) else reply(item_id), 100, 10, 0.01)


def R(tmp_path, n, callers, **kw):
    return router.Router("triage_8k", tmp_path, n, kw.pop("max_usd", 1.0), routes=ROUTES, lanes=LANES, read_prompt=lambda i: "p", make_caller=lambda name, lane: callers[name], **kw)


def rows(tmp_path):
    return [json.loads(x) for x in (tmp_path / "answers.jsonl").open()]


def test_policy_changes_which_model_is_chosen():
    assert router.plan("triage_8k", "all_models", ROUTES, LANES)["second"] == "second"
    assert router.plan("triage_8k", "no_china", ROUTES, LANES)["second"] == "third"
    p = router.plan("triage_8k", "local_only", ROUTES, LANES)
    assert p["first"] == "local" and p["second"] is None


def test_shipped_routes_name_only_real_lanes():
    from bench.lanes import load_lanes
    lanes, routes = load_lanes(), router.load_routes()
    for job in routes["jobs"].values():
        for names in job.values():
            assert isinstance(names, str) or all(n in lanes for n in names)
    assert all(l.get("origin") for l in lanes.values())


def test_confident_answer_skips_second_reader(tmp_path):
    second = {"n": 0}

    def count(prompt, max_out, item_id=""):
        second["n"] += 1
        return Reply('{"priority": "high", "confidence": 1}', 1, 1, 0.0)
    r = R(tmp_path, 2, {"cheap": fixed('{"priority": "normal", "confidence": 0.95}'), "second": count})
    out = r.run([{"id": "a", "text": "routine note"}, {"id": "b", "text": "nothing here"}])
    assert second["n"] == 0 and out["done"] == 2 and out["high"] == 0


def test_warning_word_or_low_confidence_goes_to_second_reader_and_high_wins(tmp_path):
    r = R(tmp_path, 2, {"cheap": fixed('{"priority": "normal", "confidence": 0.95}'), "second": fixed('{"priority": "high", "confidence": 0.9}')})
    out = r.run([{"id": "a", "text": "The CFO resigned today"}, {"id": "b", "text": "nothing here"}])
    got = {x["id"]: x for x in rows(tmp_path)}
    assert got["a"]["final"] == "high" and got["a"]["to_person"] and got["a"]["second_lane"] == "second"
    assert got["b"]["final"] == "normal" and got["b"]["second_lane"] is None
    assert out["second_reads"] == 1 and out["to_person"] == 1


def test_unreadable_reply_is_unsure_not_lost(tmp_path):
    r = R(tmp_path, 1, {"cheap": fixed("not json"), "second": fixed('{"priority": "normal", "confidence": 0.9}')})
    r.run([{"id": "a", "text": "x"}])
    assert rows(tmp_path)[0]["second_lane"] == "second"


def test_full_queue_defers_lowest_risk_and_keeps_every_item(tmp_path):
    spilled = []
    q = router.SecondQueue(2, spilled.append)
    q.put(1.0, {"n": "low"})
    q.put(3.0, {"n": "high"})
    q.put(2.0, {"n": "mid"})
    assert [s["n"] for s in spilled] == ["low"]
    assert q.get()["n"] == "high"
    assert q.get()["n"] == "mid"


def test_slow_second_reader_never_holds_up_first_reads(tmp_path):
    import threading
    gate = threading.Event()

    def stuck(prompt, max_out, item_id=""):
        gate.wait(5)
        return Reply('{"priority": "normal", "confidence": 0.9}', 1, 1, 0.0)
    r = R(tmp_path, 20, {"cheap": fixed('{"priority": "normal", "confidence": 0.1}'), "second": stuck}, queue_cap=3, second_workers=1, workers=2)
    items = [{"id": str(i), "text": "x"} for i in range(20)]
    r.start()
    co.run_items(items, r.first_read, r.ledger, 2)  # returns with the second reader still stuck
    assert not gate.is_set() and r.ledger.c["deferred"] >= 15
    gate.set()
    r.second_q.close()
    for t in r.threads[:1]:
        t.join(5)
    assert len(rows(tmp_path)) == 20


def test_auditor_failure_changes_nothing(tmp_path):
    def down(prompt, max_out, item_id=""):
        raise OSError("local model is off")
    r = R(tmp_path, 3, {"cheap": fixed('{"priority": "high", "confidence": 0.95}'), "local": down}, audit_rate=1.0)
    out = r.run([{"id": str(i), "text": "x"} for i in range(3)])
    assert out["done"] == 3 and out["high"] == 3 and out.get("audited", 0) == 0


def test_policy_change_applies_during_a_run(tmp_path):
    r = R(tmp_path, 2, {"cheap": fixed('{"priority": "normal", "confidence": 0.1}'), "second": fixed('{"priority": "high", "confidence": 1}'), "third": fixed('{"priority": "normal", "confidence": 1}')})
    assert r.plan["second"] == "second"
    (tmp_path / "control.json").write_text('{"policy": "no_china"}')
    r.refresh_policy()
    assert r.plan["second"] == "third" and r.ledger.context["policy"] == "No"


def test_budget_stops_the_run_before_the_cap(tmp_path):
    led = co.Ledger(tmp_path, 3, 0.01)
    assert led.reserve(0.006) and not led.reserve(0.006)
    assert "budget" in led.stopped


def test_stop_file_and_resume(tmp_path):
    lane = LANES["cheap"]
    items = [{"id": "1"}, {"id": "2"}]
    led = co.Ledger(tmp_path, 2, 1.0)
    led.add({"id": "1", "usd": 0.5})
    again = co.Ledger(tmp_path, 2, 1.0)
    assert again.seen == {"1"} and again.spent == 0.5 and again.snapshot()["cost_to_finish"] == 0.5
    (tmp_path / "STOP").write_text("")
    assert not again.reserve(0.0)
    assert lane and items


def test_one_item_crash_is_recorded_not_fatal(tmp_path):
    led = co.Ledger(tmp_path, 2, 1.0)

    def work(item):
        if item["id"] == "1":
            raise ValueError("bad")
        led.add({"id": item["id"], "usd": 0.0})
    co.run_items([{"id": "1"}, {"id": "2"}], work, led, 1)
    assert led.c["done"] == 2 and led.c["failed"] == 1


def test_saved_router_runs_with_no_keys(tmp_path, monkeypatch):
    monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)
    out = router.saved_router(tmp_path, speed=5000)
    assert out["done"] == out["total"] == 181 and 90 <= out["second_reads"] <= 100 and out["cost_so_far"] < 0.05


def rune_reply(p_high):
    return json.dumps([{"type": "choice", "name": "type", "choice": "bankruptcy" if p_high >= 0.5 else "earnings", "confidence": 0.9,
                        "probabilities": [{"value": "bankruptcy", "probability": p_high}, {"value": "earnings", "probability": 1 - p_high}]}])


DECIDE = {**LANES, "cheap": {**LANES["cheap"], "provider": "fw_decide"}}
BANDS = {**ROUTES, "first_bands": {"cheap": {"sure_high": 0.8, "sure_normal": 0.005}}}


def RB(tmp_path, n, callers, **kw):
    return router.Router("triage_8k", tmp_path, n, 1.0, routes=BANDS, lanes=DECIDE, make_caller=lambda name, lane: callers[name], read_prompt=lambda i: "p", **kw)


def test_probability_bands_decide_who_needs_a_second_reader(tmp_path):
    seen = {}
    replies = {"sure": rune_reply(0.95), "none": rune_reply(0.001), "mid": rune_reply(0.2)}

    def first(prompt, max_out, item_id=""):
        return Reply(replies[item_id], 100, 0, 0.1)

    def second(prompt, max_out, item_id=""):
        seen[item_id] = True
        return Reply('{"type": "earnings", "priority": "high"}', 10, 5, 0.1)
    RB(tmp_path, 3, {"cheap": first, "second": second}).run([{"id": k, "text": "the CFO resigned"} for k in replies])
    got = {r["id"]: r for r in rows(tmp_path)}
    assert list(seen) == ["mid"]
    assert got["sure"]["final"] == "high" and got["none"]["final"] == "normal" and got["mid"]["final"] == "high" and got["mid"]["p_high"] == 0.2


def test_laptop_off_falls_back_to_next_lane(tmp_path):
    def laptop(prompt, max_out, item_id=""):
        return Reply("", 0, 0, 0.0, "APIConnectionError: Connection error.")
    r = RB(tmp_path, 1, {"cheap": fixed(rune_reply(0.2)), "second": laptop, "third": fixed('{"priority": "high"}')})
    out = r.run([{"id": "a"}])
    got = rows(tmp_path)[0]
    assert got["second_lane"] == "third" and got["final"] == "high" and out["second_failovers"] == 1


def test_no_second_reader_on_keeps_first_answer_and_says_so(tmp_path):
    r = RB(tmp_path, 2, {"cheap": fixed(rune_reply(0.6))}, no_second=True)
    r.run([{"id": "a"}, {"id": "b"}])
    assert all(x["deferred"] and x["final"] == "high" for x in rows(tmp_path))


def test_lane_without_deployment_counts_as_off(monkeypatch):
    from bench.lanes import load_lanes
    monkeypatch.delenv("TUNED_GLIMMER_MODEL", raising=False)
    assert not router.is_on(load_lanes()["muse_glimmer_tuned_fw"])
    monkeypatch.setenv("TUNED_GLIMMER_MODEL", "m")
    monkeypatch.setenv("TUNED_GLIMMER_DEPLOYMENT", "d")
    assert router.is_on(load_lanes()["muse_glimmer_tuned_fw"])


def test_pacer_spaces_calls():
    p = router.Pacer(200)
    t = time.time()
    for _ in range(5):
        p.wait()
    assert time.time() - t >= 0.015


def test_comparison_lanes_are_never_routed():
    routes = router.load_routes()
    job = routes["jobs"]["triage_8k"]
    assert job["first"][0] == "gptoss120_fw" and job["second"][0] == "gemma4_12b_local"
    assert "rune_fw" not in json.dumps(routes) and "rune_fw" not in router.load_lanes()


def test_combos_keep_only_designs_that_hit_the_target_cheapest_first():
    out = router.combos("fresh", min_recall=98.0, baseline="sonnet5")
    assert out["false_alarm_cap"] == 11 and out["tried"] > 20
    ok = out["passing"]
    assert ok and all(r["recall"] >= 98.0 and r["false_alarms"] <= 11 for r in ok)
    assert [r["usd_per_1000"] for r in ok] == sorted(r["usd_per_1000"] for r in ok)
    names = {r["name"] for r in ok}
    assert "gptoss120_fw then gemma4_12b_local on routine calls" in names and "sonnet5" not in names  # the frontier model alone misses 2 of 82


def test_score_marks_a_router_run_and_logs_it(tmp_path, monkeypatch):
    monkeypatch.setattr(router.co, "RUNS", tmp_path)
    monkeypatch.setattr(router, "SCOREBOARD", tmp_path / "scoreboard.jsonl")
    d = tmp_path / "r1"
    d.mkdir()
    rows = [("high", "high")] * 49 + [("normal", "high")] + [("high", "normal")] * 2 + [("normal", "normal")] * 48
    with (d / "answers.jsonl").open("w") as f:
        for i, (final, key) in enumerate(rows):
            f.write(json.dumps({"id": str(i), "task": "triage_8k_fresh", "lane": "gptoss120_fw", "second_lane": "gemma4_12b_local", "final": final, "key": key, "usd": 0.0001, "seconds": 1.0}) + "\n")
    (d / "status.json").write_text(json.dumps({"items_per_sec": 2.0}))
    r = router.score_run("r1", min_recall=98.0, max_false_alarms=2, note="round 1")
    assert (r["caught"], r["real"], r["false_alarms"], r["per_hour"]) == (49, 50, 2, 7200)
    assert r["meets_target"] is True and r["models"] == ["gemma4_12b_local", "gptoss120_fw"]
    assert router.score_run("r1", min_recall=99.0, log=False)["meets_target"] is False
    assert json.loads((tmp_path / "scoreboard.jsonl").read_text())["note"] == "round 1"


def test_simulation_reproduces_published_counts():
    fresh, old = router.simulate("fresh"), router.simulate("earlier")
    by = {s["name"]: s for s in fresh["singles"]}
    assert "rune_fw" not in by
    assert (by["sonnet5"]["caught"], by["gemma4_12b_local"]["caught"], by["gptoss120_fw"]["caught"]) == (80, 81, 78)
    assert by["sonnet5"]["real"] == 82 and by["muse_glimmer_tuned_fw"]["caught"] == 77 and by["muse_glimmer_tuned_fw"]["false_alarms"] == 0
    c = {s["name"]: s for s in fresh["systems"]}["gpt-oss, then Gemma on routine calls"]
    assert (c["caught"], c["false_alarms"]) == (81, 11)
    e = {s["name"]: s for s in old["systems"]}["gpt-oss, then Gemma on routine calls"]
    assert (e["caught"], e["real"]) == (104, 105)


def test_repo_stays_free_of_private_words():
    root = Path(__file__).resolve().parent.parent
    bad = re.compile("|".join(["catch" + "light", "hack" + "athon", "linked" + "in", "bry" + "an", "fin" + "kel", r"(?-i:\bMark\b)", r"(?-i:\bJohn\b)"]), re.I)
    hits = []
    for p in list(root.glob("bench/*")) + list(root.glob("*.json")) + list(root.glob("dashboard/*")) + list(root.glob("*.md")):
        if p.is_file() and p.suffix in (".py", ".json", ".md", ".html", ".js", ".css") and bad.search(p.read_text(errors="ignore")):
            hits.append(p.name)
    assert not hits, hits
