"""Validation for attempts and custom problems.

The logging form and CSV import share these functions (R-05, R-20). Each
returns (values, errors), where errors maps a field name to a message.
"""
import re
from datetime import date

from . import constants as c
from .problem_refs import from_link

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
    elif link:
        # A link to a known site is stored in that site's form, so it can be found by ID (R-38).
        found = from_link(link)
        link = found[1] if found else link
    # A rating comes only from a lookup (R-35); AtCoder estimates can be negative.
    rating_text = _text(data, "rating")
    try:
        rating = int(rating_text) if rating_text else None
    except ValueError:
        rating = None
    values = {"title": title, "difficulty": difficulty, "patterns": chosen, "link": link or None, "rating": rating}
    return values, errors


def format_minutes(seconds):
    """Minutes for display and export: whole numbers stay whole."""
    if seconds is None:
        return ""
    minutes = round(seconds / 60, 4)
    return str(int(minutes)) if minutes == int(minutes) else str(minutes)


def format_clock(seconds):
    """Time taken as the timer shows it, minutes:seconds (for example 46:22 or 75:03)."""
    if seconds is None:
        return ""
    return f"{seconds // 60}:{seconds % 60:02d}"


PREFERENCES = ("target", "mastered")


def validate_settings(data, pattern_names, sites, kinds):
    """Check the settings form (R-13, R-32, R-36).

    `data` has "starting_difficulty", and "advanced_on", "very_hard_on", and
    "reviews_on" (R-41), each present when checked, "pref:<pattern>" set to "", "target", or "mastered" for each
    pattern, and "show:<site>:<kind>" present for each site switch left on.
    A pattern has one preference field, so it cannot be both a target and
    mastered. Returns (values, errors).
    """
    errors = {}
    level = _text(data, "starting_difficulty")
    if level not in c.LEVELS:
        errors["starting_difficulty"] = "Choose a starting difficulty."
    preferences = {}
    for name in pattern_names:
        choice = _text(data, f"pref:{name}")
        if choice and choice not in PREFERENCES:
            errors["preferences"] = "Choose target, mastered, or neither for each pattern."
        elif choice:
            preferences[name] = choice
    hidden = {(site, kind) for site in sites for kind in kinds if not data.get(f"show:{site}:{kind}")}
    # A weekly goal of problems solved (R-43); blank or 0 means no goal.
    goal = _text(data, "weekly_goal") or "0"
    if not _WHOLE.fullmatch(goal) or int(goal) > c.MAX_WEEKLY_GOAL:
        errors["weekly_goal"] = f"Enter a whole number from 0 to {c.MAX_WEEKLY_GOAL}, or leave it blank for no goal."
        goal = "0"
    values = {
        "starting_difficulty": level,
        "advanced_on": "1" if data.get("advanced_on") else "0",
        "very_hard_on": "1" if data.get("very_hard_on") else "0",
        "reviews_on": "1" if data.get("reviews_on") else "0",
        "weekly_goal": str(int(goal)),
        "preferences": preferences,
        "hidden": hidden,
    }
    return values, errors


def validate_interview(data, patterns, pattern_names):
    """Check an upcoming interview (R-15).

    `data` has "company", "date", and optional "target_difficulty"; `patterns`
    is the list of chosen pattern names. Company and date are required. A past
    date is allowed: the interview is kept but ignored, as docs/rules.md says.
    Returns (values, errors).
    """
    errors = {}
    company = _text(data, "company")
    if not company:
        errors["company"] = "Enter the company name."
    day = _text(data, "date")
    try:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError
    except ValueError:
        errors["date"] = MESSAGES["date_format"]
    difficulty = _text(data, "target_difficulty")
    if difficulty and difficulty not in c.LEVELS:
        errors["target_difficulty"] = "Choose a difficulty, or leave it as any."
    daily = _text(data, "daily_target") or str(c.PLAN_DAILY_DEFAULT)
    if not _WHOLE.fullmatch(daily) or not 1 <= int(daily) <= c.PLAN_DAILY_MAX:
        errors["daily_target"] = f"Enter a whole number of problems a day from 1 to {c.PLAN_DAILY_MAX}."
        daily = str(c.PLAN_DAILY_DEFAULT)
    chosen = [p for p in patterns if p in pattern_names]
    values = {"company": company, "date": day, "target_difficulty": difficulty or None,
              "patterns": [name for name in pattern_names if name in chosen], "daily_target": int(daily)}
    return values, errors


# A whole number in ASCII digits: str.isdigit() also passes digits such as "²" that int() refuses.
_WHOLE = re.compile(r"[0-9]+")

# Usernames are sent to the site in a request, so only the characters the sites allow are accepted.
_USERNAME = re.compile(r"^[A-Za-z0-9_.\-]{1,40}$")


def validate_accounts(data, sites):
    """Check the linked-account usernames (R-33). A blank field unlinks that site.

    Only a public username is asked for, never a password or cookie (R-03).
    Returns (values, errors), where values maps each site to a username or None.
    """
    errors, values = {}, {}
    for site in sites:
        name = _text(data, f"username:{site}")
        if name and not _USERNAME.match(name):
            errors[site] = "Enter the public username as it appears on the site: letters, digits, _, . or -."
        values[site] = name or None
    return values, errors


def validate_note(text):
    """A problem's note (R-45), trimmed; an empty note means none. Returns (note, error)."""
    note = (text or "").strip()
    if len(note) > c.MAX_NOTE_LENGTH:
        return None, f"Keep the note under {c.MAX_NOTE_LENGTH:,} characters."
    return note, None


def validate_link(url, label):
    """A solution or editorial link for a problem (R-45). Returns (values, error).

    Only web links are kept, since the user opens them in a browser; CodeCompass never
    fetches them (R-03).
    """
    url, label = (url or "").strip(), (label or "").strip()
    if not url.lower().startswith(("http://", "https://")) or " " in url or len(url) < 11:
        return None, "Enter a web link starting with http:// or https://."
    if len(url) > c.MAX_LINK_LENGTH:
        return None, f"Keep the link under {c.MAX_LINK_LENGTH:,} characters."
    if len(label) > c.MAX_LINK_LABEL:
        return None, f"Keep the label under {c.MAX_LINK_LABEL} characters."
    return {"url": url, "label": label or None}, None

