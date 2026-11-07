"""Dashboard, reviews, recommendations, hints, and the calendar (R-10 to R-17, R-27 to R-31)."""
from datetime import date, timedelta

import pytest

from codecompass.core import constants as c
from codecompass.core.mastery import pattern_score
from codecompass.core.validation import MESSAGES
from codecompass.db import get_db

PARENS = "Valid Parentheses (Test list)"
TEMPS = "Daily Temperatures (Test list)"
TWO_SUM = "Two Sum (Test list)"


def ago(days):
    return (date.today() - timedelta(days=days)).isoformat()


def log(client, problem, days_ago, outcome=c.SOLVED_ALONE):
    response = client.post("/log", data={
        "problem": problem, "date": ago(days_ago), "outcome": outcome,
        "time_minutes": "", "time_seconds": "", "notes": "",
    })
    assert response.status_code == 302, response.get_data(as_text=True)


def page(client, path="/"):
    response = client.get(path)
    assert response.status_code == 200
    return response.get_data(as_text=True)


def pid(app, title):
    with app.app_context():
        return get_db().execute("SELECT id FROM problems WHERE title = ?", (title,)).fetchone()["id"]


def query(app, sql, *args):
    with app.app_context():
        return [dict(r) for r in get_db().execute(sql, args)]


def test_new_user_dashboard(client):
    html = page(client)
    assert "reviews are due" not in html and "review is due" not in html
    assert html.count("0 of 3 attempts") == 28  # Every core pattern, and no advanced ones.
    assert "FFT and NTT" not in html
    assert "New pattern for you; hint available" in html


def test_scores_match_the_rule(client, app):
    for days in (20, 10, 2):
        log(client, PARENS, days)
    html = page(client)
    attempts = [{"date": ago(d), "difficulty": "easy", "outcome": c.SOLVED_ALONE} for d in (20, 10, 2)]
    expected = pattern_score(attempts, "normal", date.today().isoformat())
    assert f'<span class="score">{expected:.0f}</span>' in html
    detail = page(client, "/patterns/Stack")
    assert f"{expected:.2f}" in detail
    assert detail.count(ago(20)) == 1 and detail.count(ago(2)) == 1
    assert "Not enough data" in page(client, "/patterns/Trie")


def test_due_review_uses_a_stable_sibling(client, app):
    log(client, PARENS, 30)  # Due 14 days later, so 16 days overdue.
    html = page(client)
    assert "1 review is due" in html
    assert "Daily Temperatures" in html and "Review of Valid Parentheses" in html
    page(client)
    rows = query(app, "SELECT sibling_problem_id, status FROM sibling_suggestions")
    assert rows == [{"sibling_problem_id": pid(app, "Daily Temperatures"), "status": "active"}]


def test_sibling_attempt_completes_the_review(client, app):
    log(client, PARENS, 30)
    page(client)
    log(client, TEMPS, 0)
    attempts = query(app, "SELECT problem_id, review_of_problem_id FROM attempts ORDER BY id")
    assert attempts[-1] == {"problem_id": pid(app, "Daily Temperatures"),
                            "review_of_problem_id": pid(app, "Valid Parentheses")}
    html = page(client)
    assert "review is due" not in html
    assert "<dd>1 day</dd>" in html  # Review streak.
    original = page(client, f"/problems/{pid(app, 'Valid Parentheses')}")
    assert f"Next review due {(date.today() + timedelta(days=28)).isoformat()}" in original
    assert "Next review due" not in page(client, f"/problems/{pid(app, 'Daily Temperatures')}")


def test_dismissing_a_sibling_keeps_the_review_due(client, app):
    log(client, PARENS, 30)
    page(client)
    temps = pid(app, "Daily Temperatures")
    client.post(f"/problems/{temps}/not-now", data={"review_of": pid(app, "Valid Parentheses")})
    html = page(client)
    assert "1 review is due" in html
    assert "Review due" in html  # The original is suggested, since no other sibling remains.
    assert query(app, "SELECT status FROM sibling_suggestions") == [{"status": "dismissed"}]


def test_not_now_hides_a_new_problem(client, app):
    two_sum = pid(app, "Two Sum")
    assert "Two Sum" in page(client)
    client.post(f"/problems/{two_sum}/not-now")
    assert "Two Sum" not in page(client).split("<h2>Patterns</h2>")[0]
    assert query(app, "SELECT problem_id FROM not_now") == [{"problem_id": two_sum}]


def test_hint_reveal_and_lock(client, app):
    two_sum = pid(app, "Two Sum")
    html = page(client)
    assert "Show beginner hint" in html
    assert "Use a hash map" not in html
    client.post(f"/problems/{two_sum}/hint", data={"next": "/"})
    html = page(client)
    assert "Use a hash map or set" in html
    response = client.post("/log", data={"problem": TWO_SUM, "date": ago(0), "outcome": c.SOLVED_ALONE,
                                         "time_minutes": "", "time_seconds": "", "notes": ""})
    assert response.status_code == 400
    assert MESSAGES["outcome_hint"] in response.get_data(as_text=True)


def test_hint_redirect_stays_local(client, app):
    response = client.post(f"/problems/{pid(app, 'Two Sum')}/hint", data={"next": "https://evil.example"})
    assert response.headers["Location"] == "/"


def test_advanced_pattern_appears_once_attempted(client, app):
    response = client.post("/problems/new", data={
        "title": "Some flow problem", "link": "", "difficulty": "hard", "patterns": ["Max Flow and Min Cut"],
    })
    assert response.status_code == 302
    log(client, "Some flow problem (custom)", 1, c.NOT_SOLVED)
    html = page(client)
    assert "Max Flow and Min Cut" in html
    assert "FFT and NTT" not in html


def test_calendar_export(client, app):
    log(client, PARENS, 30)
    log(client, TWO_SUM, 3, c.SOLVED_WITH_HINTS)
    response = client.get("/reviews.ics")
    assert response.mimetype == "text/calendar"
    body = response.get_data(as_text=True)
    assert body.startswith("BEGIN:VCALENDAR\r\n") and body.endswith("END:VCALENDAR\r\n")
    assert body.count("BEGIN:VEVENT") == 2
    assert f"DTSTART;VALUE=DATE:{(date.today() - timedelta(days=16)).strftime('%Y%m%d')}" in body
    assert f"DTSTART;VALUE=DATE:{(date.today() + timedelta(days=7)).strftime('%Y%m%d')}" in body
    assert "SUMMARY:Review: Two Sum" in body


@pytest.mark.parametrize("path", ["/patterns/Nope", "/problems/999"])
def test_missing_pages(client, path):
    assert client.get(path).status_code == 404
