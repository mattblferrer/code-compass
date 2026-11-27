"""The help guide (R-58). Runs in local mode, and in hosted mode with CODECOMPASS_TEST_PG."""
import re

from codecompass.core import constants as c


def page(client, path):
    response = client.get(path)
    assert response.status_code == 200, path
    return response.get_data(as_text=True)


def setting_texts(html):
    """Each setting's short help on a page, by key, with spacing evened out."""
    found = re.findall(r'data-setting="([^"]+)">(.*?)</(?:small|p|dd)>', html, re.S)
    return {key: " ".join(text.split()) for key, text in found}


def test_the_guide_lists_every_shortcut(client):
    html = page(client, "/help")
    for keys in ("<kbd>/</kbd>", "<kbd>L</kbd>", "<kbd>1</kbd> to <kbd>4</kbd>", "<kbd>S</kbd>", "<kbd>?</kbd>"):
        assert keys in html, keys


def test_every_setting_has_the_same_text_on_both_pages_and_links_to_itself(client):
    settings, guide = page(client, "/settings"), page(client, "/help")
    on_settings, in_guide = setting_texts(settings), setting_texts(guide)
    assert len(on_settings) == 11  # R-61 added Hide details until solved.
    assert in_guide == on_settings  # Every setting, word for word.
    # Each setting's link in the guide opens a place that exists on the settings page.
    anchors = set(re.findall(r'href="/settings#([^"]+)"', guide))
    assert {"setting-starting_difficulty", "setting-weekly_goal", "sites", "pattern-goals", "accounts",
            "backup", "delete-all"} <= anchors
    for anchor in anchors:
        assert f'id="{anchor}"' in settings, anchor


def test_the_guide_is_one_step_from_every_page(client):
    for path in ("/", "/log", "/history", "/settings"):
        html = page(client, path)
        # In the header's More menu, the phone's More sheet, and the "?" list.
        assert html.count('href="/help"') == 3, path
        assert 'href="/help"' in html.split('class="nav-more-menu"', 1)[1].split("</nav>", 1)[0], path
    assert 'href="/help#settings"' in page(client, "/settings")


def test_the_guides_numbers_follow_the_rules(client, monkeypatch):
    monkeypatch.setattr(c, "MIN_ATTEMPTS", 4)
    monkeypatch.setattr(c, "FADE_HALF_LIFE_DAYS", 90)
    monkeypatch.setattr(c, "NOT_NOW_DAYS", 5)
    monkeypatch.setattr(c, "STALE_REVIEW_DAYS", 200)
    monkeypatch.setattr(c, "MAX_TARGET_SLOTS", 3)
    monkeypatch.setitem(c.FIRST_INTERVAL_DAYS, c.SOLVED_ALONE, 21)
    html = page(client, "/help")
    for text in ("until it has 4 attempts", "halves over 90 days", "hides a new problem for 5 days",
                 "more than 200 days ago", "<th scope=\"row\">Solved alone</th><td>21 days</td>",
                 "up to 3 recommendation slots"):
        assert text in html, text
    assert "up to 3 recommendation slots" in page(client, "/settings")


def test_the_guide_fits_the_mode_and_loads_nothing_from_outside(client, app):
    html = page(client, "/help")
    if app.config.get("MODE") == "hosted":
        # Only the sites hosted mode syncs are named (R-58). The pattern guides (R-59) may
        # still link to LeetCode's own lessons, and the company presets (R-60) name LeetCode's
        # company tags as their source, which have nothing to do with syncing.
        outside_guides = html
        for section in ('id="guides"', 'id="presets"'):
            before, rest = outside_guides.split(section, 1)
            outside_guides = before + rest.split("</section>", 1)[1]
        assert "for Codeforces or AtCoder in" in html and "LeetCode" not in outside_guides
        assert 'id="account"' in html and "A sign-in ends after 30 days without use" in html
    else:
        assert "for Codeforces, AtCoder, or LeetCode in" in html and "about 20" in html
        assert 'id="account"' not in html
    # R-24: nothing loads from outside. The only outside addresses are the curated pattern
    # guides (R-59), which are plain links the user opens; no script, style, image, or form.
    assert not re.search(r'(?:src|action)="(?:https?:)?//', html)
    assert not re.search(r'<link[^>]*href="(?:https?:)?//', html)
    guides = {g["link"] for gs in app.extensions["pattern_guides"].values() for g in gs}
    outside = set(re.findall(r'<a href="((?:https?:)?//[^"]*)"', html))
    assert outside and outside <= guides
    assert not re.search(r'<(?!a )[^>]*href="(?:https?:)?//', html)
