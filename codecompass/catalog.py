"""Load the pattern list, problem catalog, and reserve from the data files at each start."""
import csv
import hashlib
import json
from pathlib import Path

import click

from .core.catalog_rows import parse_catalog, parse_patterns
from .core.reserve import UNMAPPED_HEADER, reserve_rows, unmapped_rows
from .db import connect

DATA_DIR = Path(__file__).with_name("data")
HEADER = ["title", "link", "difficulty", "rating", "source", "patterns"]

# Change this when the loader's behavior changes, so unchanged files load again.
LOADER_VERSION = "2"


def read_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def fingerprint(*paths):
    """A hash of the loader version and each file's bytes, so unchanged files can be skipped."""
    digest = hashlib.sha256(LOADER_VERSION.encode())
    for path in paths:
        digest.update(b"\0")
        if path:
            digest.update(str(Path(path).name).encode())
            digest.update(Path(path).read_bytes())
    return digest.hexdigest()


def load(conn, patterns_path, catalog_path, reserve_path=None):
    """Add or update patterns by name, and catalog and reserve problems by link.

    Attempts and custom problems are left alone. A reserve row whose link is in
    the catalog is skipped, so the catalog's reviewed entry wins (R-37). A problem
    missing from both files is deleted if it has no attempts, and otherwise kept
    but taken out of the catalog and reserve. Raises DataFileError, and changes
    nothing, if a file is invalid.
    """
    patterns = parse_patterns(read_rows(patterns_path), Path(patterns_path).name)
    categories = {p["name"]: p["category"] for p in patterns}
    problems = parse_catalog(read_rows(catalog_path), categories, Path(catalog_path).name)
    reserve = []
    if reserve_path:
        reserve = parse_catalog(read_rows(reserve_path), categories, Path(reserve_path).name, reserve=True)
    main_links = {p["link"] for p in problems}
    reserve = [p for p in reserve if p["link"] not in main_links]

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
        existing = {row["link"]: row["id"] for row in conn.execute("SELECT id, link FROM problems WHERE link IS NOT NULL")}

        updates, links = [], []
        entries = [(p, position, None) for position, p in enumerate(problems, start=1)]
        entries += [(p, None, position) for position, p in enumerate(reserve, start=1)]
        for p, catalog_position, reserve_position in entries:
            values = (p["title"], p["difficulty"], p["rating"], p["source"], catalog_position, reserve_position)
            problem_id = existing.get(p["link"])
            if problem_id:
                updates.append(values + (problem_id,))
            else:
                problem_id = conn.execute(
                    """INSERT INTO problems (title, difficulty, rating, source, catalog_position, reserve_position,
                           link, is_custom) VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
                    values + (p["link"],),
                ).lastrowid
            links.extend((problem_id, pattern_ids[name]) for name in p["patterns"])
        conn.executemany(
            """UPDATE problems SET title = ?, difficulty = ?, rating = ?, source = ?, catalog_position = ?,
                   reserve_position = ?, is_custom = 0 WHERE id = ?""",
            updates,
        )
        conn.executemany("DELETE FROM problem_patterns WHERE problem_id = ?", [(u[-1],) for u in updates])
        conn.executemany("INSERT INTO problem_patterns (problem_id, pattern_id) VALUES (?, ?)", links)

        kept = main_links | {p["link"] for p in reserve}
        stale = [
            row for row in conn.execute(
                """SELECT id, link FROM problems
                   WHERE is_custom = 0 AND (catalog_position IS NOT NULL OR reserve_position IS NOT NULL)"""
            )
            if row["link"] not in kept
        ]
        for row in stale:
            has_attempts = conn.execute(
                "SELECT 1 FROM attempts WHERE problem_id = ? OR review_of_problem_id = ? LIMIT 1",
                (row["id"], row["id"]),
            ).fetchone()
            if has_attempts:
                conn.execute(
                    "UPDATE problems SET catalog_position = NULL, reserve_position = NULL WHERE id = ?", (row["id"],)
                )
            else:
                conn.execute("DELETE FROM problems WHERE id = ?", (row["id"],))


def load_if_changed(conn, patterns_path, catalog_path, reserve_path=None):
    """Load the files unless they are unchanged since the last load. Returns True if loaded."""
    stamp = fingerprint(patterns_path, catalog_path, reserve_path)
    row = conn.execute("SELECT value FROM app_meta WHERE key = 'data_fingerprint'").fetchone()
    if row and row["value"] == stamp:
        return False
    load(conn, patterns_path, catalog_path, reserve_path)
    with conn:
        conn.execute(
            """INSERT INTO app_meta (key, value) VALUES ('data_fingerprint', ?)
               ON CONFLICT (key) DO UPDATE SET value = excluded.value""",
            (stamp,),
        )
    return True


def _write_csv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def read_corrections(path):
    """{link: {"add": [...], "remove": [...]}} from a reserve corrections file, or {}."""
    if not path or not Path(path).exists():
        return {}
    split = lambda text: [p.strip() for p in text.split(";") if p.strip()]  # noqa: E731
    return {r["link"]: {"add": split(r["add"]), "remove": split(r["remove"])} for r in read_rows(path)}


def write_reserve(problemset_path, patterns_path, out_path, unmapped_path=None, corrections_path=None):
    """Write the reserve file, and optionally the unmapped list, from a saved
    `problemset.problems` response. Returns (reserve rows, unmapped rows)."""
    data = json.loads(Path(problemset_path).read_text(encoding="utf-8"))
    if data.get("status") != "OK":
        raise click.ClickException("The file is not a successful problemset.problems response.")
    order = [p["name"] for p in parse_patterns(read_rows(patterns_path), Path(patterns_path).name)]
    rows = reserve_rows(data["result"], order, read_corrections(corrections_path))
    _write_csv(out_path, HEADER, rows)
    unmapped = unmapped_rows(data["result"], order)
    if unmapped_path:
        _write_csv(unmapped_path, UNMAPPED_HEADER, unmapped)
    return len(rows), len(unmapped)


def find_unmapped(path, link=None, title=None):
    """The unmapped Codeforces problem with this link, or the only one with this
    title (ignoring case), as a dict; None if there is none or no file."""
    if not path or not Path(path).exists():
        return None
    rows = read_rows(path)
    if link:
        return next((r for r in rows if r["link"] == link), None)
    if title:
        matches = [r for r in rows if r["title"].lower() == title.lower()]
        return matches[0] if len(matches) == 1 else None
    return None


@click.command("build-reserve")
@click.argument("problemset", type=click.Path(exists=True, dir_okay=False))
def build_reserve_command(problemset):
    """Build data/reserve.csv and data/codeforces_unmapped.csv from a saved
    Codeforces problemset.problems response.

    Download it yourself first, for example with
    curl -o problemset.json https://codeforces.com/api/problemset.problems
    """
    count, unmapped = write_reserve(problemset, DATA_DIR / "patterns.csv", DATA_DIR / "reserve.csv",
                                    DATA_DIR / "codeforces_unmapped.csv", DATA_DIR / "reserve_corrections.csv")
    click.echo(f"Wrote {count} problems to {DATA_DIR / 'reserve.csv'} and {unmapped} problems the reserve "
               f"cannot hold to {DATA_DIR / 'codeforces_unmapped.csv'}.")


def init_app(app):
    conn = connect(app.config["DATABASE"])
    try:
        load_if_changed(conn, app.config["PATTERNS_PATH"], app.config["CATALOG_PATH"], app.config.get("RESERVE_PATH"))
    finally:
        conn.close()
    app.cli.add_command(build_reserve_command)
