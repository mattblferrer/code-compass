"""Read sync responses into submission items and rating history (R-33, R-34).

Plain functions on plain data. codecompass/remote.py fetches; codecompass/sync.py
stores. Times are Unix seconds here; the caller turns them into the user's
local dates, since only the route layer reads the clock and time zone.
"""
from . import constants as c
from .codeforces_tags import patterns_for
from .levels import atcoder_level, codeforces_level
from .problem_refs import atcoder_link, codeforces_link, leetcode_link

SITES = {"codeforces": "Codeforces", "atcoder": "AtCoder", "leetcode": "LeetCode"}
# Each site's public profile page, linked from the profile page; CodeCompass never fetches these.
PROFILE_URLS = {"codeforces": "https://codeforces.com/profile/{}", "atcoder": "https://atcoder.jp/users/{}",
                "leetcode": "https://leetcode.com/u/{}/"}
LEETCODE_NOTICE = ("LeetCode data comes from an undocumented source, so it may be incomplete, "
                   "out of date, or stop working.")


def sync_since(last_synced, now):
    """Unix seconds to sync from: FIRST_SYNC_DAYS back on a first sync, else the previous sync less the overlap."""
    if last_synced is None:
        return now - c.FIRST_SYNC_DAYS * 86400
    return last_synced - c.SYNC_OVERLAP_HOURS * 3600


def outcome_choices(accepted):
    """Outcomes offered for a synced item (R-33): "not solved" only without an accepted submission."""
    if accepted:
        return (c.SOLVED_ALONE, c.SOLVED_WITH_HINTS, c.SOLVED_AFTER_SOLUTION)
    return c.OUTCOMES


def codeforces_submissions(result, since):
    """Submissions from a user.status result at or after `since`, newest first, skipping gym contests."""
    out = []
    for s in result:
        p = s.get("problem", {})
        contest = p.get("contestId")
        if s.get("creationTimeSeconds", 0) < since or contest is None or contest >= 100000:
            continue
        out.append({
            "link": codeforces_link(contest, p["index"]),
            "title": p.get("name", "").strip(),
            "time": s["creationTimeSeconds"],
            "accepted": s.get("verdict") == "OK",
            "rating": p.get("rating"),
            "tags": p.get("tags", []),
        })
    return out


def atcoder_submissions(result, since, titles=None, estimates=None):
    """Submissions from AtCoder Problems' user/submissions at or after `since`.

    `titles` maps a task id to its title and `estimates` to its difficulty model;
    both are optional and only needed for problems not already in CodeCompass.
    """
    titles, estimates = titles or {}, estimates or {}
    out = []
    for s in result:
        if s.get("epoch_second", 0) < since:
            continue
        task = s["problem_id"]
        model = estimates.get(task) or {}
        estimate = model.get("difficulty")
        out.append({
            "link": atcoder_link(s["contest_id"], task),
            "title": titles.get(task, task),
            "time": s["epoch_second"],
            "accepted": s.get("result") == "AC",
            "rating": round(estimate) if estimate is not None and not model.get("is_experimental") else None,
            "tags": [],
        })
    return out


def leetcode_submissions(result, since):
    """Recent accepted submissions from LeetCode's recentAcSubmissionList at or after `since`."""
    out = []
    for s in result or []:
        time = int(s.get("timestamp") or 0)
        if time < since:
            continue
        out.append({"link": leetcode_link(s["titleSlug"]), "title": s["title"], "time": time,
                    "accepted": True, "rating": None, "tags": []})
    return out


def group_by_day(submissions, local_date):
    """Items to confirm (R-33): one per problem per local date, accepted if any submission that day was.

    A day with no accepted submission is dropped when the problem was accepted on a
    later day, so failed tries and the solve that follows them are one item, dated
    the day of the solve. Accepted submissions on different days stay separate items.
    `local_date` turns Unix seconds into a YYYY-MM-DD date in the user's time zone.
    """
    items = {}
    for s in submissions:
        key = (s["link"], local_date(s["time"]))
        item = items.get(key)
        if item is None:
            items[key] = {**s, "date": key[1]}
        else:
            item["accepted"] = item["accepted"] or s["accepted"]
    last_solved = {}
    for item in items.values():
        if item["accepted"]:
            last_solved[item["link"]] = max(last_solved.get(item["link"], ""), item["date"])
    kept = [i for i in items.values() if i["accepted"] or last_solved.get(i["link"], "") <= i["date"]]
    return sorted(kept, key=lambda i: (i["date"], i["link"]))


def codeforces_ratings(result):
    return [{"contest": r["contestName"], "time": r["ratingUpdateTimeSeconds"], "rating": r["newRating"]}
            for r in result]


def atcoder_ratings(history, parse_time):
    """Rated contests from AtCoder's history/json. `parse_time` turns its ISO times into Unix seconds."""
    return [{"contest": h.get("ContestNameEn") or h["ContestName"], "time": parse_time(h["EndTime"]),
             "rating": h["NewRating"]} for h in history if h.get("IsRated")]


def leetcode_ratings(history):
    return [{"contest": h["contest"]["title"], "time": h["contest"]["startTime"], "rating": round(h["rating"])}
            for h in history or [] if h.get("attended")]


def new_problem_details(site, item, pattern_order):
    """Difficulty and patterns for a synced problem that is not in CodeCompass yet.

    Ratings map by the documented tables, and Codeforces tags by docs/patterns.md.
    A value the site does not give is left blank for the user (R-33).
    """
    rating = item.get("rating")
    if site == "codeforces":
        difficulty = codeforces_level(rating) if rating else ""
        patterns = patterns_for(item.get("tags") or [], pattern_order)
    elif site == "atcoder":
        difficulty = atcoder_level(rating) if rating is not None else ""
        patterns = []
    else:
        difficulty, patterns = "", []
    return {"difficulty": difficulty, "patterns": patterns}


# The rating before a user's first rated contest, as each source reports it: Codeforces'
# oldRating and AtCoder's OldRating are 0 for a first contest, and LeetCode starts at 1500.
STARTING_RATING = {"codeforces": 0, "atcoder": 0, "leetcode": 1500}


def rating_changes(site, rows):
    """Rating history rows, oldest first, with the rating before each contest and the change it made.

    A sync stores the whole history, so the rating before a contest is the one after
    the previous contest. Shown only; never scored (R-34).
    """
    out, before = [], STARTING_RATING.get(site)
    for row in rows:
        change = None if before is None else row["rating"] - before
        out.append({**row, "old_rating": before, "change": change})
        before = row["rating"]
    return out
