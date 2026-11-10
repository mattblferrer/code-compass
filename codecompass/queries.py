"""Database reads and writes used by the routes."""


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
            "INSERT INTO problems (title, link, difficulty, source, is_custom) VALUES (?, ?, ?, 'custom', 1)",
            (values["title"], values["link"], values["difficulty"]),
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


def delete_attempt(conn, attempt_id):
    with conn:
        conn.execute("DELETE FROM attempts WHERE id = ?", (attempt_id,))


def attempts_for_problem(conn, problem_id):
    """Oldest first, in logged order (R-06)."""
    return conn.execute(
        "SELECT * FROM attempts WHERE problem_id = ? ORDER BY date, id", (problem_id,)
    ).fetchall()


def recent_attempts(conn, limit=50):
    return conn.execute(
        """SELECT a.*, p.title, p.source FROM attempts a JOIN problems p ON p.id = a.problem_id
           ORDER BY a.date DESC, a.id DESC LIMIT ?""",
        (limit,),
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
