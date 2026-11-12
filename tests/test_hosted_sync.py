"""Hosted mode's sync, run in steps across requests (R-54).

Recorded responses only (test_sync.py's `sites`). Time passes only as the sync waits for
each site's turn (conftest's no_waiting), so a step's budget and the spacing are exact.
"""
import pytest

from codecompass import remote
from codecompass import sync as syncing
from codecompass.core import constants as c
from conftest import create_app
from test_hosted import _as, sign_in, user_id
from test_sync import sites  # noqa: F401  (a fixture)

pytestmark = pytest.mark.hosted_only

STEP = {"Accept": "application/json"}


@pytest.fixture
def hosted(tmp_path, catalog_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "hosted.sqlite"), "CATALOG_PATH": catalog_path,
                       "RESERVE_PATH": None, "UNMAPPED_PATH": None, "TESTING_USER_ID": None})


def linked(app, monkeypatch, github_id, login):
    client = sign_in(app, monkeypatch, github_id, login)
    client.post("/settings/accounts", data={"username:codeforces": "practice_user", "username:atcoder": "practice_user"})
    return client


def items(app, login):
    conn = _as(app, user_id(app, login))
    try:
        return sorted((r["site"], r["problem_link"], r["date"], r["accepted"]) for r in conn.execute(
            "SELECT site, problem_link, date, accepted FROM sync_items"))
    finally:
        conn.close()


def run_to_end(client, clock, limit=100):
    """Step the sync until it ends, a second apart, as an open page does. Returns how many
    steps it took. `clock` is conftest's no_waiting: time passes only as it grows."""
    for count in range(1, limit):
        clock.append(1.0)
        progress = client.post("/sync/step", headers=STEP).get_json()
        if progress["done"]:
            return count
    raise AssertionError("The sync never ended.")


def test_a_sync_run_in_steps_lists_what_one_run_does(hosted, sites, monkeypatch, no_waiting):
    whole = linked(hosted, monkeypatch, 101, "ada")
    whole.post("/sync")
    monkeypatch.setattr(c, "SYNC_STEP_SECONDS", 1.0)  # Room for about one request a step.
    stepped = linked(hosted, monkeypatch, 202, "bo")
    first = stepped.post("/sync", headers={"X-Sync-Background": "1"})
    assert first.status_code == 202 and not first.get_json()["done"]
    assert run_to_end(stepped, no_waiting) > 2
    assert items(hosted, "bo") == items(hosted, "ada") != []
    page = stepped.get("/sync").get_data(as_text=True)
    assert "Codeforces: 5 new submissions to confirm." in page and "AtCoder: 2 new submissions to confirm." in page


def test_syncs_of_three_accounts_share_each_sites_spacing(hosted, sites, monkeypatch):
    clients = [linked(hosted, monkeypatch, 100 + n, f"user{n}") for n in range(3)]
    times = []
    fake = remote.fetch

    def timed(url, data=None):
        times.append((remote.urlparse(url).hostname, remote.wall_clock()))
        return fake(url, data)

    monkeypatch.setattr(remote, "fetch", timed)
    monkeypatch.setattr(c, "SYNC_STEP_SECONDS", 3.0)
    for client in clients:
        client.post("/sync", headers={"X-Sync-Background": "1"})
    running = list(clients)
    while running:  # The three pages take turns asking, as open tabs would.
        running = [cl for cl in running if not cl.post("/sync/step", headers=STEP).get_json()["done"]]
    for host, spacing in remote.SPACING.items():
        at = sorted(t for h, t in times if h == host)
        assert all(b - a >= spacing - 1e-6 for a, b in zip(at, at[1:])), host
    assert items(hosted, "user0") == items(hosted, "user1") == items(hosted, "user2") != []


def test_a_sync_waits_for_its_turn_when_another_holds_the_site(hosted, sites, monkeypatch, no_waiting):
    monkeypatch.setattr(c, "SYNC_STEP_SECONDS", 5.0)
    client = linked(hosted, monkeypatch, 101, "ada")
    conn = _as(hosted, user_id(hosted, "ada"))
    with conn:  # Another account's requests hold Codeforces for the next minute.
        conn.execute("INSERT INTO site_clock (host, next_at) VALUES ('codeforces.com', ?)", (remote.wall_clock() + 60,))
    conn.close()
    progress = client.post("/sync", headers={"X-Sync-Background": "1"}).get_json()
    assert not progress["done"] and progress["sites"][0]["turn"]
    assert sites.requests == []  # It asked nothing while waiting.
    monkeypatch.setattr(c, "SYNC_STEP_SECONDS", 120.0)
    assert run_to_end(client, no_waiting) == 1


def test_a_paused_sync_resumes_where_it_stopped_after_a_restart(hosted, sites, monkeypatch, tmp_path, catalog_path, no_waiting):
    monkeypatch.setattr(c, "SYNC_STEP_SECONDS", 1.0)
    client = linked(hosted, monkeypatch, 101, "ada")
    client.post("/sync", headers={"X-Sync-Background": "1"})
    asked = len(sites.requests)
    cookie = client.get_cookie("session").value
    from codecompass import pg

    pg._ready.clear()  # A new copy of the app, as on a cold start.
    restarted = create_app({"TESTING": True, "DATABASE": str(tmp_path / "hosted.sqlite"), "CATALOG_PATH": catalog_path,
                            "RESERVE_PATH": None, "UNMAPPED_PATH": None, "TESTING_USER_ID": None,
                            "SECRET_KEY": hosted.config["SECRET_KEY"]})
    again = restarted.test_client()
    again.set_cookie("session", cookie)
    run_to_end(again, no_waiting)
    # Nothing read before the restart was asked for again.
    urls = [u for u, _ in sites.requests]
    assert asked >= 1 and all(urls.count(u) == 1 for u in urls[:asked])
    assert "Codeforces: 5 new submissions to confirm." in again.get("/sync").get_data(as_text=True)
    assert len(items(restarted, "ada")) == 7


def test_one_sync_per_account_at_a_time(hosted, sites, monkeypatch):
    monkeypatch.setattr(c, "SYNC_STEP_SECONDS", 1.0)
    client = linked(hosted, monkeypatch, 101, "ada")
    client.post("/sync", headers={"X-Sync-Background": "1"})
    conn = _as(hosted, user_id(hosted, "ada"))
    started = syncing.stored_job(conn).data["now"]
    sites.now += 3600
    page = client.post("/sync", follow_redirects=True).get_data(as_text=True)
    assert "A sync is already running." in page
    assert syncing.stored_job(conn).data["now"] == started  # Still the first sync, not a new one.
    conn.close()


def test_every_page_carries_a_running_sync_on(hosted, sites, monkeypatch, no_waiting):
    monkeypatch.setattr(c, "SYNC_STEP_SECONDS", 1.0)
    client = linked(hosted, monkeypatch, 101, "ada")
    client.post("/sync", headers={"X-Sync-Background": "1"})
    page = client.get("/history").get_data(as_text=True)
    assert 'src="/static/js/sync_steps.js" data-step-url="/sync/step"' in page
    run_to_end(client, no_waiting)
    assert "sync_steps.js" not in client.get("/history").get_data(as_text=True)


def test_a_sync_that_breaks_keeps_finished_sites_and_says_where_it_stopped(hosted, sites, monkeypatch):
    real = remote.sync_step

    def atcoder_breaks(state, known=frozenset()):
        if state["site"] == "atcoder":
            raise KeyError("an unexpected response")
        return real(state, known)

    monkeypatch.setattr(remote, "sync_step", atcoder_breaks)
    client = linked(hosted, monkeypatch, 101, "ada")
    client.post("/sync")
    page = client.get("/sync").get_data(as_text=True)
    assert "Codeforces: 5 new submissions to confirm." in page
    assert "AtCoder: the sync stopped because of an unexpected problem" in page


def test_without_javascript_the_sync_page_offers_to_continue(hosted, sites, monkeypatch):
    monkeypatch.setattr(c, "SYNC_STEP_SECONDS", 1.0)
    client = linked(hosted, monkeypatch, 101, "ada")
    page = client.post("/sync", follow_redirects=True).get_data(as_text=True)
    assert "<noscript>" in page and 'action="/sync/step"' in page and "Continue syncing" in page
    monkeypatch.setattr(c, "SYNC_STEP_SECONDS", 1000.0)
    page = client.post("/sync/step", follow_redirects=True).get_data(as_text=True)
    assert "Codeforces: 5 new submissions to confirm." in page
