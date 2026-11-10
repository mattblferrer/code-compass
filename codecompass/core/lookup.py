"""Turn a site's response into custom-problem details (R-35).

No network access here: codecompass/remote.py fetches, and these functions
read what came back. Ratings and tags are mapped by the documented rules
(docs/rules.md, docs/patterns.md). AtCoder has no tags, so its patterns stay
for the user to choose.
"""
import html
import re

from .codeforces_tags import patterns_for
from .levels import atcoder_level, codeforces_level
from .problem_refs import atcoder_link, codeforces_link

# The leading problem letter in an AtCoder page title, as in "A - Welcome to AtCoder".
_ATCODER_LETTER = re.compile(r"^[A-Za-z][0-9]?\s+-\s+")


def codeforces_details(result, contest, index, pattern_order):
    """Details for one problem from a `problemset.problems` result, or None if it is not there."""
    for p in result.get("problems", []):
        if str(p.get("contestId")) == str(contest) and p.get("index", "").upper() == index.upper():
            rating = p.get("rating")
            return {
                "site": "Codeforces",
                "title": p["name"].strip(),
                "link": codeforces_link(contest, p["index"]),
                "rating": rating,
                "difficulty": codeforces_level(rating) if rating else "",
                "patterns": patterns_for(p.get("tags", []), pattern_order),
            }
    return None


def atcoder_details(page, models, contest, task):
    """Details from an AtCoder task page and AtCoder Problems' difficulty estimates, or None.

    `models` may be empty when the estimates could not be fetched; the problem then
    has no rating and the user chooses its level. An estimate flagged as
    experimental is not used, as in the catalog (docs/rules.md).
    """
    match = re.search(r"<title>(.*?)</title>", page, re.S)
    if not match:
        return None
    title = _ATCODER_LETTER.sub("", html.unescape(match.group(1)).strip())
    model = (models or {}).get(task) or {}
    estimate = model.get("difficulty")
    rating = round(estimate) if estimate is not None and not model.get("is_experimental") else None
    return {
        "site": "AtCoder",
        "title": title,
        "link": atcoder_link(contest, task),
        "rating": rating,
        "difficulty": atcoder_level(rating) if rating is not None else "",
        "patterns": [],
    }
