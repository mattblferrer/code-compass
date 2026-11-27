"""Hiding unsolved problems' details (R-61): patterns, data structures, difficulty, and review links."""
import os
import sqlite3
from datetime import date, timedelta

import pytest

from codecompass.core import constants as c
from codecompass.core.reasons import details_hidden, is_solved, reason
from codecompass.core.recommend import INTERVIEW, REVIEW, TARGET, UNSCORED, WEAK
from codecompass.core.validation import MESSAGES
from codecompass.db import get_db

PARENS = "Valid Parentheses (Test list)"
TEMPS = "Daily Temperatures (Test list)"
TODAY = date.today().isoformat()


def ago(days):
    return (date.today() - timedelta(days=days)).isoformat()


def log(client, problem, outcome, days_ago=0):
    return client.post("/log", data={"problem": problem, "date": ago(days_ago), "outcome": outcome,
                                     "time_minutes": "", "time_seconds": "", "notes": ""})


def pid(app, title):
    with app.app_context():
        return get_db().execute("SELECT id FROM problems WHERE title = ?", (title,)).fetchone()["id"]


def page(client, path="/"):
    response = client.get(path)
    assert response.status_code == 200
    return response.get_data(as_text=True)


def hide(client, on=True):
    """Save the settings form with the setting on or off, the other settings at their defaults."""
    form = {"starting_difficulty": "easy", "reviews_on": "1", **({"hide_details": "1"} if on else {})}
    response = client.post("/settings", data=form)
    assert response.status_code == 302


def setting(app):
    with app.app_context():
        row = get_db().execute("SELECT value FROM settings WHERE key = 'hide_details'").fetchone()
        return row["value"] if row else None


# --- The rule in core/ ---

def test_solved_means_any_outcome_but_not_solved():
    assert not is_solved([])
    assert not is_solved([c.NOT_SOLVED, c.NOT_SOLVED])
    for outcome in (c.SOLVED_ALONE, c.SOLVED_WITH_HINTS, c.SOLVED_AFTER_SOLUTION):
        assert is_solved([c.NOT_SOLVED, outcome])


@pytest.mark.parametrize("hide_on, solved, revealed, hidden", [
    (False, False, False, False),  # Setting off: nothing hidden.
    (True, False, False, True),
    (True, True, False, False),  # Solved in any way.
    (True, False, True, False),  # Revealed, until the next attempt.
])
def test_details_hidden(hide_on, solved, revealed, hidden):
    assert details_hidden(hide_on, solved, revealed) is hidden


@pytest.mark.parametrize("group", [TARGET, WEAK, UNSCORED, INTERVIEW, None])
def test_hidden_reasons_never_name_the_pattern(group):
    scores = {"Two Pointers": {"score": 30.0, "last": "2026-11-01"}}
    interview = {"companies": ["Acme"], "date": "2026-12-01"}
    for hint in (False, True):
        text = reason({"group": group, "pattern": "Two Pointers"}, hint, scores, "2026-11-27",
                      interview=interview, hidden=True)
        assert text and "Two Pointers" not in text


def test_a_hidden_review_reason_does_not_name_the_original():
    text = reason({"group": REVIEW, "pattern": "Stack"}, False, {}, "2026-11-27",
                  original_title="Valid Parentheses", hidden=True)
    assert text == "Due for review"
    shown = reason({"group": REVIEW, "pattern": "Stack"}, False, {}, "2026-11-27", original_title="Valid Parentheses")
    assert shown == "Review of Valid Parentheses"


# --- The setting, in the settings menu only ---

def test_the_settings_page_shows_and_keeps_the_setting(client, app):
    assert setting(app) is None  # Off for a new user.
    assert 'name="hide_details" value="1" checked' not in page(client, "/settings")
    hide(client)
    assert setting(app) == "1"
    assert 'name="hide_details" value="1" checked' in page(client, "/settings")
    hide(client, on=False)
    assert setting(app) == "0"  # Unchecked on the settings form turns it off.


def test_the_dashboard_has_no_switch_for_it(client):
    for on in (False, True):
        hide(client, on)
        html = page(client)
        assert "Hide details until solved" not in html and 'name="hide_details"' not in html
    assert client.post("/settings/hide-details", data={"hide_details": "1"}).status_code in (404, 405)


# --- What is hidden, and when it shows again ---

def test_recommendations_hide_difficulty_and_patterns_of_unsolved_problems(client):
    before = page(client).split('id="next-panel"')[1].split("</section>")[0]
    assert 'class="mark level-easy"' in before
    hide(client)
    panel = page(client).split('id="next-panel"')[1].split("</section>")[0]
    assert 'class="mark level-' not in panel
    assert "Show patterns and difficulty" in panel
    assert "Show beginner hint" not in panel  # One reveal, not two.
    for name in ("Arrays and Hashing", "Stack", "Monotonic Stack", "Topological Sort"):
        assert name not in panel


def test_problem_page_hides_until_solved_in_any_way(client, app):
    temps = pid(app, "Daily Temperatures")
    log(client, TEMPS, c.NOT_SOLVED, days_ago=3)
    hide(client)
    html = page(client, f"/problems/{temps}")
    main = html.split('id="hint-area"')[0].split('id="problem-meta"')[1]
    assert "level-medium" not in main
    assert "/patterns/Stack" not in html and "Monotonic Stack" not in html
    assert "stay hidden until you solve this problem" in html
    log(client, TEMPS, c.SOLVED_AFTER_SOLUTION)
    html = page(client, f"/problems/{temps}")
    assert "level-medium" in html and "/patterns/Stack" in html


def test_showing_the_details_counts_as_a_hint_for_the_next_attempt(client, app):
    temps = pid(app, "Daily Temperatures")
    hide(client)
    client.post(f"/problems/{temps}/hint", data={"next": f"/problems/{temps}"})
    html = page(client, f"/problems/{temps}")
    assert "level-medium" in html and "/patterns/Stack" in html
    response = log(client, TEMPS, c.SOLVED_ALONE)
    assert response.status_code == 400
    assert MESSAGES["outcome_hint"] in response.get_data(as_text=True)
    assert log(client, TEMPS, c.NOT_SOLVED).status_code == 302
    # Still unsolved, and the reveal was used by that attempt, so the details hide again.
    assert "/patterns/Stack" not in page(client, f"/problems/{temps}")


def test_log_card_hides_difficulty_patterns_and_the_review_it_completes(client, app):
    temps = pid(app, "Daily Temperatures")
    hide(client)
    card = page(client, f"/problems/{temps}/context")
    assert "level-medium" not in card and "/patterns/Stack" not in card
    assert "Hidden until you solve it" in card
    assert 'href="/settings#setting-hide_details"' in card and "dashboard" not in card
    log_page = page(client, "/log").split('id="practice-heading"')[1]
    assert 'class="mark level-' not in log_page


def test_the_picker_leaves_out_only_unsolved_problems_difficulty(client):
    log(client, PARENS, c.SOLVED_WITH_HINTS)
    hide(client)
    results = {r["label"]: r["difficulty"] for r in client.get("/problems/search?q=a").get_json()}
    assert results[PARENS] == "easy"
    assert results[TEMPS] is None
    hide(client, on=False)
    results = {r["label"]: r["difficulty"] for r in client.get("/problems/search?q=a").get_json()}
    assert results[TEMPS] == "medium"


def test_with_the_setting_off_nothing_changes(client, app):
    temps = pid(app, "Daily Temperatures")
    html = page(client, f"/problems/{temps}")
    assert "level-medium" in html and "stay hidden until you solve" not in html


# --- Older databases gain the setting ---

@pytest.mark.skipif(bool(os.environ.get("CODECOMPASS_TEST_PG")), reason="SQLite only")
def test_an_older_sqlite_database_accepts_the_setting(tmp_path):
    from codecompass.db import init_db

    path = str(tmp_path / "old.sqlite")
    old = sqlite3.connect(path)
    old.execute("""CREATE TABLE settings (
        key TEXT PRIMARY KEY CHECK (key IN ('starting_difficulty', 'advanced_on', 'very_hard_on', 'reviews_on',
                                            'weekly_goal')),
        value TEXT NOT NULL)""")
    old.execute("INSERT INTO settings VALUES ('weekly_goal', '4')")
    old.commit()
    old.close()
    init_db(path)
    init_db(path)
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO settings VALUES ('hide_details', '1')")
    assert sorted(conn.execute("SELECT key, value FROM settings")) == [("hide_details", "1"), ("weekly_goal", "4")]
    conn.close()


@pytest.mark.hosted_only
def test_an_older_account_schema_accepts_the_setting(app):
    from codecompass import pg

    with app.app_context():
        conn = get_db()
        schema = conn.execute("SELECT current_schema() AS s").fetchone()["s"]
        with conn:
            conn.execute("ALTER TABLE settings DROP CONSTRAINT settings_key_check")
            conn.execute("""ALTER TABLE settings ADD CONSTRAINT settings_key_check CHECK (key IN
                            ('starting_difficulty', 'advanced_on', 'very_hard_on', 'reviews_on', 'weekly_goal'))""")
            conn.execute("DELETE FROM app_meta WHERE key = 'pg_schema'")
        pg._ready.clear()
        user_id = int(schema[1:])
        pg.ensure_user_schema(conn, user_id)
        pg._ready.clear()
        pg.ensure_user_schema(conn, user_id)  # Safe to run again.
        with conn:
            conn.execute("INSERT INTO settings (key, value) VALUES ('hide_details', '1')")
        assert conn.execute("SELECT value FROM settings WHERE key = 'hide_details'").fetchone()["value"] == "1"
