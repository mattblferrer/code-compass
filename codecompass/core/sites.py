"""The site filter (R-36): which catalog problems a hidden site removes from recommendations.

A problem's site comes from its link. A problem with at least one advanced
pattern is an advanced problem, and any other problem is a core problem.
"""
from urllib.parse import urlparse

from .problem_refs import SITES, from_link

# Sites with catalog or reserve problems, in the order the settings page lists them.
FILTER_SITES = ("leetcode", "codeforces", "cses", "atcoder")
KINDS = ("core", "advanced")


def site_label(link):
    """Where a problem is from, for lists: "LeetCode", "Codeforces", "CSES", or "AtCoder";
    another site's address, such as "hackerrank.com"; or "Custom" without a link."""
    if not link:
        return "Custom"
    found = from_link(link)
    if found:
        return SITES[found[0]]
    host = urlparse(link if "//" in link else "//" + link).hostname or ""
    return host.removeprefix("www.") or "Custom"


def problem_kind(patterns, advanced):
    """"advanced" if any of the problem's patterns is advanced, otherwise "core"."""
    return "advanced" if any(name in advanced for name in patterns) else "core"


def is_hidden(link, patterns, advanced, hidden):
    """Whether the filter hides this problem.

    `hidden` is a set of (site, kind) pairs that are switched off. A problem with
    no link, or a link to a site the filter does not cover, is never hidden.
    """
    if not hidden or not link:
        return False
    found = from_link(link)
    return bool(found) and (found[0], problem_kind(patterns, advanced)) in hidden
