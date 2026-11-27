"""Company pattern presets (R-60): the share rule, the data file, and the interview form."""
import csv
import html
import json
import re
from fractions import Fraction
from pathlib import Path

import pytest

from codecompass import catalog, queries, views
from codecompass.core import companies as presets
from codecompass.core import constants as c
from codecompass.core.catalog_rows import DataFileError, parse_patterns
from codecompass.db import get_db

from conftest import create_app

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = parse_patterns(catalog.read_rows(catalog.DATA_DIR / "patterns.csv"))
ORDER = [p["name"] for p in PATTERNS]
CATEGORIES = {p["name"]: p["category"] for p in PATTERNS}


def listed(link, frequency, topics):
    return {"Difficulty": "MEDIUM", "Title": "A problem", "Frequency": str(frequency), "Acceptance Rate": "0.5",
            "Link": link, "Topics": topics}


# --- Mapping LeetCode's topics ---

def test_specific_topics_win_over_generic_ones():
    assert presets.topic_patterns(["Hash Table", "String", "Sliding Window"], ORDER) == ["Sliding Window"]
    assert presets.topic_patterns(["Hash Table", "String"], ORDER) == ["Arrays and Hashing", "Strings"]
    assert presets.topic_patterns(["Math", " Merge Sort "], ORDER) == ["Sorting", "Math"]  # Pattern-list order.


def test_searches_on_trees_are_tree_traversal():
    assert presets.topic_patterns(["Tree", "Depth-First Search", "Binary Tree"], ORDER) == ["Tree Traversal"]
    assert presets.topic_patterns(["Breadth-First Search", "Matrix"], ORDER) == ["Graph Traversal"]
    # A search is specific, so the generic topic beside it does not count.
    assert presets.topic_patterns(["Depth-First Search", "Hash Table"], ORDER) == ["Graph Traversal"]
    assert presets.topic_patterns(["Binary Search Tree", "Tree"], ORDER) == ["Tree Traversal", "Binary Search Trees"]


def test_ambiguous_topics_map_to_nothing():
    for topics in (["Array"], ["Dynamic Programming", "Matrix"], ["Memoization", "Recursion", "Queue", "Bitmask"],
                   ["Database"], ["Shell"], ["Concurrency"], ["Not a topic"], []):
        assert presets.topic_patterns(topics, ORDER) == [], topics


def test_every_topic_maps_to_a_known_pattern():
    assert set(presets.SPECIFIC.values()) | set(presets.GENERIC.values()) <= set(ORDER)
    assert not set(presets.SPECIFIC) & set(presets.GENERIC)


# --- The share rule, on fixture data worked out by hand ---

CATALOG = {presets.link_key("https://leetcode.com/problems/two-sum/"): ["Arrays and Hashing"]}
ROWS = [
    # In the catalog, matched ignoring case, "www.", and the trailing slash: Arrays and Hashing 100.
    listed("https://www.LeetCode.com/problems/Two-Sum", 100, "Array, Hash Table"),
    listed("https://leetcode.com/problems/b", 60, "Hash Table, String, Sliding Window"),  # Sliding Window 60.
    listed("https://leetcode.com/problems/c", 30, "Tree, Depth-First Search, Binary Tree"),  # Tree Traversal 30.
    listed("https://leetcode.com/problems/d", 30, "Depth-First Search, Union-Find"),  # 15 each.
    listed("https://leetcode.com/problems/e", 20, "Array, Dynamic Programming"),  # Not counted.
    listed("https://leetcode.com/problems/f", 10, "Math, Hash Table"),  # Math 5, Arrays and Hashing 5.
]


def test_shares_worked_out_by_hand(monkeypatch):
    monkeypatch.setattr(c, "COMPANY_MIN_PROBLEMS", 6)
    result = presets.company_shares(ROWS, CATALOG, ORDER)
    # Counted frequency: 100 + 60 + 30 + 30 + 10 = 230.
    assert result == {
        "problems": 6,
        "counted": 5,
        "catalog_share": 43.5,  # 100 / 230
        "shares": [
            ("Arrays and Hashing", 45.7),  # 105 / 230
            ("Sliding Window", 26.1),  # 60 / 230
            ("Tree Traversal", 13.0),  # 30 / 230
            ("Graph Traversal", 6.5),  # 15 / 230, before Union-Find in the pattern list
            ("Union-Find", 6.5),
            ("Math", 2.2),  # 5 / 230
        ],
    }


def test_a_short_list_gets_no_shares_of_its_own(monkeypatch):
    monkeypatch.setattr(c, "COMPANY_MIN_PROBLEMS", 7)
    assert presets.company_shares(ROWS, CATALOG, ORDER) is None


def test_shares_round_half_up():
    assert presets._percent(Fraction(1), 16) == 6.3  # 6.25
    assert presets._percent(Fraction(1), 3) == 33.3


def test_a_frequency_that_is_not_a_number_is_reported(monkeypatch):
    monkeypatch.setattr(c, "COMPANY_MIN_PROBLEMS", 1)
    with pytest.raises(ValueError, match="row 3: frequency 'often'"):
        presets.company_shares([ROWS[0], listed("https://leetcode.com/problems/x", "often", "Trie")], CATALOG, ORDER)


def test_build_rows_repeat_each_companys_columns(monkeypatch):
    monkeypatch.setattr(c, "COMPANY_MIN_PROBLEMS", 2)
    rows = presets.build_rows({"beta": ROWS[4:], "Acme": ROWS[:2], "Tiny": ROWS[:1]}, CATALOG, ORDER, "2026-10-20")
    # Tiny's list is too short, so it is listed with no shares, and beta's one counted row
    # (problem f) gives two patterns.
    assert rows == [
        {"company": "Acme", "problems": 2, "counted": 2, "catalog_share": "62.5", "snapshot": "2026-10-20",
         "pattern": "Arrays and Hashing", "share": "62.5"},
        {"company": "Acme", "problems": 2, "counted": 2, "catalog_share": "62.5", "snapshot": "2026-10-20",
         "pattern": "Sliding Window", "share": "37.5"},
        {"company": "beta", "problems": 2, "counted": 1, "catalog_share": "0.0", "snapshot": "2026-10-20",
         "pattern": "Arrays and Hashing", "share": "50.0"},
        {"company": "beta", "problems": 2, "counted": 1, "catalog_share": "0.0", "snapshot": "2026-10-20",
         "pattern": "Math", "share": "50.0"},
        {"company": "Tiny", "problems": 1, "counted": "", "catalog_share": "", "snapshot": "2026-10-20",
         "pattern": "", "share": ""},
    ]


def test_a_company_with_nothing_counted_is_listed_without_shares(monkeypatch):
    monkeypatch.setattr(c, "COMPANY_MIN_PROBLEMS", 1)
    rows = presets.build_rows({"Acme": ROWS[4:5], "Empty": []}, CATALOG, ORDER, "2026-10-20")
    assert [(r["company"], r["problems"], r["pattern"]) for r in rows] == [("Acme", 1, "")]  # Empty has no problems.


# --- The preset ---

def company(shares, **extra):
    return {"company": "Acme", "problems": 40, "counted": 38, "catalog_share": 60.0, "snapshot": "2026-10-20",
            "shares": shares, **extra}


def test_a_preset_is_its_top_core_patterns_above_the_minimum(monkeypatch):
    monkeypatch.setattr(c, "COMPANY_PRESET_MAX", 3)
    monkeypatch.setattr(c, "COMPANY_PRESET_MIN_SHARE", 5)
    shares = [("Segment Tree and Fenwick Tree", 30.0), ("Stack", 20.0), ("Heap", 10.0), ("Two Pointers", 10.0),
              ("Trie", 9.0), ("Greedy", 4.9)]
    # The advanced pattern is left out, the tie goes to Two Pointers (first in the pattern list),
    # and the cap of 3 leaves out Trie.
    assert presets.preset(company(shares), CATEGORIES, ORDER) == [("Stack", 20.0), ("Two Pointers", 10.0),
                                                                    ("Heap", 10.0)]
    monkeypatch.setattr(c, "COMPANY_PRESET_MAX", 10)
    assert presets.preset(company(shares), CATEGORIES, ORDER)[-1] == ("Trie", 9.0)  # 4.9 is under 5.


def test_the_form_shows_whole_number_shares_and_the_date():
    view = presets.preset_view(company([("Stack", 20.5), ("Heap", 9.4)]), CATEGORIES, ORDER)
    assert view == {"company": "Acme", "patterns": [["Stack", 21], ["Heap", 9]], "problems": 40,
                    "snapshot": "20 Oct 2026"}
    assert presets.preset_view(company([("Segment Tree and Fenwick Tree", 90.0)]), CATEGORIES, ORDER) is None


def test_the_most_common_patterns_average_each_company_once():
    companies = {
        "a": company([("Stack", 20.1), ("Heap", 10.0)]),
        "b": company([("Stack", 20.0), ("Trie", 5.0)], problems=900),  # Its size does not weigh more.
        "c": company([], problems=4),  # No shares of its own, so not averaged.
    }
    # Stack (20.1 + 20.0) / 2 = 20.05, rounded half up; Heap 10 / 2; Trie 5 / 2.
    assert presets.general(companies, ORDER) == {"companies": 2, "snapshot": "2026-10-20",
                                                 "shares": [("Stack", 20.1), ("Heap", 5.0), ("Trie", 2.5)]}
    assert presets.general_view(presets.general(companies, ORDER), CATEGORIES, ORDER) == {
        "patterns": [["Stack", 20], ["Heap", 5]], "companies": 2, "snapshot": "20 Oct 2026"}  # Trie is under 5%.
    assert presets.general({"c": companies["c"]}, ORDER) is None
    assert presets.general_view(None, CATEGORIES, ORDER) is None
    assert presets.fallback_view(companies["c"]) == {"company": "Acme", "problems": 4, "general": True}


# --- The data file ---

def file_row(name="Acme", pattern="Stack", share="20.0", **extra):
    return {"company": name, "problems": "40", "counted": "38", "catalog_share": "60.0", "snapshot": "2026-10-20",
            "pattern": pattern, "share": share, **extra}


def listed_row(name, problems="4"):
    return file_row(name, pattern="", share="", counted="", catalog_share="", problems=problems)


def test_reading_the_file_and_finding_companies():
    companies = presets.parse_companies([file_row(), file_row(pattern="Heap", share="10.0"),
                                         file_row("Meta"), file_row("tcs")], CATEGORIES)
    acme = presets.find(companies, "  ACME ")
    assert acme["shares"] == [("Stack", 20.0), ("Heap", 10.0)] and acme["problems"] == 40
    assert presets.find(companies, "Facebook")["company"] == "Meta"  # An alias.
    assert presets.find(companies, "TCS")["company"] == "TCS"  # Shown as it is written, not in lowercase.
    assert presets.find(companies, "Initech") is None and presets.find(companies, "") is None
    assert presets.lookup_names(companies) == {"acme": "acme", "meta": "meta", "tcs": "tcs", "facebook": "meta",
                                               "tata consultancy services": "tcs"}


def test_a_company_with_no_pattern_is_read_without_shares():
    companies = presets.parse_companies([file_row(), listed_row("hubspot"), listed_row("Tiny", "1")], CATEGORIES)
    assert presets.find(companies, "HubSpot") == {"company": "HubSpot", "problems": 4, "counted": None,
                                                  "catalog_share": None, "snapshot": "2026-10-20", "shares": []}
    assert presets.find(companies, "tiny")["problems"] == 1


def test_a_company_with_no_pattern_has_one_row_and_no_numbers_but_its_problems():
    rows = [listed_row("Tiny"), file_row("Tiny"), file_row("Beta"), listed_row("Beta"),
            listed_row("Gamma", problems="x"), file_row("Delta", pattern="", share="5.0")]
    with pytest.raises(DataFileError) as caught:
        presets.parse_companies(rows, CATEGORIES)
    assert caught.value.messages == [
        "row 3: Tiny has a row with no pattern and other rows",
        "row 5: Beta has a row with no pattern and other rows",
        "row 6: problems must be a whole number",
        "row 7: a row with no pattern has no counted, catalog_share, or share",
    ]


def test_an_invalid_file_is_refused_with_every_problem():
    rows = [file_row(), file_row("Beta"), file_row(pattern="Heap"),
            file_row("Gamma", pattern="Juggling", share="0", snapshot="Oct 2026", problems="x"),
            file_row("Beta", pattern="Stack"), file_row("Beta", pattern="Heap", counted="39")]
    with pytest.raises(DataFileError) as caught:
        presets.parse_companies(rows, CATEGORIES)
    messages = caught.value.messages
    assert messages[0] == "row 4: Acme's rows are not next to each other"
    assert messages[1].startswith("row 5: problems and counted must be whole numbers")
    assert "share must be a percentage above 0" in messages[1] and "snapshot must be a date" in messages[1]
    assert "unknown pattern 'Juggling'" in messages[1]
    assert messages[2] == "row 6: Beta's rows are not next to each other"  # Gamma came between.
    assert len(messages) == 4 and "row 7" in messages[3]


def test_the_shipped_file_loads_and_every_company_has_patterns_to_fill_in():
    companies = catalog.load_companies(catalog.DATA_DIR / "patterns.csv", catalog.DATA_DIR / "companies.csv")
    assert len(companies) >= 1
    for entry in companies.values():
        if entry["shares"]:
            assert entry["problems"] >= c.COMPANY_MIN_PROBLEMS
            assert presets.preset(entry, CATEGORIES, ORDER), entry["company"]
            assert abs(sum(share for _, share in entry["shares"]) - 100) < 1, entry["company"]
        else:
            assert entry["problems"] >= 1, entry["company"]
    assert presets.preset(presets.general(companies, ORDER), CATEGORIES, ORDER)


def test_the_doc_lists_what_the_shipped_file_holds():
    companies = catalog.load_companies(catalog.DATA_DIR / "patterns.csv", catalog.DATA_DIR / "companies.csv")
    doc = (ROOT / "docs" / "companies.md").read_text(encoding="utf-8")
    expected = presets.to_markdown(companies, CATEGORIES, ORDER, {})
    # Everything but the list of unmapped topics, which needs the snapshot itself.
    assert doc.split("**Topics that map to nothing**")[0] == expected.split("**Topics that map to nothing**")[0]


def test_the_build_command_reads_a_local_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "COMPANY_MIN_PROBLEMS", 2)
    snapshot = tmp_path / "snapshot"
    for name, rows in {"Acme": ROWS[:2], "Tiny": ROWS[:1]}.items():
        (snapshot / name).mkdir(parents=True)
        with open(snapshot / name / "5. All.csv", "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(ROWS[0]))
            writer.writeheader()
            writer.writerows(rows)
    (snapshot / "README.md").write_text("Not a company.", encoding="utf-8")
    catalog_csv = tmp_path / "catalog.csv"
    catalog_csv.write_text("title,link,difficulty,rating,source,patterns\n"
                           "Two Sum,https://leetcode.com/problems/two-sum/,easy,,Test,Arrays and Hashing\n",
                           encoding="utf-8")
    out, doc = tmp_path / "companies.csv", tmp_path / "companies.md"
    count = catalog.write_companies(snapshot, "2026-10-20", catalog.DATA_DIR / "patterns.csv", catalog_csv, out, doc)
    assert count == 2
    assert [(r["company"], r["problems"], r["pattern"], r["share"]) for r in catalog.read_rows(out)] == [
        ("Acme", "2", "Arrays and Hashing", "62.5"), ("Acme", "2", "Sliding Window", "37.5"), ("Tiny", "1", "", "")]
    text = doc.read_text(encoding="utf-8")
    assert "| Acme | 2 | 2 | 62.5% | Arrays and Hashing 63%, Sliding Window 38% |" in text
    assert "fills in these instead: Arrays and Hashing 63%, Sliding Window 38%." in text  # Acme's alone.
    assert "with how many problems each has:\n\nTiny (1)\n" in text
    assert "Array (1)" in text  # Acme's unmapped topics; Tiny's list is too short to count.


# --- The interview form ---

PRESETS_CSV = [
    file_row("Acme Corp", "Two Pointers", "30.0"),
    file_row("Acme Corp", "Stack", "25.0"),
    file_row("Acme Corp", "Segment Tree and Fenwick Tree", "20.0"),  # Advanced, so not filled in.
    file_row("Acme Corp", "Heap", "4.0"),  # Under the minimum share.
    file_row("Meta", "Tree Traversal", "50.0", problems="1396", counted="1233"),
    listed_row("Tiny Co", problems="1"),
]
# The most common patterns, averaged over Acme Corp and Meta: Tree Traversal 25, Two Pointers 15,
# Stack 12.5 (shown as 13), Segment Tree and Fenwick Tree 10 (advanced), Heap 2.


@pytest.fixture
def preset_app(catalog_path, tmp_path):
    # Its own database, so a test can compare it with the default app's.
    db_path = str(tmp_path / "presets.sqlite")
    path = tmp_path / "companies.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=presets.HEADER)
        writer.writeheader()
        writer.writerows(PRESETS_CSV)
    return create_app({"TESTING": True, "DATABASE": db_path, "CATALOG_PATH": catalog_path, "RESERVE_PATH": None,
                       "UNMAPPED_PATH": None, "COMPANIES_PATH": str(path)})


@pytest.fixture
def preset_client(preset_app):
    return preset_app.test_client()


def interviews(app):
    with app.app_context():
        return [dict(i) for i in queries.interviews(get_db())]


def checked(page):
    return re.findall(r'<input type="checkbox" name="patterns" value="([^"]+)" checked>', page)


def test_the_form_offers_the_presets(preset_client):
    page = preset_client.get("/interviews").get_data(as_text=True)
    # A search list like the problem picker's, not the browser's own suggestions.
    assert '<input name="company" id="company-search" value="" autocomplete="off"' in page
    assert 'role="combobox"' in page and '<ul id="company-results" class="picker-results" role="listbox"' in page
    assert "datalist" not in page
    data = json.loads(html.unescape(re.search(r'data-presets="([^"]+)"', page).group(1)))
    assert data["names"] == {"acme corp": 0, "meta": 1, "facebook": 1, "tiny co": 2}
    assert data["presets"][0] == {"company": "Acme Corp", "patterns": [["Two Pointers", 30], ["Stack", 25]],
                                  "problems": 40, "snapshot": "20 Oct 2026"}
    assert data["presets"][2] == {"company": "Tiny Co", "problems": 1, "general": True}
    assert data["general"] == {"patterns": [["Tree Traversal", 25], ["Two Pointers", 15], ["Stack", 13]],
                               "companies": 2, "snapshot": "20 Oct 2026"}
    assert "Presets for 2 companies, and the most common patterns for 1 more, from LeetCode" in page
    assert 'name="fill_preset"' in page and "js/company_preset.js" in page
    # Enter in a field still adds the interview: that button comes first.
    assert page.index('class="visually-hidden" tabindex="-1" aria-hidden="true">Add interview') < page.index("fill_preset")


def test_filling_in_without_javascript_checks_exactly_the_preset(preset_client, preset_app):
    form = {"company": "  acme CORP ", "date": "2030-01-02", "daily_target": "4", "target_difficulty": "hard",
            "patterns": ["Heap", "Greedy"], "fill_preset": "1"}
    response = preset_client.post("/interviews", data=form)
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert checked(page) == ["Two Pointers", "Stack"]  # Heap and Greedy are unchecked.
    assert "Filled in 2 patterns for Acme Corp. Nothing is saved until you add the interview." in page
    assert 'value="  acme CORP "' in page and 'value="2030-01-02"' in page and 'value="4"' in page
    assert '<option value="hard" selected>' in page
    assert "Fill in patterns for Acme Corp</button>" in page
    assert "Two Pointers 30%, Stack 25%. From LeetCode's company tags: 40 problems, snapshot of 20 Oct 2026." in page
    assert '<details class="add-interview" open>' in page
    assert interviews(preset_app) == []


def test_filling_in_by_an_alias(preset_client, preset_app):
    page = preset_client.post("/interviews", data={"company": "Facebook", "fill_preset": "1"}).get_data(as_text=True)
    assert checked(page) == ["Tree Traversal"] and "Filled in 1 pattern for Meta." in page
    assert "1,396 problems" in page
    assert interviews(preset_app) == []


def test_a_company_with_too_few_problems_fills_in_the_most_common_patterns(preset_client, preset_app):
    form = {"company": "tiny co", "date": "2030-01-02", "patterns": ["Heap"], "fill_preset": "1"}
    page = preset_client.post("/interviews", data=form).get_data(as_text=True)
    assert checked(page) == ["Two Pointers", "Stack", "Tree Traversal"]  # In pattern-list order on the form.
    assert ("Filled in the most common patterns across companies. Nothing is saved until you add the interview."
            in page)
    assert "Fill in the most common patterns</button>" in page
    assert ("Tiny Co has only 1 problem in LeetCode's company tags, too few for its own preset. These are the most "
            "common patterns across the 2 companies that have one: Tree Traversal 25%, Two Pointers 15%, Stack 13%. "
            "Snapshot of 20 Oct 2026.") in page
    assert interviews(preset_app) == []


def test_without_common_patterns_a_company_with_too_few_problems_is_not_listed(db_path, catalog_path, tmp_path):
    path = tmp_path / "companies.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=presets.HEADER)
        writer.writeheader()
        writer.writerow(listed_row("Tiny Co"))
    app = create_app({"TESTING": True, "DATABASE": db_path, "CATALOG_PATH": catalog_path, "RESERVE_PATH": None,
                      "UNMAPPED_PATH": None, "COMPANIES_PATH": str(path)})
    page = app.test_client().get("/interviews").get_data(as_text=True)
    assert "fill_preset" not in page and '<input name="company" value="" >' in page


def test_a_company_without_a_preset_keeps_its_patterns(preset_client, preset_app):
    page = preset_client.post("/interviews", data={"company": "Initech", "patterns": ["Heap"], "fill_preset": "1"})
    page = page.get_data(as_text=True)
    assert checked(page) == ["Heap"] and "There is no preset for Initech. Choose its patterns below." in page
    page = preset_client.post("/interviews", data={"company": " ", "fill_preset": "1"}).get_data(as_text=True)
    assert "Enter a company name first" in page and "Enter the company name." not in page
    # Saving it works as before.
    assert preset_client.post("/interviews", data={"company": "Initech", "date": "2030-01-02",
                                                   "patterns": ["Heap"]}).status_code == 302
    assert [(i["company"], i["patterns"]) for i in interviews(preset_app)] == [("Initech", ["Heap"])]


def test_filling_in_while_editing_saves_nothing(preset_client, preset_app):
    preset_client.post("/interviews", data={"company": "Acme Corp", "date": "2030-01-02", "patterns": ["Heap"]})
    before = interviews(preset_app)
    interview_id = before[0]["id"]
    page = preset_client.get(f"/interviews/{interview_id}/edit").get_data(as_text=True)
    assert "Fill in patterns for Acme Corp</button>" in page  # Offered for the company already entered.
    response = preset_client.post(f"/interviews/{interview_id}/edit",
                                  data={"company": "Acme Corp", "date": "2030-01-02", "patterns": ["Heap"],
                                        "fill_preset": "1"})
    page = response.get_data(as_text=True)
    assert checked(page) == ["Two Pointers", "Stack"]
    assert "Nothing is saved until you save the changes." in page
    assert interviews(preset_app) == before


def test_an_interview_saved_from_a_preset_is_an_ordinary_interview(preset_client, preset_app, client, app):
    page = preset_client.post("/interviews", data={"company": "Acme Corp", "fill_preset": "1"}).get_data(as_text=True)
    filled = checked(page)
    for each in (preset_client, client):
        each.post("/interviews", data={"company": "Acme Corp", "date": "2030-01-02", "patterns": filled})
    from_preset, by_hand = interviews(preset_app), interviews(app)
    for row in from_preset + by_hand:
        row.pop("id")
    assert from_preset == by_hand and from_preset[0]["patterns"] == ["Two Pointers", "Stack"]
    assert (preset_client.get("/").get_data(as_text=True).count("Two Pointers")
            == client.get("/").get_data(as_text=True).count("Two Pointers"))


def test_with_no_presets_the_form_is_as_before(db_path, catalog_path, tmp_path):
    app = create_app({"TESTING": True, "DATABASE": db_path, "CATALOG_PATH": catalog_path, "RESERVE_PATH": None,
                      "UNMAPPED_PATH": None, "COMPANIES_PATH": str(tmp_path / "missing.csv")})
    page = app.test_client().get("/interviews").get_data(as_text=True)
    assert "fill_preset" not in page and "company-results" not in page and "visually-hidden" not in page
    assert '<input name="company" value="" >' in page


def test_help_explains_presets_with_the_rules_values(preset_client, monkeypatch):
    monkeypatch.setattr(c, "COMPANY_PRESET_MAX", 4)
    page = " ".join(preset_client.get("/help").get_data(as_text=True).split())
    assert '<a href="#presets">Company presets</a>' in page
    assert "Presets cover 2 companies, each with at least 25 problems" in page
    assert ("The other company in the snapshot has too few problems to say what it asks, so it fills in the most "
            "common patterns instead") in page
    assert "up to 4 core patterns with a share of at least 5%" in page
    assert "Nothing is saved until you save the interview" in page


def test_the_form_builds_the_preset_views_once(preset_client, preset_app, monkeypatch):
    built = []
    real = views._build_company_presets
    monkeypatch.setattr(views, "_build_company_presets", lambda conn: built.append(1) or real(conn))
    for _ in range(2):
        assert preset_client.get("/interviews").status_code == 200
    assert preset_client.get("/help").status_code == 200
    assert built == [1]
