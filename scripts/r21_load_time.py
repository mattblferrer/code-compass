"""R-21 timing check: the dashboard and its recommendations with 500 logged attempts.

R-21's heavy user logs about 5 problems a day for 100 days. This script builds that
history in a new database, serves the app on 127.0.0.1, and times full requests to
the dashboard, which computes the scores, due reviews, and recommendations.

    .venv\\Scripts\\python scripts\\r21_load_time.py [--runs 10] [--keep path\\to\\copy.sqlite]

It never touches the real or demo database, and it makes no outside requests.
"""
import argparse
import logging
import random
import shutil
import statistics
import sys
import tempfile
import threading
import time
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from werkzeug.serving import make_server  # noqa: E402

from codecompass import create_app  # noqa: E402
from codecompass.core import constants as c  # noqa: E402
from codecompass.core.dates import add_days  # noqa: E402
from codecompass.core.reviews import due_dates, schedules  # noqa: E402
from codecompass.core.siblings import choose_sibling  # noqa: E402
from codecompass.db import get_db  # noqa: E402
from codecompass.demo import _outcome  # noqa: E402

DAYS = 100
PER_DAY = 5
LIMIT_SECONDS = 2.0
SEED = 21


def heavy_history(problems, today, seed=SEED):
    """DAYS * PER_DAY attempts ending today: due reviews first (as siblings), then new problems."""
    rng = random.Random(seed)
    lookup = {p["id"]: p for p in problems}
    by_level = {}
    for p in problems:
        by_level.setdefault(p["difficulty"], []).append(p)
    attempts, attempted = [], set()

    def add(problem, day, review_of=None):
        level = c.LEVELS.index(problem["difficulty"])
        attempts.append({"id": len(attempts) + 1, "problem_id": problem["id"], "date": day,
                         "outcome": _outcome(rng, max(0.1, 0.6 - 0.12 * level)),
                         "time_seconds": rng.randint(8, 55) * 60, "notes": None, "review_of_problem_id": review_of})
        attempted.add(problem["id"])

    for offset in range(DAYS):
        day = add_days(today, offset - DAYS + 1)
        done = 0
        due = sorted((d, pid) for pid, d in due_dates(schedules(attempts)).items() if d <= day)
        for _, pid in due[:3]:
            candidates = [{**p, "attempted": p["id"] in attempted} for p in problems if p["id"] != pid]
            sibling = choose_sibling(lookup[pid], candidates)
            add(lookup[sibling["id"]] if sibling else lookup[pid], day, pid if sibling else None)
            done += 1
        while done < PER_DAY:
            level = rng.choice(["easy", "medium", "medium", "hard"])
            options = [p for p in by_level[level] if p["id"] not in attempted]
            add(rng.choice(options), day)
            done += 1
    return attempts


def build(app, today):
    with app.app_context():
        conn = get_db()
        patterns = {}
        for r in conn.execute("""SELECT pp.problem_id, pt.name, pt.category FROM problem_patterns pp
                                 JOIN patterns pt ON pt.id = pp.pattern_id"""):
            patterns.setdefault(r["problem_id"], []).append((r["name"], r["category"]))
        problems = [
            {"id": r["id"], "position": r["catalog_position"], "difficulty": r["difficulty"],
             "patterns": [n for n, _ in patterns.get(r["id"], [])]}
            for r in conn.execute("SELECT id, catalog_position, difficulty FROM problems WHERE catalog_position IS NOT NULL")
            if patterns.get(r["id"]) and all(cat == "core" for _, cat in patterns[r["id"]])
        ]
        attempts = heavy_history(problems, today)
        with conn:
            conn.executemany(
                """INSERT INTO attempts (problem_id, date, outcome, time_seconds, notes, entry_method, review_of_problem_id)
                   VALUES (:problem_id, :date, :outcome, :time_seconds, :notes, 'manual', :review_of_problem_id)""",
                attempts)  # The "id" key only orders the schedule; the database assigns its own.
        counts = {name: conn.execute(f"SELECT count(*) FROM {name}").fetchone()[0] for name in ("attempts", "problems")}
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--keep", help="also save the built database here, for a browser check")
    args = parser.parse_args()

    workdir = Path(tempfile.mkdtemp(prefix="codecompass-r21-"))
    database = workdir / "r21.sqlite"
    started = time.perf_counter()
    app = create_app({"DATABASE": str(database), "SECRET_KEY": "r21"})
    startup = time.perf_counter() - started
    counts = build(app, date.today().isoformat())
    if args.keep:
        shutil.copyfile(database, args.keep)

    logging.getLogger("werkzeug").setLevel(logging.ERROR)  # No line per request.
    server = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/"
    times = []
    try:
        for _ in range(args.runs):
            begin = time.perf_counter()
            with urllib.request.urlopen(url, timeout=30) as response:
                body = response.read()
                assert response.status == 200 and b"Practice next" in body
            times.append(time.perf_counter() - begin)
    finally:
        server.shutdown()

    print(f"Database: {counts['attempts']} attempts, {counts['problems']} problems (catalog and reserve)")
    print(f"App start, including the catalog and reserve load: {startup:.2f} s")
    print("Dashboard requests (s): " + ", ".join(f"{t:.3f}" for t in times))
    print(f"Median {statistics.median(times):.3f} s, slowest {max(times):.3f} s, limit {LIMIT_SECONDS:.1f} s: "
          + ("PASS" if max(times) <= LIMIT_SECONDS else "FAIL"))
    shutil.rmtree(workdir, ignore_errors=True)
    return 0 if max(times) <= LIMIT_SECONDS else 1


if __name__ == "__main__":
    sys.exit(main())
