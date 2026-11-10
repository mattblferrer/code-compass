"""Every request CodeCompass makes to another site (R-03).

For now this is the problem lookup (R-35); the optional sync (R-33, R-34) will
live here too. Each request runs only when the user starts it, sends plain
requests with an honest User-Agent, and never retries around a refusal: if a
site refuses, the lookup stops and says so.
"""
import gzip
import json
import urllib.error
import urllib.request

from .core.lookup import atcoder_details, codeforces_details

TIMEOUT = 15
USER_AGENT = "CodeCompass (local practice tracker; problem lookup started by the user)"

CODEFORCES_PROBLEMS = "https://codeforces.com/api/problemset.problems"
ATCODER_TASK = "https://atcoder.jp/contests/{contest}/tasks/{task}"
ATCODER_ESTIMATES = "https://kenkoooo.com/atcoder/resources/problem-models.json"


class LookupFailed(Exception):
    """A lookup that could not finish. `kind` is "not_found", "refused", or "failed"."""

    def __init__(self, kind, site):
        super().__init__(kind)
        self.kind = kind
        self.site = site


def fetch(url):
    """The response body as bytes. Raises urllib errors; tests replace this function."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        body = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
        return body


def _get(url, site):
    try:
        return fetch(url)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise LookupFailed("not_found", site) from error
        if error.code in (401, 403, 429):
            raise LookupFailed("refused", site) from error
        raise LookupFailed("failed", site) from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise LookupFailed("failed", site) from error


def lookup(site, link, pattern_order):
    """Details for the problem at `link` (a stored Codeforces or AtCoder link), or a LookupFailed."""
    if site == "codeforces":
        contest, index = link.rstrip("/").split("/")[-2:]
        try:
            data = json.loads(_get(CODEFORCES_PROBLEMS, "Codeforces"))
        except ValueError as error:
            raise LookupFailed("failed", "Codeforces") from error
        if data.get("status") != "OK":
            raise LookupFailed("failed", "Codeforces")
        details = codeforces_details(data["result"], contest, index, pattern_order)
        if details is None:
            raise LookupFailed("not_found", "Codeforces")
        return details
    if site == "atcoder":
        parts = link.rstrip("/").split("/")
        contest, task = parts[-3], parts[-1]
        page = _get(ATCODER_TASK.format(contest=contest, task=task), "AtCoder").decode("utf-8", "replace")
        try:
            models = json.loads(_get(ATCODER_ESTIMATES, "AtCoder Problems"))
        except (LookupFailed, ValueError):
            models = {}  # The title still helps; the user picks the level.
        details = atcoder_details(page, models, contest, task)
        if details is None:
            raise LookupFailed("failed", "AtCoder")
        return details
    raise ValueError(f"No lookup for {site}")
