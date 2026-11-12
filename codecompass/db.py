import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hosted(config=None):
    """True in hosted mode (R-50): accounts in PostgreSQL. Local mode is one SQLite file."""
    return (config if config is not None else current_app.config).get("MODE") == "hosted"


def open_db(config, user_id=None):
    """A new connection: the SQLite file in local mode, or in hosted mode PostgreSQL searching
    the account `user_id`'s schema first (only the shared tables when None). The caller closes it."""
    if not hosted(config):
        return connect(config["DATABASE"])
    from . import pg

    conn = pg.Connection(config["DATABASE_URL"], user_id)
    if user_id is not None:
        pg.ensure_user_schema(conn, user_id)
    return conn


def current_user_id():
    """The signed-in account in hosted mode (set by auth.py), or None. Tests may name one."""
    user_id = g.get("user_id")
    if user_id is None and current_app.testing:
        user_id = current_app.config.get("TESTING_USER_ID")
    return user_id


def get_db():
    if "db" not in g:
        g.db = open_db(current_app.config, current_user_id() if hosted() else None)
    return g.db


def store_key():
    """What identifies the current user's data: the database file, or the account."""
    if hosted():
        return f"account:{current_user_id()}"
    return current_app.config["DATABASE"]


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


# Columns added after a table was first created. CREATE TABLE IF NOT EXISTS
# does not add them to an existing database, so they are added here.
ADDED_COLUMNS = [
    ("patterns", "family", "TEXT NOT NULL DEFAULT ''"),
    ("problems", "reserve_position", "INTEGER"),
    ("interviews", "daily_target", "INTEGER"),
]


# Tables whose CHECK constraint gained a value after they were first created, as
# (table, a value the current constraint names). CREATE TABLE IF NOT EXISTS leaves an
# older table as it was, so such a table is rebuilt from schema.sql, keeping its rows.
WIDENED_CHECKS = [
    ("settings", "reviews_on"),
    ("settings", "weekly_goal"),
]


def init_db(path):
    conn = connect(path)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with conn:
        conn.executescript(schema)
        for table, column, declaration in ADDED_COLUMNS:
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {declaration}")
    for table, value in WIDENED_CHECKS:
        _widen(conn, schema, table, value)
    conn.close()


def _create_statement(schema, table):
    """The CREATE TABLE statement for `table` in schema.sql."""
    start = schema.index(f"CREATE TABLE IF NOT EXISTS {table} (")
    return schema[start:schema.index(");", start) + 2]


def _widen(conn, schema, table, value):
    """Rebuild `table` with its current CHECK constraint, keeping its rows, as one transaction:
    either all of it happens or none of it does. A copy left by an older, interrupted
    rebuild is folded back in first."""
    names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    old = f"{table}_old"
    sql = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
    needs_rebuild = sql is not None and f"'{value}'" not in sql["sql"]
    if not needs_rebuild and old not in names:
        return
    steps = ["BEGIN"]
    if needs_rebuild:
        steps += [f"ALTER TABLE {table} RENAME TO {table}_widening",
                  _create_statement(schema, table),
                  f"INSERT INTO {table} SELECT * FROM {table}_widening",
                  f"DROP TABLE {table}_widening"]
    if old in names:
        steps += [f"INSERT OR IGNORE INTO {table} SELECT * FROM {old}", f"DROP TABLE {old}"]
    try:
        conn.executescript(";\n".join(steps) + ";\nCOMMIT;")
    except Exception:
        conn.rollback()
        raise


def init_app(app):
    if hosted(app.config):
        from . import pg

        pg.init_shared(app.config["DATABASE_URL"])
    else:
        init_db(app.config["DATABASE"])
    app.teardown_appcontext(close_db)
