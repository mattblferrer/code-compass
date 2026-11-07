"""Load the pattern list and problem catalog from the data files at each start."""
import csv
from pathlib import Path

from .core.catalog_rows import parse_catalog, parse_patterns
from .db import connect

DATA_DIR = Path(__file__).with_name("data")


def read_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load(conn, patterns_path, catalog_path):
    """Add or update patterns by name and catalog problems by link.

    Attempts and custom problems are left alone. A catalog problem missing from
    the file is deleted if it has no attempts, and otherwise kept but taken out
    of the catalog. Raises DataFileError, and changes nothing, if a file is invalid.
    """
    patterns = parse_patterns(read_rows(patterns_path), Path(patterns_path).name)
    categories = {p["name"]: p["category"] for p in patterns}
    problems = parse_catalog(read_rows(catalog_path), categories, Path(catalog_path).name)

    with conn:
        for position, p in enumerate(patterns, start=1):
            conn.execute(
                """INSERT INTO patterns (name, category, tier, family, description, list_position)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT (name) DO UPDATE SET category = excluded.category, tier = excluded.tier,
                       family = excluded.family, description = excluded.description,
                       list_position = excluded.list_position""",
                (p["name"], p["category"], p["tier"], p["family"], p["description"], position),
            )
        pattern_ids = {row["name"]: row["id"] for row in conn.execute("SELECT id, name FROM patterns")}

        for position, p in enumerate(problems, start=1):
            existing = conn.execute("SELECT id FROM problems WHERE link = ?", (p["link"],)).fetchone()
            values = (p["title"], p["difficulty"], p["rating"], p["source"], position)
            if existing:
                problem_id = existing["id"]
                conn.execute(
                    """UPDATE problems SET title = ?, difficulty = ?, rating = ?, source = ?,
                           catalog_position = ?, is_custom = 0 WHERE id = ?""",
                    values + (problem_id,),
                )
                conn.execute("DELETE FROM problem_patterns WHERE problem_id = ?", (problem_id,))
            else:
                problem_id = conn.execute(
                    """INSERT INTO problems (title, difficulty, rating, source, catalog_position, link, is_custom)
                       VALUES (?, ?, ?, ?, ?, ?, 0)""",
                    values + (p["link"],),
                ).lastrowid
            conn.executemany(
                "INSERT INTO problem_patterns (problem_id, pattern_id) VALUES (?, ?)",
                [(problem_id, pattern_ids[name]) for name in p["patterns"]],
            )

        links = {p["link"] for p in problems}
        stale = [
            row for row in conn.execute(
                "SELECT id, link FROM problems WHERE is_custom = 0 AND catalog_position IS NOT NULL"
            )
            if row["link"] not in links
        ]
        for row in stale:
            has_attempts = conn.execute(
                "SELECT 1 FROM attempts WHERE problem_id = ? OR review_of_problem_id = ? LIMIT 1",
                (row["id"], row["id"]),
            ).fetchone()
            if has_attempts:
                conn.execute("UPDATE problems SET catalog_position = NULL WHERE id = ?", (row["id"],))
            else:
                conn.execute("DELETE FROM problems WHERE id = ?", (row["id"],))


def init_app(app):
    conn = connect(app.config["DATABASE"])
    try:
        load(conn, app.config["PATTERNS_PATH"], app.config["CATALOG_PATH"])
    finally:
        conn.close()
