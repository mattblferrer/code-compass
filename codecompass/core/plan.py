"""The interview prep plan (R-44): which patterns to work on each day until an interview.

Plain functions on plain data; "today" is passed in. The plan names patterns, not
problems: problems are still picked on the day by the interview focus rule (R-15).
"""
from . import constants as c
from .dates import add_days, days_between


def weakest_first(names, scores, order):
    """Patterns ordered weakest first: those without a score before scored ones, then by
    score, ties in pattern-list order. `scores` maps a name to its score."""
    position = {name: i for i, name in enumerate(order)}
    return sorted(names, key=lambda n: (n in scores, scores.get(n, 0), position.get(n, len(order))))


def plan_patterns(interview_patterns, scores, active, order, weakest=c.PLAN_WEAKEST):
    """The patterns a plan covers: the interview's own, or else the `weakest` active
    patterns. Either way weakest first."""
    if interview_patterns:
        return weakest_first(interview_patterns, scores, order)
    return weakest_first(active, scores, order)[:weakest]


def prep_plan(today, interview_date, patterns, per_day=c.PLAN_PATTERNS_PER_DAY):
    """One entry per day from today to the day before the interview.

    Each day takes the next `per_day` patterns in turn, weakest first, starting again
    from the weakest when the list runs out; the last day, when there is more than one,
    reviews all of them. Empty when the interview is today or past, or there are no patterns.
    """
    days = days_between(today, interview_date)
    if days <= 0 or not patterns:
        return []
    plan = []
    for i in range(days):
        day = add_days(today, i)
        if i == days - 1 and days > 1:
            plan.append({"date": day, "patterns": list(patterns), "mixed": True})
            continue
        take = [patterns[(i * per_day + k) % len(patterns)] for k in range(min(per_day, len(patterns)))]
        plan.append({"date": day, "patterns": take, "mixed": False})
    return plan
