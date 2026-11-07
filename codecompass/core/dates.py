"""Date helpers for YYYY-MM-DD strings."""
from datetime import date, timedelta


def parse(text):
    return date.fromisoformat(text)


def days_between(earlier, later):
    return (parse(later) - parse(earlier)).days


def add_days(text, days):
    return (parse(text) + timedelta(days=days)).isoformat()
