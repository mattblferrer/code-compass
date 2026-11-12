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
    # Every site switch, and Review problems (R-41), start on.
    assert page.count('value="1" checked>') == len(FILTER_SITES) * len(KINDS) + 1
    assert 'name="reviews_on" value="1" checked' in page
    assert 'href="/settings" aria-current="page"' in page


def test_saving_every_setting(client, app):
    form = {**ALL_SHOWN, "starting_difficulty": "medium", "advanced_on": "1",
            "pref:Stack": "target", "pref:Heap": "mastered", "pref:Tree DP": "target", "pref:Trie": ""}
    del form["show:cses:core"], form["show:codeforces:advanced"]
    response = client.post("/settings", data=form)
    assert response.status_code == 302
    assert saved(app) == {
        "settings": {"starting_difficulty": "medium", "advanced_on": "1", "very_hard_on": "0", "reviews_on": "0",
                     "weekly_goal": "0"},
        "preferences": {"Stack": "target", "Heap": "mastered", "Tree DP": "target"},
        "hidden": {("cses", "core"), ("codeforces", "advanced")},
    }
    page = client.get("/settings").get_data(as_text=True)
    assert "Settings saved." in page
    assert '<option value="medium" selected>' in page
    assert 'name="show:cses:core" value="1" checked' not in page
    assert 'name="show:cses:advanced" value="1" checked' in page
    # Advanced goals sit beside the core ones, not in a closed section, so an advanced target shows.
    goals = page.split("Pattern goals")[1].split("</fieldset>")[0]
    assert 'name="pref:Tree DP"' in goals and "<details" not in goals


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


def test_each_change_saves_in_the_background(client, app):
    """The page's script posts each change with X-Autosave and gets JSON back."""
    page = client.get("/settings").get_data(as_text=True)
    assert 'id="settings-form"' in page and 'id="autosave-status"' in page and "js/settings_autosave.js" in page
    response = client.post("/settings", data={**ALL_SHOWN, "starting_difficulty": "hard", "reviews_on": "1"},
                           headers={"X-Autosave": "1"})
    assert response.status_code == 200 and response.get_json() == {"saved": True}
    assert saved(app)["settings"]["starting_difficulty"] == "hard"
    # No "Settings saved." message waits for the next page; the status line said it.
    assert "Settings saved." not in client.get("/settings").get_data(as_text=True)


def test_a_bad_background_save_changes_nothing(client, app):
    response = client.post("/settings", data={**ALL_SHOWN, "starting_difficulty": "impossible"},
                           headers={"X-Autosave": "1"})
    assert response.status_code == 400
    assert response.get_json() == {"saved": False, "errors": {"starting_difficulty": "Choose a starting difficulty."}}
    assert saved(app) == {"settings": {}, "preferences": {}, "hidden": set()}


def test_weekly_goal_setting(client, app):
    """R-43: a whole number of problems a week, blank for none."""
    response = client.post("/settings", data={**ALL_SHOWN, "starting_difficulty": "easy", "weekly_goal": "10"})
    assert response.status_code == 302 and saved(app)["settings"]["weekly_goal"] == "10"
    assert 'value="10" placeholder="No goal"' in client.get("/settings").get_data(as_text=True)
    for bad in ("-1", "2.5", "101", "ten"):
        response = client.post("/settings", data={**ALL_SHOWN, "starting_difficulty": "easy", "weekly_goal": bad})
        assert response.status_code == 400, bad
        assert "Enter a whole number from 0 to 100" in response.get_data(as_text=True)
    client.post("/settings", data={**ALL_SHOWN, "starting_difficulty": "easy", "weekly_goal": ""})
    assert saved(app)["settings"]["weekly_goal"] == "0"



def test_a_database_from_before_the_weekly_goal_can_store_it(tmp_path):
    import sqlite3

    from codecompass.db import init_db

    path = str(tmp_path / "r41.sqlite")
    old = sqlite3.connect(path)
    old.execute("""CREATE TABLE settings (
        key TEXT PRIMARY KEY CHECK (key IN ('starting_difficulty', 'advanced_on', 'very_hard_on', 'reviews_on')),
        value TEXT NOT NULL)""")
    old.execute("INSERT INTO settings VALUES ('reviews_on', '0')")
    old.commit()
    old.close()
    init_db(path)
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO settings VALUES ('weekly_goal', '5')")
    assert sorted(conn.execute("SELECT key, value FROM settings")) == [("reviews_on", "0"), ("weekly_goal", "5")]
    conn.close()
