"""Every request CodeCompass makes to another site (R-03).

Two features use it, and each runs only when the user starts it:

- Problem lookup (R-35): Codeforces' problemset.problems, an AtCoder task page,
  and AtCoder Problems' difficulty estimates.
- Sync (R-33, R-34), by public username: Codeforces' user.status and
  user.rating; AtCoder Problems' user submissions (plus its problem list and
  difficulty estimates, only when a synced problem is not in CodeCompass) and
  AtCoder's rating history; and LeetCode's public recent accepted submissions
  and contest history, from its undocumented GraphQL endpoint.

Requests are plain, with an honest User-Agent and no logins or cookies. They are
spaced by each source's published limit (docs/rules.md lists the sources and limits),
and a refusal is never retried: the sync or lookup stops and says so.
"""
import gzip
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from urllib.parse import quote, urlparse

from .core import sync as parse
from .core.lookup import atcoder_details, codeforces_details

TIMEOUT = 15
USER_AGENT = "CodeCompass (local practice tracker; lookup or sync started by the user)"

CODEFORCES_PROBLEMS = "https://codeforces.com/api/problemset.problems"
CODEFORCES_STATUS = "https://codeforces.com/api/user.status?handle={user}&from={start}&count={count}"
CODEFORCES_RATING = "https://codeforces.com/api/user.rating?handle={user}"
ATCODER_TASK = "https://atcoder.jp/contests/{contest}/tasks/{task}"
ATCODER_HISTORY = "https://atcoder.jp/users/{user}/history/json"
ATCODER_ESTIMATES = "https://kenkoooo.com/atcoder/resources/problem-models.json"
ATCODER_PROBLEMS = "https://kenkoooo.com/atcoder/resources/problems.json"
ATCODER_SUBMISSIONS = "https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions?user={user}&from_second={since}"
LEETCODE_GRAPHQL = "https://leetcode.com/graphql"
LEETCODE_QUERY = """query sync($username: String!) {
  recentAcSubmissionList(username: $username, limit: 20) { title titleSlug timestamp }
  userContestRankingHistory(username: $username) { attended rating contest { title startTime } }
}"""

# Seconds between requests to one host. Codeforces publishes one call per 2 seconds
# and AtCoder Problems asks for more than a second; the others publish none.
SPACING = {"codeforces.com": 2.0, "kenkoooo.com": 1.1, "atcoder.jp": 1.0, "leetcode.com": 2.0}
CODEFORCES_PAGE = 200
ATCODER_PAGE = 500  # AtCoder Problems returns at most this many submissions per request.
MAX_PAGES = 20

# Replaced in tests, so pacing is checked without waiting.
sleep = time.sleep
clock = time.monotonic
_last_request = {}


class RequestFailed(Exception):
    """A lookup or sync that could not finish.

    `kind` is "not_found" (no such problem), "no_user" (no such username),
    "refused", or "failed".
    """

    def __init__(self, kind, site):
        super().__init__(kind)
        self.kind = kind
        self.site = site


def fetch(url, data=None):
    """The response body as bytes; a POST when `data` is given. Raises urllib errors; tests replace this."""
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        body = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
        return body


def _pace(url):
    """Wait until the host's spacing has passed since the last request to it."""
    host = urlparse(url).hostname or ""
    host = next((h for h in SPACING if host == h or host.endswith("." + h)), host)
    last = _last_request.get(host)
    if last is not None:
        wait = SPACING.get(host, 1.0) - (clock() - last)
        if wait > 0:
            sleep(wait)
    _last_request[host] = clock()


def _get(url, site, data=None, missing="not_found"):
    _pace(url)
    try:
        return fetch(url, data) if data is not None else fetch(url)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise RequestFailed(missing, site) from error
        if error.code in (401, 403, 429):
            raise RequestFailed("refused", site) from error
        if error.code == 400 and site == "Codeforces":
            _codeforces_failure(error.read())
        raise RequestFailed("failed", site) from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise RequestFailed("failed", site) from error


def _json(body, site):
    try:
        return json.loads(body)
    except ValueError as error:
        raise RequestFailed("failed", site) from error


def _codeforces_failure(body):
    """Raise the right error for a Codeforces API response with status FAILED."""
    try:
        comment = json.loads(body).get("comment", "")
    except (ValueError, AttributeError):
        comment = ""
    if "not found" in comment:
        raise RequestFailed("no_user", "Codeforces")
    if "limit exceeded" in comment.lower():
        raise RequestFailed("refused", "Codeforces")
    raise RequestFailed("failed", "Codeforces")


def _codeforces(url):
    data = _json(_get(url, "Codeforces"), "Codeforces")
    if data.get("status") != "OK":
        _codeforces_failure(json.dumps(data))
    return data["result"]


def lookup(site, link, pattern_order):
    """Details for the problem at `link` (a stored Codeforces or AtCoder link), or a RequestFailed."""
    if site == "codeforces":
        contest, index = link.rstrip("/").split("/")[-2:]
        details = codeforces_details(_codeforces(CODEFORCES_PROBLEMS), contest, index, pattern_order)
        if details is None:
            raise RequestFailed("not_found", "Codeforces")
        return details
    if site == "atcoder":
        parts = link.rstrip("/").split("/")
        contest, task = parts[-3], parts[-1]
        page = _get(ATCODER_TASK.format(contest=contest, task=task), "AtCoder").decode("utf-8", "replace")
        try:
            models = _json(_get(ATCODER_ESTIMATES, "AtCoder Problems"), "AtCoder Problems")
        except RequestFailed:
            models = {}  # The title still helps; the user picks the level.
        details = atcoder_details(page, models, contest, task)
        if details is None:
            raise RequestFailed("failed", "AtCoder")
        return details
    raise ValueError(f"No lookup for {site}")


def sync(site, username, since, known_links=frozenset()):
    """Submissions at or after `since` (Unix seconds) and the full rating history for a username.

    Returns (submissions, ratings) as read by codecompass.core.sync, or raises
    RequestFailed. `known_links` are problems already in CodeCompass, which need
    no title or difficulty lookup.
    """
    user = quote(username, safe="")
    if site == "codeforces":
        submissions = []
        for page in range(MAX_PAGES):
            result = _codeforces(CODEFORCES_STATUS.format(user=user, start=1 + page * CODEFORCES_PAGE,
                                                          count=CODEFORCES_PAGE))
            submissions += parse.codeforces_submissions(result, since)
            # Newest first, so a page reaching back past `since` is the last one needed.
            if len(result) < CODEFORCES_PAGE or result[-1].get("creationTimeSeconds", 0) < since:
                break
        return submissions, parse.codeforces_ratings(_codeforces(CODEFORCES_RATING.format(user=user)))

    if site == "atcoder":
        history = _json(_get(ATCODER_HISTORY.format(user=user), "AtCoder", missing="no_user"), "AtCoder")
        raw, start = [], since
        for page in range(MAX_PAGES):
            result = _json(_get(ATCODER_SUBMISSIONS.format(user=user, since=start), "AtCoder Problems"),
                           "AtCoder Problems")
            raw += result
            if len(result) < ATCODER_PAGE:
                break
            start = max(s["epoch_second"] for s in result) + 1
        titles, estimates = _atcoder_details(raw, known_links)
        submissions = parse.atcoder_submissions(raw, since, titles, estimates)
        return submissions, parse.atcoder_ratings(history, lambda text: int(datetime.fromisoformat(text).timestamp()))

    if site == "leetcode":
        body = json.dumps({"query": LEETCODE_QUERY, "variables": {"username": username}}).encode()
        reply = _json(_get(LEETCODE_GRAPHQL, "LeetCode", data=body), "LeetCode")
        data = reply.get("data") or {}
        # An unknown username returns empty lists, like a user with no activity.
        if not isinstance(data.get("recentAcSubmissionList"), list):
            raise RequestFailed("failed", "LeetCode")
        return (parse.leetcode_submissions(data.get("recentAcSubmissionList"), since),
                parse.leetcode_ratings(data.get("userContestRankingHistory")))

    raise ValueError(f"No sync for {site}")


def _atcoder_details(raw, known_links):
    """Titles and difficulty estimates, fetched only when a submitted problem is not in CodeCompass."""
    unknown = {s["problem_id"] for s in raw
               if f"https://atcoder.jp/contests/{s['contest_id']}/tasks/{s['problem_id']}" not in known_links}
    if not unknown:
        return {}, {}
    titles, estimates = {}, {}
    try:
        problems = _json(_get(ATCODER_PROBLEMS, "AtCoder Problems"), "AtCoder Problems")
        titles = {p["id"]: p["name"] for p in problems if p.get("id") in unknown and p.get("name")}
        estimates = _json(_get(ATCODER_ESTIMATES, "AtCoder Problems"), "AtCoder Problems")
    except RequestFailed as error:
        if error.kind == "refused":
            raise
        # Without them the task ID stands in for the title, and the user picks the level.
    return titles, estimates
