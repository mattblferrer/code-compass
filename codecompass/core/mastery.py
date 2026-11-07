"""Mastery score for one pattern (R-09, R-10). See docs/rules.md."""
from . import constants as c
from .dates import days_between


def fade(days):
    return 0.5 ** (days / c.FADE_HALF_LIFE_DAYS)


def expected_level_index(score):
    for floor, index in c.EXPECTED_LEVEL_FLOORS:
        if score >= floor:
            return index
    return 0


def raw_score(attempts, tier, today):
    """Score from 0 to 100 for attempts given oldest first, in logged order.

    Each attempt is a dict with "date", "difficulty", and "outcome".
    """
    score, previous = 0.0, None
    for attempt in attempts:
        if previous is not None:
            score *= fade(days_between(previous, attempt["date"]))
        level = c.LEVELS.index(attempt["difficulty"])
        stretch = max(0, level - expected_level_index(score))
        target = 100 * c.OUTCOME_VALUE[attempt["outcome"]]
        if target >= score:
            rate = min(c.RATE_UP[tier] + c.STRETCH_BONUS * stretch, c.MAX_RATE_UP)
        else:
            rate = c.RATE_DOWN_STRETCH if stretch else c.RATE_DOWN
        score += rate * (target - score)
        previous = attempt["date"]
    if previous is None:
        return 0.0
    return round(score * fade(days_between(previous, today)), 2)


def pattern_score(attempts, tier, today):
    """The score, or None when the pattern shows "not enough data"."""
    if len(attempts) < c.MIN_ATTEMPTS:
        return None
    return raw_score(attempts, tier, today)
