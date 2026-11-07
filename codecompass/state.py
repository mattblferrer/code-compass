"""Read the database into plain data, run the rules in core/, and save sibling suggestions.

Routes call this module; core/ never touches the database.
"""
from .core import constants as c
from .core.dates import add_days
from .core.levels import current_level
from .core.mastery import pattern_score
from .core.reasons import hint_eligible, reason
from .core.recommend import REVIEW, active_interview, recommend
from .core.reviews import activity, due_dates, schedules, streak_days
from .core.siblings import choose_sibling
from .core.streak import review_streak

DEFAULT_SETTINGS = {"starting_difficulty": "easy", "advanced_on": "0", "very_hard_on": "0"}


class Snapshot:
    """Everything the dashboard needs, calculated for one day."""

    def __init__(self, conn, today):
        self.conn = conn
        self.today = today
        self.patterns = [dict(r) for r in conn.execute(
            "SELECT name, category, tier, family, description FROM patterns ORDER BY list_position"
        )]
        self.pattern_info = {p["name"]: p for p in self.patterns}
        self.problems = {r["id"]: {**dict(r), "patterns": []} for r in conn.execute("SELECT * FROM problems")}
        for r in conn.execute(
            """SELECT pp.problem_id, pt.name FROM problem_patterns pp
               JOIN patterns pt ON pt.id = pp.pattern_id ORDER BY pt.list_position"""
        ):
            self.problems[r["problem_id"]]["patterns"].append(r["name"])
        self.attempts = [dict(r) for r in conn.execute("SELECT * FROM attempts ORDER BY date, id")]

        self.settings = dict(DEFAULT_SETTINGS)
        self.settings.update({r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")})
        prefs = {r["name"]: r["preference"] for r in conn.execute(
            "SELECT pt.name, pp.preference FROM pattern_preferences pp JOIN patterns pt ON pt.id = pp.pattern_id"
        )}
        self.targets = {name for name, pref in prefs.items() if pref == "target"}
        self.mastered = {name for name, pref in prefs.items() if pref == "mastered"}
        self.advanced_on = self.settings["advanced_on"] == "1"
        self.very_hard_on = self.settings["very_hard_on"] == "1"
        self.advanced = {p["name"] for p in self.patterns if p["category"] == "advanced"}

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
            problem = self.problems[a["problem_id"]]
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
        self.due_now = {pid: day for pid, day in self.due.items() if day <= today}
        self.attempted = {a["problem_id"] for a in self.attempts}
        self.not_now = {r["problem_id"] for r in conn.execute(
            "SELECT problem_id FROM not_now WHERE date > ?", (add_days(today, -c.NOT_NOW_DAYS),)
        )}
        self._suggestions = [dict(r) for r in conn.execute("SELECT * FROM sibling_suggestions ORDER BY id")]

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
        """
        rows = self.by_pattern[name]
        if not rows:
            return []
        tier = self.pattern_info[name]["tier"]
        days = [rows[0]["date"]]
        while days[-1] < self.today:
            days.append(min(add_days(days[-1], step_days), self.today))
        points = []
        for day in days:
            earlier = [r for r in rows if r["date"] <= day]
            points.append({"date": day, "score": pattern_score(earlier, tier, day)})
        return points

    def activity(self, days=56):
        """Daily review activity for the strip on the dashboard (R-30)."""
        records = streak_days(self.schedules, self.today)
        return activity(records, [a["date"] for a in self.attempts], self.today, days)

    def level(self):
        history = [
            {"difficulty": self.problems[a["problem_id"]]["difficulty"], "outcome": a["outcome"]}
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

    def active_suggestion(self, due_problem_id):
        for s in reversed(self._current(due_problem_id)):
            if s["status"] == "active" and s["sibling_problem_id"] not in self.attempted:
                return s
        return None

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
        candidates = [
            {
                "id": p["id"], "position": p["catalog_position"], "difficulty": p["difficulty"],
                "patterns": p["patterns"], "attempted": p["id"] in self.attempted,
                "reserved": p["id"] in reserved, "dismissed": p["id"] in dismissed,
                "not_now": p["id"] in self.not_now,
            }
            for p in self.problems.values()
            if p["catalog_position"] is not None and not p["is_custom"] and p["id"] != due_problem_id
        ]
        inactive = {name for name in self.advanced if not self.active(name)}
        chosen = choose_sibling(original, candidates, inactive, self.very_hard_on)
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
        return hint_eligible(self.problems[problem_id]["patterns"], self.counts)

    def hint(self, problem_id):
        """Hint text if one is revealed and unused (R-27), otherwise None."""
        revealed = self.conn.execute(
            "SELECT 1 FROM hint_reveals WHERE problem_id = ? AND used = 0 LIMIT 1", (problem_id,)
        ).fetchone()
        if not revealed:
            return None
        return [{"name": n, "description": self.pattern_info[n]["description"]}
                for n in self.problems[problem_id]["patterns"]]

    def recommendations(self):
        catalog = [
            {"id": p["id"], "position": p["catalog_position"], "difficulty": p["difficulty"], "patterns": p["patterns"]}
            for p in self.problems.values()
            if p["catalog_position"] is not None and not p["is_custom"]
        ]
        due = [
            {"problem": pid, "patterns": self.problems[pid]["patterns"], "due": day,
             "position": self.problems[pid]["catalog_position"] or 10**9 + pid}
            for pid, day in self.due_now.items()
        ]
        counts = {n: self.counts[n] for n in self.counts if n not in self.scores}

        def build():
            return recommend({
                "patterns": [p["name"] for p in self.patterns],
                "advanced": self.advanced,
                "catalog": catalog,
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
        return [
            {"uid": f"review-{pid}-{day}@codecompass", "date": day,
             "summary": f"Review: {self.problems[pid]['title']}"}
            for pid, day in sorted(self.due.items(), key=lambda x: (x[1], x[0]))
        ]
