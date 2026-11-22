"""Pattern guides (R-59): the curated list, the user's own links, and where guides show."""
import io
import re
import sqlite3
from pathlib import Path
from urllib.parse import quote

import pytest

from codecompass import catalog
from codecompass.core import constants as c
from codecompass.core.catalog_rows import DataFileError
from codecompass.core.resources import from_markdown, parse_resources
from codecompass.db import get_db

ROOT = Path(__file__).resolve().parent.parent
CATEGORIES = {"Two Pointers": "core", "Segment Tree and Fenwick Tree": "advanced"}


def guide(pattern="Two Pointers", audience="interview", link="https://example.org/a", trick="", **extra):
    return {"pattern": pattern, "audience": audience, "site": "Example", "title": "A guide", "link": link,
            "note": "", "needs_account": "", "trick": trick, **extra}


def errors(rows):
    with pytest.raises(DataFileError) as caught:
        parse_resources(rows, CATEGORIES)
    return "\n".join(caught.value.messages)


def page(client, path):
    response = client.get(path)
    assert response.status_code == 200, path
    return response.get_data(as_text=True)


def pattern_path(name):
    return "/patterns/" + quote(name)


def rows(app, sql):
    with app.app_context():
        return [dict(r) for r in get_db().execute(sql)]


# --- The curated list ---

def test_the_data_file_matches_the_reviewed_list_in_docs():
    expected = from_markdown((ROOT / "docs" / "resources.md").read_text(encoding="utf-8"))
    assert catalog.read_rows(catalog.DATA_DIR / "resources.csv") == expected


def test_the_curated_list_loads_and_every_pattern_keeps_to_the_limit():
    guides = catalog.load_resources(catalog.DATA_DIR / "patterns.csv", catalog.DATA_DIR / "resources.csv")
    names = {r["name"] for r in catalog.read_rows(catalog.DATA_DIR / "patterns.csv")}
    assert guides and set(guides) <= names
    for name, listed in guides.items():
        assert len(listed) <= c.MAX_GUIDES_PER_PATTERN, name
        assert all(g["link"].startswith("https://") for g in listed), name


def test_reading_the_markdown_list():
    text = "\n".join([
        "## Core patterns",
        "### 3. Two Pointers",
        "1. Interview · Hello Interview · [Two Pointers](https://example.org/tp) (listed)",
        "2. Competitive · USACO Guide · [More on Prefix Sums](https://example.org/ps) (difference arrays) · Trick",
        "3. Interview · LeetCode Explore · [Card](https://example.org/lc) · Needs account",
        "## Sites",
        "1. Not a guide, outside any pattern",
    ])
    assert from_markdown(text) == [
        {"pattern": "Two Pointers", "audience": "interview", "site": "Hello Interview", "title": "Two Pointers",
         "link": "https://example.org/tp", "note": "", "needs_account": "", "trick": ""},
        {"pattern": "Two Pointers", "audience": "competitive", "site": "USACO Guide", "title": "More on Prefix Sums",
         "link": "https://example.org/ps", "note": "difference arrays", "needs_account": "", "trick": "yes"},
        {"pattern": "Two Pointers", "audience": "interview", "site": "LeetCode Explore", "title": "Card",
         "link": "https://example.org/lc", "note": "", "needs_account": "yes", "trick": ""},
    ]
    with pytest.raises(ValueError, match="line 2"):
        from_markdown("### 3. Two Pointers\n1. Interview - no separators [x](https://example.org)")


def test_the_data_file_is_checked():
    assert "unknown pattern 'Nope'" in errors([guide(pattern="Nope")])
    assert "audience must be one of" in errors([guide(audience="video")])
    assert "link must be a web link" in errors([guide(link="javascript:alert(1)")])
    assert "appears more than once" in errors([guide(), guide()])
    assert "trick must be yes or empty" in errors([guide(trick="no")])
    many = [guide(link=f"https://example.org/{i}") for i in range(c.MAX_GUIDES_PER_PATTERN + 1)]
    assert f"more than {c.MAX_GUIDES_PER_PATTERN} guides" in errors(many)


def test_the_data_file_keeps_each_patterns_order():
    # Core patterns: interview guides, then competitive ones, then tricks.
    parse_resources([guide(link="https://example.org/1"), guide(audience="competitive", link="https://example.org/2"),
                     guide(audience="interview", trick="yes", link="https://example.org/3")], CATEGORIES)
    assert "out of order" in errors([guide(audience="competitive", link="https://example.org/1"), guide()])
    assert "out of order" in errors([guide(trick="yes", link="https://example.org/1"), guide()])
    # Advanced patterns: competitive guides first.
    seg = "Segment Tree and Fenwick Tree"
    parse_resources([guide(pattern=seg, audience="competitive", link="https://example.org/1"),
                     guide(pattern=seg, link="https://example.org/2")], CATEGORIES)
    assert "out of order" in errors([guide(pattern=seg, link="https://example.org/1"),
                                     guide(pattern=seg, audience="competitive", link="https://example.org/2")])


# --- The pattern page ---

def test_a_pattern_page_lists_its_guides_in_order_with_labels(client, app):
    html = page(client, pattern_path("Two Pointers"))
    section = html.split('id="guides"', 1)[1].split("</section>", 1)[0]
    listed = app.extensions["pattern_guides"]["Two Pointers"]
    links = re.findall(r'<a href="(https://[^"]+)" target="_blank" rel="noopener noreferrer">', section)
    assert links == [g["link"] for g in listed]
    assert "<span>Hello Interview</span> <span>· Interview</span>" in section
    assert "<span>USACO Guide</span> <span>· Competitive programming</span>" in section
    assert "counts as help" in section

    union_find = page(client, pattern_path("Union-Find"))
    assert "<span>· Needs account</span>" in union_find and '<span class="guide-trick">· Trick</span>' in union_find
    # A note on a guide shows after its title.
    assert '<span class="guide-note">(difference arrays)</span>' in page(client, pattern_path("Intervals"))


def test_users_add_and_remove_their_own_links_for_a_pattern(client, app):
    path = pattern_path("Two Pointers")
    response = client.post(path + "/links", data={"url": "https://example.org/my-notes", "label": "My notes"})
    assert response.status_code == 302 and response.headers["Location"].endswith("#guides")
    for bad in ("javascript:alert(1)", "example.org/x", "ftp://example.org/x", ""):
        html = client.post(path + "/links", data={"url": bad}, follow_redirects=True).get_data(as_text=True)
        assert "Enter a web link starting with http:// or https://." in html, bad
    links = rows(app, "SELECT id, url, label FROM pattern_links")
    assert [(l["url"], l["label"]) for l in links] == [("https://example.org/my-notes", "My notes")]
    mine = '<a href="https://example.org/my-notes" target="_blank" rel="noopener noreferrer">My notes</a>'
    assert mine in page(client, path)
    assert mine not in page(client, pattern_path("Sliding Window"))
    # A link belongs to its pattern; another pattern's address cannot remove it.
    assert client.post(pattern_path("Sliding Window") + f"/links/{links[0]['id']}/delete").status_code == 404
    client.post(path + f"/links/{links[0]['id']}/delete")
    assert rows(app, "SELECT * FROM pattern_links") == []
    assert client.post(path + f"/links/{links[0]['id']}/delete").status_code == 404
    assert client.post(pattern_path("No Such Pattern") + "/links", data={"url": "https://example.org"}).status_code == 404


def test_a_stored_link_that_is_not_a_web_link_shows_as_text(client, app):
    with app.app_context():
        conn = get_db()
        with conn:
            conn.execute("INSERT INTO pattern_links (pattern_id, url, label) "
                         "SELECT id, 'javascript:alert(1)', 'Evil' FROM patterns WHERE name = 'Two Pointers'")
    html = page(client, pattern_path("Two Pointers"))
    assert "Evil" in html and 'href="javascript:' not in html


# --- The beginner hint and the help page ---

def test_guides_show_only_once_the_hint_is_revealed(client, app):
    problem = rows(app, "SELECT id FROM problems WHERE title = 'Course Schedule'")[0]["id"]
    first = app.extensions["pattern_guides"]["Topological Sort"][0]["link"]
    before = page(client, f"/problems/{problem}")
    assert "Show beginner hint" in before and first not in before
    client.post(f"/problems/{problem}/hint", data={"next": f"/problems/{problem}"})
    after = page(client, f"/problems/{problem}")
    hint = after.split('<details class="hint"', 1)[1].split("</details>", 1)[0]
    assert "Topological Sort" in hint and first in hint and "Reading a guide counts as help" in hint


def test_the_help_page_lists_every_curated_guide(client, app):
    html = page(client, "/help")
    section = html.split('id="guides"', 1)[1].split("</section>", 1)[0]
    for name, listed in app.extensions["pattern_guides"].items():
        assert f"<summary>{name} <small>{len(listed)}</small></summary>" in section, name
        for g in listed:
            assert f'href="{g["link"]}"' in section, (name, g["link"])
    assert 'href="#guides"' in html


def test_the_outcome_definitions_name_pattern_guides(client):
    assert "a pattern guide, or a beginner hint" in page(client, "/log")


# --- Backups and deleting all data ---

def test_links_are_in_backups_and_removed_with_all_data(client, app):
    client.post(pattern_path("Two Pointers") + "/links", data={"url": "https://example.org/kept"})
    data = client.get("/settings/backup").data
    client.post("/settings/erase", data={"confirm": "erase"})
    assert rows(app, "SELECT * FROM pattern_links") == []
    client.post("/settings/restore", data={"file": (io.BytesIO(data), "b.sqlite"), "confirm": "restore"},
                content_type="multipart/form-data")
    assert [r["url"] for r in rows(app, "SELECT url FROM pattern_links")] == ["https://example.org/kept"]
    assert "https://example.org/kept" in page(client, pattern_path("Two Pointers"))


def test_a_backup_from_before_pattern_links_restores(client, app):
    data = client.get("/settings/backup").data
    old = sqlite3.connect(":memory:")
    old.deserialize(data)
    old.execute("DROP TABLE pattern_links")
    response = client.post("/settings/restore", data={"file": (io.BytesIO(old.serialize()), "b.sqlite"),
                                                      "confirm": "restore"}, content_type="multipart/form-data")
    assert response.status_code == 302
    client.post(pattern_path("Two Pointers") + "/links", data={"url": "https://example.org/after"})
    assert [r["url"] for r in rows(app, "SELECT url FROM pattern_links")] == ["https://example.org/after"]
