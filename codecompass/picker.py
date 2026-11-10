"""Find the problem for an attempt: by title, or by site and problem ID (R-38).

The form sends the typed text in "problem", the id chosen from the search list
(if any) in "problem_id", and optionally "site" and "ref" (a problem ID or link).
"""
from urllib.parse import urlencode

from flask import url_for

from . import queries
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


def custom_url(link=None):
    """Where to add a custom problem, with the link filled in."""
    query = urlencode({"link": link}) if link else ""
    return url_for("main.new_problem") + (f"?{query}" if query else "")


def find_by_ref(conn, site, ref):
    """{"row", "link", "message"} for a site and an ID or link."""
    if site == OTHER:
        return {"row": None, "link": None, "message": MESSAGES["other"]}
    if site not in SITES:
        found = from_link(ref)
        if not found:
            return {"row": None, "link": None, "message": "Choose the site, then enter the problem ID."}
        site, link = found
    else:
        link = from_id(site, ref)
    if not link:
        return {"row": None, "link": None, "message": f"Enter {ID_HINTS[site]}, or paste the problem's link."}
    row = queries.problem_by_link(conn, link)
    if not row:
        return {"row": None, "link": link, "message": MESSAGES["not_found"]}
    return {"row": queries.picker_row(conn, row["id"]), "link": link, "message": None}


def resolve(conn, form):
    """(problem_id, error) for the submitted form. `error` is a dict with "message" and
    an optional "custom_url", or None."""
    site = (form.get("site") or "").strip()
    ref = (form.get("ref") or "").strip()
    if site == OTHER or ref:
        found = find_by_ref(conn, site, ref)
        if found["row"]:
            return found["row"]["id"], None
        show_custom = site == OTHER or found["link"] is not None
        return None, {"message": found["message"], "custom_url": custom_url(found["link"]) if show_custom else None}

    text = (form.get("problem") or "").strip()
    chosen = form.get("problem_id", "")
    if chosen.isdigit():
        row = queries.picker_row(conn, int(chosen))
        if row and label(row) == text:
            return row["id"], None
    if not text:
        return None, {"message": MESSAGES["none"]}

    if "/" in text and "." in text:
        found = from_link(text)
        row = found and queries.problem_by_link(conn, found[1])
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
    return None, {"message": MESSAGES["unknown"], "custom_url": custom_url()}


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
    return [as_result(r) for r in rows]


def as_result(row):
    return {"id": row["id"], "label": label(row), "difficulty": row["difficulty"],
            "reserve": row["catalog_position"] is None and row["reserve_position"] is not None}
