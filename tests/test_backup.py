"""A full backup as one file, and restoring it with Undo (R-46)."""
import io
import sqlite3
from datetime import date

from codecompass.core import constants as c
from codecompass.db import get_db

PARENS = "Valid Parentheses (Test list)"


def log(client, notes):
    response = client.post("/log", data={"problem": PARENS, "date": date.today().isoformat(),
                                         "outcome": c.SOLVED_ALONE, "time_minutes": "", "time_seconds": "",
                                         "notes": notes})
    assert response.status_code == 302


def notes(app):
    with app.app_context():
        return sorted(r["notes"] for r in get_db().execute("SELECT notes FROM attempts"))


def restore(client, data, confirm=True):
    form = {"file": (io.BytesIO(data), "backup.sqlite")}
    if confirm:
        form["confirm"] = "restore"
    return client.post("/settings/restore", data=form, content_type="multipart/form-data")


def test_backup_downloads_the_whole_database(client, app):
    log(client, "first")
    response = client.get("/settings/backup")
    assert response.mimetype == "application/vnd.sqlite3"
    assert f'filename="codecompass-backup-{date.today().isoformat()}.sqlite"' in response.headers["Content-Disposition"]
    copy = sqlite3.connect(":memory:")
    copy.deserialize(response.data)
    assert [r[0] for r in copy.execute("SELECT notes FROM attempts")] == ["first"]
    page = client.get("/settings").get_data(as_text=True)
    assert 'href="/settings/backup"' in page and 'data-dialog="restore-dialog"' in page


def test_restore_replaces_everything_and_can_be_undone(client, app):
    log(client, "in the backup")
    data = client.get("/settings/backup").data
    log(client, "after the backup")
    page = client.post("/settings/restore", data={"file": (io.BytesIO(data), "b.sqlite"), "confirm": "restore"},
                       content_type="multipart/form-data", follow_redirects=True).get_data(as_text=True)
    assert "Your data was replaced with the backup." in page and 'action="/settings/erase/undo"' in page
    assert notes(app) == ["in the backup"]
    client.post("/settings/erase/undo")
    assert notes(app) == ["after the backup", "in the backup"]


def test_a_backup_from_an_older_version_is_brought_up_to_date(client, app):
    data = client.get("/settings/backup").data
    old = sqlite3.connect(":memory:")
    old.deserialize(data)
    old.execute("DROP TABLE problem_notes")  # A table this version added.
    response = restore(client, old.serialize())
    assert response.status_code == 302
    with app.app_context():
        assert get_db().execute("SELECT count(*) FROM problem_notes").fetchone()[0] == 0  # The table is back.


def test_nothing_changes_without_a_sound_backup_and_a_confirmation(client, app):
    log(client, "kept")
    data = client.get("/settings/backup").data
    response = restore(client, b"name,date\nnot,a database\n")
    assert response.status_code == 400 and "t a CodeCompass backup" in response.get_data(as_text=True)
    other = sqlite3.connect(":memory:")
    other.execute("CREATE TABLE notes (x)")
    assert restore(client, other.serialize()).status_code == 400  # A database, but not CodeCompass's.
    assert restore(client, data, confirm=False).status_code == 400
    # Larger than the usual 5 MB upload limit, it is still read, and refused as not a backup.
    big = restore(client, b"x" * (6 * 1024 * 1024))
    assert big.status_code == 400 and "t a CodeCompass backup" in big.get_data(as_text=True)
    assert notes(app) == ["kept"]
    page = client.get("/settings/restore").get_data(as_text=True)
    assert "Replace all your data with a backup?" in page and 'href="/settings">Cancel</a>' in page


def test_restore_loads_the_current_catalog(client, app):
    data = client.get("/settings/backup").data
    old = sqlite3.connect(":memory:")
    old.deserialize(data)
    # A backup from before a catalog change: an older fingerprint and a problem missing.
    old.execute("UPDATE app_meta SET value = 'older' WHERE key = 'data_fingerprint'")
    old.execute("DELETE FROM problems WHERE title = 'Two Sum'")
    old.commit()
    assert restore(client, old.serialize()).status_code == 302
    with app.app_context():
        assert get_db().execute("SELECT 1 FROM problems WHERE title = 'Two Sum'").fetchone()
