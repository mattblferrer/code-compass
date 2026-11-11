"""The unreviewed Codeforces reserve: tag mapping, building, and loading (R-37)."""
import csv
import re
from pathlib import Path

import pytest

from codecompass import catalog
from codecompass.core.catalog_rows import DataFileError
from codecompass.core.codeforces_tags import BROAD, BROAD_FALLBACK, DIRECT, PAIRS, patterns_for, reserve_patterns
from codecompass.core.reserve import reserve_rows, unmapped_rows
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
    for tag, name in BROAD_FALLBACK.items():
        assert tag in listed[name], (tag, name)
    assert not BROAD & set(DIRECT)
    assert set(BROAD_FALLBACK) == BROAD


@pytest.mark.parametrize("tags, expected", [
    (["greedy", "sortings"], ["Sorting", "Greedy"]),
    (["math", "dp", "data structures"], []),
    (["trees", "dp"], ["Tree DP"]),
    # No pairs for Bitmask DP or Minimum Spanning Tree: editorials rarely use them.
    (["bitmasks", "dp"], ["Bit Manipulation"]),
    (["graphs", "dsu", "*special"], ["Union-Find"]),
    (["fft", "math"], ["FFT and NTT"]),
    (["communication"], []),
])
def test_patterns_for(tags, expected):
    assert patterns_for(tags, ORDER) == expected


@pytest.mark.parametrize("tags, expected", [
    # Broad tags count only when nothing else maps.
    (["math", "dp", "data structures"], ["Data Structure Design", "1-D Dynamic Programming", "Math"]),
    (["graphs", "dfs and similar", "trees"], ["Tree Traversal", "Graph Traversal"]),
    (["strings", "two pointers"], ["Two Pointers", "Strings"]),
    (["fft", "math"], ["FFT and NTT"]),
    (["trees", "dp"], ["Tree DP"]),
    (["communication"], []),
    ([], []),
])
def test_reserve_patterns_fall_back_on_broad_tags(tags, expected):
    assert reserve_patterns(tags, ORDER) == [n for n in ORDER if n in expected]


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
    # "Only broad" has no statistics, so it counts as solved by no one and comes last.
    assert [r["title"] for r in out] == ["Less popular", "Popular", "Easy version", "Only broad"]
    assert out[3]["patterns"] == "1-D Dynamic Programming; Math"
    assert out[0] == {
        "title": "Less popular", "link": "https://codeforces.com/problemset/problem/2/B",
        "difficulty": "very hard", "rating": 2400, "source": "Codeforces API", "patterns": "Tree DP",
    }
    assert out[2]["link"] == "https://codeforces.com/problemset/problem/7/A1"
    assert out[2]["difficulty"] == "medium"


def test_corrections_add_and_remove_patterns(tmp_path):
    result = {"problems": [
        problem(1, "A", "Tagged loosely", 1900, ["divide and conquer", "dp"]),
        problem(2, "B", "Untouched", 900, ["greedy"]),
    ]}
    corrections = tmp_path / "corrections.csv"
    corrections.write_text("link,add,remove,source\n"
                           "https://codeforces.com/problemset/problem/1/A,Segment Tree and Fenwick Tree; "
                           "2-D Dynamic Programming,Divide and Conquer,editorial\n", encoding="utf-8")
    out = reserve_rows(result, ORDER, catalog.read_corrections(corrections))
    by_title = {r["title"]: r["patterns"] for r in out}
    assert by_title == {"Tagged loosely": "2-D Dynamic Programming; Segment Tree and Fenwick Tree",
                        "Untouched": "Greedy"}
    assert catalog.read_corrections(tmp_path / "missing.csv") == {}


def test_atcoder_rows_join_the_reserve_by_solver_count(tmp_path):
    from codecompass.core.reserve import atcoder_rows, atcoder_unmapped
    source = [
        {"link": "https://atcoder.jp/contests/abc300/tasks/abc300_d", "title": "AABCC", "rating": "1100",
         "solvers": "6000", "patterns": "Number Theory; Two Pointers"},
        {"link": "https://atcoder.jp/contests/abc300/tasks/abc300_a", "title": "N-choice question", "rating": "-900",
         "solvers": "12000", "patterns": ""},
    ]
    result = {"problems": [problem(1, "A", "Popular", 800, ["greedy"]), problem(2, "B", "Rare", 1500, ["greedy"])],
              "problemStatistics": [{"contestId": 1, "index": "A", "solvedCount": 9000},
                                    {"contestId": 2, "index": "B", "solvedCount": 100}]}
    out = reserve_rows(result, ORDER, extra_rows=atcoder_rows(source, ORDER))
    assert [r["title"] for r in out] == ["Popular", "AABCC", "Rare"]
    assert out[1] == {"title": "AABCC", "link": "https://atcoder.jp/contests/abc300/tasks/abc300_d",
                      "difficulty": "medium", "rating": 1100, "source": "AtCoder",
                      "patterns": "Two Pointers; Number Theory"}
    # A problem whose editorial gave no pattern goes to the unmapped list instead.
    assert atcoder_unmapped(source) == [{"title": "N-choice question",
                                         "link": "https://atcoder.jp/contests/abc300/tasks/abc300_a",
                                         "difficulty": "easy"}]


def test_unmapped_rows_keep_what_the_reserve_cannot_hold():
    result = {"problems": [
        problem(1, "A", "In reserve", 800, ["greedy"]),
        problem(2, "B", "No tags", 1400),
        problem(3, "C", "Unrated", None, ["greedy"]),
        problem(4, "D", "Special", None, ["*special"]),
        problem(5, "E", "Question", None, kind="QUESTION"),
        problem(6, "F", "Only communication", 1900, ["communication"]),
    ]}
    assert unmapped_rows(result, ORDER) == [
        {"title": "No tags", "link": "https://codeforces.com/problemset/problem/2/B", "difficulty": "medium"},
        {"title": "Unrated", "link": "https://codeforces.com/problemset/problem/3/C", "difficulty": ""},
        {"title": "Only communication", "link": "https://codeforces.com/problemset/problem/6/F",
         "difficulty": "hard"},
    ]


def test_write_reserve_from_saved_response(tmp_path):
    saved = tmp_path / "problemset.json"
    saved.write_text('{"status": "OK", "result": {"problems": [{"contestId": 1, "index": "A", "name": "X",'
                     ' "type": "PROGRAMMING", "rating": 900, "tags": ["greedy"]}, {"contestId": 2, "index": "B",'
                     ' "name": "Y", "type": "PROGRAMMING", "tags": []}], "problemStatistics": []}}',
                     encoding="utf-8")
    out, unmapped = tmp_path / "reserve.csv", tmp_path / "unmapped.csv"
    assert catalog.write_reserve(saved, catalog.DATA_DIR / "patterns.csv", out, unmapped) == (1, 1)
    assert catalog.read_rows(out)[0]["patterns"] == "Greedy"
    assert catalog.read_rows(unmapped) == [
        {"title": "Y", "link": "https://codeforces.com/problemset/problem/2/B", "difficulty": ""}]


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


def target_pick(catalog, reserve, very_hard_on=False):
    """The problem a target pattern gets, from fixed data (R-32, R-37)."""
    from codecompass.core.recommend import recommend

    fft = "FFT and NTT"
    state = {"patterns": [fft], "advanced": [fft], "catalog": catalog, "reserve": reserve, "scores": {},
             "unscored_attempts": {}, "due": [], "excluded": set(), "targets": [fft], "mastered": [],
             "level": "easy", "advanced_on": False, "very_hard_on": very_hard_on, "interview": None}
    picks = [r["problem"] for r in recommend(state) if r["pattern"] == fft]
    return picks[0] if picks else None


def fft_problem(id_, difficulty, position=1):
    return {"id": id_, "position": position, "difficulty": difficulty, "patterns": ["FFT and NTT"]}


def test_target_skips_very_hard_catalog_problems_for_the_reserve_with_the_setting_off():
    assert target_pick([fft_problem(1, "very hard")], [fft_problem(2, "easy")]) == 2
    assert target_pick([fft_problem(1, "very hard")], [fft_problem(2, "very hard")]) is None
    assert target_pick([fft_problem(1, "very hard")], [fft_problem(2, "easy")], very_hard_on=True) == 1


def test_target_uses_any_catalog_level_before_the_reserve():
    # Catalog first: a hard catalog problem, two levels from easy, beats an easy reserve one.
    assert target_pick([fft_problem(1, "hard")], [fft_problem(2, "easy")]) == 1
