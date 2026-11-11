"""Undo after deleting an attempt or an interview (R-07, R-15)."""
from datetime import date, timedelta

from codecompass.core import constants as c
from codecompass.db import get_db

TWO_SUM = "Two Sum (Test list)"


def rows(app, sql):
    with app.app_context():
        return [dict(r) for r in get_db().execute(sql)]


def log(client, day="2026-01-05", notes=""):
    return client.post("/log", data={"problem": TWO_SUM, "date": day, "outcome": c.SOLVED_WITH_HINTS,
                                     "time_minutes": "12", "time_seconds": "", "notes": notes})


def undo_id(page):
    marker = 'action="/undo/'
    start = page.index(marker) + len(marker)
    return int(page[start:page.index('"', start)])


def test_deleted_attempt_comes_back_unchanged(client, app):
    log(client, notes="first try")
    before = rows(app, "SELECT * FROM attempts")
    attempt_id = before[0]["id"]
    page = client.post(f"/attempts/{attempt_id}/delete", follow_redirects=True).get_data(as_text=True)
    assert rows(app, "SELECT * FROM attempts") == []
    assert "Attempt deleted." in page and '<div class="flash has-action">' in page

    item = undo_id(page)
    page = client.post(f"/undo/{item}", follow_redirects=True).get_data(as_text=True)
    assert "Attempt restored." in page
    assert rows(app, "SELECT * FROM attempts") == before
    assert rows(app, "SELECT * FROM deleted_items") == []

    page = client.post(f"/undo/{item}", follow_redirects=True).get_data(as_text=True)
    assert "That can no longer be undone." in page
    assert len(rows(app, "SELECT * FROM attempts")) == 1


def test_restored_attempt_gets_a_new_id_when_its_old_one_was_reused(client, app):
    log(client, day="2026-01-05")
    log(client, day="2026-01-06", notes="second")
    second = rows(app, "SELECT id FROM attempts ORDER BY id")[-1]["id"]
    page = client.post(f"/attempts/{second}/delete", follow_redirects=True).get_data(as_text=True)
    log(client, day="2026-01-07", notes="third")  # SQLite may give this one the freed id.
    client.post(f"/undo/{undo_id(page)}")
    notes = sorted(r["notes"] or "" for r in rows(app, "SELECT notes FROM attempts"))
    assert notes == ["", "second", "third"]


def test_deleted_interview_comes_back_with_its_patterns(client, app):
    day = (date.today() + timedelta(days=6)).isoformat()
    client.post("/interviews", data={"company": "Acme", "date": day, "target_difficulty": "hard",
                                     "patterns": ["Stack", "Greedy"]})
    before = rows(app, "SELECT * FROM interviews")
    patterns = rows(app, "SELECT * FROM interview_patterns ORDER BY pattern_id")
    page = client.post(f"/interviews/{before[0]['id']}/delete", follow_redirects=True).get_data(as_text=True)
    assert "Interview with Acme deleted." in page and '<div class="flash has-action">' in page
    assert rows(app, "SELECT * FROM interviews") == []

    page = client.post(f"/undo/{undo_id(page)}", follow_redirects=True).get_data(as_text=True)
    assert "Interview with Acme restored." in page
    assert rows(app, "SELECT * FROM interviews") == before
    assert rows(app, "SELECT * FROM interview_patterns ORDER BY pattern_id") == patterns


def test_old_copies_are_cleared_at_the_next_deletion(client, app):
    with app.app_context():
        conn = get_db()
        with conn:
            conn.execute("INSERT INTO deleted_items (kind, payload, date) VALUES ('attempt', '{}', '2000-01-01')")
    log(client)
    attempt_id = rows(app, "SELECT id FROM attempts")[0]["id"]
    client.post(f"/attempts/{attempt_id}/delete")
    assert [r["date"] for r in rows(app, "SELECT date FROM deleted_items")] == [date.today().isoformat()]


def test_undo_stops_working_after_the_undo_window(client, app):
    from codecompass import queries

    log(client)
    attempt_id = rows(app, "SELECT id FROM attempts")[0]["id"]
    page = client.post(f"/attempts/{attempt_id}/delete", follow_redirects=True).get_data(as_text=True)
    item_id = undo_id(page)
    later = (date.today() + timedelta(days=c.UNDO_DAYS + 1)).isoformat()
    with app.app_context():
        assert queries.restore_deleted(get_db(), item_id, later) is None
    assert rows(app, "SELECT * FROM attempts") == []
    assert rows(app, "SELECT * FROM deleted_items") == []  # The expired copy is cleared.


def test_undo_explains_when_the_problem_is_gone(client, app):
    client.post("/problems/new", data={"title": "Gone soon", "difficulty": "easy", "patterns": ["Greedy"]})
    problem_id = rows(app, "SELECT id FROM problems WHERE title = 'Gone soon'")[0]["id"]
    client.post("/log", data={"problem_id": str(problem_id), "problem": "Gone soon (custom)", "date": "2026-01-05",
                              "outcome": c.SOLVED_ALONE, "time_minutes": ""})
    attempt_id = rows(app, "SELECT id FROM attempts")[0]["id"]
    page = client.post(f"/attempts/{attempt_id}/delete", follow_redirects=True).get_data(as_text=True)
    with app.app_context():
        conn = get_db()
        with conn:  # As a catalog or reserve reload removes a problem left with no attempts.
            conn.execute("DELETE FROM problems WHERE id = ?", (problem_id,))
    response = client.post(f"/undo/{undo_id(page)}", follow_redirects=True)
    assert response.status_code == 200
    assert "its problem is no longer in CodeCompass" in response.get_data(as_text=True)
    assert rows(app, "SELECT * FROM attempts") == []
