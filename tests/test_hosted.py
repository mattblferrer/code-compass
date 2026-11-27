"""Hosted mode: accounts, keeping each account's data its own, request safety, moving data
between modes, and deleting an account (R-25, R-33, R-50 to R-53, R-55, R-56).

These run only when CODECOMPASS_TEST_PG names a PostgreSQL server for tests. Signing in
never contacts GitHub or Google: auth.github_profile and auth.google_profile are replaced by
fixed replies.
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
                       "GITHUB_CLIENT_ID": "test-client", "GITHUB_CLIENT_SECRET": "test-secret",
                       "GOOGLE_CLIENT_ID": "test-google", "GOOGLE_CLIENT_SECRET": "test-google-secret"})


def sign_in(app, monkeypatch, github_id, login):
    """A test client signed in as the GitHub account `github_id`."""
    client = app.test_client()
    monkeypatch.setattr(auth, "github_profile", lambda: {"id": github_id, "login": login, "name": login.title()})
    response = client.get("/signin/github/callback")
    assert response.status_code == 302, response.get_data(as_text=True)
    return client


def sign_in_with_google(app, monkeypatch, sub, name):
    """A test client signed in as the Google account `sub`."""
    client = app.test_client()
    monkeypatch.setattr(auth, "google_profile", lambda: {"sub": sub, "name": name})
    response = client.get("/signin/google/callback")
    assert response.status_code == 302, response.get_data(as_text=True)
    return client


PASSWORD = "correct horse battery"


def sign_up(app, username, password=PASSWORD):
    """A test client signed in to a new account made with a username and password."""
    client = app.test_client()
    response = client.post("/signup", data={"username": username, "password": password, "password_again": password})
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


def test_signing_in_returns_to_the_page_asked_for(hosted, monkeypatch):
    client = hosted.test_client()
    assert client.get("/history?outcome=not_solved").location.startswith("/signin")
    client.post("/signin/github", data={"next": "/history?outcome=not_solved"})
    monkeypatch.setattr(auth, "github_profile", lambda: {"id": 303, "login": "cy", "name": "Cy"})
    assert client.get("/signin/github/callback").location == "/history?outcome=not_solved"
    # The account's first day is the user's date, from the browser's offset (R-51).
    client.set_cookie("tz", str(-14 * 60))
    other = hosted.test_client()
    other.set_cookie("tz", str(14 * 60))
    monkeypatch.setattr(auth, "github_profile", lambda: {"id": 304, "login": "di", "name": "Di"})
    other.get("/signin/github/callback")
    made = query(hosted, None, "SELECT created FROM users WHERE github_id = 304")[0]["created"]
    from datetime import datetime, timedelta, timezone
    assert made == (datetime.now(timezone.utc) + timedelta(hours=14)).date().isoformat()


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


def test_github_and_google_accounts_keep_no_password_and_a_password_is_kept_only_as_a_hash(hosted, monkeypatch):
    sign_in(hosted, monkeypatch, 101, "ada")
    sign_in_with_google(hosted, monkeypatch, "g-202", "Bo")
    sign_up(hosted, "cyd")
    columns = {r["column_name"] for r in query(hosted, None, """SELECT column_name FROM information_schema.columns
                                                              WHERE table_schema = 'public'""")}
    assert {name for name in columns if "password" in name} == {"password_hash"}
    rows = {r["login"]: r["password_hash"] for r in query(hosted, None, "SELECT login, password_hash FROM users")}
    assert rows["ada"] is None and rows["Bo"] is None
    assert rows["cyd"].startswith("scrypt:") and PASSWORD not in rows["cyd"]
    assert query(hosted, None, "SELECT count(*) AS n FROM sessions WHERE length(token_hash) = 64")[0]["n"] == 3


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

# --- R-51: signing in with Google ---

def test_signing_in_with_google_asks_only_for_the_id_and_name(hosted):
    client = hosted.test_client()
    page = client.get("/signin?next=/history").get_data(as_text=True)
    assert page.count("Sign in with Google") == 2 and page.count("Sign in with a username") == 2
    response = client.post("/signin/google", data={"next": "/history"})
    assert response.status_code == 302
    assert response.location.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "client_id=test-google" in response.location and "scope=openid+profile&" in response.location
    assert "nonce=" in response.location and "email" not in response.location
    with client.session_transaction() as session:
        assert session["next"] == "/history"


def test_a_google_account_is_its_own_account(hosted, monkeypatch):
    client = sign_in_with_google(hosted, monkeypatch, "1234567890", "Ada Lovelace")
    page = client.get("/account").get_data(as_text=True)
    assert "Signed in with Google as Ada Lovelace." in page and "Type your Google name" in page
    # A GitHub account with the same name is another account.
    sign_in(hosted, monkeypatch, 101, "Ada Lovelace")
    rows = query(hosted, None, "SELECT github_id, google_id FROM users WHERE login = 'Ada Lovelace' ORDER BY id")
    assert rows == [{"github_id": None, "google_id": "1234567890"}, {"github_id": 101, "google_id": None}]
    # Signing in again finds the same account, and keeps its name current.
    sign_in_with_google(hosted, monkeypatch, "1234567890", "Ada King")
    assert query(hosted, None, "SELECT login FROM users WHERE google_id = '1234567890'") == [{"login": "Ada King"}]


def test_a_failed_or_odd_google_reply_signs_no_one_in(hosted, monkeypatch):
    client = hosted.test_client()

    def declined():
        raise RuntimeError("access_denied")

    monkeypatch.setattr(auth, "google_profile", declined)
    assert "did not finish" in client.get("/signin/google/callback", follow_redirects=True).get_data(as_text=True)
    for reply in (None, {"name": "No id"}, {"sub": 5}, {"sub": ""}):
        monkeypatch.setattr(auth, "google_profile", lambda: reply)
        page = client.get("/signin/google/callback", follow_redirects=True).get_data(as_text=True)
        assert "Google did not say who you are" in page, reply
    assert query(hosted, None, "SELECT count(*) AS n FROM sessions")[0]["n"] == 0


def test_a_sign_in_the_site_has_not_set_up_is_not_offered(tmp_path, catalog_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "bare.sqlite"), "CATALOG_PATH": catalog_path,
                      "RESERVE_PATH": None, "UNMAPPED_PATH": None, "TESTING_USER_ID": None,
                      "GITHUB_CLIENT_ID": "test-client", "GOOGLE_CLIENT_ID": None})
    client = app.test_client()
    page = client.get("/signin").get_data(as_text=True)
    assert "Sign in with GitHub" in page and "Sign in with Google" not in page and "Sign in with a username" in page
    assert client.post("/signin/google").status_code == 404


def test_with_no_outside_sign_in_the_sign_in_page_still_offers_making_an_account(tmp_path, catalog_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "bare.sqlite"), "CATALOG_PATH": catalog_path,
                      "RESERVE_PATH": None, "UNMAPPED_PATH": None, "TESTING_USER_ID": None,
                      "GITHUB_CLIENT_ID": None, "GOOGLE_CLIENT_ID": None})
    page = app.test_client().get("/signin").get_data(as_text=True)
    assert "Sign in with GitHub" not in page and "Sign in with Google" not in page
    assert 'href="/signup' in page and "Make an account with a username and password" in page


# --- R-51: signing in with a username and password ---

def test_making_an_account_with_a_username_signs_in_and_signs_back_in(hosted):
    client = hosted.test_client()
    assert "Make an account" in client.get("/signup").get_data(as_text=True)
    response = client.post("/signup", data={"username": "ada.l", "password": PASSWORD, "password_again": PASSWORD,
                                            "next": "/history"})
    assert response.location == "/history"
    page = client.get("/account").get_data(as_text=True)
    assert "Signed in with the username ada.l." in page and "Change your password" in page
    client.post("/signout")
    assert client.get("/").location.startswith("/signin")
    # The username ignores case; the password does not.
    again = hosted.test_client()
    wrong = again.post("/signin/password", data={"username": "ADA.L", "password": PASSWORD.upper()})
    assert wrong.status_code == 400 and "The username or password is wrong." in wrong.get_data(as_text=True)
    assert again.get("/").location.startswith("/signin")
    right = again.post("/signin/password", data={"username": "ADA.L", "password": PASSWORD, "next": "/progress"})
    assert right.location == "/progress" and again.get("/").status_code == 200


def test_an_unknown_username_gets_the_same_answer_as_a_wrong_password(hosted):
    sign_up(hosted, "ada")
    client = hosted.test_client()
    unknown = client.post("/signin/password", data={"username": "nobody", "password": PASSWORD})
    wrong = client.post("/signin/password", data={"username": "ada", "password": "not the password"})
    for response in (unknown, wrong):
        assert response.status_code == 400
        assert "The username or password is wrong." in response.get_data(as_text=True)
    assert query(hosted, None, "SELECT count(*) AS n FROM sessions")[0]["n"] == 1  # Only the sign-up's.


def test_a_bad_username_or_password_makes_no_account(hosted):
    client = hosted.test_client()
    long = "x" * (c.PASSWORD_MAX_LENGTH + 1)
    cases = [
        ({"username": "ab", "password": PASSWORD, "password_again": PASSWORD}, "username"),
        ({"username": "-ada", "password": PASSWORD, "password_again": PASSWORD}, "username"),
        ({"username": "ada lovelace", "password": PASSWORD, "password_again": PASSWORD}, "username"),
        ({"username": "ada", "password": "short", "password_again": "short"}, "password"),
        ({"username": "ada", "password": long, "password_again": long}, "password"),
        ({"username": "longusername1", "password": "LongUsername1", "password_again": "LongUsername1"}, "password"),
        ({"username": "ada", "password": PASSWORD, "password_again": PASSWORD + "!"}, "password_again"),
    ]
    for data, field in cases:
        response = client.post("/signup", data=data)
        assert response.status_code == 400, data
        assert f'id="{field}-error"' in response.get_data(as_text=True), data
    assert query(hosted, None, "SELECT count(*) AS n FROM users WHERE password_hash IS NOT NULL")[0]["n"] == 0


def test_a_username_is_taken_whatever_its_case_but_not_by_other_ways_of_signing_in(hosted, monkeypatch):
    sign_in(hosted, monkeypatch, 101, "ada")  # A GitHub account named ada does not take the username.
    sign_up(hosted, "ada")
    response = hosted.test_client().post("/signup", data={"username": "ADA", "password": PASSWORD,
                                                          "password_again": PASSWORD})
    assert response.status_code == 400 and "That username is taken." in response.get_data(as_text=True)
    assert query(hosted, None, "SELECT count(*) AS n FROM users WHERE lower(login) = 'ada'")[0]["n"] == 2


def test_new_password_accounts_stop_at_the_cap_too(hosted, monkeypatch):
    sign_up(hosted, "ada")
    monkeypatch.setattr(c, "MAX_ACCOUNTS", query(hosted, None, "SELECT count(*) AS n FROM users")[0]["n"])
    page = hosted.test_client().post("/signup", data={"username": "bob", "password": PASSWORD,
                                                      "password_again": PASSWORD},
                                     follow_redirects=True).get_data(as_text=True)
    assert "reached its limit of accounts" in page
    assert query(hosted, None, "SELECT count(*) AS n FROM users WHERE login = 'bob'")[0]["n"] == 0
    signed_in = hosted.test_client().post("/signin/password", data={"username": "ada", "password": PASSWORD})
    assert signed_in.status_code == 302


def test_password_tries_are_limited_per_username_from_any_address(hosted, monkeypatch):
    monkeypatch.setattr(c, "PASSWORD_TRY_LIMIT", 2)
    sign_up(hosted, "ada")
    for address in ("10.0.0.1", "10.0.0.2"):
        hosted.test_client().post("/signin/password", data={"username": "ada", "password": "guess"},
                                  environ_base={"REMOTE_ADDR": address})
    third = hosted.test_client().post("/signin/password", data={"username": "Ada", "password": PASSWORD},
                                      environ_base={"REMOTE_ADDR": "10.0.0.3"}, follow_redirects=True)
    assert "Too many sign-in attempts for this username" in third.get_data(as_text=True)
    assert query(hosted, None, "SELECT count(*) AS n FROM sessions")[0]["n"] == 1  # Only the sign-up's.


def test_changing_the_password_needs_the_current_one_and_signs_out_other_browsers(hosted):
    client = sign_up(hosted, "ada")
    other = hosted.test_client()
    other.post("/signin/password", data={"username": "ada", "password": PASSWORD})
    new = "a different long passphrase"
    wrong = client.post("/account/password", data={"current_password": "nope", "password": new, "password_again": new})
    assert wrong.status_code == 400 and "That is not your current password." in wrong.get_data(as_text=True)
    mismatch = client.post("/account/password", data={"current_password": PASSWORD, "password": new,
                                                      "password_again": new + "!"})
    assert mismatch.status_code == 400 and 'id="password_again-error"' in mismatch.get_data(as_text=True)
    changed = client.post("/account/password", data={"current_password": PASSWORD, "password": new,
                                                     "password_again": new}, follow_redirects=True)
    assert "Your password was changed." in changed.get_data(as_text=True)
    assert client.get("/").status_code == 200  # This browser stays signed in.
    assert other.get("/").location.startswith("/signin")  # The other is signed out.
    fresh = hosted.test_client()
    assert fresh.post("/signin/password", data={"username": "ada", "password": PASSWORD}).status_code == 400
    assert fresh.post("/signin/password", data={"username": "ada", "password": new}).status_code == 302


def test_only_a_password_account_has_a_password_to_change(hosted, monkeypatch):
    client = sign_in(hosted, monkeypatch, 101, "ada")
    assert "Change your password" not in client.get("/account").get_data(as_text=True)
    assert client.post("/account/password", data={"current_password": "x", "password": PASSWORD,
                                                   "password_again": PASSWORD}).status_code == 404


def test_the_account_tool_resets_a_password_and_signs_the_account_out(hosted):
    client = sign_up(hosted, "ada")
    runner = hosted.test_cli_runner()
    missing = runner.invoke(args=["accounts", "reset-password", "nobody"]).output
    assert "No account signs in with the username nobody" in missing
    output = runner.invoke(args=["accounts", "reset-password", "ADA"]).output
    temporary = re.search(r"ada's new password is (\S+)", output).group(1)
    assert len(temporary) >= c.PASSWORD_MIN_LENGTH
    assert client.get("/").location.startswith("/signin")
    fresh = hosted.test_client()
    assert fresh.post("/signin/password", data={"username": "ada", "password": PASSWORD}).status_code == 400
    assert fresh.post("/signin/password", data={"username": "ada", "password": temporary}).status_code == 302


def test_the_account_tool_asks_which_account_when_names_are_shared(hosted, monkeypatch):
    sign_in(hosted, monkeypatch, 101, "ada")
    sign_up(hosted, "ada")
    runner = hosted.test_cli_runner()
    listed = runner.invoke(args=["accounts"]).output
    assert "(github)" in listed and "(password)" in listed
    assert "Add --method" in runner.invoke(args=["accounts", "delete", "ada", "--yes"]).output
    deleted = runner.invoke(args=["accounts", "delete", "ada", "--method", "password", "--yes"]).output
    assert "Deleted ada's account." in deleted
    assert query(hosted, None, "SELECT github_id FROM users WHERE login = 'ada'") == [{"github_id": 101}]


def test_the_account_tool_tells_apart_google_accounts_with_the_same_name(hosted, monkeypatch):
    sign_in_with_google(hosted, monkeypatch, "g-1", "Ada Lovelace")
    sign_in_with_google(hosted, monkeypatch, "g-2", "Ada Lovelace")
    first, second = (r["id"] for r in query(hosted, None, "SELECT id FROM users WHERE google_id IS NOT NULL ORDER BY id"))
    runner = hosted.test_cli_runner()
    listed = runner.invoke(args=["accounts"]).output
    assert f"{first}  Ada Lovelace" in listed and f"{second}  Ada Lovelace" in listed
    shared = runner.invoke(args=["accounts", "delete", "Ada Lovelace", "--method", "google", "--yes"]).output
    assert f"id {first} (google), id {second} (google)" in shared and "--id" in shared
    assert "No account has the name Ada Lovelace and id 0." in runner.invoke(
        args=["accounts", "delete", "Ada Lovelace", "--id", "0", "--yes"]).output
    deleted = runner.invoke(args=["accounts", "delete", "Ada Lovelace", "--id", str(second), "--yes"]).output
    assert "Deleted Ada Lovelace's account." in deleted
    assert query(hosted, None, "SELECT google_id FROM users WHERE google_id IS NOT NULL") == [{"google_id": "g-1"}]


def test_deleting_a_password_account_asks_for_its_username(hosted):
    client = sign_up(hosted, "ada")
    page = client.get("/account").get_data(as_text=True)
    assert "Type your username, <strong>ada</strong>, to confirm" in page
    deleted = client.post("/account", data={"confirm": "ada"}, follow_redirects=True).get_data(as_text=True)
    assert "Your account and all its data were deleted." in deleted
    assert query(hosted, None, "SELECT count(*) AS n FROM users WHERE password_hash IS NOT NULL")[0]["n"] == 0


def test_a_password_account_and_a_github_account_with_the_same_name_keep_their_data_apart(hosted, monkeypatch):
    github = sign_in(hosted, monkeypatch, 101, "ada")
    password = sign_up(hosted, "ada")
    assert log(github, "from github").status_code == 302
    assert log(password, "from password").status_code == 302
    ids = {r["kind"]: r["id"] for r in query(hosted, None, """SELECT id, CASE WHEN github_id IS NULL THEN 'password'
                                                                  ELSE 'github' END AS kind
                                                              FROM users WHERE login = 'ada'""")}
    for kind in ("github", "password"):
        assert [r["notes"] for r in query(hosted, ids[kind], "SELECT notes FROM attempts")] == [f"from {kind}"]


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
    assert "only be loaded into an account with no practice" in client.post("/demo", follow_redirects=True).get_data(as_text=True)
    assert query(hosted, user_id(hosted, "ada"), "SELECT count(*) AS n FROM attempts")[0]["n"] == count
    # Another account stays empty.
    assert "Load demo history" in sign_in(hosted, monkeypatch, 202, "bo").get("/").get_data(as_text=True)


# --- R-59: each account's own pattern links ---

def test_pattern_links_belong_to_one_account_and_move_with_its_backup(hosted, monkeypatch):
    ada = sign_in(hosted, monkeypatch, 101, "ada")
    ada.post("/patterns/Two%20Pointers/links", data={"url": "https://example.org/ada", "label": "Ada's notes"})
    [link] = query(hosted, user_id(hosted, "ada"), "SELECT id FROM pattern_links")
    bo = sign_in(hosted, monkeypatch, 202, "bo")
    page = bo.get("/patterns/Two%20Pointers").get_data(as_text=True)
    assert "https://example.org/ada" not in page and "Hello Interview" in page  # Curated guides are shared.
    assert bo.post(f"/patterns/Two%20Pointers/links/{link['id']}/delete").status_code == 404
    assert len(query(hosted, user_id(hosted, "ada"), "SELECT id FROM pattern_links")) == 1
    # Ada's backup, restored into Bo's account, brings the link with its pattern matched by name.
    backup = ada.get("/settings/backup").data
    bo.post("/settings/restore", data={"file": (io.BytesIO(backup), "ada.sqlite"), "confirm": "restore"},
            content_type="multipart/form-data")
    assert "https://example.org/ada" in bo.get("/patterns/Two%20Pointers").get_data(as_text=True)
    assert "https://example.org/ada" not in bo.get("/patterns/Sliding%20Window").get_data(as_text=True)


def test_the_demo_never_replaces_an_accounts_own_data(hosted, monkeypatch):
    client = sign_in(hosted, monkeypatch, 101, "ada")
    client.post("/problems/new", data={"title": "My own problem", "link": "", "difficulty": "easy",
                                       "patterns": "Stack"})
    client.post("/settings", data={"starting_difficulty": "easy", "pref:Heap": "mastered"})
    me = user_id(hosted, "ada")
    assert query(hosted, me, "SELECT count(*) AS n FROM problems WHERE is_custom = 1")[0]["n"] == 1
    page = client.post("/demo", follow_redirects=True).get_data(as_text=True)
    assert "only be loaded into an account with no practice" in page
    assert query(hosted, me, "SELECT count(*) AS n FROM attempts")[0]["n"] == 0
    assert query(hosted, me, "SELECT count(*) AS n FROM problems WHERE is_custom = 1")[0]["n"] == 1
    assert query(hosted, me, "SELECT preference FROM pattern_preferences") == [{"preference": "mastered"}]


def test_a_running_sync_neither_ends_undo_nor_outlives_deleting_all_data(hosted, monkeypatch):
    import json

    client = sign_in(hosted, monkeypatch, 101, "ada")
    log(client, notes="before")
    me = user_id(hosted, "ada")
    conn = _as(hosted, me)
    try:
        with conn:
            conn.execute("INSERT INTO sync_job (id, data, lease) VALUES (1, ?, 0)", (json.dumps(
                {"now": 0, "order": [], "sites": {}, "index": 0, "state": None, "results": [], "earlier": [],
                 "done": False, "shown": False}),))
    finally:
        conn.close()
    client.post("/settings/erase", data={"confirm": "erase"})
    assert query(hosted, me, "SELECT count(*) AS n FROM sync_job")[0]["n"] == 0  # The sync stopped.
    # Open pages keep asking for sync steps, which must not make the deletion final.
    client.post("/sync/step", headers={"Accept": "application/json"})
    assert query(hosted, me, "SELECT count(*) AS n FROM kept_copy")[0]["n"] == 1
    client.post("/settings/erase/undo")
    assert [r["notes"] for r in query(hosted, me, "SELECT notes FROM attempts")] == ["before"]


def test_only_one_instance_loads_the_catalog_at_a_time(hosted, catalog_path):
    """Instances starting together after a deploy wait for the one loading the catalog, then skip."""
    import threading

    from codecompass import catalog

    holder = app_db(hosted)
    holder.execute("SELECT pg_advisory_lock(?)", (catalog.CATALOG_LOCK,))
    result = {}

    def start():
        conn = app_db(hosted)
        try:
            result["loaded"] = catalog.load_if_changed(conn, hosted.config["PATTERNS_PATH"], catalog_path)
        finally:
            conn.close()

    waiting = threading.Thread(target=start)
    waiting.start()
    waiting.join(0.5)
    assert waiting.is_alive()  # Held back while another instance loads.
    holder.execute("SELECT pg_advisory_unlock(?)", (catalog.CATALOG_LOCK,))
    holder.commit()
    holder.close()
    waiting.join(10)
    assert result == {"loaded": False}  # The catalog was already loaded, so it skipped.


def test_a_custom_problem_the_catalog_gained_is_merged_in_backups(hosted, monkeypatch):
    """A backup holds each link once, so a custom problem whose link the shared catalog later
    gained is written as that catalog problem, with its attempts and notes (R-46, R-55)."""
    client = sign_in(hosted, monkeypatch, 101, "ada")
    me = user_id(hosted, "ada")
    client.post("/problems/new", data={"title": "Mine first", "link": "https://example.com/later", "difficulty": "easy",
                                       "patterns": "Stack"})
    mine = query(hosted, me, "SELECT id FROM problems WHERE is_custom = 1")[0]["id"]
    log(client, notes="on my copy", problem="Mine first (custom)")
    client.post(f"/problems/{mine}/notes", data={"note": "my note"})
    shared = app_db(hosted)
    try:
        with shared:
            shared.execute("SET LOCAL codecompass.catalog = 'on'")
            shared.execute("INSERT INTO problems (title, link, difficulty, source, is_custom, catalog_position) "
                           "VALUES ('Added later', 'https://example.com/later', 'easy', 'Test list', 0, 99)")
    finally:
        shared.close()
    later = query(hosted, me, "SELECT id FROM problems WHERE link = 'https://example.com/later' AND is_custom = 0")[0]["id"]
    client.post(f"/problems/{later}/notes", data={"note": "catalog note"})
    client.post("/settings/erase", data={"confirm": "erase"})
    client.post("/settings/erase/undo")
    rows = query(hosted, me, "SELECT p.link, p.is_custom, a.notes FROM attempts a JOIN problems p ON p.id = a.problem_id")
    assert rows == [{"link": "https://example.com/later", "is_custom": 0, "notes": "on my copy"}]
    assert query(hosted, me, "SELECT note FROM problem_notes") == [{"note": "my note\n\ncatalog note"}]


def test_a_large_backup_upload_reaches_restore_with_form_tokens_on(tmp_path, catalog_path, monkeypatch):
    """The form-token check reads the upload, so a backup's own size limit applies before it."""
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "tokens.sqlite"), "CATALOG_PATH": catalog_path,
                      "RESERVE_PATH": None, "UNMAPPED_PATH": None, "TESTING_USER_ID": None, "CSRF_CHECK": True,
                      "GITHUB_CLIENT_ID": "test-client", "GITHUB_CLIENT_SECRET": "test-secret"})
    client = sign_in(app, monkeypatch, 101, "ada")
    token = re.search(r'name="csrf_token" value="([^"]+)"', client.get("/settings/restore").get_data(as_text=True))[1]
    big = b"x" * (6 * 1024 * 1024)  # Over the app's 5 MB limit for other uploads.
    response = client.post("/settings/restore", data={"csrf_token": token, "confirm": "restore",
                                                      "file": (io.BytesIO(big), "big.sqlite")},
                           content_type="multipart/form-data")
    # Refused as not a backup by restore itself, not as too large before it.
    assert response.status_code == 400 and "t a CodeCompass backup" in response.get_data(as_text=True)


def test_a_lookup_waits_its_turn_among_every_accounts_requests(hosted, monkeypatch):
    from codecompass import remote

    client = sign_in(hosted, monkeypatch, 101, "ada")
    sent = []
    monkeypatch.setattr(remote, "fetch", lambda url, data=None: sent.append(url))
    shared = app_db(hosted)
    try:
        with shared:  # Another account's requests hold Codeforces for the next ten minutes.
            shared.execute("INSERT INTO site_clock (host, next_at) VALUES ('codeforces.com', ?)"
                           " ON CONFLICT (host) DO UPDATE SET next_at = excluded.next_at", (remote.wall_clock() + 600,))
    finally:
        shared.close()
    page = client.get("/problems/new?lookup=1&site=codeforces&ref=1520A").get_data(as_text=True)
    assert "Codeforces is busy with other requests from CodeCompass" in page and sent == []


# --- R-57: the sign-in page as a landing page, and getting started ---

def test_the_sign_in_page_shows_what_codecompass_does(hosted):
    page = hosted.test_client().get("/signin").get_data(as_text=True)
    for heading in ("Mastery by pattern", "Reviews before you forget", "What to practice next, and why",
                    "Your practice, wherever you did it"):
        assert f">{heading}</h2>" in page, heading
    assert page.count('class="preview"') == 4
    assert page.count("Sign in with GitHub") == 2  # At the top, and again at the end.
    assert "sync your submissions from Codeforces or AtCoder" in page  # No LeetCode in hosted mode (R-33).
    # Nothing in a preview can be clicked: its links have no address.
    # Each preview ends its feature, so it runs to the next feature or to the closing section.
    previews = [chunk.split('<li class="feature"')[0].split('class="landing-end"')[0]
                for chunk in page.split('class="preview"')[1:]]
    assert len(previews) == 4 and all("href=" not in p for p in previews)
    # Everything is served by the app itself (R-24): no address outside it, in a link, a
    # script, an image, or a style.
    assert not re.search(r'(?:href|src|action)="(?:https?:)?//', page)
    assert "url(http" not in page


def test_the_help_guide_needs_signing_in(hosted, monkeypatch):
    """R-58: like every page but sign-in and the privacy notice (R-51)."""
    response = hosted.test_client().get("/help")
    assert response.status_code == 302 and response.location.startswith("/signin")
    page = sign_in(hosted, monkeypatch, 101, "ada").get("/help").get_data(as_text=True)
    assert "Your account" in page and 'href="/account"' in page


def test_the_getting_started_panel_is_each_accounts_own(hosted, monkeypatch):
    ada = sign_in(hosted, monkeypatch, 101, "ada")
    bo = sign_in(hosted, monkeypatch, 202, "bo")
    assert log(ada).status_code == 302
    assert "Get started" not in ada.get("/").get_data(as_text=True)
    assert "Get started" in bo.get("/").get_data(as_text=True)  # Bo has not logged anything yet.


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
