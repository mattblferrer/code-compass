"""An account's data as a CodeCompass backup file, and back (R-46, R-55).

Both modes write a backup the same way: a SQLite database built from schema.sql, holding
the patterns, the problems the user's records use, their custom problems, and every user
table, but not the rest of the catalog and reserve, which each copy of the app has. So a
backup from either mode restores in the other, and stays small enough for the host's
upload limit. Restoring one in local mode loads the current catalog and reserve around it.

Reading a backup into an account matches problems by link to the shared catalog and
reserve, and adds the rest as the account's custom problems; patterns match by name. A
backup from the same account (as kept for Undo) keeps every id, so it comes back exactly.
"""
import json
import sqlite3
from pathlib import Path

from .core.validation import web_link

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

# Each user table, in an order that inserts a row only after the rows it refers to.
USER_TABLES = ("settings", "hidden_sites", "pattern_preferences", "interviews", "interview_patterns",
               "attempts", "sibling_suggestions", "not_now", "hint_reveals", "linked_accounts", "sync_items",
               "rating_history", "deleted_items", "sync_batches", "problem_notes", "problem_links",
               "pattern_links")
PROBLEM_COLUMNS = {
    "attempts": ("problem_id", "review_of_problem_id"),
    "sibling_suggestions": ("due_problem_id", "sibling_problem_id"),
    "not_now": ("problem_id",),
    "hint_reveals": ("problem_id",),
    "problem_notes": ("problem_id",),
    "problem_links": ("problem_id",),
}
PATTERN_COLUMNS = {"interview_patterns": ("pattern_id",), "pattern_preferences": ("pattern_id",),
                   "pattern_links": ("pattern_id",)}
# Undo records name problems and attempts inside their saved text, so they are kept only
# when every id is unchanged.
ID_BOUND = ("deleted_items", "sync_batches")
PROBLEM_FIELDS = ("id", "title", "link", "difficulty", "rating", "source", "is_custom", "catalog_position",
                  "reserve_position")


def _columns(conn, table):
    """A table's columns, read from an empty result."""
    return [d[0] for d in conn.execute(f"SELECT * FROM {table} WHERE 1 = 0").description]


def _chunks(items, size=500):
    items = list(items)
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _merge_into_catalog(conn, problems):
    """Problems for the backup, with each custom problem whose link the shared catalog now also
    has replaced by that catalog problem, as local mode merges them when the catalog gains the
    link. A backup holds each link once, so otherwise the custom problem would lose its link.
    Returns (problems, {custom id: catalog id})."""
    by_id = {p["id"]: p for p in problems}
    merged = {}
    for p in problems:
        if not p["is_custom"] or not p["link"]:
            continue
        shared = conn.execute(f"SELECT {', '.join(PROBLEM_FIELDS)} FROM problems WHERE link = ? AND is_custom = 0",
                              (p["link"],)).fetchone()
        if shared is None:
            continue
        shared = dict(zip(PROBLEM_FIELDS, shared))
        merged[p["id"]] = shared["id"]
        by_id.setdefault(shared["id"], shared)
        del by_id[p["id"]]
    return list(by_id.values()), merged


def _join_notes(rows, columns):
    """Notes that now belong to one problem, as one note: both texts, newest date."""
    problem, note, updated = (columns.index(c) for c in ("problem_id", "note", "updated"))
    joined = {}
    for row in rows:
        kept = joined.get(row[problem])
        if kept is None:
            joined[row[problem]] = row
        else:
            kept[note] = kept[note] + "\n\n" + row[note]
            kept[updated] = max(kept[updated], row[updated])
    return list(joined.values())


def _used_problems(conn):
    """Ids of every problem the account's records use, and of its custom problems.

    That includes the problems of deleted attempts kept for Undo, which name them only in
    their saved text. A local restore loads the rest of the catalog under new ids, so a
    problem left out here could come back under an id Undo would read as another problem.
    """
    ids = set()
    for table, columns in PROBLEM_COLUMNS.items():
        for column in columns:
            ids |= {r[0] for r in conn.execute(f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL")}
    ids |= {r[0] for r in conn.execute("SELECT id FROM problems WHERE is_custom = 1")}
    for (payload,) in conn.execute("SELECT payload FROM deleted_items WHERE kind = 'attempt'"):
        row = json.loads(payload)
        ids |= {row.get(c) for c in ("problem_id", "review_of_problem_id") if isinstance(row.get(c), int)}
    # Only problems that exist; an Undo record can name one a catalog reload has since removed.
    found = set()
    for chunk in _chunks(sorted(ids)):
        found |= {r[0] for r in conn.execute(
            f"SELECT id FROM problems WHERE id IN ({', '.join('?' * len(chunk))})", chunk)}
    return found


def export_account(conn):
    """The account's data as the bytes of a CodeCompass backup file."""
    out = sqlite3.connect(":memory:")
    try:
        out.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        rows = conn.execute("SELECT id, name, category, tier, family, description, list_position FROM patterns")
        out.executemany("INSERT INTO patterns (id, name, category, tier, family, description, list_position)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?)", [tuple(r) for r in rows])
        problems, links = [], set()
        for chunk in _chunks(sorted(_used_problems(conn))):
            marks = ", ".join("?" * len(chunk))
            problems += [dict(zip(PROBLEM_FIELDS, r)) for r in conn.execute(
                f"SELECT {', '.join(PROBLEM_FIELDS)} FROM problems WHERE id IN ({marks})", chunk)]
        problems, merged = _merge_into_catalog(conn, problems)
        # Shared problems first, so a custom problem with the same link loses its link, not the catalog's.
        for p in sorted(problems, key=lambda p: p["is_custom"]):
            if p["link"] in links:
                p["link"] = None
            links.add(p["link"])
            out.execute(f"INSERT INTO problems ({', '.join(PROBLEM_FIELDS)}) VALUES ({', '.join('?' * len(PROBLEM_FIELDS))})",
                        tuple(p[f] for f in PROBLEM_FIELDS))
        for chunk in _chunks(sorted(p["id"] for p in problems)):
            marks = ", ".join("?" * len(chunk))
            out.executemany("INSERT INTO problem_patterns (problem_id, pattern_id) VALUES (?, ?)",
                            [tuple(r) for r in conn.execute(
                                f"SELECT problem_id, pattern_id FROM problem_patterns WHERE problem_id IN ({marks})",
                                chunk)])
        for table in USER_TABLES:
            columns = [c for c in _columns(out, table) if c in _columns(conn, table)]
            if table == "rating_history":
                columns.append("rowid")  # Kept, so ratings keep their stored order.
            order = "rowid" if table == "rating_history" else ", ".join(columns)
            rows = [list(r) for r in conn.execute(f"SELECT {', '.join(columns)} FROM {table} ORDER BY {order}")]
            for column in PROBLEM_COLUMNS.get(table, ()):
                i = columns.index(column)
                for row in rows:
                    row[i] = merged.get(row[i], row[i])
            if table == "problem_notes":
                rows = _join_notes(rows, columns)
            out.executemany(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
                            [tuple(r) for r in rows])
        out.commit()
        return out.serialize()
    finally:
        out.close()


def clear_account(conn):
    """Delete every user row and the account's custom problems, inside the caller's transaction.
    Shared problems stay. A sync still running stops, so it cannot add to the cleared account."""
    for table in reversed(USER_TABLES):
        conn.execute(f"DELETE FROM {table}")
    conn.execute("DELETE FROM problems WHERE is_custom = 1")
    conn.execute("DELETE FROM sync_job")


def _new_problem(conn, problem, patterns):
    """Add a backup's problem as one of the account's custom problems, keeping its id when that
    id is free and was handed out before (as for Undo, or a backup of this account). Returns the
    id it has now. An id not handed out yet is never taken: PostgreSQL would later hand it to
    another account and fail (security review)."""
    values = (problem["title"], web_link(problem["link"]), problem["difficulty"], problem["rating"])
    issued = conn.execute("SELECT last_value FROM " + conn.execute(
        "SELECT pg_get_serial_sequence('public.problems', 'id')").fetchone()[0]).fetchone()[0]
    free = isinstance(problem["id"], int) and 0 < problem["id"] <= issued and not conn.execute(
        "SELECT 1 FROM public.problems WHERE id = ?", (problem["id"],)).fetchone()
    if free:
        conn.execute("INSERT INTO problems (id, title, link, difficulty, rating, source, is_custom)"
                     " VALUES (?, ?, ?, ?, ?, 'custom', 1)", (problem["id"],) + values)
        new_id = problem["id"]
    else:
        new_id = conn.execute("INSERT INTO problems (title, link, difficulty, rating, source, is_custom)"
                              " VALUES (?, ?, ?, ?, 'custom', 1)", values).lastrowid
    conn.executemany("INSERT INTO problem_patterns (problem_id, pattern_id) VALUES (?, ?)",
                     [(new_id, p) for p in sorted(patterns)])
    return new_id


def import_account(conn, copy):
    """Replace the account's data with a checked backup `copy` (an open SQLite connection),
    inside the caller's transaction."""
    clear_account(conn)
    pattern_ids = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM patterns")}
    patterns = {r[0]: pattern_ids.get(r[1]) for r in copy.execute("SELECT id, name FROM patterns")}

    copy_columns = {t: set(_columns(copy, t)) for t in USER_TABLES
                    if copy.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (t,)).fetchone()}
    used = set()
    for table, columns in PROBLEM_COLUMNS.items():
        for column in columns:
            if table in copy_columns and column in copy_columns[table]:
                used |= {r[0] for r in copy.execute(f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL")}
    used |= {r[0] for r in copy.execute("SELECT id FROM problems WHERE is_custom = 1")}
    problem_patterns = {}
    for problem_id, pattern_id in copy.execute("SELECT problem_id, pattern_id FROM problem_patterns"):
        if patterns.get(pattern_id):
            problem_patterns.setdefault(problem_id, set()).add(patterns[pattern_id])

    problems = {}
    for chunk in _chunks(sorted(used)):
        marks = ", ".join("?" * len(chunk))
        for r in copy.execute(f"SELECT id, title, link, difficulty, rating, is_custom FROM problems"
                              f" WHERE id IN ({marks})", chunk):
            problem = dict(zip(("id", "title", "link", "difficulty", "rating", "is_custom"), r))
            shared = None
            if not problem["is_custom"] and problem["link"]:
                shared = conn.execute("SELECT id FROM public.problems WHERE link = ? AND owner IS NULL",
                                      (problem["link"],)).fetchone()
            problems[problem["id"]] = shared[0] if shared else _new_problem(
                conn, problem, problem_patterns.get(problem["id"], ()))
    unchanged = all(old == new for old, new in problems.items()) and all(
        old == new for old, new in patterns.items() if new is not None)

    for table in USER_TABLES:
        if table not in copy_columns or (table in ID_BOUND and not unchanged):
            continue
        columns = [c for c in _columns(conn, table) if c in copy_columns[table] or c == "rowid"]
        rows = []
        # SQLite's rowid gives rating_history its order in either mode.
        for r in copy.execute(f"SELECT {', '.join(columns)} FROM {table} ORDER BY rowid"):
            row = dict(zip(columns, r))
            for column in PROBLEM_COLUMNS.get(table, ()):
                if column in row and row[column] is not None:
                    row[column] = problems.get(row[column])
            for column in PATTERN_COLUMNS.get(table, ()):
                row[column] = patterns.get(row[column])
            required = [c for c in PROBLEM_COLUMNS.get(table, ()) + PATTERN_COLUMNS.get(table, ())
                        if c in row and c != "review_of_problem_id"]
            if any(row[c] is None for c in required):
                continue  # A pattern this version does not have.
            if table in ("problem_links", "pattern_links") and not web_link(row.get("url")):
                continue  # Only web links are kept, as when added on the problem or pattern page.
            rows.append(tuple(row[c] for c in columns))
        if rows:
            conn.executemany(f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
                             rows)
        for column in ("id", "rowid"):
            if column in columns:
                conn.execute(f"SELECT setval(pg_get_serial_sequence('{table}', '{column}'),"
                             f" coalesce(max({column}), 0) + 1, false) FROM {table}")
    return {"unchanged": unchanged}


def keep(conn):
    """Keep the account's data for Undo, inside the caller's transaction (hosted mode)."""
    conn.execute("DELETE FROM kept_copy")
    conn.execute("INSERT INTO kept_copy (id, data) VALUES (1, ?)", (export_account(conn),))


def kept(conn):
    """The kept copy as an open SQLite connection, or None."""
    row = conn.execute("SELECT data FROM kept_copy WHERE id = 1").fetchone()
    if row is None:
        return None
    copy = sqlite3.connect(":memory:")
    copy.deserialize(bytes(row[0]))
    return copy

