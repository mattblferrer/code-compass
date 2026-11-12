"""Deleting all data from settings: asked first, then undoable until anything new is saved (R-39)."""
from datetime import date, timedelta

from codecompass import erase, views
from codecompass.core import constants as c
from codecompass.db import get_db
from conftest import kept_copy_exists

PARENS = "Valid Parentheses (Test list)"


def rows(app, sql):
    with app.app_context():
        return [dict(r) for r in get_db().execute(sql)]


def everything(app):
    """Every user table, and every problem, as plain rows."""
    tables = {t: sorted(rows(app, f"SELECT * FROM {t}"), key=lambda r: sorted(r.items(), key=str))
              for t in erase.USER_TABLES}
    tables["problems"] = rows(app, "SELECT * FROM problems ORDER BY id")
    return tables


def fill(client, app):
    """Some of every kind of data a user can have."""
    day = date.today().isoformat()
    client.post("/log", data={"problem": PARENS, "date": day, "outcome": c.SOLVED_ALONE,
                              "time_minutes": "12", "time_seconds": "", "notes": "used a stack"})
    client.post("/problems/new", data={"title": "My own problem", "link": "https://example.org/mine",
                                       "difficulty": "medium", "patterns": ["Greedy"]})
    client.post("/interviews", data={"company": "Acme", "date": (date.today() + timedelta(days=5)).isoformat(),
                                     "target_difficulty": "hard", "patterns": ["Stack"]})
    client.post("/settings/accounts", data={"username:codeforces": "practice_user"})
    with app.app_context():
        conn = get_db()
        with conn:
            conn.execute("INSERT INTO settings (key, value) VALUES ('starting_difficulty', 'medium')")
            conn.execute("""INSERT INTO sync_items (site, username, problem_link, title, date, accepted, status)
                            VALUES ('codeforces', 'practice_user', 'https://codeforces.com/problemset/problem/4/A',
                                    'Watermelon', ?, 1, 'pending')""", (day,))
            conn.execute("""INSERT INTO rating_history (site, username, contest, date, rating)
                            VALUES ('codeforces', 'practice_user', 'Round 1', ?, 1500)""", (day,))
    data = everything(app)
    for table in ("attempts", "interviews", "interview_patterns", "settings", "linked_accounts", "sync_items",
                  "rating_history"):
        assert data[table], table
    assert any(p["is_custom"] for p in data["problems"])
    return data


def erase_all(client):
    return client.post("/settings/erase", data={"confirm": "erase"}, follow_redirects=True).get_data(as_text=True)


def test_settings_offers_it_and_asks_first(client):
    page = client.get("/settings").get_data(as_text=True)
    assert 'href="/settings/erase" data-dialog="erase-dialog"' in page
    # The question is already on the page, in a dialog that opens over it.
    dialog = page.split('<dialog id="erase-dialog"', 1)[1].split("</dialog>", 1)[0]
    assert "Delete all your data?" in dialog and 'name="confirm" value="erase"' in dialog
    assert 'formmethod="dialog"' in dialog  # Cancel closes the dialog.
    # Without JavaScript the link opens the same question on its own page.
    alone = client.get("/settings/erase").get_data(as_text=True)
    assert "Delete all your data?" in alone and 'href="/settings">Cancel</a>' in alone


def test_nothing_is_deleted_without_confirming(client, app):
    before = fill(client, app)
    response = client.post("/settings/erase", data={})
    assert response.status_code == 200 and "Delete all your data?" in response.get_data(as_text=True)
    assert everything(app) == before


def test_confirming_deletes_the_users_data_and_keeps_the_catalog(client, app, db_path):
    before = fill(client, app)
    page = erase_all(client)
    assert "All your data was deleted." in page
    assert 'action="/settings/erase/undo"' in page  # The message offers Undo.
    after = everything(app)
    for table in erase.USER_TABLES:
        assert after[table] == [], table
    catalog = [p for p in before["problems"] if not p["is_custom"]]
    assert after["problems"] == catalog
    assert kept_copy_exists(app)
    # Settings are back to their defaults.
    assert '<option value="easy" selected>' in client.get("/settings").get_data(as_text=True)


def test_undo_puts_everything_back(client, app, db_path):
    before = fill(client, app)
    erase_all(client)
    client.get("/")  # Looking around does not end Undo.
    page = client.post("/settings/erase/undo", follow_redirects=True).get_data(as_text=True)
    assert "All your data was restored." in page
    assert everything(app) == before
    assert not kept_copy_exists(app)
    assert rows(app, f"SELECT * FROM app_meta WHERE key = '{erase.MARK}'") == []
    # A second Undo has nothing left to restore.
    again = client.post("/settings/erase/undo", follow_redirects=True).get_data(as_text=True)
    assert "That can no longer be undone." in again
    assert everything(app) == before


def test_saving_anything_new_makes_it_final(client, app, db_path):
    fill(client, app)
    erase_all(client)
    client.post("/log", data={"problem": PARENS, "date": date.today().isoformat(), "outcome": c.NOT_SOLVED,
                              "time_minutes": "", "time_seconds": "", "notes": "fresh start"})
    assert not kept_copy_exists(app)
    page = client.post("/settings/erase/undo", follow_redirects=True).get_data(as_text=True)
    assert "That can no longer be undone." in page
    assert [r["notes"] for r in rows(app, "SELECT notes FROM attempts")] == ["fresh start"]


def test_the_copy_expires_after_the_undo_days(client, app, db_path, monkeypatch):
    fill(client, app)
    erase_all(client)
    later = (date.today() + timedelta(days=c.UNDO_DAYS + 1)).isoformat()
    monkeypatch.setattr(views, "today", lambda: later)
    client.get("/")
    assert not kept_copy_exists(app)
    assert "That can no longer be undone." in client.post("/settings/erase/undo",
                                                          follow_redirects=True).get_data(as_text=True)
    assert rows(app, "SELECT * FROM attempts") == []
