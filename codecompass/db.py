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


def init_db(path):
    conn = connect(path)
    with conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.close()


def init_app(app):
    init_db(app.config["DATABASE"])
    app.teardown_appcontext(close_db)
