from bench import triage


def test_clean_removes_item_headings_and_numbers():
    text = "Cover page\nItem 5.02 Departure of Directors or Certain Officers\nOn May 1 the CFO resigned, see Item 5.02.\nSIGNATURES\nName"
    out = triage.clean(text)
    assert "5.02" not in out and "Departure" not in out and "Name" not in out and "CFO resigned" in out


def test_score_key_gets_full_marks_and_half_for_type_only():
    item = {"key": {"type": "earnings", "priority": "normal"}}
    assert triage.score(item, '{"type": "earnings", "priority": "normal"}')["score"] == 1.0
    assert triage.score(item, '{"type": "earnings", "priority": "high"}')["score"] == 0.5
    assert triage.score(item, "not json")["valid"] is False


def test_person_name_placeholder_is_dropped():
    from bench.tasks import _pname
    assert _pname("N/A Ryse, L.P.") == _pname("Ryse, L.P.")
    assert _pname("n/a Gm Echo Manager Ltd") == _pname("Gm Echo Manager Ltd")
    assert _pname("Jon Schroeder") == "jon schroeder"


def test_quote_check_needs_real_text_and_matching_number():
    from bench import quote
    text = "Total assets   1,234  in millions\nNet sales 55.5"
    assert quote.quote_ok(text, 1234000000, "Total assets 1,234")
    assert not quote.quote_ok(text, 9999000000, "Total assets 1,234")
    assert not quote.quote_ok(text, 1234000000, "Total assets were 1,234")
    assert not quote.quote_ok(text, None, "Total assets 1,234")


def test_caller_retries_refusals_and_counts_them(monkeypatch):
    from bench import lanes
    monkeypatch.setattr(lanes, "RETRY_WAIT", 0.0)
    caller = lanes.Caller({"provider": "fake", "model": "fake"}, fake_answers={})
    seq = [lanes.Reply("", 0, 0, 0, "RateLimitError: Error code: 429"), lanes.Reply("", 0, 0, 0, "RateLimitError: Error code: 429"), lanes.Reply("ok", 1, 1, 0)]
    monkeypatch.setattr(caller, "_once", lambda *a, **k: seq.pop(0))
    r = caller("p", 10)
    assert r.text == "ok" and r.retries == 2 and r.error == ""
