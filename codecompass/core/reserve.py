"""Build the unreviewed Codeforces reserve (R-37) from the Codeforces API's problem set.

Takes the already-parsed `problemset.problems` result, so nothing here contacts
the site. See "Codeforces reserve" in docs/rules.md.
"""
from .codeforces_tags import reserve_patterns
from .levels import atcoder_level, codeforces_level
from .problem_refs import codeforces_link

SOURCE = "Codeforces API"
ATCODER_SOURCE = "AtCoder"
UNMAPPED_HEADER = ["title", "link", "difficulty"]


def _usable(p):
    """A regular programming problem from a contest, whatever its tags or rating."""
    return (p.get("type", "PROGRAMMING") == "PROGRAMMING" and "*special" not in p.get("tags", [])
            and "contestId" in p)


def corrected(names, correction, pattern_order):
    """Apply one correction ({"add": [...], "remove": [...]}) to tag-derived names."""
    if not correction:
        return names
    found = (set(names) - set(correction.get("remove", []))) | set(correction.get("add", []))
    return [name for name in pattern_order if name in found]


def atcoder_rows(source_rows, pattern_order):
    """Reserve rows for AtCoder problems from the editorial-derived source file.

    Each source row has link, title, rating (AtCoder Problems' difficulty
    estimate), solvers, and patterns ("; "-separated, possibly empty). Rows with
    no pattern are left out; atcoder_unmapped lists them instead.
    """
    rows = []
    for s in source_rows:
        names = [n for n in pattern_order if n in {p.strip() for p in s["patterns"].split(";")}]
        if not names:
            continue
        rating = int(s["rating"])
        rows.append({"title": s["title"], "link": s["link"], "difficulty": atcoder_level(rating), "rating": rating,
                     "source": ATCODER_SOURCE, "patterns": "; ".join(names),
                     "_key": (-int(s["solvers"] or 0), 1, s["link"])})
    return rows


def atcoder_unmapped(source_rows):
    """Unmapped-list rows for AtCoder problems whose editorial gave no pattern."""
    return [{"title": s["title"], "link": s["link"], "difficulty": atcoder_level(int(s["rating"]))}
            for s in source_rows if not s["patterns"].strip()]


def reserve_rows(result, pattern_order, corrections=None, extra_rows=()):
    """Catalog-file rows for every usable problem, most-solved first.

    A problem is left out if it is not a programming problem, is tagged
    `*special`, has no rating, or has no tag that maps to a pattern, even
    through the broad-tag fallback. `corrections` maps a problem link to the
    patterns its editorial or accepted code adds or removes (docs/rules.md).
    `extra_rows` (from atcoder_rows) join the same most-solved-first order.
    """
    corrections = corrections or {}
    solved = {(s["contestId"], s["index"]): s.get("solvedCount", 0) for s in result.get("problemStatistics", [])}
    rows = []
    for p in result["problems"]:
        if not _usable(p) or not p.get("rating"):
            continue
        link = codeforces_link(p["contestId"], p["index"])
        names = corrected(reserve_patterns(p.get("tags", []), pattern_order), corrections.get(link), pattern_order)
        if not names:
            continue
        rows.append({
            "title": p["name"].strip(),
            "link": link,
            "difficulty": codeforces_level(p["rating"]),
            "rating": p["rating"],
            "source": SOURCE,
            "patterns": "; ".join(names),
            "_key": (-solved.get((p["contestId"], p["index"]), 0), -p["contestId"], p["index"]),
        })
    rows += [dict(r) for r in extra_rows]
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
