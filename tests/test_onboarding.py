"""Getting started on the dashboard (R-57). Runs in local mode, and in hosted mode with
CODECOMPASS_TEST_PG; the hosted sign-in page's tour is tested in test_hosted.py."""
from datetime import date

import pytest

from codecompass.core import constants as c

PARENS = "Valid Parentheses (Test list)"


def page(client, path="/"):
    response = client.get(path)
    assert response.status_code == 200, path
    return response.get_data(as_text=True)


def test_the_getting_started_panel_shows_until_the_first_attempt(client, app):
    html = page(client)
    assert "Get started" in html
    for link in ('href="/log"', 'href="/import"', 'href="/settings#accounts"'):
        assert link in html, link
    for path in ("/log", "/import", "/settings"):
        page(client, path)  # Each link opens its page.

    if app.config.get("MODE") == "hosted":
        assert "Load demo history" in html and "flask --app codecompass demo" not in html
    else:
        # Local mode keeps the demo in its own database, so the panel names the command.
        assert "flask --app codecompass demo" in html and "Load demo history" not in html

    response = client.post("/log", data={"problem": PARENS, "date": date.today().isoformat(),
                                         "outcome": c.SOLVED_ALONE, "time_minutes": "", "time_seconds": "", "notes": ""})
    assert response.status_code == 302
    html = page(client)
    assert "Get started" not in html and "Load demo history" not in html


def test_the_panel_names_the_sites_this_mode_syncs(client, app):
    html = page(client)
    if app.config.get("MODE") == "hosted":
        assert "from Codeforces or AtCoder by public username" in html
    else:
        assert "from Codeforces, AtCoder, or LeetCode by public username" in html


@pytest.mark.local_only  # Hosted mode's sign-in page is tested in test_hosted.py.
def test_local_mode_shows_the_landing_page_with_a_way_into_the_app(client):
    html = page(client, "/signin")
    assert html.count('class="preview"') == 4
    # No sign-in in local mode: both buttons lead straight to the dashboard instead.
    assert "Sign in with GitHub" not in html and "/signin/github" not in html
    assert html.count('<a class="button" href="/">Continue to your dashboard</a>') == 2
    assert "<title>CodeCompass</title>" in html
    # The sign-in routes exist only in hosted mode.
    assert client.post("/signin/github").status_code == 404
    assert client.get("/signin/github/callback").status_code == 404
    assert client.post("/signin/google").status_code == 404
    assert client.get("/signin/google/callback").status_code == 404
    assert client.get("/signin/password").status_code == 404
    assert client.get("/signup").status_code == 404
    assert "Sign in with a username" not in html
