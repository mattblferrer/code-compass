"""Basic accessibility checks on every main page, found in an accessibility pass: no id used
twice (the help page once reused the "?" dialog's id, so "?" could not open it there), and
every drawing either named for screen readers or hidden from them."""
import re

import pytest

PAGES = ["/", "/log", "/reviews", "/history", "/progress", "/patterns/Stack", "/settings", "/interviews",
         "/sync", "/profile", "/help", "/import", "/problems/new", "/signin"]


def html(client, path):
    response = client.get(path)
    assert response.status_code == 200, path
    return response.get_data(as_text=True)


@pytest.mark.parametrize("path", PAGES)
def test_no_id_is_used_twice(client, app, path):
    if path == "/signin" and app.config.get("MODE") == "hosted":
        client = app.test_client()  # The landing page, as a visitor sees it.
    ids = re.findall(r'\sid="([^"]+)"', html(client, path))
    assert sorted({i for i in ids if ids.count(i) > 1}) == []


@pytest.mark.parametrize("path", PAGES)
def test_the_first_link_skips_to_the_content(client, app, path):
    if path == "/signin" and app.config.get("MODE") == "hosted":
        client = app.test_client()
    page = html(client, path)
    first = re.search(r"<a\b[^>]*>", page.split("<body", 1)[1])[0]
    assert 'href="#content"' in first and '<main id="content"' in page


@pytest.mark.parametrize("path", PAGES)
def test_every_drawing_is_named_or_hidden(client, app, path):
    if path == "/signin" and app.config.get("MODE") == "hosted":
        client = app.test_client()
    for svg in re.findall(r"<svg\b[^>]*>", html(client, path)):
        assert 'aria-hidden="true"' in svg or ('role="img"' in svg and "aria-label=" in svg), svg
