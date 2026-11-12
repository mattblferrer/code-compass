"""The security review's findings and hardening (docs/verification/security_review.md, R-53).

The first tests run in both modes; those marked hosted_only need CODECOMPASS_TEST_PG.
"""
import io
import re
import sqlite3

import pytest

from codecompass.core import constants as c
from codecompass.core.validation import local_path, web_link
from conftest import app_db, create_app

EVIL = "javascript:alert(document.cookie)"


def test_only_web_links_and_local_paths_pass():
    assert web_link("https://codeforces.com/problemset/problem/4/A") and web_link("HTTP://example.org/x")
    for bad in (EVIL, " javascript:x", "JavaScript:x", "data:text/html,x", "https://ok.example/\nx", None, 5):
        assert web_link(bad) is None, bad
    assert local_path("/history?q=1") == "/history?q=1"
    for bad in ("//evil.example", "/\\evil.example", "/\\/evil.example", "https://evil.example", "/x\ny", "", None):
        assert local_path(bad) is None, bad


def tampered_backup(client, change):
    """The app's own backup, changed by `change(conn)` as someone handing over a file might."""
    copy = sqlite3.connect(":memory:")
    copy.deserialize(client.get("/settings/backup").data)
    change(copy)
    copy.commit()
    data = copy.serialize()
    copy.close()
    return data


def restore(client, data):
    return client.post("/settings/restore", data={"file": (io.BytesIO(data), "b.sqlite"), "confirm": "restore"},
                       content_type="multipart/form-data")


def test_a_backup_cannot_put_script_links_on_a_page(client, app):
    def plant(conn):
        problem = conn.execute("INSERT INTO problems (title, link, difficulty, source, is_custom)"
                               " VALUES ('Planted', ?, 'easy', 'custom', 1)", (EVIL,)).lastrowid
        conn.execute("INSERT INTO problem_patterns (problem_id, pattern_id) SELECT ?, id FROM patterns LIMIT 1",
                     (problem,))
        conn.execute("INSERT INTO attempts (problem_id, date, outcome, entry_method) VALUES (?, '2026-11-01',"
                     " 'solved_alone', 'manual')", (problem,))
        conn.execute("INSERT INTO problem_links (problem_id, url, label) VALUES (?, ?, 'Editorial')", (problem, EVIL))
        conn.execute("INSERT INTO sync_items (site, username, problem_link, title, date, accepted, status)"
                     " VALUES ('codeforces', 'x', ?, 'Synced', '2026-11-01', 1, 'pending')", (EVIL,))

    assert restore(client, tampered_backup(client, plant)).status_code == 302
    conn = app_db(app)
    problem = conn.execute("SELECT id FROM problems WHERE title = 'Planted'").fetchone()[0]
    conn.close()
    pages = [client.get(path).get_data(as_text=True) for path in (f"/problems/{problem}", "/", "/sync", "/history")]
    for page in pages:
        assert not re.search(r'href="\s*javascript:', page, re.I)
    assert "Planted" in pages[0]


def test_a_backup_with_triggers_or_views_is_refused(client, app):
    data = tampered_backup(client, lambda conn: conn.execute(
        "CREATE TRIGGER wipe AFTER INSERT ON attempts BEGIN DELETE FROM attempts; END"))
    response = restore(client, data)
    assert response.status_code == 400 and "isn&#39;t a CodeCompass backup" in response.get_data(as_text=True)


def test_redirect_after_a_hint_stays_on_this_site(client, app):
    conn = app_db(app)
    problem = conn.execute("SELECT id FROM problems ORDER BY id LIMIT 1").fetchone()[0]
    conn.close()
    response = client.post(f"/problems/{problem}/hint", data={"next": "/\\evil.example"})
    assert response.status_code == 302 and response.location == "/"
    assert client.post(f"/problems/{problem}/hint", data={"next": "/history"}).location == "/history"


# --- Hosted mode ---

@pytest.fixture
def hosted(tmp_path, catalog_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "hosted.sqlite"), "CATALOG_PATH": catalog_path,
                       "RESERVE_PATH": None, "UNMAPPED_PATH": None, "TESTING_USER_ID": None,
                       "GITHUB_CLIENT_ID": "test-client", "GITHUB_CLIENT_SECRET": "test-secret"})


@pytest.mark.hosted_only
def test_signing_in_never_sends_anyone_to_another_site(hosted, monkeypatch):
    from codecompass import auth

    client = hosted.test_client()
    page = client.get("/signin?next=/\\evil.example").get_data(as_text=True)
    assert 'name="next" value="/"' in page
    client.post("/signin/github", data={"next": "/\\evil.example"})
    monkeypatch.setattr(auth, "github_profile", lambda: {"id": 101, "login": "ada", "name": None})
    assert client.get("/signin/github/callback").location == "/"


@pytest.mark.hosted_only
def test_an_odd_form_token_is_refused_without_an_error(hosted, monkeypatch):
    from test_hosted import sign_in

    hosted.config["CSRF_CHECK"] = True
    client = sign_in(hosted, monkeypatch, 101, "ada")
    response = client.post("/settings", data={"csrf_token": "é—token"})
    assert response.status_code == 400


@pytest.mark.hosted_only
def test_a_backup_cannot_take_ids_other_accounts_will_be_given(hosted, monkeypatch):
    from test_hosted import sign_in

    ada = sign_in(hosted, monkeypatch, 101, "ada")
    ahead = app_db(hosted).execute("SELECT max(id) FROM public.problems").fetchone()[0] + 1

    def claim(conn):
        for n in range(5):
            conn.execute("INSERT INTO problems (id, title, link, difficulty, source, is_custom)"
                         " VALUES (?, ?, NULL, 'easy', 'custom', 1)", (ahead + n, f"Squatter {n}"))

    assert restore(ada, tampered_backup(ada, claim)).status_code == 302
    bo = sign_in(hosted, monkeypatch, 202, "bo")
    added = bo.post("/problems/new", data={"title": "Bo's problem", "link": "https://example.org/bo",
                                          "difficulty": "easy", "patterns": ["Greedy"]})
    assert added.status_code == 302


@pytest.mark.hosted_only
def test_undo_still_restores_custom_problems_with_their_ids(hosted, monkeypatch):
    from test_hosted import query, sign_in, user_id

    ada = sign_in(hosted, monkeypatch, 101, "ada")
    ada.post("/problems/new", data={"title": "Mine", "link": "https://example.org/mine", "difficulty": "easy",
                                    "patterns": ["Greedy"]})
    before = query(hosted, user_id(hosted, "ada"), "SELECT id, title FROM problems WHERE is_custom = 1")
    ada.post("/settings/erase", data={"confirm": "erase"})
    ada.post("/settings/erase/undo")
    assert query(hosted, user_id(hosted, "ada"), "SELECT id, title FROM problems WHERE is_custom = 1") == before


@pytest.mark.hosted_only
def test_pages_carry_the_content_policy_and_are_not_cached(hosted, monkeypatch):
    from test_hosted import sign_in

    client = sign_in(hosted, monkeypatch, 101, "ada")
    page = client.get("/")
    policy = page.headers["Content-Security-Policy"]
    assert "script-src 'self';" in policy and "frame-ancestors 'none'" in policy
    assert "form-action 'self' https://github.com" in policy
    assert page.headers["Cache-Control"] == "no-store"
    assert "<script>" not in page.get_data(as_text=True)  # Every script is a file the policy allows.
    assert "no-store" not in client.get("/static/css/app.css").headers.get("Cache-Control", "")


@pytest.mark.hosted_only
def test_the_account_tool_lists_and_deletes_accounts(hosted, monkeypatch):
    from test_hosted import log, sign_in

    log(sign_in(hosted, monkeypatch, 101, "ada"))
    sign_in(hosted, monkeypatch, 202, "bo")
    runner = hosted.test_cli_runner()
    listed = runner.invoke(args=["accounts"])
    assert f"of {c.MAX_ACCOUNTS} accounts" in listed.output
    assert re.search(r"ada\s+created \S+\s+last signed in \S+\s+1 attempts", listed.output)
    assert "No account has" in runner.invoke(args=["accounts", "delete", "nobody", "--yes"]).output
    assert "Deleted bo's account." in runner.invoke(args=["accounts", "delete", "bo"], input="y\n").output
    assert "bo " not in runner.invoke(args=["accounts"]).output


def test_the_account_tool_says_it_needs_hosted_mode(tmp_path, catalog_path, monkeypatch):
    from conftest import local_create_app

    local = local_create_app({"TESTING": True, "DATABASE": str(tmp_path / "l.sqlite"), "CATALOG_PATH": catalog_path,
                              "RESERVE_PATH": None, "UNMAPPED_PATH": None})
    assert "only in hosted mode" in local.test_cli_runner().invoke(args=["accounts"]).output


def test_a_checked_database_connection_uses_a_ca_bundle(monkeypatch):
    import psycopg

    from codecompass import pg

    seen = {}

    def connect(url, **kwargs):
        seen.update(kwargs)
        raise RuntimeError("stop here")

    monkeypatch.setattr(psycopg, "connect", connect)
    with pytest.raises(RuntimeError):
        pg.Connection("postgresql://u:p@db.example/x?sslmode=verify-full")
    assert seen["sslrootcert"].endswith(".pem")
    seen.clear()
    with pytest.raises(RuntimeError):
        pg.Connection("postgresql://u:p@db.example/x?sslmode=require")
    assert "sslrootcert" not in seen
