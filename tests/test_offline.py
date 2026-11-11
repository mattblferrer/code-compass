"""Offline use (R-24): the core features work with no internet access.

Every connection to anything but this machine is blocked, as with the network
off, and the reference flow runs: logging, the dashboard, a due review served as
a sibling, recommendations, and the other local pages. remote.fetch is left as it
is, so a stray lookup or sync request would be caught here too.
"""
import socket
from datetime import date, timedelta

import pytest

from codecompass.core import constants as c
from codecompass.db import get_db

LOOPBACK = ("127.0.0.1", "::1", "localhost")


@pytest.fixture
def offline(monkeypatch):
    """Refuse every connection that is not to this machine, and record the attempts."""
    blocked = []
    real_connect = socket.socket.connect

    def connect(sock, address):
        host = address[0] if isinstance(address, tuple) else address
        if host not in LOOPBACK:
            blocked.append(address)
            raise OSError("Network is unreachable (offline test)")
        return real_connect(sock, address)

    def create_connection(address, *args, **kwargs):
        if address[0] not in LOOPBACK:
            blocked.append(address)
            raise OSError("Network is unreachable (offline test)")
        raise OSError("No local connections expected")

    def getaddrinfo(host, *args, **kwargs):
        blocked.append((host,))
        raise socket.gaierror("Name resolution is unavailable (offline test)")

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "create_connection", create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    return blocked


def ago(days):
    return (date.today() - timedelta(days=days)).isoformat()


def ok(response):
    assert response.status_code in (200, 302), response.status_code
    return response.get_data(as_text=True)


def test_reference_flow_works_offline(client, app, offline):
    # Logging (R-04) and the dashboard (R-17).
    ok(client.post("/log", data={"problem": "Valid Parentheses (Test list)", "date": ago(30),
                                 "outcome": c.SOLVED_ALONE, "time_minutes": "12"}))
    html = ok(client.get("/"))
    # A due review, served as a sibling (R-12, R-28), and the recommendations (R-13).
    assert "1 review is due" in html and "Review of Valid Parentheses" in html
    assert "Practice next" in html
    # Logging the sibling completes the review.
    ok(client.post("/log", data={"problem": "Daily Temperatures (Test list)", "date": ago(0),
                                 "outcome": c.SOLVED_WITH_HINTS, "time_minutes": ""}))
    assert "review is due" not in ok(client.get("/"))
    with app.app_context():
        reviews = get_db().execute("SELECT count(*) FROM attempts WHERE review_of_problem_id IS NOT NULL").fetchone()[0]
    assert reviews == 1

    # "Not now", the other pages, a custom problem, and CSV export.
    problem_id = app.test_client().get("/problems/search?q=two").get_json()[0]["id"]
    ok(client.post(f"/problems/{problem_id}/not-now"))
    for path in ("/history", "/patterns/Stack", f"/problems/{problem_id}", "/interviews", "/settings",
                 "/sync", "/profile", "/import", "/problems/new", "/reviews.ics", "/attempts.csv"):
        ok(client.get(path))
    ok(client.post("/problems/new", data={"title": "Offline puzzle", "difficulty": "easy", "patterns": ["Greedy"]}))

    assert offline == []  # Nothing tried to reach the network.


def test_lookup_and_sync_fail_politely_offline(client, offline):
    # Only these two contact other sites, and only when started; offline they say so.
    page = ok(client.get("/problems/new?lookup=1&site=codeforces&ref=1520A"))
    assert "Could not reach Codeforces" in page
    client.post("/settings/accounts", data={"username:codeforces": "practice_user"})
    page = ok(client.post("/sync", follow_redirects=True))
    assert "Could not reach Codeforces" in page
    assert ok(client.get("/")) and offline  # The attempts were made, and refused.
