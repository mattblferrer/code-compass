"""Database reads and writes used by the routes."""
import json
from datetime import date, timedelta

from .core import constants as c


def patterns(conn):
    return conn.execute("SELECT id, name, category, tier, description FROM patterns ORDER BY list_position").fetchall()


PICKER_COLUMNS = "id, title, source, difficulty, link, catalog_position, reserve_position, is_custom"

# Catalog first, then custom problems, then the reserve, then problems kept only for their attempts.
PICKER_ORDER = """CASE WHEN catalog_position IS NOT NULL THEN 0 WHEN is_custom = 1 THEN 1
                       WHEN reserve_position IS NOT NULL THEN 2 ELSE 3 END,
                  coalesce(catalog_position, reserve_position, id)"""


def problems_titled(conn, title):
    """Problems whose title matches, ignoring case."""
    return conn.execute(
        f"SELECT {PICKER_COLUMNS} FROM problems WHERE lower(title) = lower(?) ORDER BY {PICKER_ORDER}", (title,)
    ).fetchall()


def problems_titled_prefix(conn, text):
    """Problems whose title starts `text`, for matching a label like "Title (Source)"."""
    return conn.execute(
        f"""SELECT {PICKER_COLUMNS} FROM problems
            WHERE substr(lower(?), 1, length(title)) = lower(title) ORDER BY {PICKER_ORDER}""",
        (text,),
    ).fetchall()


def search_problems(conn, text, limit):
    """Problems whose title contains `text`, titles starting with it first."""
    pattern = "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    return conn.execute(
        f"""SELECT {PICKER_COLUMNS} FROM problems WHERE title LIKE ? ESCAPE '\\'
            ORDER BY substr(lower(title), 1, length(?)) != lower(?), {PICKER_ORDER} LIMIT ?""",
        (pattern, text, text, limit),
    ).fetchall()


def picker_row(conn, problem_id):
    return conn.execute(f"SELECT {PICKER_COLUMNS} FROM problems WHERE id = ?", (problem_id,)).fetchone()


def get_problem(conn, problem_id):
    return conn.execute("SELECT * FROM problems WHERE id = ?", (problem_id,)).fetchone()


def problem_by_link(conn, link):
    return conn.execute("SELECT * FROM problems WHERE link = ?", (link,)).fetchone()


def problem_patterns(conn, problem_id):
    return [
        row["name"] for row in conn.execute(
            """SELECT pt.name FROM problem_patterns pp JOIN patterns pt ON pt.id = pp.pattern_id
               WHERE pp.problem_id = ? ORDER BY pt.list_position""",
            (problem_id,),
        )
    ]


def add_custom_problem(conn, values):
    with conn:
        problem_id = conn.execute(
            "INSERT INTO problems (title, link, difficulty, rating, source, is_custom) VALUES (?, ?, ?, ?, 'custom', 1)",
            (values["title"], values["link"], values["difficulty"], values.get("rating")),
        ).lastrowid
        conn.executemany(
            "INSERT INTO problem_patterns (problem_id, pattern_id) SELECT ?, id FROM patterns WHERE name = ?",
            [(problem_id, name) for name in values["patterns"]],
        )
    return problem_id


def unused_hint(conn, problem_id):
    return conn.execute(
        "SELECT 1 FROM hint_reveals WHERE problem_id = ? AND used = 0 LIMIT 1", (problem_id,)
    ).fetchone() is not None


def add_attempt(conn, values, entry_method="manual"):
    with conn:
        attempt_id = conn.execute(
            """INSERT INTO attempts (problem_id, date, outcome, time_seconds, notes, entry_method, review_of_problem_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (values["problem_id"], values["date"], values["outcome"], values["time_seconds"],
             values["notes"], entry_method, values.get("review_of_problem_id")),
        ).lastrowid
        conn.execute("UPDATE hint_reveals SET used = 1 WHERE problem_id = ? AND used = 0", (values["problem_id"],))
    return attempt_id


def get_attempt(conn, attempt_id):
    return conn.execute(
        """SELECT a.*, p.title, p.source FROM attempts a JOIN problems p ON p.id = a.problem_id
           WHERE a.id = ?""",
        (attempt_id,),
    ).fetchone()


def update_attempt(conn, attempt_id, values):
    with conn:
        conn.execute(
            """UPDATE attempts SET problem_id = ?, date = ?, outcome = ?, time_seconds = ?, notes = ?,
                   review_of_problem_id = ? WHERE id = ?""",
            (values["problem_id"], values["date"], values["outcome"], values["time_seconds"],
             values["notes"], values.get("review_of_problem_id"), attempt_id),
        )


def delete_attempt(conn, attempt_id, today):
    """Delete an attempt, keeping a copy so it can be restored. Returns the copy's id."""
    row = dict(conn.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone())
    with conn:
        conn.execute("DELETE FROM attempts WHERE id = ?", (attempt_id,))
        return _keep_deleted(conn, "attempt", row, today)


def attempts_for_problem(conn, problem_id):
    """Oldest first, in logged order (R-06)."""
    return conn.execute(
        "SELECT * FROM attempts WHERE problem_id = ? ORDER BY date, id", (problem_id,)
    ).fetchall()


def recent_attempts(conn, limit=50, until=None):
    """The latest attempts, newest first; with `until`, the latest on or before that date."""
    return conn.execute(
        """SELECT a.*, p.title, p.source FROM attempts a JOIN problems p ON p.id = a.problem_id
           WHERE ? IS NULL OR a.date <= ?
           ORDER BY a.date DESC, a.id DESC LIMIT ?""",
        (until, until, limit),
    ).fetchall()


def read_settings(conn):
    """Saved settings as {"settings": {key: value}, "preferences": {pattern: pref}, "hidden": {(site, kind)}}.

    Settings that were never saved are missing; the caller supplies defaults.
    """
    return {
        "settings": {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")},
        "preferences": {r["name"]: r["preference"] for r in conn.execute(
            "SELECT pt.name, pp.preference FROM pattern_preferences pp JOIN patterns pt ON pt.id = pp.pattern_id"
        )},
        "hidden": {(r["site"], r["category"]) for r in conn.execute("SELECT site, category FROM hidden_sites")},
    }


DEFAULT_SETTINGS = {"starting_difficulty": "easy", "advanced_on": "0", "very_hard_on": "0"}


def current_settings(conn):
    """Saved settings over the defaults, with "preferences" ({pattern: "target" or "mastered"})
    and "hidden" ({(site, kind)}). The settings page and Snapshot both read them here."""
    saved = read_settings(conn)
    return {**DEFAULT_SETTINGS, **saved["settings"], "preferences": saved["preferences"], "hidden": saved["hidden"]}


def save_settings(conn, values):
    """Replace all settings, pattern preferences, and hidden sites in one transaction (R-13, R-32, R-36)."""
    pattern_ids = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM patterns")}
    with conn:
        for key in ("starting_difficulty", "advanced_on", "very_hard_on"):
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                (key, values[key]),
            )
        conn.execute("DELETE FROM pattern_preferences")
        conn.executemany(
            "INSERT INTO pattern_preferences (pattern_id, preference) VALUES (?, ?)",
            [(pattern_ids[name], pref) for name, pref in values["preferences"].items()],
        )
        conn.execute("DELETE FROM hidden_sites")
        conn.executemany("INSERT INTO hidden_sites (site, category) VALUES (?, ?)", sorted(values["hidden"]))


def interviews(conn):
    """All interviews, soonest first, each with its pattern names in pattern-list order."""
    rows = [dict(r) for r in conn.execute("SELECT * FROM interviews ORDER BY date, id")]
    for row in rows:
        row["patterns"] = [r["name"] for r in conn.execute(
            """SELECT pt.name FROM interview_patterns ip JOIN patterns pt ON pt.id = ip.pattern_id
               WHERE ip.interview_id = ? ORDER BY pt.list_position""",
            (row["id"],),
        )]
    return rows


def get_interview(conn, interview_id):
    return next((i for i in interviews(conn) if i["id"] == interview_id), None)


def save_interview(conn, values, interview_id=None):
    """Add an interview, or replace one when `interview_id` is given. Returns its id."""
    pattern_ids = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM patterns")}
    with conn:
        if interview_id is None:
            interview_id = conn.execute(
                "INSERT INTO interviews (company, date, target_difficulty) VALUES (?, ?, ?)",
                (values["company"], values["date"], values["target_difficulty"]),
            ).lastrowid
        else:
            conn.execute("UPDATE interviews SET company = ?, date = ?, target_difficulty = ? WHERE id = ?",
                         (values["company"], values["date"], values["target_difficulty"], interview_id))
            conn.execute("DELETE FROM interview_patterns WHERE interview_id = ?", (interview_id,))
        conn.executemany("INSERT INTO interview_patterns (interview_id, pattern_id) VALUES (?, ?)",
                         [(interview_id, pattern_ids[name]) for name in values["patterns"]])
    return interview_id


def delete_interview(conn, interview_id, today):
    """Delete an interview, keeping a copy so it can be restored. Returns the copy's id."""
    row = get_interview(conn, interview_id)
    with conn:
        conn.execute("DELETE FROM interview_patterns WHERE interview_id = ?", (interview_id,))
        conn.execute("DELETE FROM interviews WHERE id = ?", (interview_id,))
        return _keep_deleted(conn, "interview", row, today)


def _keep_deleted(conn, kind, payload, today):
    """Store a deleted row, and drop copies older than c.UNDO_DAYS. Runs inside the caller's transaction."""
    cutoff = (date.fromisoformat(today) - timedelta(days=c.UNDO_DAYS)).isoformat()
    conn.execute("DELETE FROM deleted_items WHERE date < ?", (cutoff,))
    return conn.execute("INSERT INTO deleted_items (kind, payload, date) VALUES (?, ?, ?)",
                        (kind, json.dumps(payload), today)).lastrowid


def restore_deleted(conn, item_id, today):
    """Put a deleted attempt or interview back, under its old id when that id is still free.

    Returns (kind, restored row); ("missing_problem", row) when the attempt's problem is no
    longer in the database (a catalog or reserve reload can remove a problem left with no
    attempts); or None if the copy is gone, was already restored, or is older than c.UNDO_DAYS.
    """
    item = conn.execute("SELECT * FROM deleted_items WHERE id = ?", (item_id,)).fetchone()
    if item is None:
        return None
    cutoff = (date.fromisoformat(today) - timedelta(days=c.UNDO_DAYS)).isoformat()
    if item["date"] < cutoff:
        with conn:
            conn.execute("DELETE FROM deleted_items WHERE id = ?", (item_id,))
        return None
    row = json.loads(item["payload"])
    if item["kind"] == "attempt":
        if not get_problem(conn, row["problem_id"]):
            return "missing_problem", row
        if row.get("review_of_problem_id") and not get_problem(conn, row["review_of_problem_id"]):
            row["review_of_problem_id"] = None  # The review it completed is gone; the attempt still counts.
    with conn:
        if item["kind"] == "attempt":
            taken = conn.execute("SELECT 1 FROM attempts WHERE id = ?", (row["id"],)).fetchone()
            values = {k: v for k, v in row.items() if not (k == "id" and taken)}
            columns = ", ".join(values)
            new_id = conn.execute(f"INSERT INTO attempts ({columns}) VALUES ({', '.join('?' * len(values))})",
                                  tuple(values.values())).lastrowid
            row["id"] = row["id"] if not taken else new_id
        else:
            taken = conn.execute("SELECT 1 FROM interviews WHERE id = ?", (row["id"],)).fetchone()
            if taken:
                new_id = conn.execute("INSERT INTO interviews (company, date, target_difficulty) VALUES (?, ?, ?)",
                                      (row["company"], row["date"], row["target_difficulty"])).lastrowid
            else:
                new_id = conn.execute(
                    "INSERT INTO interviews (id, company, date, target_difficulty) VALUES (?, ?, ?, ?)",
                    (row["id"], row["company"], row["date"], row["target_difficulty"])).lastrowid
            pattern_ids = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM patterns")}
            conn.executemany("INSERT INTO interview_patterns (interview_id, pattern_id) VALUES (?, ?)",
                             [(new_id, pattern_ids[n]) for n in row["patterns"] if n in pattern_ids])
            row["id"] = new_id
        conn.execute("DELETE FROM deleted_items WHERE id = ?", (item_id,))
    return item["kind"], row


def all_attempts(conn):
    """Every attempt in logged order (R-19)."""
    return [dict(r) for r in conn.execute("SELECT * FROM attempts ORDER BY id")]


def _chunks(items, size=500):
    """Slices of `items` small enough for one SQL IN (...) list."""
    items = list(items)
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _with_patterns(conn, rows):
    result = {r["id"]: {**dict(r), "patterns": []} for r in rows}
    for chunk in _chunks(result):
        for r in conn.execute(
            f"""SELECT pp.problem_id, pt.name FROM problem_patterns pp JOIN patterns pt ON pt.id = pp.pattern_id
                WHERE pp.problem_id IN ({', '.join('?' * len(chunk))}) ORDER BY pt.list_position""",
            chunk,
        ):
            result[r["problem_id"]]["patterns"].append(r["name"])
    return result


PROBLEM_FIELDS = "id, title, link, difficulty, rating"


def problems_by_id(conn, ids):
    """{id: {title, link, difficulty, rating, patterns}} for the given ids only."""
    rows = []
    for chunk in _chunks(set(ids)):
        rows += conn.execute(f"SELECT {PROBLEM_FIELDS} FROM problems WHERE id IN ({', '.join('?' * len(chunk))})",
                             chunk).fetchall()
    return _with_patterns(conn, rows)


def problems_matching(conn, links, titles):
    """Problems whose link is in `links` or whose lower-case title is in `titles`, as problems_by_id
    gives them. CSV import needs only these, not the whole catalog and reserve."""
    rows = {}
    for column, values in (("link", links), ("lower(title)", titles)):
        for chunk in _chunks(set(values)):
            for r in conn.execute(
                f"SELECT {PROBLEM_FIELDS} FROM problems WHERE {column} IN ({', '.join('?' * len(chunk))})", chunk
            ):
                rows[r["id"]] = r
    return _with_patterns(conn, rows.values())


def apply_import(conn, plan):
    """Create the planned custom problems and add the planned attempts, all in one transaction (R-19)."""
    ids = {}
    with conn:
        for p in plan["new_problems"]:
            ids[p["key"]] = conn.execute(
                "INSERT INTO problems (title, link, difficulty, rating, source, is_custom) VALUES (?, ?, ?, ?, 'custom', 1)",
                (p["title"], p["link"], p["difficulty"], p.get("rating")),
            ).lastrowid
            conn.executemany(
                "INSERT INTO problem_patterns (problem_id, pattern_id) SELECT ?, id FROM patterns WHERE name = ?",
                [(ids[p["key"]], name) for name in p["patterns"]],
            )
        conn.executemany(
            """INSERT INTO attempts (problem_id, date, outcome, time_seconds, notes, entry_method, review_of_problem_id)
               VALUES (?, ?, ?, ?, ?, 'csv', ?)""",
            [(ids.get(a["problem"], a["problem"]), a["date"], a["outcome"], a["time_seconds"], a["notes"],
              ids.get(a["review_of"], a["review_of"])) for a in plan["attempts"]],
        )
        # As when logging, an attempt uses up a revealed hint on its problem (R-27).
        conn.executemany("UPDATE hint_reveals SET used = 1 WHERE problem_id = ? AND used = 0",
                         [(a["problem"],) for a in plan["attempts"] if a["problem"] not in ids])


def unused_hints(conn):
    """Problems with a revealed beginner hint not yet used by an attempt (R-27)."""
    return {row["problem_id"] for row in conn.execute("SELECT DISTINCT problem_id FROM hint_reveals WHERE used = 0")}
