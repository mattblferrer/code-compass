"""Difficulty levels: from site ratings (R-01) and the user's current level (R-13)."""
from . import constants as c


def _from_floors(rating, floors):
    if rating is None:
        return None
    for floor, level in floors:
        if rating >= floor:
            return level
    return "easy"


def codeforces_level(rating):
    return _from_floors(rating, c.CODEFORCES_LEVEL_FLOORS)


def atcoder_level(difficulty):
    return _from_floors(difficulty, c.ATCODER_LEVEL_FLOORS)


def current_level(attempts, starting, very_hard_on=False):
    """The user's current difficulty level.

    `attempts` are all attempts oldest first, each with "difficulty" and "outcome".
    """
    if not attempts:
        return starting
    recent = [a["difficulty"] for a in attempts[-c.LEVEL_WINDOW:]]
    top = max(recent.count(level) for level in c.LEVELS)
    # A tie goes to the harder level.
    level = [lv for lv in c.LEVELS if recent.count(lv) == top][-1]

    at_level = [a["outcome"] for a in attempts if a["difficulty"] == level][-c.LEVEL_STEP_WINDOW:]
    index = c.LEVELS.index(level)
    if at_level.count(c.SOLVED_ALONE) >= c.LEVEL_STEP_COUNT:
        index = min(index + 1, len(c.LEVELS) - 1)
    elif at_level.count(c.NOT_SOLVED) >= c.LEVEL_STEP_COUNT:
        index = max(index - 1, 0)
    if not very_hard_on:
        index = min(index, c.LEVELS.index(c.VERY_HARD) - 1)
    return c.LEVELS[index]
