"""Notes and links kept per problem (R-45)."""
from codecompass.core import constants as c
from codecompass.db import get_db


def pid(app, title):
    with app.app_context():
        return get_db().execute("SELECT id FROM problems WHERE title = ?", (title,)).fetchone()["id"]


def rows(app, sql):
    with app.app_context():
        return [dict(r) for r in get_db().execute(sql)]


def test_a_note_saves_as_typed_and_on_the_page(client, app):
    two_sum = pid(app, "Two Sum")
    page = client.get(f"/problems/{two_sum}").get_data(as_text=True)
    assert 'id="notes"' in page and "js/notes.js" in page
    response = client.post(f"/problems/{two_sum}/notes", data={"note": "  hash map of seen values  "},
                           headers={"X-Autosave": "1"})
    assert response.get_json() == {"saved": True}
    assert rows(app, "SELECT note FROM problem_notes") == [{"note": "hash map of seen values"}]
    assert "hash map of seen values</textarea>" in client.get(f"/problems/{two_sum}").get_data(as_text=True)
    # Without the script, Save note posts the form; an empty note removes it.
    response = client.post(f"/problems/{two_sum}/notes", data={"note": "   "})
    assert response.headers["Location"].endswith("#notes")
    assert rows(app, "SELECT * FROM problem_notes") == []


def test_a_note_that_is_too_long_is_not_saved(client, app):
    two_sum = pid(app, "Two Sum")
    response = client.post(f"/problems/{two_sum}/notes", data={"note": "x" * (c.MAX_NOTE_LENGTH + 1)},
                           headers={"X-Autosave": "1"})
    assert response.status_code == 400 and "Keep the note under" in response.get_json()["error"]
    assert rows(app, "SELECT * FROM problem_notes") == []


def test_links_are_added_and_removed(client, app):
    two_sum = pid(app, "Two Sum")
    client.post(f"/problems/{two_sum}/links", data={"url": "https://example.org/editorial", "label": "Editorial"})
    for bad in ("javascript:alert(1)", "example.org/x", "ftp://example.org/x", ""):
        page = client.post(f"/problems/{two_sum}/links", data={"url": bad}, follow_redirects=True).get_data(as_text=True)
        assert "Enter a web link starting with http:// or https://." in page, bad
    links = rows(app, "SELECT id, url, label FROM problem_links")
    assert [(l["url"], l["label"]) for l in links] == [("https://example.org/editorial", "Editorial")]
    page = client.get(f"/problems/{two_sum}").get_data(as_text=True)
    assert '<a href="https://example.org/editorial" target="_blank" rel="noopener noreferrer">Editorial</a>' in page
    client.post(f"/problems/{two_sum}/links/{links[0]['id']}/delete")
    assert rows(app, "SELECT * FROM problem_links") == []
    assert client.post(f"/problems/{two_sum}/links/{links[0]['id']}/delete").status_code == 404


def test_search_finds_problems_by_their_notes_after_titles(client, app):
    temps = pid(app, "Daily Temperatures")
    client.post(f"/problems/{temps}/notes", data={"note": "monotonic stack of indexes"})
    results = client.get("/problems/search?q=monotonic").get_json()
    assert [r["label"] for r in results] == ["Daily Temperatures (Test list)"]
    # A title match comes before a note match.
    client.post(f"/problems/{pid(app, 'Two Sum')}/notes", data={"note": "check the input is valid"})
    labels = [r["label"] for r in client.get("/problems/search?q=valid").get_json()]
    assert labels[0] == "Valid Parentheses (Test list)" and "Two Sum (Test list)" in labels
