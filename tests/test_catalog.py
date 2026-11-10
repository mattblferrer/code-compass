"""Schema, data files, and the catalog loader (R-01, R-22)."""
import csv
import re
from pathlib import Path

import pytest

from codecompass import catalog, create_app
from codecompass.core.catalog_rows import DataFileError, parse_catalog
from codecompass.db import connect, init_db

ROOT = Path(__file__).resolve().parent.parent
HEADER = ["title", "link", "difficulty", "rating", "source", "patterns"]


def write_catalog(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerows(rows)


@pytest.fixture
def conn(tmp_path):
    path = str(tmp_path / "db.sqlite")
    init_db(path)
    conn = connect(path)
    yield conn
    conn.close()


@pytest.fixture
def catalog_file(tmp_path):
    return tmp_path / "catalog.csv"


def load(conn, catalog_file):
    catalog.load(conn, catalog.DATA_DIR / "patterns.csv", catalog_file)


def problems(conn):
    rows = conn.execute(
        """SELECT p.link, p.title, p.difficulty, p.rating, p.catalog_position,
                  group_concat(pt.name, ';') AS patterns
           FROM problems p
           LEFT JOIN problem_patterns pp ON pp.problem_id = p.id
           LEFT JOIN patterns pt ON pt.id = pp.pattern_id
           GROUP BY p.id ORDER BY p.id"""
    )
    return [dict(r) for r in rows]


def test_patterns_file_matches_docs():
    expected, category = [], None
    for line in (ROOT / "docs" / "patterns.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            category = "core" if line.startswith("## Core") else "advanced" if line.startswith("## Advanced") else None
        match = re.match(r"^\| (\d+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|", line)
        if match and category:
            expected.append([match.group(2).strip(), category, match.group(3).strip().lower(),
                             match.group(4).strip(), match.group(5).strip()])
    rows = catalog.read_rows(catalog.DATA_DIR / "patterns.csv")
    assert [[r["name"], r["category"], r["tier"], r["family"], r["description"]] for r in rows] == expected


def test_schema_and_load_are_rerunnable(db_path):
    create_app({"TESTING": True, "DATABASE": db_path})
    create_app({"TESTING": True, "DATABASE": db_path})
    conn = connect(db_path)
    assert conn.execute("SELECT count(*) FROM patterns").fetchone()[0] == 54
    conn.close()


def test_load_adds_and_updates_by_link(conn, catalog_file):
    write_catalog(catalog_file, [
        ["Two Sum", "https://example.com/a", "easy", "", "List A", "Arrays and Hashing"],
        ["Flows", "https://example.com/b", "very hard", "2400", "Codeforces", "Max Flow and Min Cut; Greedy"],
    ])
    load(conn, catalog_file)
    write_catalog(catalog_file, [
        ["Two Sum (renamed)", "https://example.com/a", "medium", "", "List A", "Sorting"],
        ["Flows", "https://example.com/b", "very hard", "2400", "Codeforces", "Max Flow and Min Cut; Greedy"],
    ])
    load(conn, catalog_file)
    rows = problems(conn)
    assert len(rows) == 2
    assert rows[0] == {"link": "https://example.com/a", "title": "Two Sum (renamed)", "difficulty": "medium",
                       "rating": None, "catalog_position": 1, "patterns": "Sorting"}
    assert rows[1]["rating"] == 2400
    assert sorted(rows[1]["patterns"].split(";")) == ["Greedy", "Max Flow and Min Cut"]


def test_removed_problem_kept_only_with_attempts(conn, catalog_file):
    write_catalog(catalog_file, [
        ["Kept", "https://example.com/kept", "easy", "", "List", "Stack"],
        ["Dropped", "https://example.com/dropped", "easy", "", "List", "Stack"],
    ])
    load(conn, catalog_file)
    kept_id = conn.execute("SELECT id FROM problems WHERE title = 'Kept'").fetchone()["id"]
    with conn:
        conn.execute(
            "INSERT INTO attempts (problem_id, date, outcome, entry_method) VALUES (?, '2026-11-01', 'solved_alone', 'manual')",
            (kept_id,),
        )
    write_catalog(catalog_file, [])
    load(conn, catalog_file)
    rows = problems(conn)
    assert [(r["title"], r["catalog_position"]) for r in rows] == [("Kept", None)]
    assert conn.execute("SELECT count(*) FROM attempts").fetchone()[0] == 1


def test_custom_problems_are_left_alone(conn, catalog_file):
    with conn:
        conn.execute("INSERT INTO problems (title, difficulty, source, is_custom) VALUES ('Mine', 'easy', 'custom', 1)")
    write_catalog(catalog_file, [])
    load(conn, catalog_file)
    assert [r["title"] for r in problems(conn)] == ["Mine"]


def test_invalid_file_changes_nothing(conn, catalog_file):
    write_catalog(catalog_file, [["Good", "https://example.com/good", "easy", "", "List", "Stack"]])
    load(conn, catalog_file)
    write_catalog(catalog_file, [
        ["Good", "https://example.com/good", "hard", "", "List", "Stack"],
        ["", "https://example.com/bad", "impossible", "x", "", "Nope"],
    ])
    with pytest.raises(DataFileError) as error:
        load(conn, catalog_file)
    message = str(error.value)
    assert "row 3" in message
    for part in ("title is missing", "difficulty must be", "rating must be", "source is missing", "unknown pattern: Nope"):
        assert part in message
    assert problems(conn)[0]["difficulty"] == "easy"


@pytest.mark.parametrize("row, error", [
    (["A", "l1", "very hard", "", "S", "Stack"], "very hard problems need at least one advanced pattern"),
    (["A", "", "easy", "", "S", "Stack"], "link is missing"),
    (["A", "l1", "easy", "", "S", ""], "at least one pattern is required"),
])
def test_catalog_row_errors(row, error):
    with pytest.raises(DataFileError, match=error):
        parse_catalog([dict(zip(HEADER, row))], {"Stack": "core"})


def test_duplicate_links_rejected():
    rows = [dict(zip(HEADER, ["A", "l1", "easy", "", "S", "Stack"]))] * 2
    with pytest.raises(DataFileError, match="row 3: link appears more than once"):
        parse_catalog(rows, {"Stack": "core"})


def test_negative_atcoder_rating_allowed():
    rows = [dict(zip(HEADER, ["A", "l1", "easy", "-848", "AtCoder", "Stack"]))]
    assert parse_catalog(rows, {"Stack": "core"})[0]["rating"] == -848


def test_family_column_added_to_an_older_database(tmp_path):
    path = str(tmp_path / "old.sqlite")
    conn = connect(path)
    conn.execute(
        """CREATE TABLE patterns (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, category TEXT NOT NULL,
           tier TEXT NOT NULL, description TEXT NOT NULL, list_position INTEGER NOT NULL)"""
    )
    conn.close()
    init_db(path)
    init_db(path)
    conn = connect(path)
    assert "family" in {r["name"] for r in conn.execute("PRAGMA table_info(patterns)")}
    conn.close()


def test_shipped_catalog_is_valid():
    """R-01 verification, part 1: the real catalog file passes the validator.

    Every entry has a title, link, difficulty, source, and at least one pattern
    from the documented list, and there are at least 500 entries.
    """
    patterns = catalog.read_rows(catalog.DATA_DIR / "patterns.csv")
    categories = {p["name"]: p["category"] for p in patterns}
    rows = parse_catalog(catalog.read_rows(catalog.DATA_DIR / "catalog.csv"), categories, "catalog.csv")
    assert len(rows) >= 500
    for row in rows:
        assert row["title"] and row["link"] and row["source"]
        assert row["difficulty"] in {"easy", "medium", "hard", "very hard"}
        assert row["patterns"] and set(row["patterns"]) <= set(categories)


def test_shipped_reserve_is_valid():
    """The real reserve file passes the validator in reserve mode (R-37).

    Every entry has all five fields and only documented patterns. Unlike the
    catalog, a very hard reserve problem may have only core patterns.
    """
    patterns = catalog.read_rows(catalog.DATA_DIR / "patterns.csv")
    categories = {p["name"]: p["category"] for p in patterns}
    rows = parse_catalog(catalog.read_rows(catalog.DATA_DIR / "reserve.csv"), categories, "reserve.csv",
                         reserve=True)
    assert {row["source"] for row in rows} == {"Codeforces API", "AtCoder"}
    for row in rows:
        assert row["title"] and row["link"] and row["rating"] is not None
        assert row["difficulty"] in {"easy", "medium", "hard", "very hard"}
        assert row["patterns"] and set(row["patterns"]) <= set(categories)
