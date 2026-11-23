"""The interview prep plan (R-44): which patterns to work on each day until an interview.

Plain functions on plain data; "today" is passed in. The plan names patterns, not
problems. Within the interview focus window, Practice next picks new problems from
today's patterns in the plan (R-15).
"""
from . import constants as c
from .dates import add_days, days_between


def weakest_first(names, scores, order, mastered=()):
    """Patterns ordered weakest first: those without a score before scored ones, then by
    score, ties in pattern-list order, with mastered patterns after all others (R-32).
    `scores` maps a name to its score."""
    position = {name: i for i, name in enumerate(order)}
    return sorted(names, key=lambda n: (n in mastered, n in scores, scores.get(n, 0),
                                        position.get(n, len(order))))


def joined_patterns(interviews, date):
    """The patterns of every interview on `date`, joined in their order, since interviews on
    the same date share one plan (R-15)."""
    joined = []
    for interview in interviews:
        if interview["date"] == date:
            joined.extend(p for p in interview.get("patterns") or () if p not in joined)
    return joined


def plan_patterns(interview_patterns, scores, active, order, mastered=(), weakest=c.PLAN_WEAKEST):
    """The patterns a plan covers: the interview's own, or else the `weakest` active
    patterns. Either way weakest first."""
    if interview_patterns:
        return weakest_first(interview_patterns, scores, order, mastered)
    return weakest_first(active, scores, order, mastered)[:weakest]


def prep_plan(today, interview_date, patterns, per_day=c.PLAN_PATTERNS_PER_DAY):
    """One entry per day from today to the day before the interview.

    Days are counted back from the interview, so each date keeps its place in the plan
    whichever day it is seen from: the day before the interview reviews all the patterns,
    the day before that takes the first `per_day` patterns (the weakest), the day before
    that the next `per_day`, and so on, starting again from the weakest when the list runs
    out. Empty when the interview is today or past, or there are no patterns.
    """
    days = days_between(today, interview_date)
    if days <= 0 or not patterns:
        return []
    plan = []
    for i in range(days):
        day = add_days(today, i)
        back = days - i - 2  # 0 for two days before the interview, 1 for three days before, ...
        if back < 0:
            plan.append({"date": day, "patterns": list(patterns), "mixed": True})
            continue
        take = [patterns[(back * per_day + k) % len(patterns)] for k in range(min(per_day, len(patterns)))]
        plan.append({"date": day, "patterns": take, "mixed": False})
    return plan


def today_patterns(today, interview_date, patterns, per_day=c.PLAN_PATTERNS_PER_DAY):
    """Today's patterns in the plan, which supply new problems near the interview (R-15).

    On the interview day itself, which has no row, all of the plan's patterns, as on the
    mixed review day before it.
    """
    days = prep_plan(today, interview_date, patterns, per_day)
    return days[0]["patterns"] if days else list(patterns)
