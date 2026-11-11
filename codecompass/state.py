"""Read the database into plain data, run the rules in core/, and save sibling suggestions.

Routes call this module; core/ never touches the database.
"""
from .core import constants as c
from .core.dates import add_days
from .core.levels import current_level
from .core.mastery import pattern_score
from .core.reasons import hint_eligible, reason
from .core.recommend import REVIEW, active_interview, recommend
from .core.reviews import activity, due_dates, is_stale, last_attempts, schedules, served_reviews, streak_days
from .core.siblings import choose_sibling
from .core.sites import is_hidden
from .core.streak import review_streak

from .queries import DEFAULT_SETTINGS, current_settings  # noqa: F401 (DEFAULT_SETTINGS is used by importers)


def _load_problems(conn, where="", args=()):
    """Problems with their pattern names, all of them or those matching `where` (on problems.id)."""
    problems = {r["id"]: {**dict(r), "patterns": []}
                for r in conn.execute(f"SELECT * FROM problems {where.format(column='id')}", args)}
    for r in conn.execute(
        f"""SELECT pp.problem_id, pt.name FROM problem_patterns pp JOIN patterns pt ON pt.id = pp.pattern_id
            {where.format(column='pp.problem_id')} ORDER BY pt.list_position""",
        args,
    ):
        if r["problem_id"] in problems:
            problems[r["problem_id"]]["patterns"].append(r["name"])
    return problems


class Snapshot:
    """Everything the dashboard needs, calculated for one day."""

    def __init__(self, conn, today):
        self.conn = conn
        self.today = today
        self.patterns = [dict(r) for r in conn.execute(
            "SELECT name, category, tier, family, description FROM patterns ORDER BY list_position"
        )]
        self.pattern_info = {p["name"]: p for p in self.patterns}
        # Scores and due reviews need only the attempted problems. The whole catalog and
        # reserve (about 15,000 problems) loads on first use of self.problems, which only
        # recommendations and sibling choice need; saving an attempt does not.
        self._known = _load_problems(conn, "WHERE {column} IN (SELECT problem_id FROM attempts)")
        self._all_problems = None
        self.attempts = [dict(r) for r in conn.execute("SELECT * FROM attempts ORDER BY date, id")]

        self.settings = current_settings(conn)
        prefs = self.settings["preferences"]
        self.targets = {name for name, pref in prefs.items() if pref == "target"}
        self.mastered = {name for name, pref in prefs.items() if pref == "mastered"}
        self.advanced_on = self.settings["advanced_on"] == "1"
        self.very_hard_on = self.settings["very_hard_on"] == "1"
        self.advanced = {p["name"] for p in self.patterns if p["category"] == "advanced"}
        self.hidden_sites = self.settings["hidden"]

        interviews = []
        for r in conn.execute("SELECT * FROM interviews ORDER BY date, id"):
            names = [x["name"] for x in conn.execute(
                """SELECT pt.name FROM interview_patterns ip JOIN patterns pt ON pt.id = ip.pattern_id
                   WHERE ip.interview_id = ? ORDER BY pt.list_position""",
                (r["id"],),
            )]
            interviews.append({"id": r["id"], "company": r["company"], "date": r["date"],
                               "difficulty": r["target_difficulty"], "patterns": names})
        self.interviews = interviews
        self.interview = active_interview(interviews, today)
        self.focus_patterns = set(self.interview["patterns"]) if self.interview else set()

        # Each attempt counts in full toward each of its problem's patterns.
        self.by_pattern = {p["name"]: [] for p in self.patterns}
        for a in self.attempts:
            problem = self._known[a["problem_id"]]
            for name in problem["patterns"]:
                self.by_pattern[name].append({
                    "date": a["date"], "difficulty": problem["difficulty"], "outcome": a["outcome"],
                    "attempt": a, "problem": problem,
                })
        self.counts = {name: len(rows) for name, rows in self.by_pattern.items()}
        self.scores = {}
        for name, rows in self.by_pattern.items():
            score = pattern_score(rows, self.pattern_info[name]["tier"], today)
            if score is not None:
                self.scores[name] = {"score": score, "last": rows[-1]["date"]}

        self.schedules = schedules(self.attempts)
        self.due = due_dates(self.schedules)
        self.last_attempt = last_attempts(self.schedules)
        # Reviews of problems not attempted for a long time wait while newer ones are due (R-12).
        self.due_now = served_reviews({pid: day for pid, day in self.due.items() if day <= today},
                                      self.last_attempt, today)
        self.attempted = {a["problem_id"] for a in self.attempts}
        self.not_now = {r["problem_id"] for r in conn.execute(
            "SELECT problem_id FROM not_now WHERE date > ?", (add_days(today, -c.NOT_NOW_DAYS),)
        )}
        self._suggestions = [dict(r) for r in conn.execute("SELECT * FROM sibling_suggestions ORDER BY id")]

    @property
    def problems(self):
        """Every problem by id, loaded on first use."""
        if self._all_problems is None:
            loaded = _load_problems(self.conn)
            loaded.update(self._known)  # Keep the dicts already handed out.
            self._all_problems = loaded
        return self._all_problems

    def problem(self, problem_id):
        """One problem, without loading them all."""
        if self._all_problems is not None:
            return self._all_problems.get(problem_id)
        if problem_id not in self._known:
            self._known.update(_load_problems(self.conn, "WHERE {column} = ?", (problem_id,)))
        return self._known.get(problem_id)

    # --- Patterns ---

    def active(self, name):
        return name not in self.advanced or self.advanced_on or name in self.targets or name in self.focus_patterns

    def pattern_rows(self):
        """Patterns shown on the dashboard (R-17): active ones and any with attempts."""
        rows = []
        for p in self.patterns:
            name = p["name"]
            if not (self.active(name) or self.counts[name]):
                continue
            rows.append({
                "name": name,
                "category": p["category"],
                "family": p["family"],
                "score": self.scores.get(name, {}).get("score"),
                "change": self.score_change(name),
                "attempts": self.counts[name],
                "target": name in self.targets,
                "mastered": name in self.mastered,
            })
        return rows

    def score_change(self, name, days=14):
        """Change in score since `days` ago, using the same rule, or None if either has no score."""
        if name not in self.scores:
            return None
        then = add_days(self.today, -days)
        earlier = [r for r in self.by_pattern[name] if r["date"] <= then]
        past = pattern_score(earlier, self.pattern_info[name]["tier"], then)
        if past is None:
            return None
        return round(self.scores[name]["score"] - past)

    def score_history(self, name, step_days=7):
        """The pattern's score at weekly points from its first attempt to today.

        Each point is calculated with the same rule as today's score, using only
        the attempts made by that date. Points before the third attempt have no score.
        `attempts` counts the attempts after the previous point (`since`), for the chart's details.
        """
        rows = self.by_pattern[name]
        if not rows:
            return []
        tier = self.pattern_info[name]["tier"]
        days = [rows[0]["date"]]
        while days[-1] < self.today:
            days.append(min(add_days(days[-1], step_days), self.today))
        points, previous = [], None
        for day in days:
            earlier = [r for r in rows if r["date"] <= day]
            new = sum(1 for r in earlier if previous is None or r["date"] > previous)
            points.append({"date": day, "score": pattern_score(earlier, tier, day), "attempts": new, "since": previous})
            previous = day
        return points

    def activity(self, days=56):
        """Daily review activity for the strip on the dashboard (R-30)."""
        records = streak_days(self.schedules, self.today)
        return activity(records, [a["date"] for a in self.attempts], self.today, days)

    def level(self):
        history = [
            {"difficulty": self._known[a["problem_id"]]["difficulty"], "outcome": a["outcome"]}
            for a in self.attempts
        ]
        return current_level(history, self.settings["starting_difficulty"], self.very_hard_on)

    def streak(self):
        return review_streak(streak_days(self.schedules, self.today), self.today)

    # --- Sibling suggestions (R-28) ---

    def _current(self, due_problem_id):
        """Suggestion rows for the review now due on this problem."""
        due = self.due_now.get(due_problem_id)
        if due is None:
            return []
        return [s for s in self._suggestions if s["due_problem_id"] == due_problem_id and s["date"] >= due]

    def hidden(self, problem_id):
        """Whether the site filter hides this problem from new problems and siblings (R-36)."""
        if not self.hidden_sites:
            return False
        cache = self.__dict__.setdefault("_hidden_cache", {})
        if problem_id not in cache:
            p = self.problem(problem_id)
            cache[problem_id] = not p["is_custom"] and is_hidden(p["link"], p["patterns"], self.advanced,
                                                                  self.hidden_sites)
        return cache[problem_id]

    def active_suggestion(self, due_problem_id):
        # A sibling from a site hidden since it was suggested is passed over, so a
        # new one is chosen; this does not count as a dismissal (R-36).
        for s in reversed(self._current(due_problem_id)):
            if (s["status"] == "active" and s["sibling_problem_id"] not in self.attempted
                    and not self.hidden(s["sibling_problem_id"])):
                return s
        return None

    def _problems_with(self, name):
        """Ids of problems with this pattern, indexed on first use."""
        if not hasattr(self, "_pattern_index"):
            self._pattern_index = {}
            for p in self.problems.values():
                for pattern in p["patterns"]:
                    self._pattern_index.setdefault(pattern, []).append(p["id"])
        return self._pattern_index.get(name, [])

    def reserved(self):
        result = set()
        for pid in self.due_now:
            s = self.active_suggestion(pid)
            if s:
                result.add(s["sibling_problem_id"])
        return result

    def sibling_for(self, due_problem_id):
        """The suggested sibling's id, choosing and saving one if needed, or None for the original."""
        existing = self.active_suggestion(due_problem_id)
        if existing:
            return existing["sibling_problem_id"]
        original = self.problems[due_problem_id]
        dismissed = {s["sibling_problem_id"] for s in self._current(due_problem_id) if s["status"] == "dismissed"}
        reserved = self.reserved()
        inactive = {name for name in self.advanced if not self.active(name)}
        sharing = {pid for name in original["patterns"] for pid in self._problems_with(name)}

        def candidates(position_key):
            return [
                {
                    "id": p["id"], "position": p[position_key], "difficulty": p["difficulty"],
                    "patterns": p["patterns"], "attempted": p["id"] in self.attempted,
                    "reserved": p["id"] in reserved, "dismissed": p["id"] in dismissed,
                    "not_now": p["id"] in self.not_now,
                }
                for p in (self.problems[pid] for pid in sharing)
                if p[position_key] is not None and not p["is_custom"] and p["id"] != due_problem_id
                and not self.hidden(p["id"])
            ]

        # The reserve supplies a sibling only when no catalog problem qualifies (R-37).
        chosen = choose_sibling(original, candidates("catalog_position"), inactive, self.very_hard_on)
        if chosen is None:
            chosen = choose_sibling(original, candidates("reserve_position"), inactive, self.very_hard_on)
        if chosen is None:
            return None
        with self.conn:
            row_id = self.conn.execute(
                "INSERT INTO sibling_suggestions (due_problem_id, sibling_problem_id, status, date) VALUES (?, ?, 'active', ?)",
                (due_problem_id, chosen["id"], self.today),
            ).lastrowid
        self._suggestions.append({"id": row_id, "due_problem_id": due_problem_id,
                                  "sibling_problem_id": chosen["id"], "status": "active", "date": self.today})
        return chosen["id"]

    def review_of(self, problem_id, attempt_date):
        """The due problem whose review this attempt completes as a sibling, or None."""
        for pid, due in self.due_now.items():
            s = self.active_suggestion(pid)
            if s and s["sibling_problem_id"] == problem_id and attempt_date >= due:
                return pid
        return None

    # --- Recommendations (R-13 to R-16, R-27, R-29, R-32) ---

    def hint_eligible(self, problem_id):
        return hint_eligible(self.problem(problem_id)["patterns"], self.counts)

    def hint(self, problem_id):
        """Hint text if one is revealed and unused (R-27), otherwise None."""
        revealed = self.conn.execute(
            "SELECT 1 FROM hint_reveals WHERE problem_id = ? AND used = 0 LIMIT 1", (problem_id,)
        ).fetchone()
        if not revealed:
            return None
        return [{"name": n, "description": self.pattern_info[n]["description"]}
                for n in self.problem(problem_id)["patterns"]]

    def problem_context(self, problem_id, editing=False):
        """What the log page shows beside the form for one problem, without loading every problem.

        Patterns stay hidden, as on the problem page, while a beginner hint is on offer
        and neither the hint nor an attempt has revealed them (R-27). When `editing`, the
        review an attempt would complete and the hint rule are left out, since they apply
        only to a new attempt.
        """
        problem = self.problem(problem_id)
        if problem is None:
            return None
        attempts = [a for a in self.attempts if a["problem_id"] == problem_id]
        eligible = self.hint_eligible(problem_id)
        hint = self.hint(problem_id)
        completes = None if editing else self.review_of(problem_id, self.today)
        return {
            "problem": problem,
            "patterns": [{"name": n, "score": self.scores.get(n, {}).get("score"), "attempts": self.counts.get(n, 0)}
                         for n in problem["patterns"]],
            "patterns_hidden": eligible and not hint and not attempts,
            "attempts": attempts[-3:][::-1],
            "attempt_count": len(attempts),
            "due": self.due.get(problem_id),
            "completes": self.problem(completes) if completes else None,
            "hint_used_up": bool(hint) and not editing,
        }

    @staticmethod
    def order_position(problem):
        """Catalog order, then reserve problems most-solved first, then custom problems as added."""
        if problem["catalog_position"] is not None:
            return problem["catalog_position"]
        if problem["reserve_position"] is not None:
            return 10**8 + problem["reserve_position"]
        return 10**9 + problem["id"]

    def recommendations(self):
        def pool(position_key):
            return [
                {"id": p["id"], "position": p[position_key], "difficulty": p["difficulty"], "patterns": p["patterns"]}
                for p in self.problems.values()
                if p[position_key] is not None and not p["is_custom"] and not self.hidden(p["id"])
            ]

        catalog, reserve = pool("catalog_position"), pool("reserve_position")
        due = [
            {"problem": pid, "patterns": self.problems[pid]["patterns"], "due": day,
             "position": self.order_position(self.problems[pid])}
            for pid, day in self.due_now.items()
        ]
        counts = {n: self.counts[n] for n in self.counts if n not in self.scores}

        def build():
            return recommend({
                "patterns": [p["name"] for p in self.patterns],
                "advanced": self.advanced,
                "catalog": catalog,
                "reserve": reserve,
                "scores": self.scores,
                "unscored_attempts": counts,
                "due": due,
                "excluded": self.attempted | self.not_now | self.reserved(),
                "targets": self.targets,
                "mastered": self.mastered,
                "level": self.level(),
                "advanced_on": self.advanced_on,
                "very_hard_on": self.very_hard_on,
                "interview": self.interview,
            })

        # Siblings for the shown reviews are chosen first, so they are reserved
        # before new problems are picked (R-28). The reviews shown do not change.
        siblings = {}
        for item in build():
            if item["kind"] == REVIEW:
                siblings[item["problem"]] = self.sibling_for(item["problem"])
        items = build()
        result = []
        for item in items:
            original = None
            shown = item["problem"]
            if item["kind"] == REVIEW:
                original = item["problem"]
                shown = siblings.get(original) or original
            hint = self.hint_eligible(shown)
            result.append({
                "problem": self.problems[shown],
                "original": self.problems[original] if original else None,
                "is_sibling": original is not None and shown != original,
                "kind": item["kind"],
                "hint_eligible": hint,
                "hint": self.hint(shown),
                "due": self.due_now.get(original) if original else None,
                "reason": reason(
                    item, hint, self.scores, self.today,
                    original_title=self.problems[original]["title"] if original and shown != original else None,
                    interview=self.interview,
                ),
            })
        return result

    def calendar_events(self):
        """Reviews for the calendar file (R-31), leaving out problems that will be old by
        their due date (R-12), which wait for newer reviews."""
        return [
            {"uid": f"review-{pid}-{day}@codecompass", "date": day,
             "summary": f"Review: {self.problems[pid]['title']}"}
            for pid, day in sorted(self.due.items(), key=lambda x: (x[1], x[0]))
            if pid in self.due_now or not is_stale(self.last_attempt[pid], max(day, self.today))
        ]
