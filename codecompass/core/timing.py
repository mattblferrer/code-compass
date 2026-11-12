"""Time taken per pattern, shown on a pattern's page (R-49).

Shown only: time taken never affects scores, review dates, or recommendations (R-26).
Plain functions on plain data.
"""
from statistics import median

from . import constants as c


def median_times(rows):
    """{level: {"median": seconds, "count": timed attempts}} for each level with a timed
    attempt, easiest first. `rows` have "difficulty" and "attempt" (with "time_seconds")."""
    by_level = {}
    for r in rows:
        seconds = r["attempt"].get("time_seconds")
        if seconds:
            by_level.setdefault(r["difficulty"], []).append(seconds)
    return {level: {"median": round(median(by_level[level])), "count": len(by_level[level])}
            for level in c.LEVELS if level in by_level}
