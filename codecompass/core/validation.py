"""Validation for attempts and custom problems.

The logging form and CSV import share these functions (R-05, R-20). Each
returns (values, errors), where errors maps a field name to a message.
"""
from datetime import date

from . import constants as c

OUTCOME_LABELS = {
    c.SOLVED_ALONE: "Solved alone",
    c.SOLVED_WITH_HINTS: "Solved with hints",
    c.SOLVED_AFTER_SOLUTION: "Solved after viewing the solution",
    c.NOT_SOLVED: "Not solved",
}

# Shown next to the outcome field (R-04).
OUTCOME_DEFINITIONS = {
    c.SOLVED_ALONE: "No outside help of any kind.",
    c.SOLVED_WITH_HINTS: "Any help short of a full solution, such as AI chat, discussion posts, "
                         "topic tags, a friend, or a beginner hint.",
    c.SOLVED_AFTER_SOLUTION: "You read or watched a full solution, or used AI-written code.",
    c.NOT_SOLVED: "You did not reach a working solution.",
}

MESSAGES = {
    "problem": "Choose a problem.",
    "date_format": "Enter the date as YYYY-MM-DD.",
    "date_future": "The date cannot be in the future.",
    "outcome": "Choose an outcome.",
    "outcome_hint": "A hint was revealed for this problem, so this attempt cannot be saved as solved alone.",
    "time": "Enter the time as a positive number of minutes.",
    "title": "Enter a title.",
    "difficulty": "Choose a difficulty.",
    "patterns": "Choose at least one pattern.",
    "link": "Enter a link starting with http:// or https://, or leave it blank.",
}


def _text(data, key):
    return (data.get(key) or "").strip()


def parse_minutes(text):
    """Seconds from a positive number of minutes, or None if invalid."""
    try:
        minutes = float(text)
    except ValueError:
        return None
    if not minutes > 0 or minutes == float("inf"):
        return None
    return max(1, round(minutes * 60))


def validate_attempt(data, today, problem_id, hint_revealed=False):
    """Check an attempt.

    `data` has "date", "outcome", "time_minutes", optional "time_seconds" (from
    the timer, used while the minutes still match it), and "notes". `problem_id` is the resolved
    problem or None. `hint_revealed` is True when an unused hint was revealed
    for the problem (R-27).
    """
    errors, values = {}, {"problem_id": problem_id}

    if problem_id is None:
        errors["problem"] = MESSAGES["problem"]

    day = _text(data, "date") or today
    try:
        parsed = date.fromisoformat(day)
    except ValueError:
        errors["date"] = MESSAGES["date_format"]
    else:
        if parsed.isoformat() != day:
            errors["date"] = MESSAGES["date_format"]
        elif day > today:
            errors["date"] = MESSAGES["date_future"]
    values["date"] = day

    outcome = _text(data, "outcome")
    if outcome not in c.OUTCOMES:
        errors["outcome"] = MESSAGES["outcome"]
    elif hint_revealed and outcome == c.SOLVED_ALONE:
        errors["outcome"] = MESSAGES["outcome_hint"]
    values["outcome"] = outcome

    seconds = None
    timer = _text(data, "time_seconds")
    minutes = _text(data, "time_minutes")
    if timer.isdigit() and int(timer) >= 1 and minutes == format_minutes(int(timer)):
        # The timer's exact seconds, unless the minutes were changed by hand.
        seconds = int(timer)
    elif minutes:
        seconds = parse_minutes(minutes)
        if seconds is None:
            errors["time"] = MESSAGES["time"]
    values["time_seconds"] = seconds

    values["notes"] = _text(data, "notes") or None
    return values, errors


def validate_problem(data, patterns, pattern_names):
    """Check a custom problem (R-02). `patterns` is the list of chosen names."""
    errors = {}
    title = _text(data, "title")
    if not title:
        errors["title"] = MESSAGES["title"]
    difficulty = _text(data, "difficulty").lower()
    if difficulty not in c.LEVELS:
        errors["difficulty"] = MESSAGES["difficulty"]
    chosen = [p for p in patterns if p in pattern_names]
    if not chosen:
        errors["patterns"] = MESSAGES["patterns"]
    link = _text(data, "link")
    if link and not link.lower().startswith(("http://", "https://")):
        errors["link"] = MESSAGES["link"]
    values = {"title": title, "difficulty": difficulty, "patterns": chosen, "link": link or None}
    return values, errors


def format_minutes(seconds):
    """Minutes for display and export: whole numbers stay whole."""
    if seconds is None:
        return ""
    minutes = round(seconds / 60, 4)
    return str(int(minutes)) if minutes == int(minutes) else str(minutes)
