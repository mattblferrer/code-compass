"""PostgreSQL for hosted mode (R-50, R-52).

The rest of the app is written against Python's sqlite3 interface. `Connection` gives
the same interface over psycopg, so the queries run unchanged in both modes:

- `?` placeholders become psycopg's `%s`, and a literal `%` is escaped;
- `LIKE` becomes `ILIKE`, since SQLite's LIKE ignores case;
- an INSERT into a table with an `id` column returns it, for `cursor.lastrowid`;
- rows can be read by name or position, like sqlite3.Row;
- `with conn:` commits or rolls back, as with sqlite3.

Each account has its own schema, `u<user id>`, holding the user tables (schema_pg_user.sql).
The catalog, reserve, patterns, and accounts are shared in `public` (schema_pg_shared.sql).
A connection for an account searches its schema first, so every query reaches only that
account's tables. Problems are shared, so each account schema has a view named `problems`
showing the shared catalog and reserve plus that account's own custom problems; inserts
through it are owned by the account, and it cannot reach another account's rows.

psycopg is imported only here, so local mode never needs it.
"""
import functools
import hashlib
import re
from pathlib import Path

SHARED_SCHEMA_PATH = Path(__file__).with_name("schema_pg_shared.sql")
USER_SCHEMA_PATH = Path(__file__).with_name("schema_pg_user.sql")

# Tables whose INSERTs return the new row's id, for cursor.lastrowid.
ID_TABLES = {"attempts", "interviews", "problems", "sibling_suggestions", "not_now", "hint_reveals",
             "sync_items", "deleted_items", "sync_batches", "problem_links", "users", "sync_jobs"}

_INSERT = re.compile(r"^\s*INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_.]*)", re.IGNORECASE)
_LIKE = re.compile(r"\bLIKE\b")
_NAMED = re.compile(r"(?<![:\w]):([A-Za-z_]\w*)")


def schema_name(user_id):
    """The schema holding one account's tables."""
    return f"u{int(user_id)}"


@functools.lru_cache(maxsize=1024)
def translate(sql):
    """The SQL as psycopg needs it: placeholders (`?` and `:name`), escaped percent signs, and ILIKE.
    Text inside single quotes keeps its question marks and case."""
    out, quoted, start = [], False, 0
    pieces = []
    for i, ch in enumerate(sql):
        if ch == "'":
            if not quoted:
                pieces.append((sql[start:i], False))
                start = i
            else:
                pieces.append((sql[start:i + 1], True))
                start = i + 1
            quoted = not quoted
    pieces.append((sql[start:], quoted))
    for text, is_literal in pieces:
        text = text.replace("%", "%%")
        if not is_literal:
            text = _NAMED.sub(r"%(\1)s", _LIKE.sub("ILIKE", text.replace("?", "%s")))
        out.append(text)
    return "".join(out)


class Row:
    """A result row readable by column name or position, like sqlite3.Row."""

    __slots__ = ("_names", "_values")

    def __init__(self, names, values):
        self._names, self._values = names, values

    def keys(self):
        return list(self._names)

    def __getitem__(self, key):
        if isinstance(key, (int, slice)):
            return self._values[key]
        try:
            return self._values[self._names.index(key)]
        except ValueError:
            raise IndexError(f"No item with that key: {key}") from None

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __eq__(self, other):
        return isinstance(other, Row) and self._names == other._names and self._values == other._values

    def __repr__(self):
        return f"Row({dict(zip(self._names, self._values))!r})"


def _row_factory(cursor):
    names = [d.name for d in cursor.description] if cursor.description else []
    return lambda values: Row(names, tuple(values))


class Cursor:
    """The part of sqlite3.Cursor the app uses."""

    def __init__(self, cursor, lastrowid=None, rows=None):
        self._cursor, self.lastrowid, self._rows = cursor, lastrowid, rows

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def description(self):
        return [(d.name,) for d in self._cursor.description] if self._cursor.description else None

    def fetchone(self):
        if self._rows is not None:
            return self._rows.pop(0) if self._rows else None
        return self._cursor.fetchone() if self._cursor.description else None

    def fetchall(self):
        if self._rows is not None:
            rows, self._rows = self._rows, []
            return rows
        return self._cursor.fetchall() if self._cursor.description else []

    def __iter__(self):
        return iter(self.fetchall())


class Connection:
    """A psycopg connection with the sqlite3 interface the app uses. `user_id` picks the
    account whose schema is searched first; without it only the shared tables are reached."""

    hosted = True

    def __init__(self, url, user_id=None):
        import psycopg
        from psycopg import ClientCursor

        # Client-side binding, as sqlite3 does it, so untyped parameters such as `? IS NULL` work.
        extra = {}
        if "sslmode=verify-full" in url and "sslrootcert" not in url:
            # Check the database's certificate against certifi's authorities (installed with requests),
            # since a host's system list may not be where the bundled libpq looks.
            import certifi

            extra["sslrootcert"] = certifi.where()
        self._conn = psycopg.connect(url, cursor_factory=ClientCursor, row_factory=_row_factory, **extra)
        self.url, self.user_id = url, user_id
        path = f"{schema_name(user_id)}, public" if user_id is not None else "public"
        self._conn.execute(f"SET search_path TO {path}")
        self._conn.commit()

    def execute(self, sql, params=()):
        cursor = self._conn.cursor()
        match = _INSERT.match(sql)
        table = match.group(1).split(".")[-1].lower() if match else None
        if table in ID_TABLES and "RETURNING" not in sql.upper():
            cursor.execute(translate(sql + " RETURNING id"), _params(params))
            row = cursor.fetchone()
            return Cursor(cursor, lastrowid=row[0] if row else None, rows=[])
        if params:
            cursor.execute(translate(sql), _params(params))
        else:
            cursor.execute(_plain(sql))
        return Cursor(cursor)

    def executemany(self, sql, seq):
        rows = [_params(p) for p in seq]
        cursor = self._conn.cursor()
        if rows:
            cursor.executemany(translate(sql), rows)
        return Cursor(cursor)

    def executescript(self, script):
        with self._conn.cursor() as cursor:
            cursor.execute(script)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        return False


def _params(params):
    """Parameters as psycopg takes them: a dict for named placeholders, else a tuple."""
    return dict(params) if isinstance(params, dict) else tuple(params)


def _plain(sql):
    """SQL run without parameters: no placeholder handling, but LIKE still ignores case."""
    pieces, quoted, start, out = [], False, 0, []
    for i, ch in enumerate(sql):
        if ch == "'":
            pieces.append((sql[start:i], quoted))
            start, quoted = i, not quoted
    pieces.append((sql[start:], quoted))
    for text, is_literal in pieces:
        out.append(text if is_literal else _LIKE.sub("ILIKE", text))
    return "".join(out)


def _digest(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def init_shared(url):
    """Create or update the shared tables. Safe to rerun, and safe when two cold starts run it
    at once: a lock makes the second wait."""
    script = SHARED_SCHEMA_PATH.read_text(encoding="utf-8")
    conn = Connection(url)
    try:
        with conn:
            conn.execute("SELECT pg_advisory_xact_lock(726354)")
            conn.executescript(script)
    finally:
        conn.close()


_ready = set()  # Accounts whose schema is current in this process.


def ensure_user_schema(conn, user_id):
    """Create or update an account's schema, at most once per process for each account.
    Uses the shared connection `conn`; the stamp in the account's app_meta skips an
    unchanged script."""
    conn_key = (conn.url, user_id)
    if conn_key in _ready:
        return
    script = USER_SCHEMA_PATH.read_text(encoding="utf-8")
    schema, stamp = schema_name(user_id), _digest(script)
    current = conn.execute(
        """SELECT 1 FROM information_schema.tables WHERE table_schema = ? AND table_name = 'app_meta'""",
        (schema,)).fetchone()
    if current:
        row = conn.execute(f"SELECT value FROM {schema}.app_meta WHERE key = 'pg_schema'").fetchone()
        if row and row["value"] == stamp:
            _ready.add(conn_key)
            return
    with conn:
        conn.execute("SELECT pg_advisory_xact_lock(726355, ?)", (int(user_id),))
        conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        conn.execute(f"SET LOCAL search_path TO {schema}, public")
        conn.executescript(script.replace("{owner}", str(int(user_id))))
        conn.execute(f"""INSERT INTO {schema}.app_meta (key, value) VALUES ('pg_schema', ?)
                         ON CONFLICT (key) DO UPDATE SET value = excluded.value""", (stamp,))
    _ready.add(conn_key)


def drop_user_schema(conn, user_id):
    """Remove an account's schema and custom problems (R-56). Runs inside the caller's transaction."""
    conn.execute(f"DROP SCHEMA IF EXISTS {schema_name(user_id)} CASCADE")
    conn.execute("DELETE FROM public.problems WHERE owner = ?", (int(user_id),))
    _ready.discard((conn.url, user_id))
