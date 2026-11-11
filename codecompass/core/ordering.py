"""Sorting the attempts listed on a pattern's page.

Plain functions on plain data. Each row has "date", "difficulty", "outcome",
"attempt" (with "id"), and "problem" (with "title").
"""
from . import constants as c

SORT_KEYS = ("date", "problem", "difficulty", "outcome")
# The order a column sorts in when it is first chosen: newest dates first, the rest A to Z,
# easiest level first, and outcomes from solved alone to not solved.
FIRST_ORDER = {"date": "desc", "problem": "asc", "difficulty": "asc", "outcome": "asc"}
DEFAULT_SORT = ("date", "desc")


def chosen_sort(key, order):
    """A valid (key, order), falling back to newest first for anything unknown."""
    if key not in SORT_KEYS:
        return DEFAULT_SORT
    return key, order if order in ("asc", "desc") else FIRST_ORDER[key]


def next_order(column, key, order):
    """The order a column's header sorts in when clicked: the other way if it is the
    current sort, otherwise the column's first order."""
    if column == key:
        return "asc" if order == "desc" else "desc"
    return FIRST_ORDER[column]


def sort_rows(rows, key, order):
    """The rows sorted by `key` in `order`. Ties keep the newest attempt first."""
    value = {
        "date": lambda r: r["date"],
        "problem": lambda r: r["problem"]["title"].casefold(),
        "difficulty": lambda r: c.LEVELS.index(r["difficulty"]),
        "outcome": lambda r: c.OUTCOMES.index(r["outcome"]),
    }[key]
    newest = sorted(rows, key=lambda r: (r["date"], r["attempt"]["id"]), reverse=True)
    return sorted(newest, key=value, reverse=(order == "desc"))
