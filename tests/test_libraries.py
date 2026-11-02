import datetime as dt

from bench import adv_library, sec_pdfs


def test_category_and_window():
    assert sec_pdfs.category("7372") == "software and internet"
    assert sec_pdfs.category("6770") is None
    assert sec_pdfs.window_start(dt.date(2026, 10, 30)) == "2025-09-30"
    assert sec_pdfs.window_start(dt.date(2026, 1, 15)) == "2024-12-15"


def test_parse_form_idx():
    text = ("S-1              Anthropic, PBC        2130357     2026-10-26  edgar/data/2130357/x.txt\n"
            "1-A              Arte Consulting Inc.  2137570     2026-07-02  edgar/data/2137570/y.txt\n"
            "F-1/A            Some Co               123         2026-07-02  edgar/data/123/z.txt\n")
    assert sec_pdfs.parse_form_idx(text) == {"2130357", "2137570", "123"}
    assert sec_pdfs.parse_form_idx(text, forms=("S-1",)) == {"2130357"}


def test_recent_filings_keeps_major_forms_in_window():
    sub = {"filings": {"recent": {"form": ["10-K", "8-K", "S-1", "10-Q"],
                                  "filingDate": ["2026-02-01", "2026-02-02", "2026-10-26", "2024-01-01"],
                                  "accessionNumber": ["a", "b", "c", "d"],
                                  "primaryDocument": ["a.htm", "b.htm", "c.htm", "d.htm"]}, "files": []}}
    assert [f["acc"] for f in sec_pdfs.recent_filings(sub, "2025-09-30")] == ["a", "c"]


def test_clean_html_drops_hidden_header():
    raw = b"<html><ix:header>hidden</ix:header><script>x</script><p>body</p></html>"
    assert sec_pdfs.clean_html(raw) == b"<html><p>body</p></html>"


def test_adv_month_names():
    assert adv_library.month_of("ADV_Brochures_2026_March_1_of_2.zip") == "2026-03"
    assert adv_library.month_of("FIRM_CRS_MONTHLY_20260930_502.zip") == "2026-09"
    assert adv_library.month_of("ADVW_20250901_20250930.zip") == "2025-09"
    assert adv_library.month_window(dt.date(2026, 10, 30))[0] == "2026-09"
    assert adv_library.iso("06/26/2026") == "2026-06-26"
