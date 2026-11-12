"""Demo dataset (R-25): 8 weeks of made-up practice history on the real catalog.

Build it with `flask --app codecompass demo`, then run the app with the
environment variable CODECOMPASS_DEMO=1 to use it. The demo has its own
database, so it never touches real data.
"""
import random

import click

from .core import constants as c
from .core.dates import add_days
from .core.reviews import due_dates, schedules
from .core.siblings import choose_sibling
from .db import connect

WEEKS = 8
SEED = 189

# How well the made-up user does in each pattern at the start, and per attempt after.
STRONG = ["Arrays and Hashing", "Two Pointers", "Sorting", "Strings", "Binary Search"]
MIDDLE = ["Sliding Window", "Stack", "Linked List", "Prefix Sums", "Heap", "Tree Traversal", "Intervals"]
WEAK = ["1-D Dynamic Programming", "Graph Traversal", "Greedy", "Backtracking and Brute Force", "Trie"]
TOUCHED = ["Union-Find", "Topological Sort"]  # One or two attempts, so they show "not enough data".
NOTES = ["Missed an edge case with an empty input.", "Took a while to see the pattern.",
         "Clean first try.", "Needed the hint about the ordering.", "Off-by-one at the end."]


def _outcome(rng, skill):
    roll = rng.random()
    if roll < skill:
        return c.SOLVED_ALONE
    if roll < skill + (1 - skill) * 0.5:
        return c.SOLVED_WITH_HINTS
    if roll < skill + (1 - skill) * 0.75:
        return c.SOLVED_AFTER_SOLUTION
    return c.NOT_SOLVED


def simulate(problems, today, seed=SEED):
    """Return made-up attempts, oldest first, as dicts ready to insert.

    `problems` are catalog problems with "id", "position", "difficulty", "patterns".
    """
    rng = random.Random(seed)
    start = add_days(today, -WEEKS * 7)
    skill = {}
    for name in STRONG:
        skill[name] = 0.7
    for name in MIDDLE:
        skill[name] = 0.45
    for name in WEAK:
        skill[name] = 0.25
    for name in TOUCHED:
        skill[name] = 0.4
    practiced = STRONG + MIDDLE + WEAK
    by_pattern = {}
    for p in problems:
        for name in p["patterns"]:
            by_pattern.setdefault(name, []).append(p)
    lookup = {p["id"]: p for p in problems}

    attempts, attempted = [], set()

    def add(problem, day, review_of=None):
        names = problem["patterns"]
        level = c.LEVELS.index(problem["difficulty"])
        chance = sum(skill.get(n, 0.3) for n in names) / len(names) - 0.12 * (level - 1)
        outcome = _outcome(rng, max(0.05, min(0.95, chance)))
        for n in names:
            skill[n] = min(0.92, skill.get(n, 0.3) + 0.02)
        attempts.append({
            "id": len(attempts) + 1, "problem_id": problem["id"], "date": day, "outcome": outcome,
            "time_seconds": rng.randint(8, 55) * 60 + rng.randint(0, 59) if rng.random() < 0.6 else None,
            "notes": rng.choice(NOTES) if rng.random() < 0.2 else None,
            "review_of_problem_id": review_of,
        })
        attempted.add(problem["id"])

    def level_for(name, stage):
        return "easy" if stage < 0.3 else "medium" if skill.get(name, 0.3) < 0.75 or stage < 0.7 else "hard"

    # A couple of patterns touched once or twice, early on: {day offset: pattern}.
    touched = {10: TOUCHED[0], 19: TOUCHED[1], 23: TOUCHED[1]}
    days = WEEKS * 7 + 1  # Through today.

    for offset in range(days):
        day = add_days(start, offset)
        last_days = offset >= days - 6
        if not last_days and rng.random() < 0.15:
            continue  # A rest day.

        # Reviews first, as siblings where one exists. The last day is left
        # alone so some reviews are due when the demo opens.
        if offset < days - 1:
            due = sorted((d, pid) for pid, d in due_dates(schedules(attempts)).items() if d <= day)
            for _, pid in due[: rng.choice([2, 3, 3])]:
                original = lookup[pid]
                candidates = [
                    {**p, "attempted": p["id"] in attempted}
                    for p in problems if p["id"] != pid
                ]
                sibling = choose_sibling(original, candidates)
                if sibling:
                    add(lookup[sibling["id"]], day, review_of=pid)
                else:
                    add(original, day)

        # One or two new problems.
        stage = offset / days
        picks = [touched[offset]] if offset in touched else []
        picks += [rng.choice(practiced) for _ in range(rng.choice([1, 1, 2]))]
        for name in picks:
            wanted = level_for(name, stage)
            options = [p for p in by_pattern.get(name, []) if p["id"] not in attempted]
            if not options:
                continue
            options.sort(key=lambda p: (p["difficulty"] != wanted, p["position"]))
            add(options[0], day)

    attempts.sort(key=lambda a: (a["date"], a["id"]))
    return attempts


def build(conn, today, seed=SEED):
    """Replace all practice data in `conn` with the demo history.

    The made-up user has no advanced patterns turned on, so like the app
    (R-32) they only meet catalog problems whose patterns are all core.
    """
    patterns = {}
    for row in conn.execute(
        """SELECT pp.problem_id, pt.name, pt.category FROM problem_patterns pp
           JOIN patterns pt ON pt.id = pp.pattern_id ORDER BY pt.list_position"""
    ):
        patterns.setdefault(row["problem_id"], []).append((row["name"], row["category"]))
    problems = []
    rows = conn.execute(
        "SELECT id, catalog_position, difficulty FROM problems WHERE catalog_position IS NOT NULL"
    ).fetchall()
    for row in rows:
        tagged = patterns.get(row["id"], [])
        if not tagged or any(category != "core" for _, category in tagged):
            continue
        problems.append({"id": row["id"], "position": row["catalog_position"],
                         "difficulty": row["difficulty"], "patterns": [name for name, _ in tagged]})
    attempts = simulate(problems, today, seed)
    with conn:
        for table in ("attempts", "sibling_suggestions", "not_now", "hint_reveals", "pattern_preferences"):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("DELETE FROM problems WHERE is_custom = 1")
        if getattr(conn, "hosted", False):
            # Number the attempts from 1 again, as SQLite does once the table is empty.
            conn.execute("SELECT setval(pg_get_serial_sequence('attempts', 'id'), 1, false)")
        else:
            # Problems kept only because earlier demo attempts used them, such as the placeholder
            # problems of older versions. In hosted mode such problems are shared, so they stay.
            conn.execute("DELETE FROM problems WHERE catalog_position IS NULL AND reserve_position IS NULL")
        conn.executemany(
            """INSERT INTO attempts (problem_id, date, outcome, time_seconds, notes, entry_method, review_of_problem_id)
               VALUES (:problem_id, :date, :outcome, :time_seconds, :notes, 'manual', :review_of_problem_id)""",
            attempts,
        )
        conn.execute(
            "INSERT INTO pattern_preferences (pattern_id, preference) SELECT id, 'target' FROM patterns WHERE name = ?",
            ("Graph Traversal",),
        )
    return len(attempts)


def init_app(app):
    @app.cli.command("demo")
    def demo_command():
        """Build the demo database (R-25). Replaces any earlier demo data."""
        from datetime import date

        if not app.config.get("DEMO"):
            raise click.ClickException(
                "Set CODECOMPASS_DEMO=1 first, so the demo never replaces your real data."
            )
        conn = connect(app.config["DATABASE"])
        try:
            count = build(conn, date.today().isoformat())
        finally:
            conn.close()
        click.echo(f"Demo database ready with {count} attempts: {app.config['DATABASE']}")
