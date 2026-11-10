"""Turn a site and a problem ID, or a pasted link, into the problem's stored link (R-38).

Links are stored in one form per site (docs/data_model.md), so a problem can be
found by link however the user typed it. Nothing here contacts a site.
"""
import re
from urllib.parse import urlparse

SITES = {
    "leetcode": "LeetCode",
    "codeforces": "Codeforces",
    "cses": "CSES",
    "atcoder": "AtCoder",
}

# What the ID field expects for each site, shown next to it.
ID_HINTS = {
    "leetcode": "the name in the link, such as two-sum",
    "codeforces": "contest and letter, such as 1520A",
    "cses": "the task number, such as 1068",
    "atcoder": "the task ID, such as abc300_a",
}

_CF_ID = re.compile(r"^(\d+)\s*[/_\- ]?\s*([A-Za-z]\d?)$")
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_ATCODER_TASK = re.compile(r"^([a-z0-9_]+)_([a-z0-9]+)$")


def codeforces_link(contest, index):
    return f"https://codeforces.com/problemset/problem/{int(contest)}/{index.upper()}"


def cses_link(task):
    return f"https://cses.fi/problemset/task/{int(task)}"


def leetcode_link(slug):
    return f"https://leetcode.com/problems/{slug}/"


def atcoder_link(contest, task):
    return f"https://atcoder.jp/contests/{contest}/tasks/{task}"


def from_link(text):
    """(site, stored link) for a link to a known site, or None."""
    text = text.strip()
    if "://" not in text:
        text = "https://" + text
    try:
        url = urlparse(text)
    except ValueError:
        return None
    host = (url.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    parts = [p for p in url.path.split("/") if p]

    if host in ("codeforces.com", "mirror.codeforces.com", "m1.codeforces.com", "m2.codeforces.com", "m3.codeforces.com"):
        if len(parts) >= 4 and parts[:2] == ["problemset", "problem"] and parts[2].isdigit():
            return "codeforces", codeforces_link(parts[2], parts[3])
        if len(parts) >= 4 and parts[0] == "contest" and parts[1].isdigit() and parts[2] == "problem":
            return "codeforces", codeforces_link(parts[1], parts[3])
    elif host == "cses.fi":
        if len(parts) >= 3 and parts[0] == "problemset" and parts[1] in ("task", "view") and parts[2].isdigit():
            return "cses", cses_link(parts[2])
    elif host == "leetcode.com":
        if len(parts) >= 2 and parts[0] == "problems" and _SLUG.match(parts[1].lower()):
            return "leetcode", leetcode_link(parts[1].lower())
    elif host == "atcoder.jp":
        if len(parts) >= 4 and parts[0] == "contests" and parts[2] == "tasks":
            return "atcoder", atcoder_link(parts[1].lower(), parts[3].lower())
    return None


def short_id(link):
    """The site's own ID for a stored link, such as "Codeforces 1520A", or None."""
    found = from_link(link or "")
    if not found:
        return None
    site, stored = found
    parts = stored.rstrip("/").split("/")
    if site == "codeforces":
        return f"Codeforces {parts[-2]}{parts[-1]}"
    if site == "atcoder":
        return f"AtCoder {parts[-1]}"
    return f"{SITES[site]} {parts[-1]}"


def from_id(site, text):
    """The stored link for a problem ID on `site`, or None if it is not in that site's form.

    A pasted link to any known site is also accepted.
    """
    text = (text or "").strip()
    if not text:
        return None
    if "/" in text and "." in text:
        found = from_link(text)
        return found[1] if found else None
    if site == "codeforces":
        match = _CF_ID.match(text)
        return codeforces_link(match.group(1), match.group(2)) if match else None
    if site == "cses":
        return cses_link(text) if text.isdigit() else None
    if site == "leetcode":
        slug = text.lower()
        return leetcode_link(slug) if _SLUG.match(slug) else None
    if site == "atcoder":
        match = _ATCODER_TASK.match(text.lower())
        return atcoder_link(match.group(1), text.lower()) if match else None
    return None
