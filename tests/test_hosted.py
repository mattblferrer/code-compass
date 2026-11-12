"""Hosted mode: accounts, keeping each account's data its own, request safety, moving data
between modes, and deleting an account (R-25, R-33, R-50 to R-53, R-55, R-56).

These run only when CODECOMPASS_TEST_PG names a PostgreSQL server for tests. Signing in
never contacts GitHub: auth.github_profile is replaced by a fixed profile.
"""
import io
import re
import time
from datetime import date

import pytest

from codecompass import auth
from codecompass.core import constants as c
from conftest import app_db, create_app, local_create_app

pytestmark = pytest.mark.hosted_only

PARENS = "Valid Parentheses (Test list)"
TODAY = date.today().isoformat()


@pytest.fixture
def hosted(tmp_path, catalog_path):
    """A hosted app where every request must be signed in."""
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "hosted.sqlite"), "CATALOG_PATH": catalog_path,
                       "RESERVE_PATH": None, "UNMAPPED_PATH": None, "TESTING_USER_ID": None,
                       "GITHUB_CLIENT_ID": "test-client", "GITHUB_CLIENT_SECRET": "test-secret"})


def sign_in(app, monkeypatch, github_id, login):
    """A test client signed in as the GitHub account `github_id`."""
    client = app.test_client()
    monkeypatch.setattr(auth, "github_profile", lambda: {"id": github_id, "login": login, "name": login.title()})
    response = client.get("/signin/github/callback")
    assert response.status_code == 302, response.get_data(as_text=True)
    return client


def query(app, user_id, sql, *args):
    conn = app_db(app) if user_id is None else _as(app, user_id)
    try:
        return [dict(r) for r in conn.execute(sql, args)]
    finally:
        conn.close()


def _as(app, user_id):
    from codecompass.db import open_db

    return open_db(app.config, user_id)


def user_id(app, login):
    return query(app, None, "SELECT id FROM users WHERE login = ?", login)[0]["id"]


def log(client, notes="", problem=PARENS, day=TODAY, outcome=c.SOLVED_ALONE):
    return client.post("/log", data={"problem": problem, "date": day, "outcome": outcome, "time_minutes": "",
                                     "time_seconds": "", "notes": notes})


# --- R-51: signing in ---

def test_every_page_needs_signing_in_except_sign_in_and_privacy(hosted):
    client = hosted.test_client()
    for path in ("/", "/log", "/history", "/settings", "/sync", "/reviews", "/progress", "/interviews",
                 "/profile", "/account", "/settings/backup", "/problems/1"):
        response = client.get(path)
        assert response.status_code == 302 and response.location.startswith("/signin"), path
    assert client.post("/log", data={"problem": PARENS}).status_code == 401
    assert client.get("/signin").status_code == 200
    assert "What is kept" in client.get("/privacy").get_data(as_text=True)


def test_signing_in_starts_with_github_and_keeps_only_a_local_next_page(hosted):
    client = hosted.test_client()
    response = client.post("/signin/github", data={"next": "https://elsewhere.example/steal"})
    assert response.status_code == 302
    assert response.location.startswith("https://github.com/login/oauth/authorize?")
    assert "client_id=test-client" in response.location and "password" not in response.location
    with client.session_transaction() as session:
        assert session["next"] == "/"


def test_sign_in_makes_an_account_and_signing_out_ends_that_session_everywhere(hosted, monkeypatch):
    client = sign_in(hosted, monkeypatch, 101, "ada")
    page = client.get("/").get_data(as_text=True)
    assert 'class="account-link"' in page and ">ada</a>" in page
    assert query(hosted, None, "SELECT login, name FROM users WHERE github_id = 101") == [{"login": "ada", "name": "Ada"}]
    copied = client.get_cookie("session").value
    client.post("/signout")
    assert client.get("/").location.startswith("/signin")
    thief = hosted.test_client()
    thief.set_cookie("session", copied)
    assert thief.get("/").location.startswith("/signin")  # The copied cookie no longer works.
    assert query(hosted, None, "SELECT count(*) AS n FROM sessions")[0]["n"] == 0


def test_no_password_is_stored(hosted, monkeypatch):
    sign_in(hosted, monkeypatch, 101, "ada")
    columns = {r["column_name"] for r in query(hosted, None, """SELECT column_name FROM information_schema.columns
                                                              WHERE table_schema = 'public'""")}
    assert not any("password" in name for name in columns)
    assert query(hosted, None, "SELECT count(*) AS n FROM sessions WHERE length(token_hash) = 64")[0]["n"] == 1


def test_a_session_ends_after_30_days_without_use(hosted, monkeypatch):
    client = sign_in(hosted, monkeypatch, 101, "ada")
    conn = app_db(hosted)
    with conn:
        conn.execute("UPDATE sessions SET last_used = ?", (time.time() - 31 * 86400,))
    conn.close()
    assert client.get("/").location.startswith("/signin")


def test_new_accounts_stop_at_the_cap_but_existing_ones_sign_in(hosted, monkeypatch):
    sign_in(hosted, monkeypatch, 101, "ada")
    count = query(hosted, None, "SELECT count(*) AS n FROM users")[0]["n"]
    monkeypatch.setattr(c, "MAX_ACCOUNTS", count)
    client = hosted.test_client()
    monkeypatch.setattr(auth, "github_profile", lambda: {"id": 202, "login": "bo", "name": None})
    page = client.get("/signin/github/callback", follow_redirects=True).get_data(as_text=True)
    assert "reached its limit of accounts" in page
    assert query(hosted, None, "SELECT count(*) AS n FROM users WHERE github_id = 202")[0]["n"] == 0
    assert sign_in(hosted, monkeypatch, 101, "ada").get("/").status_code == 200


def test_a_failed_or_odd_github_reply_signs_no_one_in(hosted, monkeypatch):
    client = hosted.test_client()

    def declined():
        raise RuntimeError("access_denied")

    monkeypatch.setattr(auth, "github_profile", declined)
    assert "did not finish" in client.get("/signin/github/callback", follow_redirects=True).get_data(as_text=True)
    monkeypatch.setattr(auth, "github_profile", lambda: {"message": "Bad credentials"})
    assert "did not say who you are" in client.get("/signin/github/callback",
                                                   follow_redirects=True).get_data(as_text=True)
    assert query(hosted, None, "SELECT count(*) AS n FROM sessions")[0]["n"] == 0


# --- R-52: each account's data is its own ---

def test_two_accounts_see_and_change_only_their_own_data(hosted, monkeypatch):
    ada = sign_in(hosted, monkeypatch, 101, "ada")
    bo = sign_in(hosted, monkeypatch, 202, "bo")
    assert log(ada, "ada's secret approach").status_code == 302
    ada.post("/problems/new", data={"title": "Ada's own problem", "link": "https://example.org/ada",
                                    "difficulty": "medium", "patterns": ["Greedy"]})
    ada.post("/interviews", data={"company": "Acme", "date": "2099-01-01", "target_difficulty": "", "patterns": []})
    ada_id = user_id(hosted, "ada")
    attempt = query(hosted, ada_id, "SELECT id FROM attempts")[0]["id"]
    custom = query(hosted, ada_id, "SELECT id FROM problems WHERE is_custom = 1")[0]["id"]
    interview = query(hosted, ada_id, "SELECT id FROM interviews")[0]["id"]
    ada.post(f"/problems/{custom}/notes", data={"note": "only ada"})
    before = ada.get("/settings/backup").data

    # Nothing of Ada's shows to Bo.
    for path in ("/", "/history", "/interviews", "/progress", "/reviews"):
        page = bo.get(path).get_data(as_text=True)
        assert "secret approach" not in page and "Acme" not in page and "Ada&#39;s own problem" not in page, path
    assert bo.get("/problems/search?q=Ada").get_json() == {"results": [], "notes": []} or \
        "Ada" not in bo.get("/problems/search?q=Ada").get_data(as_text=True)
    assert bo.get(f"/problems/{custom}").status_code == 404
    assert bo.get(f"/attempts/{attempt}/edit").status_code == 404
    assert bo.get(f"/interviews/{interview}/edit").status_code == 404

    # Bo's attempts on Ada's ids change nothing of Ada's.
    bo.post(f"/attempts/{attempt}/delete")
    bo.post(f"/attempts/{attempt}/edit", data={"problem": PARENS, "date": TODAY, "outcome": c.NOT_SOLVED,
                                               "time_minutes": "", "time_seconds": "", "notes": "changed"})
    bo.post(f"/interviews/{interview}/delete")
    bo.post(f"/problems/{custom}/notes", data={"note": "bo was here"})
    bo.post(f"/problems/{custom}/links", data={"url": "https://example.org/x", "label": ""})
    bo.post(f"/problems/{custom}/hint")
    bo.post(f"/problems/{custom}/not-now")
    bo.post("/undo/1")
    bo.post("/sync/batches/1/undo")
    bo.post("/settings/erase", data={"confirm": "erase"})
    assert ada.get("/settings/backup").data == before
    assert query(hosted, user_id(hosted, "bo"), "SELECT count(*) AS n FROM attempts")[0]["n"] == 0


def test_an_account_cannot_change_shared_problems_whatever_it_asks(hosted, monkeypatch):
    import psycopg

    sign_in(hosted, monkeypatch, 101, "ada")
    conn = _as(hosted, user_id(hosted, "ada"))
    try:
        for sql in ("UPDATE problems SET title = 'Changed' WHERE is_custom = 0",
                    "DELETE FROM problems WHERE is_custom = 0",
                    "INSERT INTO public.problems (title, difficulty, source) VALUES ('Planted', 'easy', 'x')",
                    "DELETE FROM problem_patterns"):
            with pytest.raises(psycopg.Error):
                with conn:
                    conn.execute(sql)
    finally:
        conn.close()
    assert "Changed" not in [r["title"] for r in query(hosted, None, "SELECT title FROM problems")]


def test_custom_problems_with_the_same_link_stay_apart(hosted, monkeypatch):
    for github_id, login in ((101, "ada"), (202, "bo")):
        client = sign_in(hosted, monkeypatch, github_id, login)
        response = client.post("/problems/new", data={"title": f"{login} copy", "link": "https://example.org/same",
                                                      "difficulty": "easy", "patterns": ["Greedy"]})
        assert response.status_code == 302
    for login in ("ada", "bo"):
        titles = [r["title"] for r in query(hosted, user_id(hosted, login), "SELECT title FROM problems WHERE is_custom = 1")]
        assert titles == [f"{login} copy"]


# --- R-53: request safety ---

def test_a_form_posted_without_its_token_changes_nothing(hosted, monkeypatch):
    hosted.config["CSRF_CHECK"] = True
    client = sign_in(hosted, monkeypatch, 101, "ada")
    response = log(client, "forged")
    assert response.status_code == 400 and "That form expired" in response.get_data(as_text=True)
    page = client.get("/log").get_data(as_text=True)
    token = re.search(r'name="csrf-token" content="([^"]+)"', page).group(1)
    assert f'name="csrf_token" value="{token}"' in page
    data = {"problem": PARENS, "date": TODAY, "outcome": c.SOLVED_ALONE, "time_minutes": "", "time_seconds": "",
            "notes": "real", "csrf_token": token}
    assert client.post("/log", data=data).status_code == 302
    assert client.post("/sync/step", headers={"Accept": "application/json", "X-CSRF-Token": "wrong"}).status_code == 400
    assert [r["notes"] for r in query(hosted, user_id(hosted, "ada"), "SELECT notes FROM attempts")] == ["real"]


def test_plain_http_redirects_to_https_and_cookies_are_secure(tmp_path, catalog_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "https.sqlite"), "CATALOG_PATH": catalog_path,
                      "RESERVE_PATH": None, "UNMAPPED_PATH": None, "FORCE_HTTPS": True})
    client = app.test_client()
    response = client.get("/privacy")
    assert response.status_code == 301 and response.location == "https://localhost/privacy"
    secure = client.get("/privacy", base_url="https://localhost")
    assert secure.status_code == 200
    assert secure.headers["Strict-Transport-Security"] and secure.headers["X-Frame-Options"] == "DENY"
    assert app.config["SESSION_COOKIE_SECURE"] and app.config["SESSION_COOKIE_HTTPONLY"]
    # Behind the host's proxy, the original scheme counts.
    assert client.get("/privacy", headers={"X-Forwarded-Proto": "https"}).status_code == 200


def test_sign_ins_uploads_and_sync_starts_are_limited(hosted, monkeypatch):
    monkeypatch.setattr(c, "SIGNIN_LIMIT", 2)
    monkeypatch.setattr(c, "UPLOAD_LIMIT", 1)
    monkeypatch.setattr(c, "SYNC_START_LIMIT", 1)
    outsider = hosted.test_client()
    assert outsider.post("/signin/github").location.startswith("https://github.com/")
    assert outsider.post("/signin/github").location.startswith("https://github.com/")
    assert "Too many sign-in attempts" in outsider.post("/signin/github", follow_redirects=True).get_data(as_text=True)

    client = sign_in(hosted, monkeypatch, 101, "ada")
    csv_file = lambda: {"file": (io.BytesIO(b"title,date,outcome\n"), "a.csv")}  # noqa: E731
    client.post("/import", data=csv_file(), content_type="multipart/form-data")
    second = client.post("/import", data=csv_file(), content_type="multipart/form-data")
    assert "Too many files uploaded" in second.get_data(as_text=True)
    restore = client.post("/settings/restore", data={"file": (io.BytesIO(b"x"), "b.sqlite"), "confirm": "restore"},
                          content_type="multipart/form-data")
    assert restore.status_code == 429

    client.post("/settings/accounts", data={"username:codeforces": "practice_user", "username:atcoder": ""})
    from codecompass import remote, views

    monkeypatch.setattr(remote, "fetch", lambda url, data=None: b'{"status": "OK", "result": []}')
    monkeypatch.setattr(views, "now_seconds", lambda: 1793534400)
    client.post("/sync")
    assert "Too many syncs started" in client.post("/sync", follow_redirects=True).get_data(as_text=True)


# --- R-33: LeetCode stays out of hosted mode ---

def test_hosted_mode_links_and_syncs_codeforces_and_atcoder_only(hosted, monkeypatch):
    client = sign_in(hosted, monkeypatch, 101, "ada")
    page = client.get("/settings").get_data(as_text=True)
    assert 'name="username:codeforces"' in page and 'name="username:atcoder"' in page
    assert 'name="username:leetcode"' not in page and "LeetCode data comes from" not in page
    client.post("/settings/accounts", data={"username:codeforces": "tourist", "username:leetcode": "someone"})
    assert [r["site"] for r in query(hosted, user_id(hosted, "ada"), "SELECT site FROM linked_accounts")] == ["codeforces"]
    bad = client.post("/settings/accounts", data={"username:codeforces": "tourist", "username:atcoder": "bad name!"})
    assert bad.status_code == 400
    assert "Link a Codeforces or AtCoder username" in sign_in(hosted, monkeypatch, 202, "bo").get("/sync").get_data(as_text=True)


# --- R-25: demo history for a new account ---

def test_an_empty_account_can_load_the_demo_history_once(hosted, monkeypatch):
    client = sign_in(hosted, monkeypatch, 101, "ada")
    assert "Load demo history" in client.get("/").get_data(as_text=True)
    page = client.post("/demo", follow_redirects=True).get_data(as_text=True)
    assert "Loaded 8 weeks of made-up practice." in page and "Load demo history" not in page
    count = query(hosted, user_id(hosted, "ada"), "SELECT count(*) AS n FROM attempts")[0]["n"]
    assert count > 0  # The test catalog is small, so the history is short.
    assert "only be loaded into an account with no attempts" in client.post("/demo", follow_redirects=True).get_data(as_text=True)
    assert query(hosted, user_id(hosted, "ada"), "SELECT count(*) AS n FROM attempts")[0]["n"] == count
    # Another account stays empty.
    assert "Load demo history" in sign_in(hosted, monkeypatch, 202, "bo").get("/").get_data(as_text=True)


# --- R-55: moving data between local mode and an account ---

def records(conn):
    return sorted(tuple(r) for r in conn.execute(
        """SELECT a.date, p.title, p.link, p.is_custom, a.outcome, a.time_seconds, a.notes, r.title
           FROM attempts a JOIN problems p ON p.id = a.problem_id
           LEFT JOIN problems r ON r.id = a.review_of_problem_id"""))


def test_data_moves_from_local_mode_to_an_account_and_back(hosted, monkeypatch, tmp_path, catalog_path):
    local = local_create_app({"TESTING": True, "DATABASE": str(tmp_path / "local.sqlite"), "CATALOG_PATH": catalog_path,
                              "RESERVE_PATH": None, "UNMAPPED_PATH": None})
    here = local.test_client()
    here.post("/problems/new", data={"title": "My own problem", "link": "https://example.org/mine",
                                     "difficulty": "medium", "patterns": ["Greedy"]})
    log(here, "first", day="2026-10-01")
    log(here, "second", problem="Two Sum (Test list)", day="2026-10-05", outcome=c.SOLVED_WITH_HINTS)
    log(here, "third", problem="My own problem (custom)", day="2026-10-07", outcome=c.NOT_SOLVED)
    here.post("/interviews", data={"company": "Acme", "date": "2099-01-01", "target_difficulty": "", "patterns": ["Stack"]})
    local_conn = app_db(local)
    original = records(local_conn)
    local_conn.close()
    backup = here.get("/settings/backup").data
    local_dashboard = here.get("/").get_data(as_text=True)

    client = sign_in(hosted, monkeypatch, 101, "ada")
    response = client.post("/settings/restore", data={"file": (io.BytesIO(backup), "local.sqlite"), "confirm": "restore"},
                           content_type="multipart/form-data")
    assert response.status_code == 302
    conn = _as(hosted, user_id(hosted, "ada"))
    assert records(conn) == original
    conn.close()
    # Scores and due dates match: the dashboard's pattern tiles and review count are the same.
    tiles = lambda html: re.findall(r'class="tile[^"]*".*?</li>', html, re.S)  # noqa: E731
    assert tiles(client.get("/").get_data(as_text=True)) == tiles(local_dashboard)
    assert "Acme" in client.get("/interviews").get_data(as_text=True)

    back = local_create_app({"TESTING": True, "DATABASE": str(tmp_path / "back.sqlite"), "CATALOG_PATH": catalog_path,
                             "RESERVE_PATH": None, "UNMAPPED_PATH": None})
    returned = back.test_client().post("/settings/restore",
                                       data={"file": (io.BytesIO(client.get("/settings/backup").data), "h.sqlite"),
                                             "confirm": "restore"}, content_type="multipart/form-data")
    assert returned.status_code == 302
    back_conn = app_db(back)
    assert records(back_conn) == original
    back_conn.close()


def test_an_import_into_an_account_can_be_undone(hosted, monkeypatch):
    client = sign_in(hosted, monkeypatch, 101, "ada")
    log(client, "kept")
    backup = client.get("/settings/backup").data
    log(client, "later")
    client.post("/settings/restore", data={"file": (io.BytesIO(backup), "b.sqlite"), "confirm": "restore"},
                content_type="multipart/form-data")
    ada = user_id(hosted, "ada")
    assert [r["notes"] for r in query(hosted, ada, "SELECT notes FROM attempts")] == ["kept"]
    client.post("/settings/erase/undo")
    assert sorted(r["notes"] for r in query(hosted, ada, "SELECT notes FROM attempts")) == ["kept", "later"]


# --- R-56: deleting an account ---

def test_deleting_an_account_removes_everything_and_a_new_sign_in_starts_empty(hosted, monkeypatch):
    client = sign_in(hosted, monkeypatch, 101, "ada")
    log(client, "mine")
    client.post("/problems/new", data={"title": "Own", "link": "https://example.org/own", "difficulty": "easy",
                                       "patterns": ["Greedy"]})
    old = user_id(hosted, "ada")
    wrong = client.post("/account", data={"confirm": "someone"})
    assert wrong.status_code == 400 and query(hosted, None, "SELECT count(*) AS n FROM users WHERE id = ?", old)[0]["n"] == 1
    page = client.post("/account", data={"confirm": "ada"}, follow_redirects=True).get_data(as_text=True)
    assert "Your account and all its data were deleted." in page
    assert query(hosted, None, "SELECT count(*) AS n FROM users WHERE github_id = 101")[0]["n"] == 0
    assert query(hosted, None, "SELECT count(*) AS n FROM problems WHERE owner = ?", old)[0]["n"] == 0
    assert query(hosted, None, "SELECT count(*) AS n FROM sessions WHERE user_id = ?", old)[0]["n"] == 0
    assert query(hosted, None, "SELECT count(*) AS n FROM information_schema.schemata WHERE schema_name = ?",
                 f"u{old}")[0]["n"] == 0
    again = sign_in(hosted, monkeypatch, 101, "ada")
    assert user_id(hosted, "ada") != old
    assert query(hosted, user_id(hosted, "ada"), "SELECT count(*) AS n FROM attempts")[0]["n"] == 0
    assert "Load demo history" in again.get("/").get_data(as_text=True)


def test_the_privacy_notice_says_what_is_kept_and_how_to_delete_it(hosted):
    page = hosted.test_client().get("/privacy").get_data(as_text=True)
    assert "What is kept" in page and "deletes the account" in page and "No email, no password" in page
