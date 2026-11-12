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
import contextvars
import gzip
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from urllib.parse import quote, urlparse

from .core import sync as parse
from .core.lookup import atcoder_details, codeforces_details
from .core.problem_refs import atcoder_link

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

# Replaced in tests, so pacing is checked without waiting.
sleep = time.sleep
clock = time.monotonic
_last_request = {}
# The time of day, for spacing shared across processes in hosted mode (R-54). Tests replace it.
wall_clock = time.time
# In hosted mode, sync.py sets this for the requests of one step: called as pacer(host, spacing)
# before each request, it waits for the host's turn across every account (R-54).
pacer = contextvars.ContextVar("pacer", default=None)


class RequestFailed(Exception):
    """A lookup or sync that could not finish.

    `kind` is "not_found" (no such problem), "no_user" (no such username),
    "refused", or "failed".
    """

    def __init__(self, kind, site):
        super().__init__(kind)
        self.kind = kind
        self.site = site


class SameHostRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only within the same host, so a request never reaches a source
    that docs/rules.md does not list (R-03). Another host fails like any other error."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlparse(newurl).hostname != urlparse(req.full_url).hostname:
            raise urllib.error.HTTPError(newurl, code, "Redirect to another site refused", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(SameHostRedirects)


def fetch(url, data=None):
    """The response body as bytes; a POST when `data` is given. Raises urllib errors; tests replace this."""
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    with _opener.open(request, timeout=TIMEOUT) as response:
        body = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
        return body


def _pace(url):
    """Wait until the host's spacing has passed since the last request to it."""
    host = urlparse(url).hostname or ""
    host = next((h for h in SPACING if host == h or host.endswith("." + h)), host)
    shared = pacer.get()
    if shared is not None:
        shared(host, SPACING.get(host, 1.0))
        return
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


def sync(site, username, since, known_links=frozenset(), report=None):
    """Submissions at or after `since` (Unix seconds) and the full rating history for a username.

    Returns (submissions, ratings) as read by codecompass.core.sync, or raises
    RequestFailed. `known_links` are problems already in CodeCompass, which need
    no title or difficulty lookup. `report`, if given, is called with what has been
    read so far: the step ("submissions", "details", or "ratings"), how many
    submissions have been read, and the oldest and newest submission times.

    It runs sync_step until the sync is done; hosted mode runs the same steps a few at a
    time, across requests (R-54).
    """
    state = sync_state(site, username, since)
    while True:
        try:
            done = sync_step(state, known_links)
        finally:  # What was read is reported even when a request fails.
            for event in state["events"]:
                if report:
                    report(event)
            state["events"] = []
        if done:
            return state["submissions"], state["ratings"]


def sync_state(site, username, since):
    """A sync not started yet, as plain data that can be saved between steps."""
    if site not in ("codeforces", "atcoder", "leetcode"):
        raise ValueError(f"No sync for {site}")
    first = {"codeforces": "submissions", "atcoder": "ratings", "leetcode": "submissions"}[site]
    return {"site": site, "username": username, "since": since, "phase": first, "start": None,
            "seen": {"read": 0, "oldest": None, "newest": None}, "events": [], "read_ids": [], "raw": [],
            "history": None, "submissions": [], "ratings": []}


def _report(state, name, times=()):
    """Note what has been read so far, for the progress shown while syncing."""
    seen = state["seen"]
    times = list(times)
    if times:
        seen["read"] += len(times)
        low, high = min(times), max(times)
        seen["oldest"] = low if seen["oldest"] is None else min(seen["oldest"], low)
        seen["newest"] = high if seen["newest"] is None else max(seen["newest"], high)
    state["events"].append({"step": name, **seen})


def sync_step(state, known_links=frozenset()):
    """Make the next request of a sync (`state`, from sync_state) and note what it read.
    Returns True when the sync is done; its results are then in state["submissions"] and
    state["ratings"]. Raises RequestFailed as sync does."""
    site, since = state["site"], state["since"]
    user = quote(state["username"], safe="")
    phase = state["phase"]

    if site == "codeforces":
        if phase == "submissions":
            # Pages until the history runs out or reaches back past `since`. The list is
            # newest first, so a later sync usually needs one page and a first sync reads all.
            if state["start"] is None:
                state["start"] = 1
                _report(state, "submissions")
            result = _codeforces(CODEFORCES_STATUS.format(user=user, start=state["start"], count=CODEFORCES_PAGE))
            # A page with no submission not already read does not reach further back, and
            # paging on would repeat forever. (A new submission during the sync shifts the
            # pages by one, so some overlap is normal.)
            ids, read_ids = {s.get("id") for s in result}, set(state["read_ids"])
            if result and ids <= read_ids:
                raise RequestFailed("failed", "Codeforces")
            state["read_ids"] = sorted(read_ids | ids, key=str)
            state["submissions"] += parse.codeforces_submissions(result, since)
            _report(state, "submissions", (s.get("creationTimeSeconds", 0) for s in result))
            if len(result) < CODEFORCES_PAGE or result[-1].get("creationTimeSeconds", 0) < since:
                state["phase"] = "ratings"
                _report(state, "ratings")
            else:
                state["start"] += CODEFORCES_PAGE
            return False
        state["ratings"] = parse.codeforces_ratings(_codeforces(CODEFORCES_RATING.format(user=user)))
        return True

    if site == "atcoder":
        if phase == "ratings":
            _report(state, "ratings")
            state["history"] = _json(_get(ATCODER_HISTORY.format(user=user), "AtCoder", missing="no_user"), "AtCoder")
            # Oldest first from `since`, a page at a time, until a page comes back short.
            state["phase"], state["start"] = "submissions", since
            _report(state, "submissions")
            return False
        if phase == "submissions":
            start = state["start"]
            result = _json(_get(ATCODER_SUBMISSIONS.format(user=user, since=start), "AtCoder Problems"),
                           "AtCoder Problems")
            state["raw"] += result
            _report(state, "submissions", (s["epoch_second"] for s in result))
            if len(result) < ATCODER_PAGE:
                state["phase"] = "details"
                _report(state, "details")
                return False
            following = max(s["epoch_second"] for s in result) + 1
            if following <= start:
                raise RequestFailed("failed", "AtCoder Problems")  # A page that does not move forward.
            state["start"] = following
            return False
        # Titles and difficulty estimates, asked for only when a submitted problem is not in
        # CodeCompass, one request a step so a step never repeats one. Without them the task ID
        # stands in for the title, and the user picks the level.
        unknown = sorted({s["problem_id"] for s in state["raw"]
                          if atcoder_link(s["contest_id"], s["problem_id"]) not in known_links})
        try:
            if unknown and "titles" not in state:
                problems = _json(_get(ATCODER_PROBLEMS, "AtCoder Problems"), "AtCoder Problems")
                state["titles"] = {p["id"]: p["name"] for p in problems if p.get("id") in unknown and p.get("name")}
                return False
            if unknown and "estimates" not in state:
                models = _json(_get(ATCODER_ESTIMATES, "AtCoder Problems"), "AtCoder Problems")
                state["estimates"] = {k: v for k, v in models.items() if k in unknown}
        except RequestFailed as error:
            if error.kind == "refused":
                raise
            state.setdefault("titles", {})  # Titles already read are kept.
            state["estimates"] = {}
        state["submissions"] = parse.atcoder_submissions(state["raw"], since, state.get("titles", {}),
                                                         state.get("estimates", {}))
        state["ratings"] = parse.atcoder_ratings(state["history"],
                                                 lambda text: int(datetime.fromisoformat(text).timestamp()))
        state["raw"] = []
        return True

    _report(state, "submissions")
    body = json.dumps({"query": LEETCODE_QUERY, "variables": {"username": state["username"]}}).encode()
    reply = _json(_get(LEETCODE_GRAPHQL, "LeetCode", data=body), "LeetCode")
    data = reply.get("data") or {}
    # An unknown username returns empty lists, like a user with no activity.
    if not isinstance(data.get("recentAcSubmissionList"), list):
        raise RequestFailed("failed", "LeetCode")
    state["submissions"] = parse.leetcode_submissions(data.get("recentAcSubmissionList"), since)
    state["ratings"] = parse.leetcode_ratings(data.get("userContestRankingHistory"))
    return True
