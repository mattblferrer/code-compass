"""Sync by public username and rating history (R-33, R-34).

Tests never call real sites: remote.fetch is replaced by the recorded responses
in tests/data/sync. They keep the shapes of real responses fetched on
2026-11-10, with a fictional username and invented submissions, and each sync
runs at a fixed time, 2026-11-01 12:00 UTC. Submissions fall at midday UTC, so
their local dates are the same in any time zone within 11 hours of UTC.
"""
import io
import json
import urllib.error
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from codecompass import remote, views
from codecompass.core import constants as c
from codecompass.core import sync as rules
from codecompass.core.validation import validate_accounts
from codecompass.db import get_db

DATA = Path(__file__).parent / "data" / "sync"
NOW = 1793534400  # 2026-11-01 12:00 UTC
DAY = 86400
RECORDED = {
    "/api/user.status": "codeforces_status.json",
    "/api/user.rating": "codeforces_rating.json",
    "/atcoder/atcoder-api/v3/user/submissions": "atcoder_submissions.json",
    "/atcoder/resources/problems.json": "atcoder_problems.json",
    "/atcoder/resources/problem-models.json": "atcoder_problem_models.json",
    "/users/practice_user/history/json": "atcoder_history.json",
    "/graphql": "leetcode.json",
}


@pytest.fixture
def sites(monkeypatch):
    """Serve recorded responses by path. `sites.fail` maps a path to an error; every request is recorded."""
    class Sites:
        fail, requests = {}, []

    def fake(url, data=None):
        Sites.requests.append((url, data))
        path = urlparse(url).path
        if path in Sites.fail:
            raise Sites.fail[path]
        if path in RECORDED:
            return (DATA / RECORDED[path]).read_bytes()
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    monkeypatch.setattr(remote, "fetch", fake)
    monkeypatch.setattr(views, "now_seconds", lambda: Sites.now)
    Sites.fail, Sites.requests, Sites.now = {}, [], NOW
    return Sites


def link(client, **usernames):
    data = {f"username:{site}": usernames.get(site, "") for site in ("codeforces", "atcoder", "leetcode")}
    return client.post("/settings/accounts", data=data)


def sync(client):
    return client.post("/sync", follow_redirects=True).get_data(as_text=True)


def profile(client):
    return client.get("/profile").get_data(as_text=True)


def rows(app, sql, *args):
    with app.app_context():
        return [dict(r) for r in get_db().execute(sql, args)]


def items(app, status="pending"):
    """Items by (link, date); Codeforces links are shortened to contest/index, such as 4/A."""
    return {(r["problem_link"].removeprefix("https://codeforces.com/problemset/problem/"), r["date"]): r
            for r in rows(app, "SELECT * FROM sync_items WHERE status = ?", status)}


def item_id(app, link_part):
    return next(r["id"] for r in rows(app, "SELECT id, problem_link FROM sync_items") if link_part in r["problem_link"])


def add_problem(client, title, link, patterns=("Greedy",)):
    client.post("/problems/new", data={"title": title, "link": link, "difficulty": "easy", "patterns": list(patterns)})


# --- Codeforces: listing ---

def test_first_sync_lists_the_last_30_days_once_per_problem_and_day(client, app, sites):
    link(client, codeforces="practice_user")
    page = sync(client)
    assert "Codeforces: 4 new submissions to confirm." in page
    listed = items(app)
    # 1520A had a wrong answer then an accepted one that day: one item, accepted. Its wrong
    # answer the day before folds into that solve too.
    assert listed[("1520/A", "2026-10-28")]["accepted"] == 1
    assert ("1520/A", "2026-10-27") not in listed
    # 4A was solved on 10-18 and failed again on 10-20, with no later solve: two items.
    assert listed[("4/A", "2026-10-20")]["accepted"] == 0
    assert listed[("4/A", "2026-10-18")]["accepted"] == 1
    assert ("2284/F", "2026-10-25") in listed
    # 71A is from 41 days ago, and gym contests are skipped.
    assert len(listed) == 4
    assert rows(app, "SELECT count(*) AS n FROM attempts")[0]["n"] == 0  # Nothing saved before an outcome.
    status_url = sites.requests[0][0]
    assert parse_qs(urlparse(status_url).query)["handle"] == ["practice_user"]


def test_items_show_problem_and_date_with_no_outcome_chosen(client, sites):
    link(client, codeforces="practice_user")
    page = sync(client)
    assert "Do Not Be Distracted!" in page and "2026-10-28" in page
    assert "checked" not in page.split("Waiting for an outcome")[1]
    # "Not solved" is offered only for the item with no accepted submission.
    assert page.count('value="not_solved"') == 1


def test_second_sync_adds_nothing_and_reaches_back_only_to_the_last_sync(client, app, sites):
    link(client, codeforces="practice_user")
    sync(client)
    synced = rows(app, "SELECT last_synced FROM linked_accounts")[0]["last_synced"]
    assert synced == "2026-11-01T12:00:00+00:00"
    sites.now = NOW + 3 * DAY
    sites.requests.clear()
    assert "Codeforces: no new submissions." in sync(client)
    assert len(items(app)) == 4
    # The status list is newest first, so one page reaching past the last sync is enough.
    assert sum("user.status" in url for url, _ in sites.requests) == 1


def test_a_later_accepted_submission_marks_an_existing_item_accepted(client, app, sites):
    from codecompass import sync as syncing

    link(client, codeforces="practice_user")
    sync(client)
    with app.app_context():
        conn = get_db()
        late = [{"link": "https://codeforces.com/problemset/problem/4/A", "title": "Watermelon",
                 "time": 1792497600 + 3600, "accepted": True, "rating": 800, "tags": []}]  # 2026-10-20 13:00 UTC
        added = syncing._store(conn, "codeforces", "practice_user", late, [], NOW, views.local_date)
    assert added == 0
    assert items(app)[("4/A", "2026-10-20")]["accepted"] == 1


def test_failed_day_waiting_for_an_outcome_folds_into_a_later_solve(client, app, sites):
    from codecompass import sync as syncing

    def submission(day, accepted):
        return {"link": "https://codeforces.com/problemset/problem/7/A", "title": "Kalevitch and Chess",
                "time": 1791460800 + day * DAY, "accepted": accepted, "rating": 1100, "tags": []}  # 10-08 + day

    link(client, codeforces="practice_user")
    with app.app_context():
        conn = get_db()
        syncing._store(conn, "codeforces", "practice_user", [submission(0, False), submission(1, False)], [], NOW,
                       views.local_date)
    first = items(app)[("7/A", "2026-10-08")]["id"]
    response = client.post(f"/sync/items/{first}", data={"outcome": c.NOT_SOLVED, "details": "1",
                                                         "difficulty": "easy", "patterns": ["Simulation and Implementation"]})
    assert response.status_code == 302  # Logged before the solve, so it stays.
    assert ("7/A", "2026-10-09") in items(app)
    with app.app_context():
        conn = get_db()
        added = syncing._store(conn, "codeforces", "practice_user",
                               [submission(1, False), submission(3, True)], [], NOW, views.local_date)
    assert added == 1
    assert [key for key in items(app) if key[0] == "7/A"] == [("7/A", "2026-10-11")]
    assert ("7/A", "2026-10-08") in items(app, "confirmed")
    assert rows(app, "SELECT outcome FROM attempts") == [{"outcome": c.NOT_SOLVED}]


# --- Confirming ---

def test_each_outcome_saves_the_matching_attempt(client, app, sites):
    add_problem(client, "Watermelon (mine)", "https://codeforces.com/problemset/problem/4/A")
    link(client, codeforces="practice_user")
    sync(client)
    accepted = next(r["id"] for (key, day), r in items(app).items() if key == "4/A" and day == "2026-10-18")
    not_accepted = next(r["id"] for (key, day), r in items(app).items() if key == "4/A" and day == "2026-10-20")

    response = client.post(f"/sync/items/{accepted}", data={"outcome": c.SOLVED_WITH_HINTS})
    assert response.status_code == 302
    response = client.post(f"/sync/items/{not_accepted}", data={"outcome": c.NOT_SOLVED})
    assert response.status_code == 302
    saved = rows(app, "SELECT date, outcome, entry_method FROM attempts ORDER BY date")
    assert saved == [{"date": "2026-10-18", "outcome": c.SOLVED_WITH_HINTS, "entry_method": "sync"},
                     {"date": "2026-10-20", "outcome": c.NOT_SOLVED, "entry_method": "sync"}]
    assert ("4/A", "2026-10-18") not in items(app)
    assert ("4/A", "2026-10-18") in items(app, "confirmed")


@pytest.mark.parametrize("outcome", [c.SOLVED_ALONE, c.SOLVED_AFTER_SOLUTION])
def test_solved_alone_and_after_solution(client, app, sites, outcome):
    add_problem(client, "Watermelon (mine)", "https://codeforces.com/problemset/problem/4/A")
    link(client, codeforces="practice_user")
    sync(client)
    client.post(f"/sync/items/{items(app)[('4/A', '2026-10-18')]['id']}", data={"outcome": outcome})
    assert rows(app, "SELECT outcome FROM attempts") == [{"outcome": outcome}]


def test_accepted_item_cannot_be_saved_as_not_solved_or_without_an_outcome(client, app, sites):
    add_problem(client, "Watermelon (mine)", "https://codeforces.com/problemset/problem/4/A")
    link(client, codeforces="practice_user")
    sync(client)
    item = items(app)[("4/A", "2026-10-18")]["id"]
    assert client.post(f"/sync/items/{item}", data={"outcome": c.NOT_SOLVED}).status_code == 400
    page = client.post(f"/sync/items/{item}", data={}).get_data(as_text=True)
    assert "Choose an outcome." in page
    assert rows(app, "SELECT count(*) AS n FROM attempts")[0]["n"] == 0


def test_unmatched_problem_becomes_a_custom_problem_with_mapped_tags(client, app, sites):
    link(client, codeforces="practice_user")
    page = sync(client)
    assert "New to CodeCompass" in page and "Easy; Backtracking and Brute Force, Simulation and Implementation." in page
    client.post(f"/sync/items/{item_id(app, '1520/A')}", data={"outcome": c.SOLVED_ALONE})
    problem = rows(app, "SELECT id, title, difficulty, rating, is_custom FROM problems WHERE link = ?",
                   "https://codeforces.com/problemset/problem/1520/A")[0]
    assert (problem["title"], problem["difficulty"], problem["rating"], problem["is_custom"]) == \
        ("Do Not Be Distracted!", "easy", 800, 1)
    patterns = rows(app, """SELECT pt.name FROM problem_patterns pp JOIN patterns pt ON pt.id = pp.pattern_id
                            WHERE pp.problem_id = ? ORDER BY pt.name""", problem["id"])
    assert [p["name"] for p in patterns] == ["Backtracking and Brute Force", "Simulation and Implementation"]
    assert rows(app, "SELECT outcome, date FROM attempts") == [{"outcome": c.SOLVED_ALONE, "date": "2026-10-28"}]


def test_missing_level_is_asked_for_before_saving(client, app, sites):
    link(client, codeforces="practice_user")
    page = sync(client)
    assert "Choose the level" in page  # 2284F has no rating.
    item = item_id(app, "2284/F")
    form = client.get(f"/sync/items/{item}").get_data(as_text=True)
    assert 'value="Combinatorics" checked' in form and "Tags on Codeforces: combinatorics, math, matrices" in form
    response = client.post(f"/sync/items/{item}", data={"details": "1", "outcome": c.SOLVED_WITH_HINTS,
                                                       "patterns": ["Combinatorics"]})
    assert response.status_code == 400 and "Choose a difficulty." in response.get_data(as_text=True)
    assert rows(app, "SELECT count(*) AS n FROM attempts")[0]["n"] == 0
    response = client.post(f"/sync/items/{item}", data={"details": "1", "outcome": c.SOLVED_WITH_HINTS,
                                                       "difficulty": "hard", "patterns": ["Combinatorics"]})
    assert response.status_code == 302
    assert rows(app, "SELECT difficulty, rating FROM problems WHERE title = 'Fun Times'") == \
        [{"difficulty": "hard", "rating": None}]


def test_dismissed_item_creates_no_attempt_and_does_not_return(client, app, sites):
    link(client, codeforces="practice_user")
    sync(client)
    item = item_id(app, "2284/F")
    client.post(f"/sync/items/{item}/dismiss")
    sites.now = NOW + DAY
    sync(client)
    assert ("2284/F", "2026-10-25") not in items(app)
    assert rows(app, "SELECT count(*) AS n FROM attempts")[0]["n"] == 0
    assert client.post(f"/sync/items/{item}", data={"outcome": c.SOLVED_ALONE}).status_code == 404


def test_item_is_hidden_when_an_attempt_on_that_problem_and_date_exists(client, app, sites):
    add_problem(client, "Watermelon (mine)", "https://codeforces.com/problemset/problem/4/A")
    client.post("/log", data={"problem": "Watermelon (mine) (custom)", "date": "2026-10-18",
                              "outcome": c.SOLVED_ALONE, "time_minutes": ""})
    assert len(rows(app, "SELECT * FROM attempts")) == 1
    link(client, codeforces="practice_user")
    page = sync(client)
    assert "2026-10-18" not in page.split("Waiting for an outcome")[1].split("Rating history")[0]
    assert "2026-10-20" in page  # The other day is still listed.


def test_revealed_hint_rules_out_solved_alone(client, app, sites):
    add_problem(client, "Watermelon (mine)", "https://codeforces.com/problemset/problem/4/A")
    problem = rows(app, "SELECT id FROM problems WHERE title = 'Watermelon (mine)'")[0]["id"]
    client.post(f"/problems/{problem}/hint")
    link(client, codeforces="practice_user")
    page = sync(client)
    assert "You revealed a hint for this problem" in page
    item = items(app)[("4/A", "2026-10-18")]["id"]
    response = client.post(f"/sync/items/{item}", data={"outcome": c.SOLVED_ALONE})
    assert response.status_code == 400
    assert rows(app, "SELECT count(*) AS n FROM attempts")[0]["n"] == 0


# --- AtCoder and LeetCode ---

def test_atcoder_sync_uses_titles_and_estimates_for_new_problems(client, app, sites):
    link(client, atcoder="practice_user")
    page = sync(client)
    assert "AtCoder: 2 new submissions to confirm." in page
    listed = items(app)
    a = listed[("https://atcoder.jp/contests/abc300/tasks/abc300_a", "2026-10-21")]
    b = listed[("https://atcoder.jp/contests/abc300/tasks/abc300_b", "2026-10-22")]
    assert (a["title"], a["rating"], a["accepted"]) == ("N-choice question", -1147, 1)
    assert (b["title"], b["rating"], b["accepted"]) == ("Same Map in the RPG World", 486, 0)
    # AtCoder has no tags, so the patterns are left for the user.
    assert "Choose the patterns" in page


def test_atcoder_problems_already_here_need_no_extra_requests(client, app, sites):
    add_problem(client, "N-choice", "https://atcoder.jp/contests/abc300/tasks/abc300_a")
    add_problem(client, "Same Map", "https://atcoder.jp/contests/abc300/tasks/abc300_b")
    link(client, atcoder="practice_user")
    sync(client)
    assert not any("resources/" in url for url, _ in sites.requests)


def test_leetcode_sync_reads_recent_accepted_submissions(client, app, sites):
    link(client, leetcode="practice_user")
    page = sync(client)
    assert "LeetCode: 2 new submissions to confirm." in page  # Two Sum twice on one day; Climbing Stairs is too old.
    url, body = next((u, d) for u, d in sites.requests if "leetcode" in u)
    assert url == remote.LEETCODE_GRAPHQL
    assert json.loads(body)["variables"] == {"username": "practice_user"}
    assert all(r["accepted"] == 1 for r in items(app).values())


def test_leetcode_notice_in_settings_sync_list_and_rating_history(client, sites):
    page = client.get("/settings").get_data(as_text=True)
    assert rules.LEETCODE_NOTICE in page
    link(client, leetcode="practice_user")
    assert sync(client).count(rules.LEETCODE_NOTICE) == 1  # On the sync list.
    assert profile(client).count(rules.LEETCODE_NOTICE) == 1  # On the LeetCode rating history.


def test_no_leetcode_notice_on_the_sync_page_without_leetcode(client, sites):
    link(client, codeforces="practice_user")
    assert rules.LEETCODE_NOTICE not in sync(client)


# --- Rating history (R-34) ---

def test_rating_history_equals_the_source(client, app, sites):
    link(client, codeforces="practice_user", atcoder="practice_user", leetcode="practice_user")
    sync(client)
    stored = rows(app, "SELECT site, contest, date, rating FROM rating_history ORDER BY site, date")
    assert stored == [
        {"site": "atcoder", "contest": "AtCoder Beginner Contest 370", "date": "2026-09-07", "rating": 37},
        {"site": "atcoder", "contest": "AtCoder Beginner Contest 375", "date": "2026-10-12", "rating": 190},
        {"site": "codeforces", "contest": "Codeforces Round 960 (Div. 2)", "date": "2026-08-03", "rating": 412},
        {"site": "codeforces", "contest": "Educational Codeforces Round 170", "date": "2026-09-14", "rating": 803},
        {"site": "codeforces", "contest": "Codeforces Round 975 (Div. 3)", "date": "2026-10-12", "rating": 1046},
        {"site": "leetcode", "contest": "Weekly Contest 410", "date": "2026-10-05", "rating": 1500},
        {"site": "leetcode", "contest": "Biweekly Contest 140", "date": "2026-10-19", "rating": 1533},
    ]


def test_stored_history_shows_with_the_network_disabled(client, sites):
    link(client, codeforces="practice_user")
    sync(client)
    offline = urllib.error.URLError("network is unreachable")
    sites.fail = {path: offline for path in RECORDED}
    assert "Could not reach Codeforces, so the Codeforces sync stopped." in sync(client)
    page = profile(client)
    assert "Educational Codeforces Round 170" in page and "1046" in page
    assert "<svg" in page


def test_linked_user_with_no_rated_contests_sees_a_message(client, sites, monkeypatch):
    link(client, atcoder="practice_user")
    assert "to fetch the rating history." in profile(client)
    recorded = remote.fetch
    monkeypatch.setattr(remote, "fetch", lambda url, data=None: b"[]" if "history/json" in url else recorded(url, data))
    sync(client)
    assert "practice_user has no rated contests on AtCoder." in profile(client)


def test_ratings_never_change_scores_due_dates_or_recommendations(client, app, sites):
    for day, outcome in (("2026-10-01", c.SOLVED_ALONE), ("2026-10-08", c.NOT_SOLVED), ("2026-10-15", c.SOLVED_ALONE)):
        client.post("/log", data={"problem": "Two Sum (Test list)", "date": day, "outcome": outcome})
    link(client, codeforces="practice_user")
    client.get("/")  # Shows the saved messages, so they are not part of the comparison.
    before = client.get("/").get_data(as_text=True)
    with app.app_context():
        conn = get_db()
        with conn:
            conn.executemany("INSERT INTO rating_history VALUES ('codeforces', 'practice_user', ?, ?, ?)",
                             [("Round A", "2026-10-02", 3500), ("Round B", "2026-10-09", 100)])
    assert "Arrays and Hashing" in before and 'class="tile scored' in before  # A scored pattern is compared.
    assert client.get("/").get_data(as_text=True) == before


# --- Failures and limits ---

def test_unknown_codeforces_user(client, app, sites):
    body = (DATA / "codeforces_no_user.json").read_bytes()
    sites.fail["/api/user.status"] = urllib.error.HTTPError("u", 400, "Bad Request", {}, io.BytesIO(body))
    link(client, codeforces="no_such_user")
    page = sync(client)
    assert "Codeforces: no user named no_such_user was found." in page
    assert rows(app, "SELECT last_synced FROM linked_accounts") == [{"last_synced": None}]


def test_refused_sync_stops_and_changes_nothing(client, app, sites):
    link(client, codeforces="practice_user", atcoder="practice_user")
    sites.fail["/api/user.rating"] = urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None)
    page = sync(client)
    assert "Codeforces refused the request, so the Codeforces sync stopped. Try again later." in page
    assert "AtCoder: 2 new submissions to confirm." in page
    assert not any("codeforces" in r["problem_link"] for r in items(app).values())
    assert rows(app, "SELECT last_synced FROM linked_accounts WHERE site = 'codeforces'") == [{"last_synced": None}]
    # The refused request is not retried.
    assert sum("user.rating" in url for url, _ in sites.requests) == 1
    assert client.get("/").status_code == 200 and client.get("/log").status_code == 200


def test_requests_are_spaced_by_each_sites_limit(client, sites, no_waiting, monkeypatch):
    monkeypatch.setattr(remote, "clock", lambda: 100.0)  # No time passes between requests.
    link(client, codeforces="practice_user", atcoder="practice_user")
    sync(client)
    # Codeforces: status then rating, 2 s apart. AtCoder Problems: submissions, problems, models, 1.1 s apart.
    assert sorted(no_waiting) == [1.1, 1.1, 2.0]


def test_no_request_without_a_sync(client, sites):
    link(client, codeforces="practice_user", leetcode="practice_user")
    for path in ("/", "/sync", "/settings", "/history", "/log"):
        client.get(path)
    assert sites.requests == []


def test_sync_without_a_linked_account_asks_for_one(client, sites):
    page = sync(client)
    assert "Link a username in settings first." in page
    assert sites.requests == []


# --- Linked accounts ---

def test_settings_ask_only_for_public_usernames(client, app):
    page = client.get("/settings").get_data(as_text=True)
    assert 'name="username:codeforces"' in page and 'type="password"' not in page
    assert "password" not in page.lower() and "cookie" not in page.lower()
    response = link(client, codeforces="tourist", leetcode="bad name!")
    assert response.status_code == 400
    assert rows(app, "SELECT * FROM linked_accounts") == []


def test_changing_a_username_starts_a_first_sync_and_blank_unlinks(client, app, sites):
    link(client, codeforces="practice_user")
    sync(client)
    link(client, codeforces="practice_user")  # Unchanged: keeps the last sync time.
    assert rows(app, "SELECT last_synced FROM linked_accounts")[0]["last_synced"] is not None
    link(client, codeforces="other_user")
    assert rows(app, "SELECT username, last_synced FROM linked_accounts") == \
        [{"username": "other_user", "last_synced": None}]
    link(client)
    assert rows(app, "SELECT * FROM linked_accounts") == []


def test_validate_accounts():
    values, errors = validate_accounts({"username:codeforces": " tourist ", "username:atcoder": "a b"},
                                       ("codeforces", "atcoder", "leetcode"))
    assert values["codeforces"] == "tourist" and values["leetcode"] is None
    assert list(errors) == ["atcoder"]


# --- Plain rules ---

def test_sync_since():
    assert rules.sync_since(None, NOW) == NOW - c.FIRST_SYNC_DAYS * DAY
    assert rules.sync_since(NOW, NOW + 5 * DAY) == NOW - c.SYNC_OVERLAP_HOURS * 3600


def test_group_by_day_merges_one_problem_per_day():
    subs = [{"link": "x", "title": "X", "time": 10, "accepted": False, "rating": None, "tags": []},
            {"link": "x", "title": "X", "time": 20, "accepted": True, "rating": None, "tags": []},
            {"link": "x", "title": "X", "time": 30, "accepted": False, "rating": None, "tags": []}]
    grouped = rules.group_by_day(subs, lambda t: "2026-10-01" if t < 25 else "2026-10-02")
    assert [(g["date"], g["accepted"]) for g in grouped] == [("2026-10-01", True), ("2026-10-02", False)]


def test_failed_days_before_a_solve_become_one_item_and_each_solved_day_stays():
    def sub(day, accepted):
        return {"link": "x", "title": "X", "time": day, "accepted": accepted, "rating": None, "tags": []}

    subs = [sub(1, False), sub(2, True), sub(3, False), sub(4, True), sub(5, False)]
    grouped = rules.group_by_day(subs, lambda t: f"2026-10-0{t}")
    assert [(g["date"], g["accepted"]) for g in grouped] == [
        ("2026-10-02", True), ("2026-10-04", True), ("2026-10-05", False)]


def test_rating_chart_places_contests_by_date():
    rows = [{"contest": "A", "date": "2026-01-01", "rating": 1000},
            {"contest": "B", "date": "2026-01-11", "rating": 1100},
            {"contest": "C", "date": "2026-03-01", "rating": 1050}]
    xs = [d["x"] for d in views.rating_chart(rows)["dots"]]
    # 10 days, then 49 days: the gaps keep that ratio rather than being equal.
    assert (xs[2] - xs[1]) / (xs[1] - xs[0]) == pytest.approx(4.9, rel=0.01)


def test_rating_chart_page_carries_the_points_for_zooming(client, sites):
    link(client, codeforces="practice_user")
    sync(client)
    page = profile(client)
    assert "data-points='[" in page and '"date": "2026-09-14"' in page
    assert "js/rating_chart.js" in page
    assert "Rating history" not in sync(client) and "data-points" not in sync(client)


def test_contest_history_shows_each_change():
    rows = [{"contest": "A", "date": "2026-01-01", "rating": 1602},
            {"contest": "B", "date": "2026-02-01", "rating": 1764},
            {"contest": "C", "date": "2026-03-01", "rating": 1700}]
    changed = rules.rating_changes("codeforces", rows)
    assert [(r["old_rating"], r["change"]) for r in changed] == [(0, 1602), (1602, 162), (1764, -64)]
    assert rules.rating_changes("leetcode", rows[:1])[0]["change"] == 102  # LeetCode starts at 1500.
    assert views.rating_change_label(changed[1]) == "1602 → 1764 (+162)"
    assert views.rating_change_label(changed[2]) == "1764 → 1700 (−64)"


def test_profile_shows_ratings_changes_and_links(client, sites):
    assert "No account is linked." in profile(client)
    link(client, codeforces="practice_user", leetcode="practice_user")
    sync(client)
    page = profile(client)
    assert 'href="https://codeforces.com/profile/practice_user"' in page
    assert 'href="https://leetcode.com/u/practice_user/"' in page
    # Codeforces: 412, 803, 1046 from 0, newest first in the table.
    table = page.split("Contest history")[1]
    assert table.index("+243") < table.index("+391") < table.index("+412")
    assert "<dd>1046</dd>" in page  # Current and best.
    # The chart's points carry the change for the hover details; the no-script dots have it as a title.
    assert '"old_rating": 412' in page and '"change": 391' in page
    assert "Educational Codeforces Round 170, 2026-09-14: 412 → 803 (+391)" in page
    # LeetCode's first contest leaves the rating at 1500; the second adds 33 (1532.618 rounds to 1533).
    assert ">0<" in page and "+33" in page


def test_shared_atcoder_task_matches_the_stored_problem(sites):
    # ABC042 C is task arc058_a; the catalog and reserve store it under arc058.
    stored = "https://atcoder.jp/contests/arc058/tasks/arc058_a"
    raw = [{"epoch_second": NOW, "problem_id": "arc058_a", "contest_id": "abc042", "result": "AC"}]
    assert rules.atcoder_submissions(raw, 0)[0]["link"] == stored
    # Already known by that link, so no title or estimate request is needed.
    assert remote._atcoder_details(raw, {stored}) == ({}, {})
    assert sites.requests == []
