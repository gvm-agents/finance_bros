import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bench import __main__ as cli  # noqa: E402
from bench import adv, collect, readiness, sec, tasks  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


def formd_item():
    key = sec.parse_form_d((FIX / "formd_full.xml").read_text())
    return {"id": "9999999-x", "text": sec.render_form_d_text(key), "key": key, "split": "test"}


def perfect_formd(key):
    return json.dumps({**{f: key[f] for f in tasks.FORMD_FIELDS}, "related_persons": key["related_persons"]})


def test_parse_form_d_key():
    k = formd_item()["key"]
    assert k["issuer_name"] == "Fictional Sensors Labs, Inc."
    assert k["total_amount_sold"] == 12250000 and k["number_of_investors"] == 14
    assert k["related_persons"][0] == {"name": "Ada Q Example", "relationships": ["Director", "Executive Officer"]}


def test_formd_perfect_and_invented():
    it = formd_item()
    s = tasks.formd_score(it, "```json\n" + perfect_formd(it["key"]) + "\n```")
    assert s["score"] == 1.0 and s["invented"] == 0
    bad = json.loads(perfect_formd(it["key"]))
    bad["total_amount_sold"] = 13000000          # a number not in the filing
    bad["related_persons"] = bad["related_persons"][:1]
    s = tasks.formd_score(it, json.dumps(bad))
    assert s["invented"] == 1 and s["score"] < 1.0
    assert tasks.formd_score(it, "no json here")["valid"] is False


def test_number_parsing():
    assert tasks.to_number("$12.25 million") == 12250000.0
    assert tasks.same_value("$12,250,000", 12250000)
    assert tasks.same_value("Indefinite", "Indefinite")


def test_snapshot_scoring_catches_invented_numbers():
    it = formd_item()
    it["facts"] = tasks.snapshot_facts(it["key"])
    table = ("| Field | Value |\n|---|---|\n| Issuer | Fictional Sensors Labs, Inc. |\n| Industry | Other Technology |\n"
             "| Amount sold | $12,250,000 |\n| Offering size | $15.0 million |\n| First sale | 2026-08-15 |\n| Investors | 14 |")
    good = "SNAPSHOT: " + " ".join(["Fictional Sensors Labs raised $12.25 million from 14 investors."] * 8) + "\n\n" + table
    s = tasks.snapshot_score(it, good)
    assert s["table_accuracy"] == 1.0 and s["invented"] == 0 and s["score"] == 1.0
    s = tasks.snapshot_score(it, good.replace("$12.25 million", "$40 million"))
    assert s["invented"] > 0 and s["score"] < 1.0


def test_format_table_exact():
    it = formd_item()
    it["text"] = tasks.format_prose(it["key"])
    gold = "| Name | Relationships |\n|---|---|\n| Ada Q Example | Director; Executive Officer |\n| Ben Sample | Director |"
    assert tasks.format_score(it, gold)["score"] == 1.0
    assert tasks.format_score(it, gold.replace("Director; Executive Officer", "Executive Officer, Director"))["score"] < 1.0


def test_sic_division_and_xbrl():
    assert sec.sic_division("7372") == "I" and sec.sic_division("3674") == "D" and sec.sic_division("6022") == "H"
    facts = {"facts": {"us-gaap": {"Assets": {"units": {"USD": [
        {"val": 100, "end": "2025-12-31", "accn": "A1", "form": "10-K"},
        {"val": 90, "end": "2024-12-31", "accn": "A1", "form": "10-K"}]}}}}}
    assert sec.xbrl_answers(facts, "A1") == {"total_assets": 100}


def test_item_1_skips_table_of_contents():
    text = "Item 1. Business 3\nItem 1A. Risk Factors 9\n...\nItem 1. Business\nWe make sensors.\nItem 1A. Risk Factors\nRisky."
    assert sec.item_1(text) == "We make sensors."


def test_end_to_end_with_fake_lane(tmp_path, monkeypatch):
    it = formd_item()
    monkeypatch.setattr(collect, "ITEMS", tmp_path / "items")
    monkeypatch.setattr(cli, "RUNS", tmp_path / "runs")
    collect.save("formd_extract", [it])
    lanes = {"fake": {"provider": "fake", "model": "fake", "price_in": 1.0, "price_out": 2.0, "group": "frontier",
                      "price_source": "test"}}
    monkeypatch.setattr(cli, "load_lanes", lambda: lanes)
    path = cli.run(["fake"], ["formd_extract"], "test", None, 1.0, "t1", 1, fake={it["id"]: perfect_formd(it["key"])})
    rows = cli.summarize(path)
    assert rows[0]["score"] == 1.0 and rows[0]["n"] == 1 and rows[0]["usd_per_1000"] > 0
    out = cli.report("t1")
    assert "fake" in out.read_text()
    # resume: same run id does not repeat finished items
    cli.run(["fake"], ["formd_extract"], "test", None, 1.0, "t1", 1, fake={it["id"]: "{}"})
    assert len(path.read_text().splitlines()) == 1


def test_spending_cap_stops_before_overspend(tmp_path, monkeypatch):
    it = formd_item()
    monkeypatch.setattr(collect, "ITEMS", tmp_path / "items")
    monkeypatch.setattr(cli, "RUNS", tmp_path / "runs")
    collect.save("formd_extract", [it])
    lanes = {"pricey": {"provider": "fake", "model": "fake", "price_in": 1e6, "price_out": 1e6, "group": "frontier",
                        "price_source": "test"}}
    monkeypatch.setattr(cli, "load_lanes", lambda: lanes)
    path = cli.run(["pricey"], ["formd_extract"], "test", None, 0.01, "cap", 1, fake={})
    assert not path.exists() or path.read_text() == ""


def test_export_sft_uses_train_only(tmp_path, monkeypatch):
    a, b = formd_item(), formd_item()
    a["id"], a["split"], b["id"], b["split"] = "a", "train", "b", "test"
    monkeypatch.setattr(collect, "ITEMS", tmp_path / "items")
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    collect.save("formd_extract", [a, b])
    rows = [json.loads(l) for l in cli.export_sft("formd_extract").read_text().splitlines()]
    assert len(rows) == 1 and json.loads(rows[0]["messages"][1]["content"])["total_amount_sold"] == 12250000


# ---------------------------------------------------------------- added 2026-10-29

def test_name_items_balanced_and_not_trivial(monkeypatch):
    names = {"1": "Acme Robotics Inc", "2": "Acme Foods Corp", "3": "Zeta Labs Inc", "4": "Zeta Mining Co",
             "5": "Northwind Data Inc", "6": "Northwind Shipping LLC"}
    subs = {"1": {"name": "Acme Robotics Inc", "formerNames": [{"name": "ACME ROBOTICS HOLDINGS LTD"}]},
            "3": {"name": "Zeta Labs Inc", "formerNames": [{"name": "Totally Different Name Inc"}]},
            "5": {"name": "Northwind Data Inc", "formerNames": [{"name": "Northwind Data Inc."}]}}
    monkeypatch.setattr(collect.sec, "get_json", lambda url: {str(i): {"cik_str": k, "title": v} for i, (k, v) in enumerate(names.items())})
    monkeypatch.setattr(collect.sec, "submissions", lambda cik: {"stateOfIncorporation": "DE", "sicDescription": "X",
                                                                 **subs.get(cik, {"name": names[cik]})})
    items = collect.name_items([], log=lambda *_: None, pairs=10)
    same = [i for i in items if i["key"]["same"]]
    diff = [i for i in items if not i["key"]["same"]]
    assert [i["id"] for i in same] == ["pos-1"]      # unguessable rename and spelling-only twin are left out
    assert len(diff) == 1 and diff[0]["a"]["name"].split()[0] == diff[0]["b"]["name"].split()[0]


def adv_item():
    text = ("FORM ADV cover\n" + "x" * 9000 + "\nItem 5 Information About Your Advisory Business - Employees\n"
            "A. Approximately how many employees do you have? 32\n(1) advisory functions 30\n"
            "         Discretionary:      (a) $ 628,902,725      (d) 1,548\n"
            "         Non-Discretionary:  (b) $ 1,763,081        (e) 6\n"
            "         Total:              (c) $ 630,665,806      (f) 1,554\nMain office: San Ramon, CA\n")
    key = {"total_employees": 32, "advisory_employees": 30, "aum_discretionary": 628902725,
           "aum_non_discretionary": 1763081, "aum_total": 630665806, "accounts_total": 1554, "main_office_state": "CA"}
    return {"id": "adv-38", "text": adv.window(text), "key": key, "split": "test"}


def test_adv_window_key_and_score():
    it = adv_item()
    assert it["text"] and adv.key_in_text(it["key"], it["text"])
    assert not adv.key_in_text({**it["key"], "aum_total": 999999999}, it["text"])
    assert tasks.adv_score(it, json.dumps(it["key"]))["score"] == 1.0
    wrong = {**it["key"], "aum_total": 700000000}
    s = tasks.adv_score(it, json.dumps(wrong))
    assert s["score"] < 1.0 and s["invented"] == 1


def test_readiness_key_must_not_be_on_macbook(monkeypatch, tmp_path):
    lanes = {"fw": {"provider": "fireworks", "runs_on": "mini", "model": "accounts/fireworks/models/x"}}
    monkeypatch.setattr(readiness, "SECRETS_FILE", tmp_path / "none.env")
    monkeypatch.setenv("FIREWORKS_API_KEY", "secret-value")
    rep = readiness.Report()
    readiness.check_fireworks(rep, lanes, "macbook", online=False)
    assert rep.rows[0][1] == "FAIL" and "secret-value" not in json.dumps(rep.rows)
    monkeypatch.delenv("FIREWORKS_API_KEY")
    rep = readiness.Report()
    readiness.check_fireworks(rep, lanes, "macbook", online=False)
    assert rep.rows[0][1] == "PASS"


def test_readiness_corpus_and_spend(tmp_path):
    (tmp_path / "data" / "items").mkdir(parents=True)
    rows = [{"id": str(i), "split": "test" if i < 70 else "train", "key": {"same": i % 2 == 0}} for i in range(100)]
    (tmp_path / "data" / "items" / "name_match.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    (tmp_path / "spend_cap.json").write_text(json.dumps({"total_usd": 100, "fireworks_limit_confirmed": None}))
    rep = readiness.Report()
    readiness.check_corpus(rep, tmp_path)
    readiness.check_spend(rep, tmp_path)
    res = {r[0]: r[1] for r in rep.rows}
    assert res["Data: name_match"] == "PASS" and res["Data: sector"] == "FAIL"
    assert res["Spending cap"] == "FAIL"         # not confirmed by the owner yet


def test_confirm_lanes_refuse_to_run():
    import pytest
    from bench.lanes import Caller
    with pytest.raises(ValueError):
        Caller({"provider": "fireworks", "model": "accounts/fireworks/models/x", "deployment": "CONFIRM"})


def test_merge_skips_duplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "RUNS", tmp_path)
    row = {"lane": "a", "task": "t", "item": "1"}
    other = tmp_path / "other.jsonl"
    other.write_text(json.dumps(row) + "\n" + json.dumps({**row, "item": "2"}) + "\n")
    assert cli.merge("r1", other) == 2
    assert cli.merge("r1", other) == 0
