"""Date helpers for YYYY-MM-DD strings."""
from datetime import date, timedelta


def parse(text):
    return date.fromisoformat(text)


def days_between(earlier, later):
    return (parse(later) - parse(earlier)).days


def add_days(text, days):
    return (parse(text) + timedelta(days=days)).isoformat()


MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def short_date(text, today):
    """A date as pages show it, such as "Tue 10 Nov", with the year when it is not this year."""
    day = parse(text)
    label = f"{WEEKDAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]}"
    return label if text[:4] == today[:4] else f"{label} {day.year}"


def full_date(text):
    """A date in full, such as "Tue 10 Nov 2026", for hover text and screen readers."""
    day = parse(text)
    return f"{WEEKDAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]} {day.year}"


def friendly_date(text, today, within=6):
    """A date relative to today when it is within `within` days, otherwise short_date.

    "Today", "Yesterday", "Tomorrow", "in 3 days", "5 days ago". With `within` 1,
    only today, yesterday, and tomorrow are named, as day headings in a list use.
    """
    gap = days_between(today, text)
    if gap == 0:
        return "Today"
    if gap == -1:
        return "Yesterday"
    if gap == 1:
        return "Tomorrow"
    if 1 < gap <= within:
        return f"in {gap} days"
    if -within <= gap < -1:
        return f"{-gap} days ago"
    return short_date(text, today)
