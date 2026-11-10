"""Build the unreviewed Codeforces reserve (R-37) from the Codeforces API's problem set.

Takes the already-parsed `problemset.problems` result, so nothing here contacts
the site. See "Codeforces reserve" in docs/rules.md.
"""
from .codeforces_tags import reserve_patterns
from .levels import codeforces_level
from .problem_refs import codeforces_link

SOURCE = "Codeforces API"
UNMAPPED_HEADER = ["title", "link", "difficulty"]


def _usable(p):
    """A regular programming problem from a contest, whatever its tags or rating."""
    return (p.get("type", "PROGRAMMING") == "PROGRAMMING" and "*special" not in p.get("tags", [])
            and "contestId" in p)


def reserve_rows(result, pattern_order):
    """Catalog-file rows for every usable problem, most-solved first.

    A problem is left out if it is not a programming problem, is tagged
    `*special`, has no rating, or has no tag that maps to a pattern, even
    through the broad-tag fallback.
    """
    solved = {(s["contestId"], s["index"]): s.get("solvedCount", 0) for s in result.get("problemStatistics", [])}
    rows = []
    for p in result["problems"]:
        if not _usable(p) or not p.get("rating"):
            continue
        names = reserve_patterns(p.get("tags", []), pattern_order)
        if not names:
            continue
        rows.append({
            "title": p["name"].strip(),
            "link": codeforces_link(p["contestId"], p["index"]),
            "difficulty": codeforces_level(p["rating"]),
            "rating": p["rating"],
            "source": SOURCE,
            "patterns": "; ".join(names),
            "_key": (-solved.get((p["contestId"], p["index"]), 0), -p["contestId"], p["index"]),
        })
    rows.sort(key=lambda r: r["_key"])
    seen, unique = set(), []
    for r in rows:
        if r["link"] in seen:
            continue
        seen.add(r["link"])
        del r["_key"]
        unique.append(r)
    return unique


def unmapped_rows(result, pattern_order):
    """The usable problems the reserve cannot hold, because they have no rating or
    no tag that maps to a pattern. Kept only so the custom-problem form can be
    filled in for them (R-38). `difficulty` is blank when there is no rating."""
    rows, seen = [], set()
    for p in result["problems"]:
        if not _usable(p):
            continue
        if p.get("rating") and reserve_patterns(p.get("tags", []), pattern_order):
            continue
        link = codeforces_link(p["contestId"], p["index"])
        if link in seen:
            continue
        seen.add(link)
        rows.append({"title": p["name"].strip(), "link": link,
                     "difficulty": codeforces_level(p["rating"]) if p.get("rating") else ""})
    return rows
