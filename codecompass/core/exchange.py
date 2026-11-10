"""CSV export and import of attempts (R-19, R-20).

Plain functions on plain data: export_rows builds the rows to write, and
plan_import decides what an imported file adds. The columns are listed in
docs/data_model.md. Import rows use the same validators as the logging form
and the custom-problem form (R-05, R-02).
"""
from . import constants as c
from .problem_refs import from_link
from .validation import OUTCOME_LABELS, format_minutes, validate_attempt, validate_problem

COLUMNS = ["date", "title", "link", "difficulty", "rating", "patterns", "outcome", "time_minutes", "notes", "review_of"]
REQUIRED = ("date", "title", "outcome")
LEVEL_LABELS = {"easy": "Easy", "medium": "Medium", "hard": "Hard", "very hard": "Very hard"}
FIELD_NAMES = {"date": "date", "outcome": "outcome", "time": "time_minutes", "title": "title",
               "difficulty": "difficulty", "patterns": "patterns", "link": "link"}

# Both the label and the stored code are accepted for an outcome, ignoring case.
OUTCOME_CODES = {**{label.lower(): code for code, label in OUTCOME_LABELS.items()},
                 **{code: code for code in OUTCOME_LABELS}}

REASONS = {
    "ambiguous": "The title matches more than one problem; add the problem's link to choose one.",
    "unmatched": "No problem matches this link or title; add difficulty and patterns to create it as a custom problem.",
    "review_of": "review_of matches no single problem.",
    "duplicate": "Duplicate of an attempt already saved.",
    "missing_columns": "The file needs the columns date, title, and outcome.",
}


def _canonical(link):
    found = from_link(link)
    return found[1] if found else link


def _problem_ref(problem):
    """How a problem is named in the review_of column: its link, or its title if it has none."""
    return problem["link"] or problem["title"]


def export_rows(attempts, problems):
    """Rows for the export file, one per attempt, in the order given (logged order).

    `problems` maps an id to a dict with title, link, difficulty, rating, and patterns.
    """
    rows = []
    for a in attempts:
        p = problems[a["problem_id"]]
        review_of = problems.get(a["review_of_problem_id"]) if a.get("review_of_problem_id") else None
        rows.append({
            "date": a["date"],
            "title": p["title"],
            "link": p["link"] or "",
            "difficulty": LEVEL_LABELS[p["difficulty"]],
            "rating": "" if p.get("rating") is None else str(p["rating"]),
            "patterns": "; ".join(p["patterns"]),
            "outcome": OUTCOME_LABELS[a["outcome"]],
            "time_minutes": format_minutes(a["time_seconds"]),
            "notes": a["notes"] or "",
            "review_of": _problem_ref(review_of) if review_of else "",
        })
    return rows


class _Index:
    """Problems found by canonical link or by lower-case title, including ones the import creates."""

    def __init__(self, problems):
        self.by_link, self.by_title = {}, {}
        for key, p in problems.items():
            self.add(key, p["title"], p["link"])

    def add(self, key, title, link):
        if link:
            self.by_link[_canonical(link)] = key
        self.by_title.setdefault(title.strip().lower(), []).append(key)

    def match(self, title, link):
        """("found", key), ("ambiguous", None), or ("none", None)."""
        if link and _canonical(link) in self.by_link:
            return "found", self.by_link[_canonical(link)]
        keys = self.by_title.get(title.strip().lower(), []) if title else []
        if len(keys) == 1:
            return "found", keys[0]
        return ("ambiguous", None) if keys else ("none", None)


def _attempt_key(problem, date, outcome, seconds, notes, review_of):
    return (problem, date, outcome, seconds, notes or None, review_of)


def plan_import(rows, header, problems, attempts, pattern_names, today):
    """Decide what an imported file adds (R-19, R-20).

    `rows` are dicts from the file, keyed by `header` (the file's column names).
    `problems` maps an id to a dict with title and link; `attempts` are the saved
    attempts. Returns a dict with:
      new_problems: custom problems to create, each with "key", title, link, difficulty, patterns
      attempts: attempts to add, each with "problem" and "review_of" as a problem id or a new key
      skipped: (row number, reason) pairs, row numbers counted as in a spreadsheet (header is 1)
      error: a message when the whole file cannot be read, else None
    """
    plan = {"new_problems": [], "attempts": [], "skipped": [], "error": None}
    columns = {name.strip().lower() for name in header or [] if name}
    if not set(REQUIRED) <= columns:
        plan["error"] = REASONS["missing_columns"]
        return plan

    index = _Index(problems)
    seen = {_attempt_key(a["problem_id"], a["date"], a["outcome"], a["time_seconds"], a["notes"],
                         a.get("review_of_problem_id")) for a in attempts}
    names = set(pattern_names)
    rows = [{(k or "").strip().lower(): (v or "").strip() for k, v in raw.items() if k is not None} for raw in rows]

    # First pass: the custom problems this file can create, so that a review_of
    # pointing at one created further down the file still matches.
    candidates = {}
    for row in rows:
        title, link = row.get("title", ""), row.get("link", "")
        patterns = [p.strip() for p in row.get("patterns", "").split(";") if p.strip()]
        if not title or not row.get("difficulty") or not patterns or index.match(title, link)[0] != "none":
            continue
        problem, problem_errors = validate_problem({"title": title, "link": link, "difficulty": row["difficulty"]},
                                                   patterns, names)
        if problem_errors or any(p not in names for p in patterns):
            continue
        key = f"new-{len(candidates)}"
        candidates[key] = problem
        index.add(key, problem["title"], problem["link"])

    created = []
    for number, row in enumerate(rows, start=2):
        title, link = row.get("title", ""), row.get("link", "")

        reasons = []
        if not row.get("date"):
            reasons.append("date: Enter the date as YYYY-MM-DD.")
        outcome = OUTCOME_CODES.get(row.get("outcome", "").lower(), "")
        values, errors = validate_attempt({"date": row.get("date") or "missing", "outcome": outcome,
                                           "time_minutes": row.get("time_minutes", ""), "notes": row.get("notes", "")},
                                          today, problem_id=0)
        for field, message in errors.items():
            if field == "date" and not row.get("date"):
                continue
            reasons.append(f"{FIELD_NAMES.get(field, field)}: {message}")
        if not title:
            reasons.append("title: Enter a title.")

        review_key = None
        if row.get("review_of"):
            ref = row["review_of"]
            looks_like_link = ref.lower().startswith(("http://", "https://"))
            status, review_key = index.match("" if looks_like_link else ref, ref if looks_like_link else "")
            if status != "found":
                reasons.append(REASONS["review_of"])

        status, key = index.match(title, link) if title else ("none", None)
        if title and status == "ambiguous":
            reasons.append(REASONS["ambiguous"])
        elif title and status == "none":
            # Not a candidate, so it lacks difficulty or patterns, or they are invalid.
            patterns = [p.strip() for p in row.get("patterns", "").split(";") if p.strip()]
            if not row.get("difficulty") or not patterns:
                reasons.append(REASONS["unmatched"])
            else:
                _, problem_errors = validate_problem({"title": title, "link": link, "difficulty": row["difficulty"]},
                                                     patterns, names)
                for field, message in problem_errors.items():
                    reasons.append(f"{FIELD_NAMES.get(field, field)}: {message}")
                unknown = [p for p in patterns if p not in names]
                if unknown:
                    reasons.append("patterns: Not on the pattern list: " + ", ".join(unknown) + ".")

        if reasons:
            plan["skipped"].append((number, " ".join(reasons)))
            continue
        if key in candidates and key not in created:
            created.append(key)
        attempt_key = _attempt_key(key, values["date"], values["outcome"], values["time_seconds"], values["notes"],
                                   review_key)
        if attempt_key in seen:
            plan["skipped"].append((number, REASONS["duplicate"]))
            continue
        seen.add(attempt_key)
        plan["attempts"].append({"row": number, "problem": key, "date": values["date"], "outcome": values["outcome"],
                                 "time_seconds": values["time_seconds"], "notes": values["notes"],
                                 "review_of": review_key})

    # A review_of naming a custom problem that no valid row created cannot be kept.
    for attempt in [a for a in plan["attempts"] if a["review_of"] in candidates and a["review_of"] not in created]:
        plan["attempts"].remove(attempt)
        plan["skipped"].append((attempt["row"], REASONS["review_of"]))
    plan["skipped"].sort()
    plan["new_problems"] = [{"key": key, **candidates[key]} for key in created]
    return plan
