"""A full backup as one file, and restoring it with Undo (R-46)."""
import gzip
import io
import sqlite3
from datetime import date

from codecompass import backup
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


def problem_titles(data):
    copy = sqlite3.connect(":memory:")
    copy.deserialize(data)
    return sorted(r[0] for r in copy.execute("SELECT title FROM problems"))


def test_a_backup_holds_only_the_problems_its_records_use(client, app):
    """The rest of the catalog and reserve stays out, so a backup fits the host's upload limit (R-46, R-55)."""
    log(client, "first")
    assert problem_titles(client.get("/settings/backup").data) == ["Valid Parentheses"]


def test_a_gzipped_backup_restores(client, app):
    """The restore form compresses the file before sending it (restore_gzip.js)."""
    log(client, "in the backup")
    data = client.get("/settings/backup").data
    log(client, "after the backup")
    response = client.post("/settings/restore", data={"file": (io.BytesIO(gzip.compress(data)), "b.sqlite.gz"),
                                                      "confirm": "restore"}, content_type="multipart/form-data")
    assert response.status_code == 302
    assert notes(app) == ["in the backup"]


def test_a_damaged_or_oversized_gzip_changes_nothing(client, app, monkeypatch):
    log(client, "kept")
    data = client.get("/settings/backup").data
    damaged = restore(client, gzip.compress(data)[:-20])
    assert damaged.status_code == 400 and "damaged, or larger than" in damaged.get_data(as_text=True)
    # Larger than the limit once unpacked, though small as sent.
    monkeypatch.setattr(backup, "MAX_BACKUP_BYTES", len(data) - 1)
    oversized = restore(client, gzip.compress(data))
    assert oversized.status_code == 400 and "damaged, or larger than" in oversized.get_data(as_text=True)
    assert notes(app) == ["kept"]


def test_undo_of_a_deleted_attempt_still_finds_its_problem_after_a_restore(client, app):
    """A deleted attempt kept for Undo names its problem by id, so a backup keeps that problem
    even when nothing else uses it; otherwise a restore could give its id to another problem."""
    form = {"date": date.today().isoformat(), "outcome": c.SOLVED_ALONE, "time_minutes": "", "time_seconds": "",
            "notes": ""}
    assert client.post("/log", data={**form, "problem": "Daily Temperatures (Test list)"}).status_code == 302
    log(client, "deleted")
    with app.app_context():
        attempt_id = get_db().execute("SELECT id FROM attempts WHERE notes = 'deleted'").fetchone()[0]
    client.post(f"/attempts/{attempt_id}/delete")
    with app.app_context():
        item_id = get_db().execute("SELECT id FROM deleted_items").fetchone()[0]
    data = client.get("/settings/backup").data
    assert problem_titles(data) == ["Daily Temperatures", "Valid Parentheses"]
    assert restore(client, data).status_code == 302
    page = client.post(f"/undo/{item_id}", follow_redirects=True).get_data(as_text=True)
    assert "Attempt restored." in page
    with app.app_context():
        assert get_db().execute("""SELECT p.title FROM attempts a JOIN problems p ON p.id = a.problem_id
                                   WHERE a.notes = 'deleted'""").fetchone()[0] == "Valid Parentheses"


def test_the_restore_pages_compress_the_upload(client):
    for path in ("/settings", "/settings/restore"):
        assert "/static/js/restore_gzip.js" in client.get(path).get_data(as_text=True), path
    assert client.get("/static/js/restore_gzip.js").status_code == 200
