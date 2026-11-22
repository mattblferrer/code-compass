"""Curated pattern guides (R-59): reading docs/resources.md, and checking the data file.

`docs/resources.md` is where the list is written and reviewed. `from_markdown` turns it
into the rows of `data/resources.csv` (the build-resources command), and `parse_resources`
checks that file when the app starts. A test keeps the two in step.
"""
import re

from . import constants as c
from .catalog_rows import DataFileError
from .validation import web_link

INTERVIEW, COMPETITIVE = "interview", "competitive"
AUDIENCES = {INTERVIEW: "Interview", COMPETITIVE: "Competitive programming"}
HEADER = ["pattern", "audience", "site", "title", "link", "note", "needs_account", "trick"]

_PATTERN = re.compile(r"^### \d+\. (.+)$")
# 1. Interview · Site · [Title](https://...) (optional note) · Needs account · Trick
_ENTRY = re.compile(
    r"^\d+\. (Interview|Competitive) · (.+?) · \[(.+?)\]\((\S+?)\)(?: \(([^)]+)\))?"
    r"(?P<flags>(?: · (?:Needs account|Trick))*)$"
)
# Marks how a link was checked; it is for the document's readers, not shown in the app.
CHECK_NOTES = {"listed"}


def from_markdown(text):
    """The resources.csv rows for every guide in docs/resources.md, in its order.

    Raises ValueError naming any numbered line under a pattern that does not read as a guide.
    """
    rows, errors, pattern = [], [], None
    for number, line in enumerate(text.splitlines(), start=1):
        heading = _PATTERN.match(line)
        if heading:
            pattern = heading.group(1).strip()
            continue
        if line.startswith("## "):
            pattern = None
            continue
        if pattern is None or not re.match(r"^\d+\. ", line):
            continue
        entry = _ENTRY.match(line)
        if not entry:
            errors.append(f"line {number}: not a guide entry: {line}")
            continue
        audience, site, title, link, note = entry.groups()[:5]
        flags = entry.group("flags")
        rows.append({
            "pattern": pattern,
            "audience": audience.lower(),
            "site": site.strip(),
            "title": title.strip(),
            "link": link,
            "note": "" if (note or "") in CHECK_NOTES else (note or "").strip(),
            "needs_account": "yes" if "Needs account" in flags else "",
            "trick": "yes" if "Trick" in flags else "",
        })
    if errors:
        raise ValueError("resources.md has entries that cannot be read:\n" + "\n".join(errors))
    return rows


def _rank(guide, category):
    """Where a guide may sit in its pattern's list: the pattern's own audience first (interview
    for core patterns, competitive for advanced ones), then the other, then tricks."""
    if guide["trick"]:
        return 2
    first = INTERVIEW if category == "core" else COMPETITIVE
    return 0 if guide["audience"] == first else 1


def parse_resources(rows, categories, filename="resources.csv"):
    """Return guide dicts with "pattern", "audience", "site", "title", "link", "note",
    "needs_account", and "trick" (both booleans), in file order.

    `categories` maps each pattern name to "core" or "advanced". Raises DataFileError with
    every problem found.
    """
    guides, errors = [], []
    last_rank, counts, links = {}, {}, set()
    for number, row in enumerate(rows, start=2):
        values = {key: (row.get(key) or "").strip() for key in HEADER}
        found = []
        pattern = values["pattern"]
        if pattern not in categories:
            found.append(f"unknown pattern {pattern!r}" if pattern else "pattern is missing")
        if values["audience"] not in AUDIENCES:
            found.append(f"audience must be one of {', '.join(AUDIENCES)}")
        for key in ("site", "title"):
            if not values[key]:
                found.append(f"{key} is missing")
        if not web_link(values["link"]) or " " in values["link"]:
            found.append("link must be a web link starting with http:// or https://")
        elif (pattern, values["link"]) in links:
            found.append("link appears more than once for this pattern")
        for key in ("needs_account", "trick"):
            if values[key] not in ("", "yes"):
                found.append(f"{key} must be yes or empty")
        if found:
            errors.append(f"row {number}: " + "; ".join(found))
            continue
        guide = {**values, "needs_account": values["needs_account"] == "yes", "trick": values["trick"] == "yes"}
        rank = _rank(guide, categories[pattern])
        counts[pattern] = counts.get(pattern, 0) + 1
        if counts[pattern] > c.MAX_GUIDES_PER_PATTERN:
            errors.append(f"row {number}: {pattern} has more than {c.MAX_GUIDES_PER_PATTERN} guides")
        elif rank < last_rank.get(pattern, 0):
            errors.append(f"row {number}: out of order for {pattern}: its own audience's guides come first, "
                          "then the other audience's, then tricks")
        last_rank[pattern] = max(rank, last_rank.get(pattern, 0))
        links.add((pattern, values["link"]))
        guides.append(guide)
    if errors:
        raise DataFileError(filename, errors)
    return guides


def by_pattern(guides):
    """{pattern name: [guide, ...]} in file order."""
    grouped = {}
    for guide in guides:
        grouped.setdefault(guide["pattern"], []).append(guide)
    return grouped
