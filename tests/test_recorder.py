import json
from datetime import datetime, timezone

from bench import recorder

FEED = {"name": "A", "group": "G", "url": "http://x"}


def row(title, link="l"):
    return {"title": title, "link": link, "time": datetime(2026, 11, 1, tzinfo=timezone.utc), "summary": "s"}


def lines(path):
    return [json.loads(x) for f in sorted(path.glob("headlines-*.jsonl")) for x in f.open()]


def test_same_story_is_saved_once_even_with_new_link_or_publisher(tmp_path):
    r = recorder.Recorder(tmp_path)
    assert r.save(FEED, [row("Big news - Paper A"), row("Big news - Paper B", "other"), row("Other news")]) == 2
    assert r.save(FEED, [row("Big news - Paper A")]) == 0
    got = lines(tmp_path)
    assert len(got) == 2 and got[0]["source"] == "A" and got[0]["seen"]


def test_restart_remembers_what_it_saw(tmp_path):
    recorder.Recorder(tmp_path).save(FEED, [row("Big news")])
    assert recorder.Recorder(tmp_path).save(FEED, [row("Big news")]) == 0


def test_bad_feed_does_not_stop_the_rest(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder.time, "sleep", lambda s: None)

    def reader(feed):
        if feed["name"] == "A":
            raise OSError("down")
        return [row("Fine")]
    r = recorder.Recorder(tmp_path, reader)
    assert r.one_pass([FEED, {"name": "B", "group": "G", "url": "http://y"}]) == 1
    state = json.loads((tmp_path / "feeds.json").read_text())
    assert state["A"]["status"] == "error" and state["B"]["status"] == "ok"


def test_each_feed_waits_its_turn(tmp_path, monkeypatch):
    monkeypatch.setattr(recorder.time, "sleep", lambda s: None)
    calls = []
    r = recorder.Recorder(tmp_path, lambda f: calls.append(f["name"]) or [])
    r.one_pass([FEED])
    r.one_pass([FEED])
    assert calls == ["A"]
    assert recorder.wait_for({"url": "x", "sec": True}) == 120 and recorder.wait_for({"url": "https://api.gdeltproject.org"}) == 900


STREAM = {"name": "Stream", "group": "Community", "url": "wss://x"}


def post(text, lang="en", op="create", reply=False):
    r = {"text": text, "langs": [lang], "createdAt": "2026-11-01T22:00:00.000Z"}
    if reply:
        r["reply"] = {}
    return json.dumps({"did": "did:plc:x", "commit": {"operation": op, "rkey": str(hash(text)), "record": r}})


def test_stream_keeps_only_english_new_posts_on_watched_topics(tmp_path):
    r = recorder.Recorder(tmp_path)
    assert r.stream_message(STREAM, post("Nvidia ships a new data center chip"))
    assert not r.stream_message(STREAM, post("Lovely weather today"))
    assert not r.stream_message(STREAM, post("Nvidia en francais", lang="fr"))
    assert not r.stream_message(STREAM, post("Nvidia again", op="delete"))
    assert not r.stream_message(STREAM, post("Nvidia reply", reply=True))
    assert not r.stream_message(STREAM, "not json")
    got = lines(tmp_path)
    assert len(got) == 1 and got[0]["link"].startswith("https://bsky.app/profile/") and r.streams["Stream"]["read"] == 6


def test_stream_allowance_caps_a_flood(tmp_path):
    r = recorder.Recorder(tmp_path)
    for i in range(30):
        r.stream_message({**STREAM, "keep_per_minute": 3}, post(f"Nvidia story number {i}"))
    assert len(lines(tmp_path)) <= 6 and r.streams["Stream"]["matched"] == 30


def test_dropped_stream_is_survived(tmp_path):
    r = recorder.Recorder(tmp_path)

    def broken(url, **kw):
        raise OSError("no network")
    r.stream_loop(STREAM, connect=broken, forever=False)
    assert "no network" in r.streams["Stream"]["status"]
