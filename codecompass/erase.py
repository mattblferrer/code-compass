"""Delete all the user's data, with an Undo (R-39).

Before erasing, the whole database is copied to a file beside it. Undo copies it
back, so everything returns exactly as it was. The copy is removed as soon as the
user saves anything new, so Undo can never overwrite a fresh start, and in any
case after UNDO_DAYS (core/constants.py).
"""
import os
import sqlite3

from .core.dates import undo_cutoff

# Everything the user entered, synced, or chose. The built-in catalog and reserve
# problems and the patterns stay; settings fall back to their defaults.
USER_TABLES = ("attempts", "interview_patterns", "interviews", "settings", "hidden_sites",
               "pattern_preferences", "sibling_suggestions", "not_now", "hint_reveals",
               "linked_accounts", "sync_items", "sync_batches", "rating_history", "deleted_items",
               "problem_notes", "problem_links")
MARK = "erased_on"  # In app_meta, the day of an erase that can still be undone.


def copy_path(database):
    return f"{database}-erased"


def keep_copy(conn, database):
    """Copy the whole database aside, so the change about to be made can be undone.
    Also used before restoring a backup (R-46)."""
    path = copy_path(database)
    _remove(path)
    copy = sqlite3.connect(path)
    try:
        conn.backup(copy)
    finally:
        copy.close()


def mark(conn, today):
    """Note the day of a change that can still be undone."""
    with conn:
        conn.execute("INSERT OR REPLACE INTO app_meta (key, value) VALUES (?, ?)", (MARK, today))


def erase_all(conn, database, today):
    """Copy the database for Undo, then delete all the user's data."""
    keep_copy(conn, database)
    with conn:
        for table in USER_TABLES:
            conn.execute(f"DELETE FROM {table}")
        # Custom problems, and problems kept only because an attempt used them.
        conn.execute("""DELETE FROM problems WHERE is_custom = 1
                        OR (catalog_position IS NULL AND reserve_position IS NULL)""")
    mark(conn, today)


def undo_erase(conn, database, today):
    """Put everything back from the copy. Returns False if there is nothing to undo."""
    path = copy_path(database)
    if not _undoable(conn, path, today):
        discard(conn, database)
        return False
    copy = sqlite3.connect(path)
    try:
        copy.backup(conn)  # The copy was made before the mark was set, so the mark goes too.
    finally:
        copy.close()
    _remove(path)
    return True


def can_undo(conn, database, today):
    return _undoable(conn, copy_path(database), today)


def discard(conn, database):
    """Remove the copy, so the erase becomes final."""
    if conn.execute("SELECT 1 FROM app_meta WHERE key = ?", (MARK,)).fetchone():
        with conn:
            conn.execute("DELETE FROM app_meta WHERE key = ?", (MARK,))
    _remove(copy_path(database))


def _undoable(conn, path, today):
    row = conn.execute("SELECT value FROM app_meta WHERE key = ?", (MARK,)).fetchone()
    cutoff = undo_cutoff(today)
    return row is not None and row["value"] >= cutoff and os.path.exists(path)


def _remove(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
