"""Logging, editing, and custom problems (R-02, R-04 to R-07, R-26, R-27)."""
import pytest

from codecompass.core import constants as c
from codecompass.core.validation import MESSAGES, format_minutes, validate_attempt
from codecompass.db import get_db
from codecompass.views import today

TODAY = "2026-11-10"
TWO_SUM = "Two Sum (Test list)"
PARENS = "Valid Parentheses (Test list)"


def good(**changes):
    data = {"date": "2026-11-09", "outcome": c.SOLVED_ALONE, "time_minutes": "", "notes": ""}
    data.update(changes)
    return data


# --- Validation (R-05, R-26, R-27) ---

@pytest.mark.parametrize("problem_id, data, fields", [
    (None, good(), {"problem"}),
    (1, good(outcome=""), {"outcome"}),
    (1, good(date="2026-11-11"), {"date"}),
    (None, good(outcome=""), {"problem", "outcome"}),
    (None, good(date="2026-11-11"), {"problem", "date"}),
    (None, good(outcome="", date="2026-11-11"), {"problem", "outcome", "date"}),
], ids=["no problem", "no outcome", "future date", "problem+outcome", "problem+date", "all three"])
def test_six_invalid_inputs(problem_id, data, fields):
    _, errors = validate_attempt(data, TODAY, problem_id)
    assert set(errors) == fields
    messages = {"problem": MESSAGES["problem"], "outcome": MESSAGES["outcome"], "date": MESSAGES["date_future"]}
    for field in fields:
        assert errors[field] == messages[field]


def test_valid_attempt_and_default_date():
    values, errors = validate_attempt(good(date="", notes="  used a stack  "), TODAY, 1)
    assert errors == {}
    assert values == {"problem_id": 1, "date": TODAY, "outcome": c.SOLVED_ALONE,
                      "time_seconds": None, "notes": "used a stack"}


@pytest.mark.parametrize("bad_date", ["2026-13-01", "11/09/2026", "2026-1-9"])
def test_bad_date_format(bad_date):
    _, errors = validate_attempt(good(date=bad_date), TODAY, 1)
    assert errors == {"date": MESSAGES["date_format"]}


@pytest.mark.parametrize("minutes, timer, seconds", [
    ("25", "", 1500),
    ("2.5", "", 150),
    ("2.0833", "125", 125),
    ("3", "125", 180),
    ("", "125", None),
    ("0.001", "", 1),
])
def test_time_in_minutes_saved_as_seconds(minutes, timer, seconds):
    values, errors = validate_attempt(good(time_minutes=minutes, time_seconds=timer), TODAY, 1)
    assert errors == {}
    assert values["time_seconds"] == seconds


@pytest.mark.parametrize("minutes", ["0", "-5", "abc", "inf"])
def test_invalid_time_names_the_field(minutes):
    _, errors = validate_attempt(good(time_minutes=minutes), TODAY, 1)
    assert errors == {"time": MESSAGES["time"]}


def test_minutes_display_round_trips():
    for seconds in (1, 59, 60, 125, 1500, 5999):
        values, _ = validate_attempt(good(time_minutes=format_minutes(seconds)), TODAY, 1)
        assert values["time_seconds"] == seconds


def test_revealed_hint_blocks_solved_alone():
    _, errors = validate_attempt(good(), TODAY, 1, hint_revealed=True)
    assert errors == {"outcome": MESSAGES["outcome_hint"]}
    _, errors = validate_attempt(good(outcome=c.SOLVED_WITH_HINTS), TODAY, 1, hint_revealed=True)
    assert errors == {}


# --- Routes ---

def attempts(app):
    with app.app_context():
        return [dict(r) for r in get_db().execute(
            "SELECT problem_id, date, outcome, time_seconds, notes, entry_method FROM attempts ORDER BY id"
        )]


def problem_id(app, title):
    with app.app_context():
        return get_db().execute("SELECT id FROM problems WHERE title = ?", (title,)).fetchone()["id"]


def post_attempt(client, **fields):
    data = {"problem": TWO_SUM, "date": "2026-01-05", "outcome": c.SOLVED_ALONE,
            "time_minutes": "", "time_seconds": "", "notes": ""}
    data.update(fields)
    return client.post("/log", data=data)


def test_log_form_shows_outcome_definitions(client):
    page = client.get("/log").get_data(as_text=True)
    assert "AI chat" in page and "AI-written code" in page
    assert TWO_SUM in page


def test_twenty_reference_attempts_reload(client, app):
    outcomes = list(c.OUTCOMES)
    sent = []
    for i in range(20):
        title = [TWO_SUM, PARENS, "Daily Temperatures (Test list)", "Course Schedule (Codeforces)"][i % 4]
        fields = {
            "problem": title,
            "date": f"2026-0{1 + i % 9}-{10 + i % 18:02d}",
            "outcome": outcomes[i % 4],
            "time_minutes": "" if i % 3 == 0 else str(5 + i),
            "notes": "" if i % 2 else f"note {i}",
        }
        assert post_attempt(client, **fields).status_code == 302
        sent.append(fields)
    saved = attempts(app)
    assert len(saved) == 20
    for fields, row in zip(sent, saved):
        assert row["date"] == fields["date"]
        assert row["outcome"] == fields["outcome"]
        assert row["time_seconds"] == (int(fields["time_minutes"]) * 60 if fields["time_minutes"] else None)
        assert row["notes"] == (fields["notes"] or None)
        assert row["entry_method"] == "manual"


def test_invalid_attempt_is_not_saved(client, app):
    response = post_attempt(client, problem="Not a real problem", outcome="", date="2999-01-01")
    assert response.status_code == 400
    page = response.get_data(as_text=True)
    for key in ("problem", "outcome", "date_future"):
        assert MESSAGES[key] in page
    assert attempts(app) == []


def test_future_date_uses_local_today(client, app):
    assert post_attempt(client, date=today()).status_code == 302


def test_repeat_attempts_listed_oldest_first(client, app):
    for day in ("2026-03-10", "2026-01-10", "2026-02-10"):
        post_attempt(client, date=day)
    page = client.get(f"/problems/{problem_id(app, 'Two Sum')}").get_data(as_text=True)
    assert len(attempts(app)) == 3
    assert page.index("2026-01-10") < page.index("2026-02-10") < page.index("2026-03-10")


def test_edit_and_delete_attempt(client, app):
    post_attempt(client, time_minutes="10")
    with app.app_context():
        attempt_id = get_db().execute("SELECT id FROM attempts").fetchone()["id"]
    form = client.get(f"/attempts/{attempt_id}/edit").get_data(as_text=True)
    assert 'value="10"' in form

    response = client.post(f"/attempts/{attempt_id}/edit", data={
        "problem": PARENS, "date": "2026-01-06", "outcome": c.NOT_SOLVED,
        "time_minutes": "", "time_seconds": "600", "notes": "fixed",
    })
    assert response.status_code == 302
    assert attempts(app) == [{"problem_id": problem_id(app, "Valid Parentheses"), "date": "2026-01-06",
                              "outcome": c.NOT_SOLVED, "time_seconds": None, "notes": "fixed",
                              "entry_method": "manual"}]

    assert client.post(f"/attempts/{attempt_id}/delete").status_code == 302
    assert attempts(app) == []
    assert client.get(f"/attempts/{attempt_id}/edit").status_code == 404


def test_timer_seconds_kept_exactly(client, app):
    post_attempt(client, time_minutes="2.0833", time_seconds="125")
    assert attempts(app)[0]["time_seconds"] == 125


def test_add_custom_problem_then_log(client, app):
    response = client.post("/problems/new", data={
        "title": "Rotting Oranges", "link": "", "difficulty": "medium", "patterns": ["Graph Traversal", "Heap"],
    })
    assert response.status_code == 302
    new_id = problem_id(app, "Rotting Oranges")
    assert f"problem={new_id}" in response.headers["Location"]
    assert "Rotting Oranges (custom)" in client.get(response.headers["Location"]).get_data(as_text=True)
    assert post_attempt(client, problem="Rotting Oranges (custom)").status_code == 302
    with app.app_context():
        names = {r["name"] for r in get_db().execute(
            "SELECT pt.name FROM problem_patterns pp JOIN patterns pt ON pt.id = pp.pattern_id WHERE pp.problem_id = ?",
            (new_id,),
        )}
    assert names == {"Graph Traversal", "Heap"}


def test_custom_problem_errors_and_duplicates(client, app):
    response = client.post("/problems/new", data={"title": "", "link": "ftp://x", "difficulty": "", "patterns": []})
    assert response.status_code == 400
    page = response.get_data(as_text=True)
    for key in ("title", "difficulty", "patterns", "link"):
        assert MESSAGES[key] in page

    response = client.post("/problems/new", data={
        "title": "Copy", "link": "https://example.com/two-sum", "difficulty": "easy", "patterns": ["Stack"],
    })
    assert f"problem={problem_id(app, 'Two Sum')}" in response.headers["Location"]
    with app.app_context():
        assert get_db().execute("SELECT count(*) FROM problems WHERE title = 'Copy'").fetchone()[0] == 0


def test_hint_forces_lower_outcome_once(client, app):
    pid = problem_id(app, "Two Sum")
    with app.app_context():
        conn = get_db()
        conn.execute("INSERT INTO hint_reveals (problem_id, date) VALUES (?, '2026-01-05')", (pid,))
        conn.commit()
    response = post_attempt(client)
    assert response.status_code == 400
    assert MESSAGES["outcome_hint"] in response.get_data(as_text=True)
    assert post_attempt(client, outcome=c.SOLVED_WITH_HINTS).status_code == 302
    assert post_attempt(client, outcome=c.SOLVED_ALONE, date="2026-01-06").status_code == 302
