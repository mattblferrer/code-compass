"""A full backup of the user's data, and restoring one (R-46).

The backup is one SQLite file holding all of the user's data: attempts, interviews, custom
problems, notes and links, settings and goals, sync items, and rating history, with only the
catalog and reserve problems those records use (transfer.py). It is the same in both modes,
so it moves between them (R-55), and small enough for the host's upload limit. Restoring
replaces everything after the user confirms, and can be undone like deleting all data
(R-39): the current data is kept aside first.

The restore form compresses a backup with gzip before uploading it (restore_gzip.js), so a
gzipped file is unpacked here, up to the same size limit.
"""
import sqlite3
import zlib

from . import catalog, erase, sync, transfer
from .db import init_db

# The largest backup accepted, once unpacked. An older backup that holds the whole catalog
# and reserve is a few megabytes; one in the current form is far smaller.
MAX_BACKUP_BYTES = 100 * 1024 * 1024
HEADER = b"SQLite format 3\x00"
GZIP_HEADER = b"\x1f\x8b"
# Tables every CodeCompass database has; a file without them is not a backup.
REQUIRED = {"app_meta", "patterns", "problems", "attempts", "settings", "interviews"}


def snapshot(conn):
    """The user's data as the bytes of a backup file, the same in both modes (transfer.py, R-55)."""
    return transfer.export_account(conn)


def unpack(data):
    """A gzipped upload unpacked, or None if it is damaged or larger than MAX_BACKUP_BYTES
    once unpacked. Anything not gzipped comes back as it is."""
    if not data or not data.startswith(GZIP_HEADER):
        return data
    unzip = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        out = unzip.decompress(data, MAX_BACKUP_BYTES + 1)
    except zlib.error:
        return None
    if len(out) > MAX_BACKUP_BYTES or unzip.unconsumed_tail or not unzip.eof:
        return None
    return out


def check(data):
    """An open in-memory copy of a backup, or an error message if it is not a sound one.
    `data` may be gzipped."""
    if data and data.startswith(GZIP_HEADER):
        data = unpack(data)
        if data is None:
            return None, (f"That file is damaged, or larger than {MAX_BACKUP_BYTES // 2**20} MB once unpacked. "
                          "Nothing was changed.")
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
    sync.stop(database)  # A running sync's results belong to the data being replaced.
    erase.keep_copy(conn, database)
    try:
        copy.backup(conn)
    finally:
        copy.close()
    init_db(database)
    catalog.load_if_changed(conn, *paths)
    erase.mark(conn, today)
