"""CSV export and import of attempts (R-19, R-20)."""
import csv
import io
import random

import pytest

from codecompass import create_app, queries
from codecompass.core import constants as c
from codecompass.core.exchange import COLUMNS
from codecompass.db import get_db
from conftest import app_db

OUTCOMES = [c.SOLVED_ALONE, c.SOLVED_WITH_HINTS, c.SOLVED_AFTER_SOLUTION, c.NOT_SOLVED]
NOTES = ["", "", "Off by one, then fixed", 'Used "two pointers", finally', "line one\nline two", "a, b; c"]


def make_csv(rows, columns=COLUMNS):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in columns})
    return out.getvalue()


def upload(client, text, name="attempts.csv"):
    data = {"file": (io.BytesIO(text.encode("utf-8")), name)}
    return client.post("/import", data=data, content_type="multipart/form-data")


def records(app):
    """Attempts as comparable records, naming problems by title rather than id."""
    conn = app_db(app)
    try:
        return [tuple(r) for r in conn.execute(
            """SELECT a.date, p.title, p.link, p.is_custom, a.outcome, a.time_seconds, a.notes, r.title
               FROM attempts a JOIN problems p ON p.id = a.problem_id
               LEFT JOIN problems r ON r.id = a.review_of_problem_id ORDER BY a.id"""
        )]
    finally:
        conn.close()


def seed_reference_attempts(app, count=100):
    """100 reference attempts over the test catalog and two custom problems."""
    rng = random.Random(19)
    with app.app_context():
        conn = get_db()
        queries.add_custom_problem(conn, {"title": "Spreadsheet Puzzle", "link": None, "difficulty": "hard",
                                          "patterns": ["Greedy", "Sorting"]})
        queries.add_custom_problem(conn, {"title": "Island Walk", "link": "https://example.org/island",
                                          "difficulty": "very hard", "patterns": ["Graph Traversal", "Tree DP"]})
        ids = [r["id"] for r in conn.execute("SELECT id FROM problems ORDER BY id")]
        with conn:
            for i in range(count):
                problem = rng.choice(ids)
                review_of = rng.choice([p for p in ids if p != problem]) if rng.random() < 0.15 else None
                seconds = rng.choice([None, 60, 90, 1500, 3725, 59 * 60 + 1])
                conn.execute(
                    """INSERT INTO attempts (problem_id, date, outcome, time_seconds, notes, entry_method,
                       review_of_problem_id) VALUES (?, ?, ?, ?, ?, 'manual', ?)""",
                    (problem, f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}", rng.choice(OUTCOMES), seconds,
                     rng.choice(NOTES) or None, review_of),
                )


@pytest.fixture
def empty_app(tmp_path, catalog_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "empty.sqlite"), "CATALOG_PATH": catalog_path,
                       "RESERVE_PATH": None, "UNMAPPED_PATH": None})


def test_round_trip_of_100_attempts_then_reimport_adds_nothing(client, app, db_path, empty_app, tmp_path):
    seed_reference_attempts(app)
    response = client.get("/attempts.csv")
    assert response.mimetype == "text/csv"
    assert "attachment" in response.headers["Content-Disposition"]
    text = response.get_data(as_text=True).lstrip("﻿")
    assert text.splitlines()[0] == ",".join(COLUMNS)

    target = empty_app.test_client()
    page = upload(target, text).get_data(as_text=True)
    assert "Imported 100 of 100 rows." in page
    assert "Created 2 custom problems" in page
    assert records(empty_app) == records(app)

    again = upload(target, text).get_data(as_text=True)
    assert "Imported 0 of 100 rows." in again
    assert again.count("Duplicate of an attempt already saved.") == 100
    assert len(records(empty_app)) == 100


def test_unmatched_rows_create_custom_problems_only_with_difficulty_and_patterns(client, app):
    rows = [
        {"date": "2026-03-01", "title": "New One", "difficulty": "Easy", "patterns": "Stack", "outcome": "Solved alone"},
        {"date": "2026-03-02", "title": "New Two", "link": "https://example.net/two", "difficulty": "Medium",
         "patterns": "Greedy; Sorting", "outcome": "Not solved"},
        {"date": "2026-03-03", "title": "New Three", "difficulty": "Very hard", "patterns": "Tree DP",
         "outcome": "Solved with hints", "time_minutes": "25"},
        {"date": "2026-03-04", "title": "No Details", "outcome": "Solved alone"},
        {"date": "2026-03-05", "title": "Only Difficulty", "difficulty": "Hard", "outcome": "Solved alone"},
    ]
    page = upload(client, make_csv(rows)).get_data(as_text=True)
    assert "Imported 3 of 5 rows." in page
    assert "Created 3 custom problems: New One, New Two, New Three." in page
    assert page.count("add difficulty and patterns to create it as a custom problem") == 2
    with app.app_context():
        created = {r["title"]: (r["difficulty"], r["is_custom"]) for r in get_db().execute(
            "SELECT title, difficulty, is_custom FROM problems WHERE is_custom = 1")}
    assert created == {"New One": ("easy", 1), "New Two": ("medium", 1), "New Three": ("very hard", 1)}


def test_ten_rows_with_three_invalid(client, app):
    good = {"title": "two sum", "outcome": "Solved alone"}
    rows = [{"date": f"2026-02-0{i}", **good} for i in range(1, 8)]
    rows.insert(2, {"date": "2026-02-30", **good})                             # Row 4: impossible date.
    rows.insert(5, {"date": "2026-02-10", "title": "Two Sum", "outcome": "Great"})  # Row 7: bad outcome.
    rows.insert(8, {"date": "2026-02-11", "title": "Two Sum", "outcome": "Solved alone",
                    "time_minutes": "-5"})                                      # Row 10: bad time.
    page = upload(client, make_csv(rows)).get_data(as_text=True)
    assert "Imported 7 of 10 rows." in page
    skipped = [line for line in page.splitlines() if line.strip().startswith("<tr><td>")]
    assert [s.split("</td>")[0].split("<td>")[1] for s in skipped] == ["4", "7", "10"]
    assert "date: Enter the date as YYYY-MM-DD." in page
    assert "outcome: Choose an outcome." in page
    assert "time_minutes: Enter the time as a positive number of minutes." in page
    assert len(records_for(app)) == 7


def test_link_wins_and_shared_titles_need_a_link(client, app):
    with app.app_context():
        queries.add_custom_problem(get_db(), {"title": "Two Sum", "link": "https://example.org/my-two-sum",
                                              "difficulty": "easy", "patterns": ["Arrays and Hashing"]})
    rows = [
        {"date": "2026-04-01", "title": "Two Sum", "outcome": "Solved alone"},
        {"date": "2026-04-02", "title": "Anything", "link": "https://example.org/my-two-sum", "outcome": "Solved alone"},
    ]
    page = upload(client, make_csv(rows)).get_data(as_text=True)
    assert "Imported 1 of 2 rows." in page
    assert "The title matches more than one problem" in page
    assert [r[2] for r in records_for(app)] == ["https://example.org/my-two-sum"]


def test_review_of_must_match_a_problem(client, app):
    rows = [
        {"date": "2026-05-01", "title": "Two Sum", "outcome": "Solved alone", "review_of": "Valid Parentheses"},
        {"date": "2026-05-02", "title": "Two Sum", "outcome": "Solved alone", "review_of": "Nonexistent"},
    ]
    page = upload(client, make_csv(rows)).get_data(as_text=True)
    assert "Imported 1 of 2 rows." in page
    assert "review_of matches no single problem." in page
    assert records_for(app)[0][7] == "Valid Parentheses"


def test_files_that_cannot_be_read(client):
    page = upload(client, make_csv([{"date": "2026-01-01"}], columns=["date", "name"]))
    assert page.status_code == 400
    assert "The file needs the columns date, title, and outcome." in page.get_data(as_text=True)
    bad = client.post("/import", data={"file": (io.BytesIO(b"\xff\xfe\x00bad"), "x.csv")},
                      content_type="multipart/form-data")
    assert bad.status_code == 400 and "not UTF-8 text" in bad.get_data(as_text=True)
    assert client.post("/import", data={}, content_type="multipart/form-data").status_code == 400


def test_history_links_to_export_and_import(client):
    page = client.get("/history").get_data(as_text=True)
    assert 'href="/attempts.csv"' in page and 'href="/import"' in page


def records_for(app):
    return records(app)


def plan(rows, problems, hinted=frozenset()):
    from codecompass.core.exchange import plan_import

    columns = sorted({k for r in rows for k in r} | {"date", "title", "outcome"})
    full = [{k: r.get(k, "") for k in columns} for r in rows]
    return plan_import(full, columns, problems, [], ["Greedy", "Arrays and Hashing"], "2026-11-10", hinted=hinted)


LEETCODE_TWO_SUM = {1: {"title": "Two Sum", "link": "https://leetcode.com/problems/two-sum/"}}


def test_a_row_with_a_link_never_matches_another_problem_by_title():
    row = {"date": "2026-11-01", "title": "Two Sum", "link": "https://codeforces.com/problemset/problem/1/A",
           "outcome": "Solved alone"}
    # Without the details to create it, it is skipped instead of landing on LeetCode's Two Sum.
    result = plan([row], LEETCODE_TWO_SUM)
    assert result["attempts"] == [] and "No problem matches" in result["skipped"][0][1]
    # With them, it becomes its own custom problem.
    result = plan([{**row, "difficulty": "Easy", "patterns": "Greedy"}], LEETCODE_TWO_SUM)
    assert [p["link"] for p in result["new_problems"]] == ["https://codeforces.com/problemset/problem/1/A"]
    assert result["attempts"][0]["problem"] == result["new_problems"][0]["key"]


def test_rows_with_one_title_and_different_links_make_different_problems():
    rows = [{"date": "2026-11-01", "title": "Foo", "link": f"https://codeforces.com/problemset/problem/{n}/A",
             "difficulty": "Easy", "patterns": "Greedy", "outcome": "Solved alone"} for n in (2, 3)]
    result = plan(rows, {})
    assert len(result["new_problems"]) == 2
    assert len({a["problem"] for a in result["attempts"]}) == 2


def test_a_linked_row_can_still_match_a_problem_saved_without_a_link():
    row = {"date": "2026-11-01", "title": "My puzzle", "link": "https://example.com/puzzle", "outcome": "Not solved"}
    result = plan([row], {7: {"title": "My puzzle", "link": None}})
    assert result["attempts"][0]["problem"] == 7


def test_import_follows_the_hint_rule_like_the_form():
    rows = [{"date": "2026-11-01", "title": "Two Sum", "outcome": "Solved alone"},
            {"date": "2026-11-02", "title": "Two Sum", "outcome": "Solved with hints"},
            {"date": "2026-11-03", "title": "Two Sum", "outcome": "Solved alone"}]
    result = plan(rows, LEETCODE_TWO_SUM, hinted={1})
    assert result["skipped"][0][0] == 2 and "hint was revealed" in result["skipped"][0][1]
    # The first attempt saved uses the hint, so a later "solved alone" is allowed.
    assert [a["outcome"] for a in result["attempts"]] == [c.SOLVED_WITH_HINTS, c.SOLVED_ALONE]


def test_importing_an_attempt_uses_up_a_revealed_hint(client, app):
    with app.app_context():
        problem_id = get_db().execute("SELECT id FROM problems WHERE title = 'Two Sum'").fetchone()[0]
    client.post(f"/problems/{problem_id}/hint")
    page = upload(client, make_csv([{"date": "2026-11-01", "title": "Two Sum", "outcome": "Solved alone"},
                                    {"date": "2026-11-02", "title": "Two Sum", "outcome": "Solved with hints"}]))
    assert "hint was revealed" in page.get_data(as_text=True)
    with app.app_context():
        conn = get_db()
        assert not queries.unused_hint(conn, problem_id)
        assert [r[0] for r in conn.execute("SELECT outcome FROM attempts")] == [c.SOLVED_WITH_HINTS]


def test_import_reads_only_the_problems_the_file_names(app):
    from codecompass.core.exchange import references

    rows = [{"Title": " Two Sum ", "Link": "", "review_of": "https://codeforces.com/contest/1520/problem/A"},
            {"title": "Valid Parentheses", "link": "leetcode.com/problems/valid-parentheses/"}]
    links, titles = references(rows)
    assert links == {"https://codeforces.com/problemset/problem/1520/A",
                     "https://leetcode.com/problems/valid-parentheses/"}
    assert titles == {"two sum", "valid parentheses"}
    with app.app_context():
        found = queries.problems_matching(get_db(), links, titles)
    assert sorted(p["title"] for p in found.values()) == ["Two Sum", "Valid Parentheses"]
    assert all(p["patterns"] for p in found.values())
