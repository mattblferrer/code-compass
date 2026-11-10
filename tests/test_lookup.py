"""Looking up a Codeforces or AtCoder problem when adding a custom problem (R-35).

Tests never call real sites: remote.fetch is replaced by recorded responses in
tests/data/lookup, trimmed from real ones fetched on 2026-11-10.
"""
import urllib.error
from pathlib import Path
from urllib.parse import quote

import pytest

from codecompass import remote
from codecompass.db import get_db

DATA = Path(__file__).parent / "data" / "lookup"
RECORDED = {
    remote.CODEFORCES_PROBLEMS: DATA / "codeforces_problemset.json",
    remote.ATCODER_TASK.format(contest="abc300", task="abc300_a"): DATA / "atcoder_abc300_a.html",
    remote.ATCODER_ESTIMATES: DATA / "atcoder_problem_models.json",
}


@pytest.fixture
def sites(monkeypatch):
    """Serve recorded responses; `sites.fail` maps a URL to an error to raise. Records each URL fetched."""
    class Sites:
        fail = {}
        fetched = []

    def fake(url):
        Sites.fetched.append(url)
        if url in Sites.fail:
            raise Sites.fail[url]
        if url in RECORDED:
            return RECORDED[url].read_bytes()
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    monkeypatch.setattr(remote, "fetch", fake)
    Sites.fail, Sites.fetched = {}, []
    return Sites


def look_up(client, ref, site="codeforces"):
    return client.get(f"/problems/new?lookup=1&site={site}&ref={quote(ref)}").get_data(as_text=True)


def problem_count(app):
    with app.app_context():
        return get_db().execute("SELECT count(*) FROM problems").fetchone()[0]


def test_codeforces_id_fills_the_form_without_saving(client, app, sites):
    before = problem_count(app)
    page = look_up(client, "1520A")
    assert 'value="Do Not Be Distracted!"' in page
    assert 'value="https://codeforces.com/problemset/problem/1520/A"' in page
    assert '<option value="easy" selected>' in page
    assert 'name="rating" value="800"' in page
    assert 'value="Backtracking and Brute Force" checked' in page
    assert 'value="Simulation and Implementation" checked' in page
    assert "Filled in from Codeforces. Check the details, then add the problem." in page
    assert problem_count(app) == before


def test_pasted_codeforces_link_works_too(client, sites):
    page = look_up(client, "https://codeforces.com/contest/1520/problem/A")
    assert 'value="Do Not Be Distracted!"' in page


def test_unrated_problem_leaves_the_level_to_the_user(client, sites):
    page = look_up(client, "2284F")
    assert 'value="Fun Times"' in page
    assert 'name="rating" value=""' in page
    assert "selected" not in page.split('name="difficulty"')[1].split("</select>")[0]
    assert "choose the level," in page
    # Broad tags (math, dp, data structures) map to nothing; specific ones do.
    assert 'value="Combinatorics" checked' in page and 'value="Matrices and Matrix Exponentiation" checked' in page


def test_advanced_tags_open_the_advanced_patterns(client, sites):
    page = look_up(client, "2268E")
    assert '<option value="very hard" selected>' in page
    assert 'value="FFT and NTT" checked' in page
    assert "<details open>" in page


def test_atcoder_task_uses_the_difficulty_estimate(client, sites):
    page = look_up(client, "abc300_a", site="atcoder")
    assert 'value="N-choice question"' in page
    assert 'value="https://atcoder.jp/contests/abc300/tasks/abc300_a"' in page
    assert 'name="rating" value="-1147"' in page and '<option value="easy" selected>' in page
    assert "Filled in from AtCoder. Check the details, choose the patterns, then add the problem." in page


def test_atcoder_lookup_still_helps_without_estimates(client, sites):
    sites.fail[remote.ATCODER_ESTIMATES] = urllib.error.URLError("offline")
    page = look_up(client, "https://atcoder.jp/contests/abc300/tasks/abc300_a")
    assert 'value="N-choice question"' in page
    assert "choose the level and patterns," in page


def test_saving_after_a_lookup_keeps_the_rating(client, app, sites):
    look_up(client, "1520A")
    response = client.post("/problems/new", data={
        "title": "Do Not Be Distracted!", "link": "https://codeforces.com/problemset/problem/1520/A",
        "difficulty": "easy", "rating": "800", "patterns": ["Simulation and Implementation"]})
    assert response.status_code == 302
    with app.app_context():
        row = get_db().execute("SELECT rating, is_custom FROM problems WHERE title = 'Do Not Be Distracted!'").fetchone()
    assert (row["rating"], row["is_custom"]) == (800, 1)


def test_existing_problem_is_shown_instead_of_a_duplicate(client, app, sites):
    client.post("/problems/new", data={"title": "Mine", "link": "https://codeforces.com/contest/1520/problem/A",
                                       "difficulty": "easy", "patterns": ["Greedy"]})
    before = problem_count(app)
    page = look_up(client, "1520a")
    assert "<strong>Mine</strong> is already in CodeCompass." in page
    assert "Log an attempt on it" in page
    assert sites.fetched == []  # No request is needed for a problem already here.
    assert problem_count(app) == before


@pytest.mark.parametrize("ref, site", [("hello", "codeforces"), ("abc300", "atcoder"),
                                       ("https://leetcode.com/problems/two-sum/", "codeforces")])
def test_unrecognized_ids_and_links(client, sites, ref, site):
    page = look_up(client, ref, site=site)
    assert "Enter a Codeforces or AtCoder problem ID" in page
    assert sites.fetched == []


def test_unknown_ids(client, sites):
    assert "Codeforces has no problem with that ID." in look_up(client, "1520Z")
    assert "AtCoder has no problem with that ID." in look_up(client, "abc300_z", site="atcoder")


def test_refused_and_failed_lookups_leave_manual_entry_working(client, app, sites):
    sites.fail[remote.CODEFORCES_PROBLEMS] = urllib.error.HTTPError(remote.CODEFORCES_PROBLEMS, 403, "Forbidden", {}, None)
    page = look_up(client, "1520A")
    assert "Codeforces refused the request, so the lookup stopped." in page
    assert 'value="https://codeforces.com/problemset/problem/1520/A"' in page  # The link is kept for manual entry.

    sites.fail[remote.CODEFORCES_PROBLEMS] = urllib.error.URLError("network is unreachable")
    assert "Could not reach Codeforces. Check your connection" in look_up(client, "1520A")

    response = client.post("/problems/new", data={"title": "Typed by hand", "difficulty": "medium",
                                                  "patterns": ["Greedy"]})
    assert response.status_code == 302


def test_the_form_page_makes_no_request(client, sites):
    client.get("/problems/new")
    client.get("/problems/new?link=" + quote("https://codeforces.com/problemset/problem/1520/A"))
    assert sites.fetched == []
