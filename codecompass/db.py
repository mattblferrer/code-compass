import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


# Columns added after a table was first created. CREATE TABLE IF NOT EXISTS
# does not add them to an existing database, so they are added here.
ADDED_COLUMNS = [
    ("patterns", "family", "TEXT NOT NULL DEFAULT ''"),
    ("problems", "reserve_position", "INTEGER"),
]


# Tables whose CHECK constraint gained a value after they were first created, as
# (table, a value the current constraint names). CREATE TABLE IF NOT EXISTS leaves an
# older table as it was, so such a table is rebuilt from schema.sql, keeping its rows.
WIDENED_CHECKS = [
    ("settings", "reviews_on"),
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
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone()
        if sql and f"'{value}'" not in sql["sql"]:
            with conn:
                conn.execute(f"ALTER TABLE {table} RENAME TO {table}_old")
            conn.executescript(schema)  # Creates the table again with the current constraint.
            with conn:
                conn.execute(f"INSERT INTO {table} SELECT * FROM {table}_old")
                conn.execute(f"DROP TABLE {table}_old")
    conn.close()


def init_app(app):
    init_db(app.config["DATABASE"])
    app.teardown_appcontext(close_db)
