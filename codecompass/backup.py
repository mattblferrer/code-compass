"""A full backup of the user's data, and restoring one (R-46).

The backup is the whole database as one SQLite file, so it holds everything exactly:
attempts, interviews, custom problems, notes and links, settings and goals, sync items,
and rating history. Restoring replaces everything after the user confirms, and can be
undone like deleting all data (R-39): the current database is copied aside first.
"""
import sqlite3

from . import catalog, erase, transfer
from .db import init_db

# The largest backup accepted; a database with the catalog and reserve is a few megabytes.
MAX_BACKUP_BYTES = 100 * 1024 * 1024
HEADER = b"SQLite format 3\x00"
# Tables every CodeCompass database has; a file without them is not a backup.
REQUIRED = {"app_meta", "patterns", "problems", "attempts", "settings", "interviews"}


def snapshot(conn):
    """The database as bytes, for the backup download: the whole file in local mode, and in
    hosted mode the account's data in the same format (transfer.py, R-55)."""
    if getattr(conn, "hosted", False):
        return transfer.export_account(conn)
    return conn.serialize()


def check(data):
    """An open in-memory copy of a backup, or an error message if it is not a sound one."""
    if not data or not data.startswith(HEADER):
        return None, "That file isn't a CodeCompass backup. Choose a .sqlite file saved from Settings."
    copy = sqlite3.connect(":memory:")
    try:
        # The file comes from elsewhere, so SQLite reads it in the mode it advises for that.
        copy.setconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE, True)
        copy.setconfig(sqlite3.SQLITE_DBCONFIG_TRUSTED_SCHEMA, False)
        copy.deserialize(data)
        names = {r[0] for r in copy.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if not REQUIRED <= names:
            raise sqlite3.DatabaseError("missing tables")
        # CodeCompass's database has no triggers or views; a file with any could run its own SQL
        # on later saves once restored (security review).
        if copy.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger', 'view')").fetchone():
            raise sqlite3.DatabaseError("unexpected triggers or views")
        if copy.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise sqlite3.DatabaseError("damaged")
    except sqlite3.Error:
        copy.close()
        return None, "That file isn't a CodeCompass backup, or it is damaged. Nothing was changed."
    return copy, None


def restore(conn, database, copy, today, paths):
    """Replace the database with the checked backup `copy`, keeping the current one for Undo.

    The restored database is brought up to date as an app start would: its tables
    (init_db), and the catalog, reserve, and patterns from `paths` (patterns, catalog,
    reserve), since a backup may come from an earlier version. It is marked so that Undo,
    and the rule that saving anything new makes it final, work as after deleting all data.

    In hosted mode the backup is read into the account (transfer.py), which matches its
    problems to the shared catalog by link, so it may come from either mode (R-55).
    """
    if getattr(conn, "hosted", False):
        try:
            with conn:
                transfer.keep(conn)
                transfer.import_account(conn, copy)
        finally:
            copy.close()
        erase.mark(conn, today)
        return
    erase.keep_copy(conn, database)
    try:
        copy.backup(conn)
    finally:
        copy.close()
    init_db(database)
    catalog.load_if_changed(conn, *paths)
    erase.mark(conn, today)
