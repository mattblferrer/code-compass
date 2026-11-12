"""The site filter's effect on recommendations (R-36), from the author's reference history.

tests/data/r36_site_filter.json holds the catalog, attempts, and expected lists.
Each case starts from a fresh database, and its steps run in order on it.
"""
import csv
import json
from pathlib import Path

import pytest

from codecompass import create_app, queries
from conftest import app_db
from codecompass.state import Snapshot

DATA = json.loads((Path(__file__).parent / "data" / "r36_site_filter.json").read_text(encoding="utf-8"))
TODAY = DATA["today"]


@pytest.fixture
def fresh(tmp_path):
    """A function that builds a database with the reference catalog and attempts."""
    count = {"n": 0}

    def build():
        count["n"] += 1
        folder = tmp_path / str(count["n"])
        folder.mkdir()
        catalog_path = folder / "catalog.csv"
        with open(catalog_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["title", "link", "difficulty", "rating", "source", "patterns"])
            for p in DATA["catalog"]:
                writer.writerow([p["title"], p["link"], p["difficulty"], "", "Reference", "; ".join(p["patterns"])])
        db_path = str(folder / "db.sqlite")
        app = create_app({"TESTING": True, "DATABASE": db_path, "CATALOG_PATH": str(catalog_path),
                          "RESERVE_PATH": None, "UNMAPPED_PATH": None})
        conn = app_db(app)
        ids = {r["title"]: r["id"] for r in conn.execute("SELECT id, title FROM problems")}
        with conn:
            for a in DATA["attempts"]:
                conn.execute("INSERT INTO attempts (problem_id, date, outcome, entry_method) VALUES (?, ?, ?, 'manual')",
                             (ids[a["problem"]], a["date"], a["outcome"]))
        return conn

    return build


def apply(conn, step):
    queries.save_settings(conn, {**DATA["settings"],
                                 "preferences": {name: "target" for name in step.get("targets", [])},
                                 "hidden": {tuple(pair) for pair in step["hidden"]}})


def listed(snap):
    out = []
    for r in snap.recommendations():
        if r["kind"] == "review":
            out.append(f"review:{r['original']['title']}>{r['problem']['title']}")
        else:
            out.append(f"new:{r['problem']['title']}")
    return out


@pytest.mark.parametrize("case", DATA["cases"], ids=[c["name"] for c in DATA["cases"]])
def test_site_filter_lists(case, fresh):
    conn = fresh()
    try:
        for number, step in enumerate(case["steps"], start=1):
            apply(conn, step)
            assert listed(Snapshot(conn, TODAY)) == step["expected"], f"step {number}"
    finally:
        conn.close()


@pytest.mark.parametrize("case", DATA["cases"], ids=[c["name"] for c in DATA["cases"]])
def test_filter_never_changes_scores_or_due_dates(case, fresh):
    plain = fresh()
    apply(plain, {"hidden": []})
    reference = Snapshot(plain, TODAY)
    titles = {p["id"]: p["title"] for p in reference.problems.values()}
    assert {titles[pid]: day for pid, day in reference.due.items()} == DATA["due_dates"]
    plain.close()
    conn = fresh()
    try:
        for step in case["steps"]:
            apply(conn, step)
            snap = Snapshot(conn, TODAY)
            snap.recommendations()
            assert snap.scores == reference.scores
            assert {titles[pid]: day for pid, day in snap.due.items()} == DATA["due_dates"]
    finally:
        conn.close()
