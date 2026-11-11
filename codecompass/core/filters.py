"""Filters for the History list and the Sync list.

Plain functions on plain data. Filters come from a page's address as text; anything
unknown is dropped, so a stale or mistyped link shows the whole list.
"""
from . import constants as c
from .progress import is_date

METHODS = {"manual": "Typed in", "csv": "Imported from CSV", "sync": "Saved from sync"}


def _dates(args, out):
    for key in ("start", "end"):
        if is_date(args.get(key) or ""):
            out[key] = args[key]
    return out


def read_history(args, sites, patterns):
    """The History filters in `args` that are valid: outcome, difficulty, site, pattern,
    start and end dates, reviews only, and how the attempt was logged."""
    out = {}
    if args.get("outcome") in c.OUTCOMES:
        out["outcome"] = args["outcome"]
    if args.get("difficulty") in c.LEVELS:
        out["difficulty"] = args["difficulty"]
    if args.get("site") in sites:
        out["site"] = args["site"]
    if args.get("pattern") in patterns:
        out["pattern"] = args["pattern"]
    if args.get("reviews") == "1":
        out["reviews"] = "1"
    if args.get("method") in METHODS:
        out["method"] = args["method"]
    return _dates(args, out)


def read_sync(args, sites, patterns):
    """The Sync filters in `args` that are valid: verdict, difficulty, site, pattern, new
    to CodeCompass or not, needing details or not, and start and end dates."""
    out = {}
    if args.get("verdict") in ("ac", "wa"):
        out["verdict"] = args["verdict"]
    if args.get("difficulty") in c.LEVELS:
        out["difficulty"] = args["difficulty"]
    if args.get("site") in sites:
        out["site"] = args["site"]
    if args.get("pattern") in patterns:
        out["pattern"] = args["pattern"]
    if args.get("new") in ("new", "known"):
        out["new"] = args["new"]
    if args.get("needs") in ("yes", "no"):
        out["needs"] = args["needs"]
    return _dates(args, out)


def _in_dates(day, f):
    return ("start" not in f or day >= f["start"]) and ("end" not in f or day <= f["end"])


def history_match(row, f):
    """Whether an attempt row passes the filters. A row has "outcome", "difficulty", "site",
    "patterns", "date", "review" (whether it completed a review), and "entry_method"."""
    return (("outcome" not in f or row["outcome"] == f["outcome"])
            and ("difficulty" not in f or row["difficulty"] == f["difficulty"])
            and ("site" not in f or row["site"] == f["site"])
            and ("pattern" not in f or f["pattern"] in row["patterns"])
            and ("reviews" not in f or row["review"])
            and ("method" not in f or row["entry_method"] == f["method"])
            and _in_dates(row["date"], f))


def sync_match(item, f):
    """Whether a sync item passes the filters. An item has "accepted", "difficulty" (None
    when not known yet), "site", "patterns", "new" (not in CodeCompass yet), "needs"
    (still needing a level or patterns), and "date"."""
    return (("verdict" not in f or item["accepted"] == (f["verdict"] == "ac"))
            and ("difficulty" not in f or item["difficulty"] == f["difficulty"])
            and ("site" not in f or item["site"] == f["site"])
            and ("pattern" not in f or f["pattern"] in item["patterns"])
            and ("new" not in f or item["new"] == (f["new"] == "new"))
            and ("needs" not in f or item["needs"] == (f["needs"] == "yes"))
            and _in_dates(item["date"], f))
