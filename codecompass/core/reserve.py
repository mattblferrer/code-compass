"""Build the unreviewed Codeforces reserve (R-37) from the Codeforces API's problem set.

Takes the already-parsed `problemset.problems` result, so nothing here contacts
the site. See "Codeforces reserve" in docs/rules.md.
"""
from .codeforces_tags import patterns_for
from .levels import codeforces_level
from .problem_refs import codeforces_link

SOURCE = "Codeforces API"


def reserve_rows(result, pattern_order):
    """Catalog-file rows for every usable problem, most-solved first.

    A problem is left out if it is not a programming problem, is tagged
    `*special`, has no rating, or has no tag that maps to a pattern.
    """
    solved = {(s["contestId"], s["index"]): s.get("solvedCount", 0) for s in result.get("problemStatistics", [])}
    rows = []
    for p in result["problems"]:
        tags = p.get("tags", [])
        if p.get("type", "PROGRAMMING") != "PROGRAMMING" or "*special" in tags or not p.get("rating"):
            continue
        if "contestId" not in p:
            continue
        names = patterns_for(tags, pattern_order)
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
