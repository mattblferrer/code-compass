"""Validation for the pattern and catalog data files (R-01).

Rows are dicts read from CSV. Row numbers count the header as row 1.
"""
from . import constants as c

CATEGORIES = ("core", "advanced")
TIERS = ("narrow", "normal", "broad")


class DataFileError(ValueError):
    """Raised with every problem found in a data file."""

    def __init__(self, filename, messages):
        self.messages = messages
        super().__init__(f"{filename} has errors:\n" + "\n".join(messages))


def _text(row, key):
    return (row.get(key) or "").strip()


def parse_patterns(rows, filename="patterns.csv"):
    """Return pattern dicts with "name", "category", "tier", "description"."""
    patterns, errors, seen = [], [], set()
    for number, row in enumerate(rows, start=2):
        name = _text(row, "name")
        category = _text(row, "category")
        tier = _text(row, "tier")
        description = _text(row, "description")
        problems = []
        if not name:
            problems.append("name is missing")
        elif name in seen:
            problems.append(f"name {name!r} appears more than once")
        if category not in CATEGORIES:
            problems.append(f"category must be one of {', '.join(CATEGORIES)}")
        if tier not in TIERS:
            problems.append(f"tier must be one of {', '.join(TIERS)}")
        if not description:
            problems.append("description is missing")
        if problems:
            errors.append(f"row {number}: " + "; ".join(problems))
            continue
        seen.add(name)
        patterns.append({"name": name, "category": category, "tier": tier, "description": description})
    if errors:
        raise DataFileError(filename, errors)
    return patterns


def parse_catalog(rows, categories, filename="catalog.csv"):
    """Return problem dicts with "title", "link", "difficulty", "rating", "source", "patterns".

    `categories` maps each known pattern name to "core" or "advanced".
    """
    problems, errors, links = [], [], set()
    for number, row in enumerate(rows, start=2):
        title = _text(row, "title")
        link = _text(row, "link")
        difficulty = _text(row, "difficulty").lower()
        rating_text = _text(row, "rating")
        source = _text(row, "source")
        names = [p.strip() for p in _text(row, "patterns").split(";") if p.strip()]
        found = []
        if not title:
            found.append("title is missing")
        if not link:
            found.append("link is missing")
        elif link in links:
            found.append("link appears more than once")
        if difficulty not in c.LEVELS:
            found.append(f"difficulty must be one of {', '.join(c.LEVELS)}")
        rating = None
        if rating_text:
            try:
                rating = int(rating_text)
            except ValueError:
                found.append("rating must be a whole number")
        if not source:
            found.append("source is missing")
        if not names:
            found.append("at least one pattern is required")
        unknown = [n for n in names if n not in categories]
        if unknown:
            found.append("unknown pattern: " + ", ".join(unknown))
        elif difficulty == c.VERY_HARD and names and all(categories[n] == "core" for n in names):
            found.append("very hard problems need at least one advanced pattern")
        if found:
            errors.append(f"row {number}: " + "; ".join(found))
            continue
        links.add(link)
        problems.append({
            "title": title,
            "link": link,
            "difficulty": difficulty,
            "rating": rating,
            "source": source,
            "patterns": names,
        })
    if errors:
        raise DataFileError(filename, errors)
    return problems
