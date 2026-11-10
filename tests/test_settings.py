"""The settings page: starting difficulty, switches, pattern goals, and the site filter (R-13, R-32, R-36)."""
from codecompass import queries
from codecompass.core.sites import FILTER_SITES, KINDS, is_hidden, problem_kind
from codecompass.db import get_db

ALL_SHOWN = {f"show:{site}:{kind}": "1" for site in FILTER_SITES for kind in KINDS}


def saved(app):
    with app.app_context():
        return queries.read_settings(get_db())


def test_defaults_shown_before_anything_is_saved(client):
    page = client.get("/settings").get_data(as_text=True)
    assert '<option value="easy" selected>' in page
    assert 'name="advanced_on" value="1" checked' not in page
    assert 'name="very_hard_on" value="1" checked' not in page
    assert page.count('<option value="" selected>Neither</option>') == 54
    assert page.count('value="1" checked>') == len(FILTER_SITES) * len(KINDS)
    assert 'href="/settings" aria-current="page"' in page


def test_saving_every_setting(client, app):
    form = {**ALL_SHOWN, "starting_difficulty": "medium", "advanced_on": "1",
            "pref:Stack": "target", "pref:Heap": "mastered", "pref:Tree DP": "target", "pref:Trie": ""}
    del form["show:cses:core"], form["show:codeforces:advanced"]
    response = client.post("/settings", data=form)
    assert response.status_code == 302
    assert saved(app) == {
        "settings": {"starting_difficulty": "medium", "advanced_on": "1", "very_hard_on": "0"},
        "preferences": {"Stack": "target", "Heap": "mastered", "Tree DP": "target"},
        "hidden": {("cses", "core"), ("codeforces", "advanced")},
    }
    page = client.get("/settings").get_data(as_text=True)
    assert "Settings saved." in page
    assert '<option value="medium" selected>' in page
    assert 'name="show:cses:core" value="1" checked' not in page
    assert 'name="show:cses:advanced" value="1" checked' in page
    # An advanced target opens the advanced patterns section.
    assert "<details open>" in page


def test_saving_again_replaces_earlier_choices(client, app):
    client.post("/settings", data={**ALL_SHOWN, "starting_difficulty": "easy", "pref:Stack": "target"})
    client.post("/settings", data={**ALL_SHOWN, "starting_difficulty": "hard", "pref:Stack": "mastered",
                                   "very_hard_on": "1"})
    result = saved(app)
    assert result["preferences"] == {"Stack": "mastered"}
    assert result["settings"]["very_hard_on"] == "1"
    assert result["hidden"] == set()


def test_invalid_values_change_nothing(client, app):
    response = client.post("/settings", data={**ALL_SHOWN, "starting_difficulty": "impossible",
                                              "pref:Stack": "both"})
    page = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "Choose a starting difficulty." in page
    assert "Choose target, mastered, or neither for each pattern." in page
    assert saved(app) == {"settings": {}, "preferences": {}, "hidden": set()}


def test_a_pattern_has_one_goal(client):
    """Each pattern has a single choice, so it cannot be a target and mastered at once (R-32)."""
    page = client.get("/settings").get_data(as_text=True)
    assert page.count('name="pref:Stack"') == 1


def test_problem_kind_and_hidden_sites():
    advanced = {"Segment Tree and Fenwick Tree"}
    assert problem_kind(["Stack"], advanced) == "core"
    assert problem_kind(["Stack", "Segment Tree and Fenwick Tree"], advanced) == "advanced"
    hidden = {("cses", "core")}
    assert is_hidden("https://cses.fi/problemset/task/1068", ["Stack"], advanced, hidden)
    assert not is_hidden("https://cses.fi/problemset/task/1648", ["Segment Tree and Fenwick Tree"], advanced, hidden)
    assert not is_hidden("https://leetcode.com/problems/two-sum/", ["Stack"], advanced, hidden)
    # Links to other sites, and problems without a link, are never hidden.
    assert not is_hidden("https://example.com/x", ["Stack"], advanced, {("leetcode", "core")})
    assert not is_hidden(None, ["Stack"], advanced, hidden)
    assert not is_hidden("https://cses.fi/problemset/task/1068", ["Stack"], advanced, set())


def test_every_page_offers_the_light_and_dark_toggle(client):
    for path in ("/", "/log", "/history", "/sync", "/profile", "/settings"):
        page = client.get(path).get_data(as_text=True)
        assert 'id="theme-toggle"' in page and "js/theme.js" in page
        # The saved choice is applied before the stylesheet loads, so the page never flashes.
        assert page.index('localStorage.getItem("codecompass-theme")') < page.index("css/app.css")


def test_dark_tokens_match_for_the_system_setting_and_the_toggle():
    import re
    from pathlib import Path

    css = (Path(__file__).parent.parent / "codecompass" / "static" / "css" / "app.css").read_text(encoding="utf-8")
    media = css.split('  :root:not([data-theme="light"]) {', 1)[1].split("}", 1)[0]
    chosen = css.split(':root[data-theme="dark"] {', 1)[1].split("}", 1)[0]
    tokens = lambda block: re.findall(r"(--[\w-]+|color-scheme):\s*([^;]+);", block)
    assert tokens(media) and tokens(media) == tokens(chosen)
