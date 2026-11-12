"""The History calendar: problems solved per day over a year, and stats for that year (R-40).

Plain functions on plain data. Attempts are dicts with "date" (YYYY-MM-DD) and
"outcome"; "today" is passed in.
"""
from datetime import date, timedelta

from . import constants as c
from .dates import MONTHS

SOLVED = (c.SOLVED_ALONE, c.SOLVED_WITH_HINTS, c.SOLVED_AFTER_SOLUTION)
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def is_date(text):
    """Whether `text` is a real date written as YYYY-MM-DD."""
    if len(text) != 10:
        return False
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return True


def day_totals(attempts):
    """{date: {"solved": n, "attempts": n, and a count for each outcome}} for days with attempts.

    A problem counts as solved on a day for each attempt solved in any way: alone,
    with hints, or after viewing the solution.
    """
    totals = {}
    for a in attempts:
        day = totals.setdefault(a["date"], {"solved": 0, "attempts": 0, **{o: 0 for o in c.OUTCOMES}})
        day["attempts"] += 1
        day[a["outcome"]] += 1
        if a["outcome"] in SOLVED:
            day["solved"] += 1
    return totals


def shade(solved):
    """The calendar shade for a day's solves: 0 for none, up to len(c.CALENDAR_SHADES)."""
    return sum(1 for floor in c.CALENDAR_SHADES if solved >= floor)


def period(year, today):
    """(first day, last day, label) shown: a calendar year, or the past 12 months when `year` is None."""
    end = date.fromisoformat(today)
    if year is None:
        return (end - timedelta(days=364)).isoformat(), today, "Past 12 months"
    return f"{year:04d}-01-01", f"{year:04d}-12-31", str(year)


def weeks(first, last, totals, today, goal=0):
    """Columns of Monday-to-Sunday days covering first..last, for the calendar grid.

    Each day is None outside the period, or {"date", "solved", "shade", "future",
    "totals"}. Each week has "month", the month's short name when a month starts in it,
    and "met", whether its problems solved reached the weekly goal (R-43; never without one).
    """
    start, end = date.fromisoformat(first), date.fromisoformat(last)
    monday = start - timedelta(days=start.weekday())
    columns = []
    while monday <= end:
        days, month = [], None
        for offset in range(7):
            day = monday + timedelta(days=offset)
            if day < start or day > end:
                days.append(None)
                continue
            text = day.isoformat()
            if day.day == 1 or (day == start and not columns):
                month = MONTHS[day.month - 1]
            found = totals.get(text)
            solved = found["solved"] if found else 0
            days.append({"date": text, "solved": solved, "shade": shade(solved), "future": text > today,
                         "totals": found})
        solved = sum(totals.get((monday + timedelta(days=k)).isoformat(), {}).get("solved", 0) for k in range(7))
        columns.append({"days": days, "month": month, "met": bool(goal) and solved >= goal,
                        "solved": solved})
        monday += timedelta(days=7)
    return columns


def week_start(day):
    """The Monday of the week holding `day` (weeks run Monday to Sunday)."""
    d = date.fromisoformat(day)
    return (d - timedelta(days=d.weekday())).isoformat()


def week_progress(totals, today, goal):
    """This week's problems solved against the weekly goal (R-43), or None without a goal."""
    if not goal:
        return None
    start = week_start(today)
    solved = sum(t["solved"] for d, t in totals.items() if start <= d <= today)
    return {"solved": solved, "goal": goal, "met": solved >= goal, "start": start,
            "share": min(1.0, solved / goal)}


def stats(totals, first, last):
    """Totals for the days first..last: problems solved, attempts, days practised, solves per
    day practised (one decimal), and the weekday with the most attempts (None without any)."""
    shown = {d: t for d, t in totals.items() if first <= d <= last}
    solved = sum(t["solved"] for t in shown.values())
    attempts = sum(t["attempts"] for t in shown.values())
    by_weekday = [0] * 7
    for d, t in shown.items():
        by_weekday[date.fromisoformat(d).weekday()] += t["attempts"]
    busiest = None
    if attempts:
        busiest = WEEKDAYS[max(range(7), key=lambda i: (by_weekday[i], -i))]  # Ties go to the earlier day.
    return {
        "solved": solved,
        "attempts": attempts,
        "days": len(shown),
        "average": round(solved / len(shown), 1) if shown else 0,
        "busiest": busiest,
        "busiest_attempts": max(by_weekday) if attempts else 0,
    }


def years(totals, today):
    """Calendar years with attempts, newest first, always including this year."""
    found = {int(d[:4]) for d in totals} | {int(today[:4])}
    return sorted(found, reverse=True)
