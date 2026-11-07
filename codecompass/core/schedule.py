"""Review intervals (R-12, R-28). See docs/rules.md."""
from . import constants as c
from .dates import add_days, parse

FIRST = "first"
EARLY = "early"
REVIEW = "review"


def review_schedule(attempts):
    """Walk one problem's schedule.

    `attempts` are the attempts on the problem and on its siblings for its
    reviews, oldest first, each a dict with "date" and "outcome". Returns one
    dict per attempt with "kind", "interval", and "due".
    """
    rows, interval, due = [], None, None
    for attempt in attempts:
        outcome = attempt["outcome"]
        if interval is None:
            kind, interval = FIRST, c.FIRST_INTERVAL_DAYS[outcome]
        elif parse(attempt["date"]) < parse(due):
            kind, interval = EARLY, c.FIRST_INTERVAL_DAYS[outcome]
        else:
            kind = REVIEW
            if outcome == c.SOLVED_ALONE:
                interval *= 2
            else:
                interval = c.FIRST_INTERVAL_DAYS[outcome]
        due = add_days(attempt["date"], interval)
        rows.append({"kind": kind, "interval": interval, "due": due})
    return rows


def next_due(attempts):
    rows = review_schedule(attempts)
    return rows[-1]["due"] if rows else None
