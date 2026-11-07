"""Recommendation list (R-13, R-14, R-15, R-29, R-32). See docs/rules.md."""
from . import constants as c
from .dates import days_between

REVIEW = "review"
TARGET = "target"
UNSCORED = "unscored"
WEAK = "weak"
INTERVIEW = "interview"


def active_interview(interviews, today):
    """The interview that focuses the list (R-15), or None.

    Each interview has "company", "date", and optional "patterns" and
    "difficulty". The nearest one from today to 14 days ahead is used, and
    interviews on that same date are combined.
    """
    upcoming = [i for i in interviews if 0 <= days_between(today, i["date"]) <= c.FOCUS_WINDOW_DAYS]
    if not upcoming:
        return None
    nearest = min(i["date"] for i in upcoming)
    same_day = [i for i in upcoming if i["date"] == nearest]
    patterns = []
    for item in same_day:
        for pattern in item.get("patterns") or ():
            if pattern not in patterns:
                patterns.append(pattern)
    given = [i["difficulty"] for i in same_day if i.get("difficulty")]
    return {
        "companies": [i["company"] for i in same_day],
        "date": nearest,
        "patterns": patterns,
        "difficulty": max(given, key=c.LEVELS.index) if given else None,
    }


def recommend(state):
    """Build the list.

    `state` keys:
      patterns: pattern names in pattern-list order
      advanced: names of advanced patterns
      catalog: problems with "id", "position", "difficulty", "patterns"
      scores: {pattern: {"score", "last"}} for scored patterns
      unscored_attempts: {pattern: attempt count} for unscored patterns
      due: due reviews with "problem", "patterns", "due", "position"
      excluded: problem ids that cannot be new (attempted, not now, reserved)
      targets, mastered: pattern names
      level, advanced_on, very_hard_on
      interview: the result of active_interview, or None

    Returns dicts with "kind" (review or new), "problem", "group", and "pattern".
    """
    patterns = list(state["patterns"])
    advanced = set(state.get("advanced", ()))
    targets = set(state.get("targets", ()))
    mastered = set(state.get("mastered", ()))
    scores = state.get("scores", {})
    attempts = state.get("unscored_attempts", {})
    advanced_on = state.get("advanced_on", False)
    very_hard_on = state.get("very_hard_on", False)
    excluded = set(state.get("excluded", ()))
    interview = state.get("interview")
    company = set(interview["patterns"]) if interview else set()

    def active(name):
        return name not in advanced or advanced_on or name in targets or name in company

    def list_order(name):
        return patterns.index(name)

    scored = sorted(
        (p for p in scores if active(p)),
        key=lambda p: (p in mastered, scores[p]["score"], scores[p]["last"], list_order(p)),
    )
    unscored = sorted(
        (p for p in patterns if active(p) and p not in scores),
        key=lambda p: (p in mastered, -attempts.get(p, 0), list_order(p)),
    )
    target_patterns = [p for p in unscored if p in targets] + [p for p in scored if p in targets]

    focus = interview is not None and (bool(company) or bool(scored))
    level_name = state["level"]
    if focus and interview.get("difficulty"):
        level_name = interview["difficulty"]
        if level_name == c.VERY_HARD:
            very_hard_on = True
    level = c.LEVELS.index(level_name)

    def weakness(review):
        values = [scores[p]["score"] if p in scores else -1 for p in review["patterns"]]
        return min(values) if values else -1

    reviews = list(state.get("due", ()))
    if focus:
        reviews.sort(key=lambda r: (weakness(r), r["due"], r["position"]))
    else:
        reviews.sort(key=lambda r: (r["due"], weakness(r), r["position"]))

    result = [
        {"kind": REVIEW, "problem": r["problem"], "group": REVIEW, "pattern": None}
        for r in reviews[: c.MAX_REVIEW_SLOTS]
    ]
    chosen_ids = set()

    def pick(pattern, is_target):
        options = []
        for problem in state["catalog"]:
            if pattern not in problem["patterns"]:
                continue
            if problem["id"] in excluded or problem["id"] in chosen_ids:
                continue
            if not all(active(p) for p in problem["patterns"]):
                continue
            gap = c.LEVELS.index(problem["difficulty"]) - level
            if abs(gap) > 1 and not is_target:
                continue
            options.append((problem, gap))
        allowed = [o for o in options if very_hard_on or o[0]["difficulty"] != c.VERY_HARD]
        if is_target and not allowed:
            allowed = options
        if not allowed:
            return None
        problem, _ = min(
            allowed,
            key=lambda o: ((abs(o[1]), o[1] > 0), len(o[0]["patterns"]) - 1, o[0]["position"]),
        )
        return problem

    supplied = set()

    def fill(group_name, group, count, is_target=False):
        added, just_reset = 0, False
        while added < count:
            progress = False
            for pattern in group:
                if added == count:
                    break
                if pattern in supplied:
                    continue
                problem = pick(pattern, is_target)
                if problem:
                    chosen_ids.add(problem["id"])
                    supplied.add(pattern)
                    result.append({"kind": "new", "problem": problem["id"], "group": group_name, "pattern": pattern})
                    added += 1
                    progress = True
            if added == count or (not progress and just_reset):
                break
            if not progress:
                supplied.difference_update(group)
                just_reset = True
            else:
                just_reset = False

    def free():
        return c.LIST_SIZE - len(result)

    fill(TARGET, target_patterns, min(c.MAX_TARGET_SLOTS, free()), is_target=True)
    if focus:
        if company:
            ranked = [p for p in unscored if p in company] + [p for p in scored if p in company]
            fill(INTERVIEW, ranked[: c.FOCUS_WEAKEST_PATTERNS], free())
        else:
            fill(WEAK, scored[: c.FOCUS_WEAKEST_PATTERNS], free())
    elif not scored:
        fill(UNSCORED, unscored, free())
    else:
        fill(UNSCORED, unscored, min(c.MAX_UNSCORED_SLOTS, free()))
        fill(WEAK, scored, free())
    for r in reviews[c.MAX_REVIEW_SLOTS:]:
        if free() <= 0:
            break
        result.append({"kind": REVIEW, "problem": r["problem"], "group": REVIEW, "pattern": None})
    return result
