"""Filtering the History and Sync lists."""
from datetime import date, timedelta

from codecompass.core import constants as c
from codecompass.core import filters
from codecompass.db import get_db

PARENS = "Valid Parentheses (Test list)"  # Easy, Stack.
TEMPS = "Daily Temperatures (Test list)"  # Medium, Monotonic Stack and Queue; Stack.
COURSES = "Course Schedule (Codeforces)"  # Medium, Topological Sort.


def ago(days):
    return (date.today() - timedelta(days=days)).isoformat()


def log(client, problem, days_ago, outcome=c.SOLVED_ALONE):
    response = client.post("/log", data={"problem": problem, "date": ago(days_ago), "outcome": outcome,
                                         "time_minutes": "", "time_seconds": "", "notes": ""})
    assert response.status_code == 302


def titles(client, query=""):
    page = client.get("/history" + query).get_data(as_text=True)
    if '<div class="table-wrap log">' not in page:
        return page, []
    table = page.split('<div class="table-wrap log">', 1)[1]
    return page, [cell.split(">", 1)[1].split("<", 1)[0]
                  for cell in table.split('<td class="problem-cell">')[1:]]


# --- Plain rules ---

def test_unknown_filters_are_dropped():
    args = {"outcome": "nonsense", "difficulty": "hard", "site": "Mars", "pattern": "Stack", "start": "2026-02-30",
            "end": "2026-03-01", "reviews": "yes", "method": "csv"}
    assert filters.read_history(args, {"LeetCode"}, {"Stack"}) == {
        "difficulty": "hard", "pattern": "Stack", "end": "2026-03-01", "method": "csv"}
    assert filters.read_sync({"verdict": "ac", "new": "maybe", "needs": "no"}, set(), set()) == {
        "verdict": "ac", "needs": "no"}


def test_history_match():
    row = {"outcome": c.NOT_SOLVED, "difficulty": "easy", "site": "LeetCode", "patterns": ["Stack"],
           "date": "2026-03-04", "review": False, "entry_method": "sync"}
    assert filters.history_match(row, {})
    assert filters.history_match(row, {"outcome": c.NOT_SOLVED, "pattern": "Stack", "method": "sync",
                                       "start": "2026-03-04", "end": "2026-03-04"})
    assert not filters.history_match(row, {"reviews": "1"})
    assert not filters.history_match(row, {"start": "2026-03-05"})
    assert not filters.history_match(row, {"difficulty": "medium"})


def test_sync_match():
    item = {"accepted": False, "difficulty": None, "site": "Codeforces", "patterns": [], "new": True,
            "needs": True, "date": "2026-10-20"}
    assert filters.sync_match(item, {"verdict": "wa", "new": "new", "needs": "yes", "site": "Codeforces"})
    assert not filters.sync_match(item, {"verdict": "ac"})
    assert not filters.sync_match(item, {"difficulty": "easy"})  # A level not known yet matches no level.


# --- History ---

def test_history_filters_by_outcome_difficulty_pattern_and_how_it_was_logged(client):
    log(client, PARENS, 3, c.NOT_SOLVED)
    log(client, TEMPS, 2)
    log(client, COURSES, 1, c.SOLVED_WITH_HINTS)
    page, everything = titles(client)
    assert everything == ["Course Schedule", "Daily Temperatures", "Valid Parentheses"]
    assert 'name="outcome"' in page and "js/filters.js" in page and "Clear filters" not in page
    _, not_solved = titles(client, f"?outcome={c.NOT_SOLVED}")
    assert not_solved == ["Valid Parentheses"]
    page, medium = titles(client, "?difficulty=medium")
    assert medium == ["Course Schedule", "Daily Temperatures"]
    assert "2 of 3 attempts match" in page and "Clear filters" in page
    assert titles(client, "?pattern=Stack")[1] == ["Daily Temperatures", "Valid Parentheses"]
    assert titles(client, "?method=csv")[1] == []
    assert "No attempts match these filters." in titles(client, "?method=csv")[0]
    assert titles(client, f"?start={ago(2)}&end={ago(2)}")[1] == ["Daily Temperatures"]
    # The test catalog's links all go to example.com.
    assert titles(client, "?site=example.com")[1] == everything


def test_history_reviews_only(client, app):
    log(client, PARENS, 30)  # Due 16 days ago.
    client.get("/")  # Chooses its sibling.
    log(client, PARENS, 0)  # Done on the problem itself, this completes the review.
    log(client, COURSES, 0)
    assert titles(client, "?reviews=1")[1] == ["Valid Parentheses"]


def test_filters_leave_the_calendar_whole(client):
    log(client, PARENS, 3, c.NOT_SOLVED)
    page = client.get(f"/history?outcome={c.NOT_SOLVED}").get_data(as_text=True)
    assert f'<option value="{c.NOT_SOLVED}" selected>' in page
    # The calendar still counts every attempt; filters apply to the list only.
    assert "<dt>Attempts</dt><dd>1</dd>" in page
