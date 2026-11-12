import csv
import hashlib
import os
import sqlite3
from pathlib import Path

import pytest

import codecompass

# Tests never open the real data in the project's instance folder. Every SQLite file a test
# opens, through the app or directly, must be elsewhere (pytest's tmp_path); anything else
# stops the test before the file is touched.
INSTANCE_DIR = (Path(__file__).resolve().parent.parent / "instance").resolve()
_real_sqlite_connect = sqlite3.connect


def _guarded_connect(database, *args, **kwargs):
    if isinstance(database, (str, os.PathLike)) and str(database) != ":memory:" and not str(database).startswith("file:"):
        if Path(database).resolve().is_relative_to(INSTANCE_DIR):
            raise RuntimeError(f"A test tried to open real data: {database}")
    elif isinstance(database, str) and database.startswith("file:") and "instance" in database:
        raise RuntimeError(f"A test tried to open real data: {database}")
    return _real_sqlite_connect(database, *args, **kwargs)


sqlite3.connect = _guarded_connect

# Hosted mode (R-50): with CODECOMPASS_TEST_PG set to a PostgreSQL server's URL, every app the
# tests create runs in hosted mode instead, signed in as one account, with a fresh database for
# each SQLite path a test names (so a test that restarts the app on the same path finds its
# data). The server is a local one for tests, never the live site's.
TEST_PG = os.environ.get("CODECOMPASS_TEST_PG")
_pg_databases = []


def _database_for(path):
    import psycopg

    name = "t_" + hashlib.sha1(str(path).encode()).hexdigest()[:16]
    base = TEST_PG.rsplit("/", 1)[0]
    with psycopg.connect(TEST_PG, autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
            conn.execute(f'CREATE DATABASE "{name}" TEMPLATE template0')
            _pg_databases.append(name)
    return f"{base}/{name}"


if TEST_PG:
    _local_create_app = codecompass.create_app

    def _hosted_create_app(test_config=None):
        import psycopg

        config = dict(test_config or {})
        # The SQLite path stays as the test gave it (a temporary file), so code that opens it
        # directly finds an empty file, never real data. It also names the test's PostgreSQL database.
        if "DATABASE" not in config:
            raise RuntimeError("Hosted-mode tests must give DATABASE, a temporary path.")
        url = _database_for(config["DATABASE"])
        config.update(MODE="hosted", DATABASE_URL=url)
        # Tests of other features run signed in, over plain HTTP, without form tokens; the tests
        # of sign-in and request safety (test_hosted.py) turn these back on.
        for key, value in (("TESTING_USER_ID", 1), ("FORCE_HTTPS", False), ("CSRF_CHECK", False)):
            config.setdefault(key, value)
        app = _local_create_app(config)
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute("INSERT INTO users (id, github_id, login, created) OVERRIDING SYSTEM VALUE"
                         " VALUES (1, 1, 'tester', '2026-01-01') ON CONFLICT DO NOTHING")
            conn.execute("SELECT setval(pg_get_serial_sequence('users', 'id'), (SELECT max(id) FROM users))")
        return app

    codecompass.create_app = _hosted_create_app

create_app = codecompass.create_app
# The app as local mode makes it, even while the suite runs in hosted mode (for R-55's round trips).
local_create_app = _local_create_app if TEST_PG else codecompass.create_app


def kept_copy_exists(app):
    """Whether the copy kept for Undo (R-39, R-46) exists: a file in local mode, a row in hosted mode."""
    from codecompass import erase

    if app.config.get("MODE") != "hosted":
        return os.path.exists(erase.copy_path(app.config["DATABASE"]))
    conn = app_db(app)
    try:
        return conn.execute("SELECT 1 FROM kept_copy").fetchone() is not None
    finally:
        conn.close()


def app_db(app):
    """A new connection to the test app's data, as the app's own account sees it. The caller closes it."""
    from codecompass.db import open_db

    return open_db(app.config, app.config.get("TESTING_USER_ID"))


def pytest_collection_modifyitems(config, items):
    """Tests of local mode alone (the database file, its background sync thread, LeetCode) run
    only in local mode, and tests of hosted mode alone only with CODECOMPASS_TEST_PG."""
    for item in items:
        if TEST_PG and "local_only" in item.keywords:
            item.add_marker(pytest.mark.skip(reason="local mode only"))
        if not TEST_PG and "hosted_only" in item.keywords:
            item.add_marker(pytest.mark.skip(reason="needs CODECOMPASS_TEST_PG, a PostgreSQL server for tests"))


@pytest.fixture(autouse=True)
def drop_test_databases():
    yield
    if TEST_PG and _pg_databases:
        import psycopg

        with psycopg.connect(TEST_PG, autocommit=True) as conn:
            while _pg_databases:
                conn.execute(f'DROP DATABASE IF EXISTS "{_pg_databases.pop()}" WITH (FORCE)')

TEST_CATALOG = [
    ["Two Sum", "https://example.com/two-sum", "easy", "", "Test list", "Arrays and Hashing"],
    ["Valid Parentheses", "https://example.com/parens", "easy", "", "Test list", "Stack"],
    ["Daily Temperatures", "https://example.com/temps", "medium", "", "Test list", "Monotonic Stack and Queue; Stack"],
    ["Course Schedule", "https://example.com/courses", "medium", "1700", "Codeforces", "Topological Sort"],
]


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.sqlite")


@pytest.fixture
def catalog_path(tmp_path):
    path = tmp_path / "catalog.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["title", "link", "difficulty", "rating", "source", "patterns"])
        writer.writerows(TEST_CATALOG)
    return str(path)


@pytest.fixture
def app(db_path, catalog_path):
    return create_app({"TESTING": True, "DATABASE": db_path, "CATALOG_PATH": catalog_path, "RESERVE_PATH": None,
                       "UNMAPPED_PATH": None})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    """Requests are paced per site (remote.SPACING); tests record the waits instead of sleeping."""
    from codecompass import remote

    import time

    from codecompass.core import constants

    waits = []
    monkeypatch.setattr(remote, "sleep", waits.append)
    monkeypatch.setattr(remote, "_last_request", {})
    # Hosted mode spaces requests by the time of day (R-54); here it passes only as the waits do.
    start = time.time()
    monkeypatch.setattr(remote, "wall_clock", lambda: start + sum(waits))
    # A sync finishes within one step unless a test of the steps says otherwise.
    monkeypatch.setattr(constants, "SYNC_STEP_SECONDS", 100000.0)
    return waits
