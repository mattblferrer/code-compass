"""Finding a problem to log: title search, and site and ID (R-38)."""
import csv
from urllib.parse import quote

import pytest

from codecompass import create_app
from codecompass.core import constants as c
from codecompass.core.problem_refs import from_id, from_link, short_id
from codecompass.db import get_db

CF = "https://codeforces.com/problemset/problem/1520/A"


@pytest.mark.parametrize("site, text, link", [
    ("codeforces", "1520A", CF),
    ("codeforces", "1520 a", CF),
    ("codeforces", "1520/A", CF),
    ("codeforces", "1662F1", "https://codeforces.com/problemset/problem/1662/F1"),
    ("codeforces", "https://codeforces.com/contest/1520/problem/A", CF),
    ("codeforces", "codeforces.com/problemset/problem/1520/A?locale=en", CF),
    ("cses", "1068", "https://cses.fi/problemset/task/1068"),
    ("cses", "https://cses.fi/problemset/view/1068/", "https://cses.fi/problemset/task/1068"),
    ("leetcode", "Two-Sum", "https://leetcode.com/problems/two-sum/"),
    ("leetcode", "https://leetcode.com/problems/two-sum/description/", "https://leetcode.com/problems/two-sum/"),
    ("atcoder", "abc300_a", "https://atcoder.jp/contests/abc300/tasks/abc300_a"),
    # A pasted link to another site is still understood.
    ("cses", "https://leetcode.com/problems/two-sum/", "https://leetcode.com/problems/two-sum/"),
])
def test_ids_and_links_become_stored_links(site, text, link):
    assert from_id(site, text) == link


@pytest.mark.parametrize("site, text", [
    ("codeforces", "A1520"), ("cses", "12a"), ("leetcode", "two sum"), ("atcoder", "abc300"),
    ("codeforces", ""), ("nowhere", "1"), ("codeforces", "https://example.com/1520/A"),
])
def test_bad_ids_are_rejected(site, text):
    assert from_id(site, text) is None


def test_short_ids():
    assert short_id(CF) == "Codeforces 1520A"
    assert short_id("https://cses.fi/problemset/task/1068") == "CSES 1068"
    assert from_link("https://example.com/x") is None


# --- The logging form ---

RESERVE = [
    ["Treasure Hunt", "https://codeforces.com/problemset/problem/1/A", "easy", "800", "Codeforces API", "Greedy"],
    ["Treasure Hunt", "https://codeforces.com/problemset/problem/2/A", "medium", "1300", "Codeforces API", "Greedy"],
    ["Two Sum Again", "https://codeforces.com/problemset/problem/3/A", "easy", "800", "Codeforces API", "Greedy"],
]


# Codeforces problems the reserve cannot hold (no mappable tag, or no rating).
UNMAPPED = [
    ["Untagged Puzzle", "https://codeforces.com/problemset/problem/4/B", "hard"],
    ["Brand New", "https://codeforces.com/problemset/problem/5/C", ""],
]


@pytest.fixture
def reserve_app(db_path, catalog_path, tmp_path):
    path = tmp_path / "reserve.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["title", "link", "difficulty", "rating", "source", "patterns"])
        writer.writerows(RESERVE)
    unmapped = tmp_path / "unmapped.csv"
    with open(unmapped, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["title", "link", "difficulty"])
        writer.writerows(UNMAPPED)
    return create_app({"TESTING": True, "DATABASE": db_path, "CATALOG_PATH": catalog_path,
                       "RESERVE_PATH": str(path), "UNMAPPED_PATH": str(unmapped)})


@pytest.fixture
def rclient(reserve_app):
    return reserve_app.test_client()


def logged(app):
    with app.app_context():
        return [dict(r) for r in get_db().execute(
            "SELECT p.title, p.link FROM attempts a JOIN problems p ON p.id = a.problem_id ORDER BY a.id"
        )]


def log(client, **fields):
    data = {"date": "2026-11-01", "outcome": c.SOLVED_ALONE, "time_minutes": "", "notes": ""}
    data.update(fields)
    return client.post("/log", data=data)


def test_search_puts_catalog_before_reserve_and_prefix_first(rclient):
    labels = [r["label"] for r in rclient.get("/problems/search?q=two sum").get_json()]
    assert labels == ["Two Sum (Test list)", "Two Sum Again (Codeforces 3A)"]
    results = rclient.get("/problems/search?q=hunt").get_json()
    assert [r["label"] for r in results] == ["Treasure Hunt (Codeforces 1A)", "Treasure Hunt (Codeforces 2A)"]
    assert all(r["reserve"] for r in results)


def test_search_by_pasted_link(rclient):
    results = rclient.get("/problems/search?q=" + quote("https://codeforces.com/contest/2/problem/A")).get_json()
    assert [r["label"] for r in results] == ["Treasure Hunt (Codeforces 2A)"]


def test_log_by_chosen_search_result(rclient, reserve_app):
    result = rclient.get("/problems/search?q=hunt").get_json()[1]
    assert log(rclient, problem=result["label"], problem_id=str(result["id"])).status_code == 302
    assert logged(reserve_app) == [{"title": "Treasure Hunt", "link": "https://codeforces.com/problemset/problem/2/A"}]


def test_log_by_typed_label_or_unique_title(rclient, reserve_app):
    assert log(rclient, problem="Treasure Hunt (Codeforces 1A)").status_code == 302
    assert log(rclient, problem="two sum again").status_code == 302
    assert [r["link"][-3:] for r in logged(reserve_app)] == ["1/A", "3/A"]


def test_shared_title_asks_to_choose(rclient, reserve_app):
    response = log(rclient, problem="Treasure Hunt")
    assert response.status_code == 400
    assert "Several problems have that title" in response.get_data(as_text=True)
    assert logged(reserve_app) == []


def test_log_by_site_and_id(rclient, reserve_app):
    assert log(rclient, problem="", site="codeforces", ref="2A").status_code == 302
    assert logged(reserve_app)[0]["link"] == "https://codeforces.com/problemset/problem/2/A"


def test_site_and_id_wins_over_typed_title(rclient, reserve_app):
    assert log(rclient, problem="Two Sum (Test list)", site="codeforces", ref="1A").status_code == 302
    assert logged(reserve_app)[0]["link"].endswith("/1/A")


def test_unknown_id_offers_custom_problem_with_link(rclient, reserve_app):
    response = log(rclient, problem="", site="codeforces", ref="9999Z")
    page = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "not in CodeCompass yet" in page
    assert "/problems/new?link=https%3A%2F%2Fcodeforces.com%2Fproblemset%2Fproblem%2F9999%2FZ" in page
    assert logged(reserve_app) == []


def test_unmapped_codeforces_problem_fills_in_the_custom_form(rclient, reserve_app):
    link = quote("https://codeforces.com/problemset/problem/4/B", safe="")
    expected = f"/problems/new?link={link}&title=Untagged+Puzzle&difficulty=hard"
    found = rclient.get("/problems/find?site=codeforces&ref=4B").get_json()
    assert found["problem"] is None
    assert "do not map to a pattern or level" in found["message"]
    assert found["custom_url"] == expected
    # The same offer for the ID typed into the form, the exact title, or a pasted link.
    for fields in ({"problem": "", "site": "codeforces", "ref": "4B"}, {"problem": "untagged puzzle"},
                   {"problem": "https://codeforces.com/contest/4/problem/B"}):
        page = log(rclient, **fields).get_data(as_text=True)
        assert expected.replace("&", "&amp;") in page, fields
    assert logged(reserve_app) == []


def test_unrated_unmapped_problem_leaves_the_level_blank(rclient):
    found = rclient.get("/problems/find?site=codeforces&ref=5C").get_json()
    assert found["custom_url"].endswith("&title=Brand+New")
    page = rclient.get(found["custom_url"]).get_data(as_text=True)
    assert 'value="Brand New"' in page and "selected" not in page


def test_custom_form_prefills_a_valid_level_only(rclient):
    assert '<option value="hard" selected>' in rclient.get("/problems/new?difficulty=hard").get_data(as_text=True)
    assert "selected" not in rclient.get("/problems/new?difficulty=impossible").get_data(as_text=True)


def test_badly_formed_id_names_the_expected_form(rclient):
    page = log(rclient, problem="", site="cses", ref="abc").get_data(as_text=True)
    assert "the task number, such as 1068" in page


def test_other_site_points_to_custom_problem(rclient):
    page = log(rclient, problem="", site="other", ref="").get_data(as_text=True)
    assert "logged as custom problems" in page
    assert 'href="/problems/new"' in page


def test_find_endpoint(rclient):
    found = rclient.get("/problems/find?site=codeforces&ref=1A").get_json()
    assert found["problem"]["label"] == "Treasure Hunt (Codeforces 1A)"
    missing = rclient.get("/problems/find?site=cses&ref=1068").get_json()
    assert missing["problem"] is None
    assert missing["custom_url"] == "/problems/new?link=https%3A%2F%2Fcses.fi%2Fproblemset%2Ftask%2F1068"


def test_custom_problem_form_prefills_link_and_stores_it_in_site_form(rclient, reserve_app):
    page = rclient.get("/problems/new?link=" + quote("https://cses.fi/problemset/task/1068")).get_data(as_text=True)
    assert 'value="https://cses.fi/problemset/task/1068"' in page
    response = rclient.post("/problems/new", data={
        "title": "Weird Algorithm", "link": "https://cses.fi/problemset/view/1068",
        "difficulty": "easy", "patterns": ["Simulation and Implementation"],
    })
    assert response.status_code == 302
    found = rclient.get("/problems/find?site=cses&ref=1068").get_json()
    assert found["problem"]["label"] == "Weird Algorithm (custom)"


def test_edit_form_keeps_the_chosen_problem(rclient, reserve_app):
    log(rclient, problem="", site="codeforces", ref="2A")
    with reserve_app.app_context():
        attempt_id = get_db().execute("SELECT id FROM attempts").fetchone()["id"]
    page = rclient.get(f"/attempts/{attempt_id}/edit").get_data(as_text=True)
    assert 'value="Treasure Hunt (Codeforces 2A)"' in page
    response = rclient.post(f"/attempts/{attempt_id}/edit", data={
        "problem": "Treasure Hunt (Codeforces 2A)", "date": "2026-11-02", "outcome": c.NOT_SOLVED,
        "time_minutes": "", "notes": "",
    })
    assert response.status_code == 302
    assert logged(reserve_app)[0]["link"].endswith("/2/A")


def test_problem_picked_by_title_wins_over_a_leftover_other_site(rclient, reserve_app):
    # The user chose "Other", then picked a problem from the title search instead.
    result = rclient.get("/problems/search?q=hunt").get_json()[0]
    response = log(rclient, problem=result["label"], problem_id=str(result["id"]), site="other", ref="")
    assert response.status_code == 302
    assert logged(reserve_app) == [{"title": "Treasure Hunt", "link": "https://codeforces.com/problemset/problem/1/A"}]
    # With nothing picked, "Other" still points to a custom problem.
    page = log(rclient, problem="", site="other").get_data(as_text=True)
    assert "custom problems" in page


@pytest.mark.parametrize("text", ["https://atcoder.jp/contests/abc042/tasks/arc058_a",
                                  "https://atcoder.jp/contests/arc058/tasks/arc058_a"])
def test_shared_atcoder_task_has_one_link(text):
    # ABC042 C is ARC058 A: it is stored under the contest its task ID names.
    assert from_link(text) == ("atcoder", "https://atcoder.jp/contests/arc058/tasks/arc058_a")
    assert from_id("atcoder", "arc058_a") == "https://atcoder.jp/contests/arc058/tasks/arc058_a"
    # Other contests keep their own name, even when the task ID is spelled differently.
    assert from_link("https://atcoder.jp/contests/tessoku-book/tasks/tessoku_book_a")[1] == \
        "https://atcoder.jp/contests/tessoku-book/tasks/tessoku_book_a"
