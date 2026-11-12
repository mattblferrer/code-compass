"""Find the problem for an attempt: by title, or by site and problem ID (R-38).

The form sends the typed text in "problem", the id chosen from the search list
(if any) in "problem_id", and optionally "site" and "ref" (a problem ID or link).
"""
from urllib.parse import urlencode

from flask import current_app, url_for

from . import catalog, queries
from .core.problem_refs import ID_HINTS, SITES, from_id, from_link, short_id
from .core.validation import MESSAGES as VALIDATION_MESSAGES

OTHER = "other"
SEARCH_LIMIT = 12

MESSAGES = {
    # These two start with the R-05 message, so it still names the field to fix.
    "none": f"{VALIDATION_MESSAGES['problem']} Pick one from the list, or find it by site and ID.",
    "unknown": f"{VALIDATION_MESSAGES['problem']} No saved problem has that title, so pick one from the list "
               "or find it by site and ID.",
    "ambiguous": "Several problems have that title. Choose one from the list, or find it by site and ID.",
    "other": "Problems from other sites are logged as custom problems.",
    "not_found": "That problem is not in CodeCompass yet.",
    # A Codeforces or AtCoder problem whose tags, editorial, or rating give no pattern or
    # level, so it is not in the reserve (R-37).
    "unmapped": "That problem is not in CodeCompass yet, because its tags, editorial, or rating do not map "
                "to a pattern or level. Add it as a custom problem; the details the site gives are filled in.",
}


def label(row):
    """The text shown for a problem in the picker."""
    if row["reserve_position"] is not None and row["catalog_position"] is None:
        site_id = short_id(row["link"])
        if site_id:
            return f"{row['title']} ({site_id})"
    return f"{row['title']} ({row['source']})"


def label_for(conn, problem_id):
    row = queries.picker_row(conn, problem_id)
    return label(row) if row else ""


def custom_url(link=None, title=None, difficulty=None):
    """Where to add a custom problem, with whatever details are known filled in."""
    values = {key: value for key, value in (("link", link), ("title", title), ("difficulty", difficulty)) if value}
    query = urlencode(values)
    return url_for("main.new_problem") + (f"?{query}" if query else "")


def unmapped(link=None, title=None):
    """The unmapped Codeforces problem for this link or title, or None."""
    return catalog.find_unmapped(current_app.config.get("UNMAPPED_PATH"), link=link, title=title)


def find_by_ref(conn, site, ref):
    """{"row", "link", "message", "known"} for a site and an ID or link. `known`
    holds the details of an unmapped Codeforces problem, for the custom form."""
    if site == OTHER:
        return {"row": None, "link": None, "message": MESSAGES["other"], "known": None}
    if site not in SITES:
        found = from_link(ref)
        if not found:
            return {"row": None, "link": None, "message": "Choose the site, then enter the problem ID.",
                    "known": None}
        site, link = found
    else:
        link = from_id(site, ref)
    if not link:
        return {"row": None, "link": None, "message": f"Enter {ID_HINTS[site]}, or paste the problem's link.",
                "known": None}
    row = queries.problem_by_link(conn, link)
    if not row:
        known = unmapped(link=link)
        return {"row": None, "link": link, "message": MESSAGES["unmapped" if known else "not_found"], "known": known}
    return {"row": queries.picker_row(conn, row["id"]), "link": link, "message": None, "known": None}


def custom_url_for(found):
    """The custom-problem link for a find_by_ref result that matched nothing."""
    known = found.get("known") or {}
    return custom_url(found["link"], known.get("title"), known.get("difficulty"))


def resolve(conn, form):
    """(problem_id, error) for the submitted form. `error` is a dict with "message" and
    an optional "custom_url", or None."""
    site = (form.get("site") or "").strip()
    ref = (form.get("ref") or "").strip()
    text = (form.get("problem") or "").strip()
    chosen = form.get("problem_id", "")
    picked = None
    if chosen.isdigit():
        row = queries.picker_row(conn, int(chosen))
        if row and label(row) == text:
            picked = row["id"]

    # A typed ID is used as typed (picking from the list clears it). Otherwise a problem
    # picked by title wins over a leftover site choice, including "Other".
    if ref or (site == OTHER and picked is None):
        found = find_by_ref(conn, site, ref)
        if found["row"]:
            return found["row"]["id"], None
        show_custom = site == OTHER or found["link"] is not None
        return None, {"message": found["message"], "custom_url": custom_url_for(found) if show_custom else None}
    if picked is not None:
        return picked, None
    if not text:
        return None, {"message": MESSAGES["none"]}

    pasted = from_link(text) if "/" in text and "." in text else None
    if pasted:
        row = queries.problem_by_link(conn, pasted[1])
        if row:
            return row["id"], None

    by_label = [r for r in queries.problems_titled_prefix(conn, text) if label(r).lower() == text.lower()]
    if len(by_label) == 1:
        return by_label[0]["id"], None
    by_title = queries.problems_titled(conn, text)
    if len(by_title) == 1:
        return by_title[0]["id"], None
    if len(by_label) > 1 or len(by_title) > 1:
        return None, {"message": MESSAGES["ambiguous"]}
    known = unmapped(link=pasted[1]) if pasted else unmapped(title=text)
    if known:
        return None, {"message": MESSAGES["unmapped"],
                      "custom_url": custom_url(known["link"], known["title"], known["difficulty"])}
    return None, {"message": MESSAGES["unknown"], "custom_url": custom_url(pasted[1] if pasted else None)}


def search(conn, text):
    """Search results as plain dicts for the picker's list."""
    text = text.strip()
    if not text:
        return []
    rows = []
    found = from_link(text) if "/" in text and "." in text else None
    if found:
        row = queries.problem_by_link(conn, found[1])
        if row:
            rows = [queries.picker_row(conn, row["id"])]
    if not rows:
        rows = queries.search_problems(conn, text, SEARCH_LIMIT)
        # Then problems whose note mentions it (R-45), after every title match.
        if len(rows) < SEARCH_LIMIT:
            seen = {r["id"] for r in rows}
            rows += [r for r in queries.search_notes(conn, text, SEARCH_LIMIT) if r["id"] not in seen]
            rows = rows[:SEARCH_LIMIT]
    return [as_result(r) for r in rows]


def as_result(row):
    return {"id": row["id"], "label": label(row), "difficulty": row["difficulty"],
            "reserve": row["catalog_position"] is None and row["reserve_position"] is not None}
