"""The unreviewed Codeforces reserve: tag mapping, building, and loading (R-37)."""
import csv
import re
from pathlib import Path

import pytest

from codecompass import catalog
from codecompass.core.catalog_rows import DataFileError
from codecompass.core.codeforces_tags import BROAD, DIRECT, PAIRS, patterns_for
from codecompass.core.reserve import reserve_rows
from codecompass.db import connect, init_db

ROOT = Path(__file__).resolve().parent.parent
ORDER = [r["name"] for r in catalog.read_rows(catalog.DATA_DIR / "patterns.csv")]


def write(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(catalog.HEADER)
        writer.writerows(rows)
    return path


@pytest.fixture
def conn(tmp_path):
    path = str(tmp_path / "db.sqlite")
    init_db(path)
    conn = connect(path)
    yield conn
    conn.close()


def rows(conn):
    return {r["link"]: dict(r) for r in conn.execute(
        "SELECT link, title, difficulty, catalog_position, reserve_position, is_custom FROM problems"
    )}


# --- Tag mapping ---

def test_mapping_matches_patterns_doc():
    """Every tag the code maps is listed for that pattern in docs/patterns.md."""
    listed = {}
    for line in (ROOT / "docs" / "patterns.md").read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\| \d+ \| ([^|]+) \|(?:[^|]*\|){4} ([^|]+) \|$", line)
        if match:
            listed[match.group(1).strip()] = {t.strip() for t in match.group(2).split(",")}
    for tag, name in DIRECT.items():
        assert tag in listed[name], (tag, name)
    for pair, name in PAIRS.items():
        assert pair <= listed[name], (pair, name)
    assert not BROAD & set(DIRECT)


@pytest.mark.parametrize("tags, expected", [
    (["greedy", "sortings"], ["Sorting", "Greedy"]),
    (["math", "dp", "data structures"], []),
    (["trees", "dp"], ["Tree DP"]),
    (["bitmasks", "dp"], ["Bit Manipulation", "Bitmask DP"]),
    (["graphs", "dsu", "*special"], ["Union-Find", "Minimum Spanning Tree"]),
    (["fft", "math"], ["FFT and NTT"]),
    (["communication"], []),
])
def test_patterns_for(tags, expected):
    assert patterns_for(tags, ORDER) == expected


# --- Building the reserve file ---

def problem(contest, index, name, rating=None, tags=(), kind="PROGRAMMING"):
    p = {"contestId": contest, "index": index, "name": name, "type": kind, "tags": list(tags)}
    if rating:
        p["rating"] = rating
    return p


def test_reserve_rows_filters_and_orders():
    result = {
        "problems": [
            problem(1, "A", "Popular", 800, ["greedy"]),
            problem(2, "B", "Less popular", 2400, ["dp", "trees"]),
            problem(3, "C", "Unrated", None, ["greedy"]),
            problem(4, "D", "Only broad", 1500, ["math", "dp"]),
            problem(5, "E", "Special", 1500, ["greedy", "*special"]),
            problem(6, "F", "Question", 1500, ["greedy"], kind="QUESTION"),
            problem(7, "A1", "Easy version", 1300, ["implementation"]),
        ],
        "problemStatistics": [
            {"contestId": 1, "index": "A", "solvedCount": 500},
            {"contestId": 2, "index": "B", "solvedCount": 9000},
            {"contestId": 7, "index": "A1", "solvedCount": 100},
        ],
    }
    out = reserve_rows(result, ORDER)
    assert [r["title"] for r in out] == ["Less popular", "Popular", "Easy version"]
    assert out[0] == {
        "title": "Less popular", "link": "https://codeforces.com/problemset/problem/2/B",
        "difficulty": "very hard", "rating": 2400, "source": "Codeforces API", "patterns": "Tree DP",
    }
    assert out[2]["link"] == "https://codeforces.com/problemset/problem/7/A1"
    assert out[2]["difficulty"] == "medium"


def test_write_reserve_from_saved_response(tmp_path):
    saved = tmp_path / "problemset.json"
    saved.write_text('{"status": "OK", "result": {"problems": [{"contestId": 1, "index": "A", "name": "X",'
                     ' "type": "PROGRAMMING", "rating": 900, "tags": ["greedy"]}], "problemStatistics": []}}',
                     encoding="utf-8")
    out = tmp_path / "reserve.csv"
    assert catalog.write_reserve(saved, catalog.DATA_DIR / "patterns.csv", out) == 1
    assert catalog.read_rows(out)[0]["patterns"] == "Greedy"


# --- Loading ---

def test_reserve_loads_after_catalog_and_catalog_wins(conn, tmp_path):
    main = write(tmp_path / "catalog.csv", [
        ["Reviewed", "https://codeforces.com/problemset/problem/1/A", "easy", "800", "Codeforces API", "Greedy"],
    ])
    reserve = write(tmp_path / "reserve.csv", [
        ["Reviewed (raw)", "https://codeforces.com/problemset/problem/1/A", "easy", "800", "Codeforces API", "Sorting"],
        ["Raw", "https://codeforces.com/problemset/problem/2/B", "very hard", "2500", "Codeforces API", "Greedy"],
    ])
    catalog.load(conn, catalog.DATA_DIR / "patterns.csv", main, reserve)
    found = rows(conn)
    assert found["https://codeforces.com/problemset/problem/1/A"]["title"] == "Reviewed"
    assert found["https://codeforces.com/problemset/problem/1/A"]["reserve_position"] is None
    raw = found["https://codeforces.com/problemset/problem/2/B"]
    # A very hard reserve problem may have only core patterns, unlike the catalog.
    assert (raw["catalog_position"], raw["reserve_position"], raw["difficulty"]) == (None, 1, "very hard")


def test_very_hard_core_only_still_rejected_in_catalog(conn, tmp_path):
    main = write(tmp_path / "catalog.csv", [
        ["Raw", "https://codeforces.com/problemset/problem/2/B", "very hard", "2500", "Codeforces API", "Greedy"],
    ])
    with pytest.raises(DataFileError, match="very hard problems need at least one advanced pattern"):
        catalog.load(conn, catalog.DATA_DIR / "patterns.csv", main)


def test_problem_moves_between_catalog_and_reserve(conn, tmp_path):
    link = "https://codeforces.com/problemset/problem/3/C"
    entry = ["Mover", link, "medium", "1300", "Codeforces API", "Greedy"]
    empty = write(tmp_path / "empty.csv", [])
    catalog.load(conn, catalog.DATA_DIR / "patterns.csv", write(tmp_path / "c.csv", [entry]), empty)
    first_id = conn.execute("SELECT id FROM problems WHERE link = ?", (link,)).fetchone()["id"]
    catalog.load(conn, catalog.DATA_DIR / "patterns.csv", empty, write(tmp_path / "r.csv", [entry]))
    row = rows(conn)[link]
    assert (row["catalog_position"], row["reserve_position"]) == (None, 1)
    assert conn.execute("SELECT id FROM problems WHERE link = ?", (link,)).fetchone()["id"] == first_id


def test_stale_reserve_problem_kept_only_with_attempts(conn, tmp_path):
    empty = write(tmp_path / "empty.csv", [])
    reserve = write(tmp_path / "r.csv", [
        ["Kept", "https://codeforces.com/problemset/problem/4/A", "easy", "800", "Codeforces API", "Greedy"],
        ["Dropped", "https://codeforces.com/problemset/problem/4/B", "easy", "800", "Codeforces API", "Greedy"],
    ])
    catalog.load(conn, catalog.DATA_DIR / "patterns.csv", empty, reserve)
    kept = conn.execute("SELECT id FROM problems WHERE title = 'Kept'").fetchone()["id"]
    with conn:
        conn.execute("INSERT INTO attempts (problem_id, date, outcome, entry_method) "
                     "VALUES (?, '2026-11-01', 'solved_alone', 'manual')", (kept,))
    catalog.load(conn, catalog.DATA_DIR / "patterns.csv", empty, empty)
    assert [(r["title"], r["reserve_position"]) for r in rows(conn).values()] == [("Kept", None)]


def test_unchanged_files_are_not_reloaded(conn, tmp_path):
    patterns = catalog.DATA_DIR / "patterns.csv"
    main = write(tmp_path / "catalog.csv", [["A", "https://example.com/a", "easy", "", "List", "Stack"]])
    assert catalog.load_if_changed(conn, patterns, main) is True
    assert catalog.load_if_changed(conn, patterns, main) is False
    write(main, [["A renamed", "https://example.com/a", "easy", "", "List", "Stack"]])
    assert catalog.load_if_changed(conn, patterns, main) is True
    assert rows(conn)["https://example.com/a"]["title"] == "A renamed"


def test_reserve_column_added_to_an_older_database(tmp_path):
    path = str(tmp_path / "old.sqlite")
    conn = connect(path)
    conn.execute("""CREATE TABLE problems (id INTEGER PRIMARY KEY, title TEXT NOT NULL, link TEXT UNIQUE,
                    difficulty TEXT NOT NULL, rating INTEGER, source TEXT NOT NULL,
                    is_custom INTEGER NOT NULL DEFAULT 0, catalog_position INTEGER)""")
    conn.close()
    init_db(path)
    conn = connect(path)
    assert "reserve_position" in {r["name"] for r in conn.execute("PRAGMA table_info(problems)")}
    conn.close()
