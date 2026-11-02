import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from bench import dashboard as D
from bench import goals as G


@pytest.fixture
def server(tmp_path):
    rows = tmp_path / "h.jsonl"
    rows.write_text("\n".join(json.dumps({"id": f"h{i}", "source": "S", "group": "G", "title": f"Nvidia data center {i}", "link": "", "time": f"2026-10-30T0{i}:00:00+00:00", "summary": "<b>x</b>"}) for i in range(5)))
    run = tmp_path / "runs" / "r"
    run.mkdir(parents=True)
    (run / "status.json").write_text('{"state": "running", "done": 1, "context": {"task": "t"}}')
    store = D.Store(False, "r", None, 60, runs=tmp_path / "runs", recorder=tmp_path / "none")
    store.source_files = lambda: [rows]
    store.goals_file = tmp_path / "goals.json"
    srv = D.ThreadingHTTPServer(("127.0.0.1", 0), D.handler(store))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}", store, run
    srv.shutdown()


def get(url):
    return json.load(urllib.request.urlopen(url, timeout=5))


def post(url, body, headers=None):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **(headers or {})})
    return json.load(urllib.request.urlopen(req, timeout=5))


def test_every_data_address_answers(server):
    base, _, _ = server
    assert len(get(base + "/api/headlines")["rows"]) == 5
    assert get(base + "/api/status")["done"] == 1
    assert get(base + "/api/context")["context"]["task"] == "t"
    c = get(base + "/api/compare")
    assert c["singles"] and c["policies"]
    assert b"Open Model Dashboard" in urllib.request.urlopen(base + "/").read()


def test_headlines_are_tagged_and_article_falls_back_to_summary(server):
    base, _, _ = server
    r = get(base + "/api/headlines")["rows"][0]
    assert "Data centers" in r["topics"] and "Big tech" in r["topics"]
    a = get(base + "/api/article?id=h1")
    assert a["full"] is False and a["text"] == "<b>x</b>"


def test_policy_button_writes_the_control_file(server):
    base, _, run = server
    assert post(base + "/api/policy", {"policy": "local_only"})["policy"] == "local_only"
    assert json.loads((run / "control.json").read_text())["policy"] == "local_only"


def test_other_sites_cannot_change_anything(server):
    base, _, _ = server
    with pytest.raises(urllib.error.HTTPError):
        post(base + "/api/policy", {"policy": "local_only"}, {"Origin": "http://elsewhere.example"})


def test_goals_keep_their_tree(server):
    base, _, _ = server
    a = post(base + "/api/goals", {"title": "Main"})
    b = post(base + "/api/goals", {"title": "Follow-up", "parent": a["id"]})
    post(base + "/api/goal", {"id": b["id"], "status": "done"})
    got = {g["id"]: g for g in get(base + "/api/goals")["goals"]}
    assert got[b["id"]]["parent"] == a["id"] and got[b["id"]]["status"] == "done"


def test_goal_rejects_unknown_parent(tmp_path):
    with pytest.raises(ValueError):
        G.add("x", parent="g9", path=tmp_path / "g.json")


def test_replay_reveals_rows_over_time(tmp_path):
    rows = tmp_path / "h.jsonl"
    rows.write_text("\n".join(json.dumps({"id": str(i), "source": "S", "group": "G", "title": "t", "time": f"2026-10-30T{i:02d}:00:00+00:00"}) for i in range(10)))
    s = D.Store(False, None, rows, 3600.0)
    early = len(s.visible()[0])
    s.t0 = time.time() - 6
    assert early < len(s.visible()[0]) <= 10


def test_private_addresses_are_never_fetched():
    assert not D.public_host("http://127.0.0.1:8000/x")
    assert not D.public_host("http://169.254.169.254/latest")
    assert not D.public_host("file:///etc/hosts")


def test_future_dated_rows_do_not_break_the_clock(tmp_path):
    rows = tmp_path / "h.jsonl"
    rows.write_text(json.dumps({"id": "1", "source": "S", "group": "G", "title": "t", "time": "2031-01-01T00:00:00+00:00"}))
    s = D.Store(False, None, None, 60)
    s.source_files = lambda: [rows]
    assert s.rows() == []
