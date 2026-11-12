"""Dashboard, reviews, recommendations, hints, and the calendar (R-10 to R-17, R-27 to R-31)."""
from datetime import date, timedelta

import pytest

from codecompass.core import constants as c
from codecompass.core.mastery import pattern_score
from codecompass.core.validation import MESSAGES
from codecompass.db import get_db

PARENS = "Valid Parentheses (Test list)"
TEMPS = "Daily Temperatures (Test list)"
TWO_SUM = "Two Sum (Test list)"


def ago(days):
    return (date.today() - timedelta(days=days)).isoformat()


def log(client, problem, days_ago, outcome=c.SOLVED_ALONE):
    response = client.post("/log", data={
        "problem": problem, "date": ago(days_ago), "outcome": outcome,
        "time_minutes": "", "time_seconds": "", "notes": "",
    })
    assert response.status_code == 302, response.get_data(as_text=True)


def page(client, path="/"):
    response = client.get(path)
    assert response.status_code == 200
    return response.get_data(as_text=True)


def pid(app, title):
    with app.app_context():
        return get_db().execute("SELECT id FROM problems WHERE title = ?", (title,)).fetchone()["id"]


def query(app, sql, *args):
    with app.app_context():
        return [dict(r) for r in get_db().execute(sql, args)]


def test_new_user_dashboard(client):
    html = page(client)
    assert "reviews are due" not in html and "review is due" not in html
    assert html.count('class="tile unstarted"') == 28  # Every core pattern, and no advanced ones.
    assert "FFT and NTT" not in html
    assert "New pattern for you" in html and "Hint available" in html


def test_scores_match_the_rule(client, app):
    for days in (20, 10, 2):
        log(client, PARENS, days)
    html = page(client)
    attempts = [{"date": ago(d), "difficulty": "easy", "outcome": c.SOLVED_ALONE} for d in (20, 10, 2)]
    expected = pattern_score(attempts, "normal", date.today().isoformat())
    assert f"<strong>{expected:.0f}</strong>" in html
    detail = page(client, "/patterns/Stack")
    assert f"{expected:.2f}" in detail
    # Each attempt's date shows once (rows also carry it in data-date, for sorting).
    assert detail.count(f'datetime="{ago(20)}"') == 1 and detail.count(f'datetime="{ago(2)}"') == 1
    assert "Not enough data" in page(client, "/patterns/Trie")


def test_due_review_uses_a_stable_sibling(client, app):
    log(client, PARENS, 30)  # Due 14 days later, so 16 days overdue.
    html = page(client)
    assert "1 review is due" in html
    assert "Daily Temperatures" in html and "Review of Valid Parentheses" in html
    page(client)
    rows = query(app, "SELECT sibling_problem_id, status FROM sibling_suggestions")
    assert rows == [{"sibling_problem_id": pid(app, "Daily Temperatures"), "status": "active"}]


def test_sibling_attempt_completes_the_review(client, app):
    log(client, PARENS, 30)
    page(client)
    log(client, TEMPS, 0)
    attempts = query(app, "SELECT problem_id, review_of_problem_id FROM attempts ORDER BY id")
    assert attempts[-1] == {"problem_id": pid(app, "Daily Temperatures"),
                            "review_of_problem_id": pid(app, "Valid Parentheses")}
    html = page(client)
    assert "review is due" not in html
    assert "<dt>Review streak</dt><dd>1 day</dd>" in html
    original = page(client, f"/problems/{pid(app, 'Valid Parentheses')}")
    review = original.split('id="review-heading"')[1]
    assert "<dt>Next review</dt>" in review and f'datetime="{(date.today() + timedelta(days=28)).isoformat()}"' in review
    assert "<dt>Next review</dt>" not in page(client, f"/problems/{pid(app, 'Daily Temperatures')}")


def test_dismissing_a_sibling_keeps_the_review_due(client, app):
    log(client, PARENS, 30)
    page(client)
    temps = pid(app, "Daily Temperatures")
    client.post(f"/problems/{temps}/not-now", data={"review_of": pid(app, "Valid Parentheses")})
    html = page(client)
    assert "1 review is due" in html
    assert "Due for another try" in html  # The original is suggested, since no other sibling remains.
    assert f'<time datetime="{ago(16)}">' in html
    assert query(app, "SELECT status FROM sibling_suggestions") == [{"status": "dismissed"}]


def test_not_now_hides_a_new_problem(client, app):
    two_sum = pid(app, "Two Sum")
    assert "Two Sum" in page(client)
    client.post(f"/problems/{two_sum}/not-now")
    assert "Two Sum" not in page(client).split("<h2>Patterns</h2>")[0]
    assert query(app, "SELECT problem_id FROM not_now") == [{"problem_id": two_sum}]


def test_hint_reveal_and_lock(client, app):
    two_sum = pid(app, "Two Sum")
    html = page(client)
    assert "Show beginner hint" in html
    assert "Use a hash map" not in html
    client.post(f"/problems/{two_sum}/hint", data={"next": "/"})
    html = page(client)
    assert "Use a hash map or set" in html
    assert f'<details class="hint" open data-hint-id="{two_sum}">' in html  # Can be hidden again.
    response = client.post("/log", data={"problem": TWO_SUM, "date": ago(0), "outcome": c.SOLVED_ALONE,
                                         "time_minutes": "", "time_seconds": "", "notes": ""})
    assert response.status_code == 400
    assert MESSAGES["outcome_hint"] in response.get_data(as_text=True)


def test_hint_redirect_stays_local(client, app):
    response = client.post(f"/problems/{pid(app, 'Two Sum')}/hint", data={"next": "https://evil.example"})
    assert response.headers["Location"] == "/"


def test_advanced_pattern_appears_once_attempted(client, app):
    response = client.post("/problems/new", data={
        "title": "Some flow problem", "link": "", "difficulty": "hard", "patterns": ["Max Flow and Min Cut"],
    })
    assert response.status_code == 302
    log(client, "Some flow problem (custom)", 1, c.NOT_SOLVED)
    html = page(client)
    assert "Max Flow and Min Cut" in html
    assert "FFT and NTT" not in html


def test_calendar_export(client, app):
    log(client, PARENS, 30)
    log(client, TWO_SUM, 3, c.SOLVED_WITH_HINTS)
    response = client.get("/reviews.ics")
    assert response.mimetype == "text/calendar"
    body = response.get_data(as_text=True)
    assert body.startswith("BEGIN:VCALENDAR\r\n") and body.endswith("END:VCALENDAR\r\n")
    assert body.count("BEGIN:VEVENT") == 2
    assert f"DTSTART;VALUE=DATE:{(date.today() - timedelta(days=16)).strftime('%Y%m%d')}" in body
    assert f"DTSTART;VALUE=DATE:{(date.today() + timedelta(days=7)).strftime('%Y%m%d')}" in body
    assert "SUMMARY:Review: Two Sum" in body


# --- Old reviews wait for newer ones (R-12) ---
# Two Sum last attempted 200 days ago was due 186 days ago; Valid Parentheses last
# attempted 30 days ago was due 16 days ago. Both are due, but Two Sum is old.

def test_served_reviews_rule():
    from codecompass.core.reviews import is_stale, served_reviews

    today = "2026-11-11"
    assert not is_stale("2026-05-15", today)  # Exactly 180 days ago is still recent.
    assert is_stale("2026-05-14", today)  # 181 days ago is old.
    due = {1: "2026-05-28", 2: "2026-10-26"}
    last = {1: "2026-05-14", 2: "2026-10-12"}
    assert served_reviews(due, last, today) == {2: "2026-10-26"}  # The old one waits.
    assert served_reviews({1: "2026-05-28"}, last, today) == {1: "2026-05-28"}  # Nothing newer is due.
    assert served_reviews({}, last, today) == {}


def test_an_old_review_waits_while_a_recent_one_is_due(client, app):
    log(client, TWO_SUM, 200)
    log(client, PARENS, 30)
    html = page(client)
    assert "1 review is due" in html
    assert "Review of Valid Parentheses" in html
    assert "Two Sum" not in html.split("<h2>Patterns</h2>")[0]
    # No sibling is chosen for the review that waits.
    assert query(app, "SELECT due_problem_id FROM sibling_suggestions") == [{"due_problem_id": pid(app, "Valid Parentheses")}]
    body = client.get("/reviews.ics").get_data(as_text=True)
    assert "SUMMARY:Review: Valid Parentheses" in body and "Two Sum" not in body


def test_an_old_review_is_served_when_nothing_recent_is_due(client, app):
    log(client, TWO_SUM, 200)
    html = page(client)
    assert "1 review is due" in html
    assert "Due for another try" in html and "Two Sum" in html.split("<h2>Patterns</h2>")[0]
    assert "SUMMARY:Review: Two Sum" in client.get("/reviews.ics").get_data(as_text=True)


def test_attempting_an_old_problem_still_completes_its_review(client, app):
    log(client, TWO_SUM, 200)
    log(client, PARENS, 30)
    log(client, TWO_SUM, 0)  # A review, solved alone: the 14-day interval doubles.
    review = page(client, f"/problems/{pid(app, 'Two Sum')}").split('id="review-heading"')[1]
    assert f'datetime="{(date.today() + timedelta(days=28)).isoformat()}"' in review and "<dd>28 days</dd>" in review


# --- Reviews off (R-41) ---

def save_reviews(client, on):
    from codecompass.core.sites import FILTER_SITES, KINDS

    form = {"starting_difficulty": "easy", **{f"show:{s}:{k}": "1" for s in FILTER_SITES for k in KINDS}}
    if on:
        form["reviews_on"] = "1"
    assert client.post("/settings", data=form).status_code == 302


def test_with_reviews_off_only_new_problems_are_recommended(client, app):
    log(client, PARENS, 30)  # Due 16 days ago.
    assert "1 review is due" in page(client)  # This also chooses its sibling.
    with app.app_context():
        get_db().execute("DELETE FROM sibling_suggestions")
        get_db().commit()
    save_reviews(client, on=False)
    html = page(client)
    assert "review is due" not in html and "Review of" not in html and "Due for another try" not in html
    assert "Review streak" not in html and "Review missed" not in html
    assert 'class="tag review"' not in html.split("<h2>Patterns</h2>")[0]
    assert "BEGIN:VEVENT" not in client.get("/reviews.ics").get_data(as_text=True)
    assert "<dt>Next review</dt>" not in page(client, f"/problems/{pid(app, 'Valid Parentheses')}")
    assert query(app, "SELECT * FROM sibling_suggestions") == []
    # The schedule is kept: turning reviews on again shows the same due date.
    save_reviews(client, on=True)
    html = page(client)
    assert "1 review is due" in html and f'<time datetime="{ago(16)}">' in html


def test_an_older_database_gains_the_reviews_setting(tmp_path):
    import sqlite3

    from codecompass.db import init_db

    path = str(tmp_path / "old.sqlite")
    old = sqlite3.connect(path)
    old.execute("""CREATE TABLE settings (
        key TEXT PRIMARY KEY CHECK (key IN ('starting_difficulty', 'advanced_on', 'very_hard_on')),
        value TEXT NOT NULL)""")
    old.execute("INSERT INTO settings VALUES ('starting_difficulty', 'hard')")
    old.commit()
    old.close()
    init_db(path)
    init_db(path)  # Safe to run again.
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO settings VALUES ('reviews_on', '0')")
    assert sorted(conn.execute("SELECT key, value FROM settings")) == [("reviews_on", "0"), ("starting_difficulty", "hard")]
    conn.close()


@pytest.mark.parametrize("path", ["/patterns/Nope", "/problems/999"])
def test_missing_pages(client, path):
    assert client.get(path).status_code == 404


def test_pattern_map_groups_by_family(client):
    html = page(client)
    for family in ("Arrays and strings", "Trees", "Graphs", "Recursion and DP"):
        assert f'aria-label="{family}"' in html
    assert "FFT and NTT" not in html


def test_difficulty_pills_are_colored(client):
    assert 'class="mark level-easy"' in page(client)


def test_score_history_on_pattern_page(client):
    for days in (30, 25, 20, 2):
        log(client, PARENS, days)
    html = page(client, "/patterns/Stack")
    assert "Score over time" in html
    assert html.count('class="dot"') == 4  # Weekly points from the third attempt on.
    assert "Score over time" not in page(client, "/patterns/Trie")


def test_score_chart_carries_each_weeks_change_for_the_details_box(client):
    """The score chart shows the same details box as the rating history: old → new (+delta)."""
    import html as markup
    import json

    for days in (30, 25, 20, 2):
        log(client, PARENS, days)
    html = page(client, "/patterns/Stack")
    data = html.split("data-points='", 1)[1].split("'", 1)[0]
    dots = json.loads(markup.unescape(data))
    assert dots[0]["old"] is None and dots[0]["change"] is None
    for before, after in zip(dots, dots[1:]):
        assert after["old"] == before["shown"] and after["change"] == after["shown"] - before["shown"]
    # Every attempt is counted in the week it falls in; the first two come before the first score.
    assert sum(d["attempts"] for d in dots) == 2
    assert html.index("js/chart_tip.js") < html.index("js/score_chart.js")


def test_undo_not_now_for_a_new_problem(client, app):
    two_sum = pid(app, "Two Sum")
    html = client.post(f"/problems/{two_sum}/not-now", follow_redirects=True).get_data(as_text=True)
    assert ">Undo</button>" in html
    not_now_id = query(app, "SELECT id FROM not_now")[0]["id"]
    html = client.post("/not-now/undo", data={"not_now_id": not_now_id, "suggestion_id": ""},
                       follow_redirects=True).get_data(as_text=True)
    assert "Recommendation restored." in html
    assert query(app, "SELECT * FROM not_now") == []
    assert "Two Sum" in html.split('aria-labelledby="patterns-heading"')[0]


def test_undo_restores_the_same_sibling(client, app):
    log(client, PARENS, 30)
    page(client)
    temps, parens = pid(app, "Daily Temperatures"), pid(app, "Valid Parentheses")
    client.post(f"/problems/{temps}/not-now", data={"review_of": parens})
    page(client)  # The dashboard may choose another sibling, or fall back to the original.
    suggestion = query(app, "SELECT id FROM sibling_suggestions WHERE status = 'dismissed'")[0]["id"]
    not_now_id = query(app, "SELECT id FROM not_now")[0]["id"]
    client.post("/not-now/undo", data={"not_now_id": not_now_id, "suggestion_id": suggestion})
    rows = query(app, "SELECT sibling_problem_id, status FROM sibling_suggestions")
    assert rows == [{"sibling_problem_id": temps, "status": "active"}]
    assert "Review of Valid Parentheses" in page(client)


# --- The cards beside the log form ---

def test_log_page_shows_the_chosen_problem_and_what_to_practice_next(client, app):
    log(client, PARENS, 30)  # Due, so Daily Temperatures is suggested as its sibling.
    page(client)
    html = page(client, f"/log?problem={pid(app, 'Daily Temperatures')}")
    assert "This problem" in html and "Logging it completes the review of <strong>Valid Parentheses</strong>" in html
    # Monotonic Stack and Queue has no attempts yet, so a hint is on offer and the patterns stay hidden (R-27).
    assert "Hidden until you show the hint or log an attempt." in html and "Monotonic Stack" not in html
    assert "Practice next" in html and 'data-pick-id="' in html
    # With nothing chosen, the card says how to use it.
    assert "Pick a problem to see its level" in page(client, "/log")


def test_problem_card_keeps_patterns_hidden_until_the_hint_or_an_attempt(client, app):
    # R-27: a problem in a pattern with no attempts offers a hint, so its patterns stay hidden.
    two_sum = pid(app, "Two Sum")
    card = page(client, f"/problems/{two_sum}/context")
    assert "Hidden until you show the hint or log an attempt." in card and "Arrays and Hashing" not in card
    client.post(f"/problems/{two_sum}/hint")
    card = page(client, f"/problems/{two_sum}/context")
    assert "Arrays and Hashing" in card
    assert "You showed the hint, so this attempt can't be saved as solved alone." in card
    # When editing an attempt, the rules for a new attempt are left out.
    assert "can't be saved as solved alone" not in page(client, f"/problems/{two_sum}/context?editing=1")
    assert client.get("/problems/99999/context").status_code == 404


def test_edit_page_shows_the_problem_but_not_practice_next(client, app):
    log(client, PARENS, 3)
    attempt_id = query(app, "SELECT id FROM attempts")[0]["id"]
    html = page(client, f"/attempts/{attempt_id}/edit")
    assert "This problem" in html and "Valid Parentheses" in html
    assert "Practice next" not in html


# --- Navigation and form checks ---

def test_phone_tab_bar_has_the_main_pages_and_more(client):
    html = page(client, "/settings")
    bar = html.split('<nav class="tab-bar"')[1].split("</nav>")[0]
    for label in ("Dashboard", "Log", "History", "More", "Interviews", "Sync", "Profile", "Settings"):
        assert f"<span>{label}</span>" in bar or f">{label}</a>" in bar
    # A page under More marks More as the current tab, and itself inside the sheet.
    assert '<summary aria-current="page">' in bar
    assert 'aria-current="page">Settings</a>' in bar
    assert '<summary aria-current="page">' not in page(client, "/log").split('<nav class="tab-bar"')[1]


def test_log_form_carries_the_servers_own_messages_for_checks_as_you_go(client):
    import html as html_lib
    import json

    attrs = page(client, "/log").split('id="attempt-form"')[1].split(">")[0]
    messages = json.loads(html_lib.unescape(attrs.split('data-messages="')[1].split('"')[0]))
    assert messages["date_future"] == MESSAGES["date_future"]
    assert messages["time"] == MESSAGES["time"] and messages["outcome"] == MESSAGES["outcome"]
    assert messages["unknown"].startswith(MESSAGES["problem"])


def test_practice_next_shows_where_each_problem_is_from(client, app):
    """The test catalog links to example.com, so each problem's site shows as that address."""
    dashboard = page(client).split('id="next-panel"')[1]
    assert dashboard.count('<span class="source">example.com</span>') == len(dashboard.split('class="title"')) - 1
    log_page = page(client, "/log").split('id="practice-heading"')[1]
    assert '<span class="source">example.com</span>' in log_page
    card = page(client, f"/problems/{pid(app, 'Two Sum')}/context")
    assert '<span class="source">example.com</span>' in card


# --- Sorting a pattern's attempts ---

def stack_rows(client, query=""):
    html = page(client, "/patterns/Stack" + query)
    body = html.split('id="pattern-attempts"')[1].split("<tbody>")[1].split("</tbody>")[0]
    return html, [part.split('"')[0] for part in body.split('data-date="')[1:]]


def test_pattern_attempts_list_newest_first_and_sort_by_any_column(client, app):
    log(client, PARENS, 20, c.SOLVED_WITH_HINTS)  # Valid Parentheses, easy.
    log(client, TEMPS, 10)  # Daily Temperatures, medium.
    log(client, PARENS, 2, c.NOT_SOLVED)
    html, dates = stack_rows(client)
    assert dates == [ago(2), ago(10), ago(20)]
    assert '<th scope="col" aria-sort="descending">' in html  # Date, the default.
    # Clicking Date again sorts oldest first; another column starts in its own first order.
    assert f'sort=date&amp;order=asc#attempts' in html and f'sort=problem&amp;order=asc#attempts' in html
    _, by_problem = stack_rows(client, "?sort=problem&order=asc")
    assert by_problem == [ago(10), ago(2), ago(20)]  # Daily Temperatures, then Valid Parentheses newest first.
    _, by_outcome = stack_rows(client, "?sort=outcome&order=desc")
    assert by_outcome == [ago(2), ago(20), ago(10)]  # Not solved, with hints, alone.
    _, by_level = stack_rows(client, "?sort=difficulty&order=asc")
    assert by_level == [ago(2), ago(20), ago(10)]  # Easy (newest first), then medium.
    # Anything unknown falls back to newest first.
    assert stack_rows(client, "?sort=nonsense&order=sideways")[1] == dates


def test_a_patterns_sort_does_not_carry_over_to_another(client, app):
    log(client, TEMPS, 10)
    page(client, "/patterns/Stack?sort=problem&order=asc")
    other = page(client, "/patterns/Monotonic Stack and Queue")
    assert 'id="pattern-attempts" data-sort="date" data-order="desc"' in other
    assert "js/sort_table.js" in other


def test_sort_rules():
    from codecompass.core import ordering

    assert ordering.chosen_sort("problem", None) == ("problem", "asc")
    assert ordering.chosen_sort(None, "asc") == ("date", "desc")
    assert ordering.next_order("date", "date", "desc") == "asc"
    assert ordering.next_order("outcome", "date", "desc") == "asc"



def test_a_half_done_settings_upgrade_is_finished_on_the_next_start(tmp_path):
    """An older version could stop between renaming the table and copying it back."""
    import sqlite3

    from codecompass.db import init_db

    path = str(tmp_path / "half.sqlite")
    init_db(path)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE settings_old (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute("INSERT INTO settings_old VALUES ('starting_difficulty', 'hard')")
    conn.commit()
    conn.close()
    init_db(path)
    conn = sqlite3.connect(path)
    assert list(conn.execute("SELECT key, value FROM settings")) == [("starting_difficulty", "hard")]
    assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'settings_old'").fetchone()
    conn.close()


def test_a_failed_settings_upgrade_changes_nothing(tmp_path, monkeypatch):
    import sqlite3

    import pytest as _pytest

    from codecompass import db

    path = str(tmp_path / "old.sqlite")
    old = sqlite3.connect(path)
    old.execute("""CREATE TABLE settings (
        key TEXT PRIMARY KEY CHECK (key IN ('starting_difficulty', 'advanced_on', 'very_hard_on')),
        value TEXT NOT NULL)""")
    old.execute("INSERT INTO settings VALUES ('starting_difficulty', 'hard')")
    old.commit()
    old.close()
    monkeypatch.setattr(db, "_create_statement", lambda schema, table: "CREATE TABLE broken (")
    with _pytest.raises(sqlite3.Error):
        db.init_db(path)
    conn = sqlite3.connect(path)
    assert list(conn.execute("SELECT key, value FROM settings")) == [("starting_difficulty", "hard")]
    assert [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE name LIKE 'settings%'")] == ["settings"]
    conn.close()


def test_interview_countdown_and_undo_cutoff():
    from codecompass.core.dates import countdown, undo_cutoff

    assert countdown("2026-11-11", "2026-11-17", 14) == {"days": 6, "past": False, "focus_in": 0, "focus_share": 1}
    assert countdown("2026-11-11", "2026-12-09", 14) == {"days": 28, "past": False, "focus_in": 14, "focus_share": 0.5}
    assert countdown("2026-11-11", "2026-11-08", 14)["past"]
    assert undo_cutoff("2026-03-01") == "2026-02-28"


def test_not_now_lasts_seven_days(client, app, monkeypatch):
    """R-29: a problem set aside with "not now" is left out for 7 days and returns after."""
    from codecompass import views

    two_sum = pid(app, "Two Sum")
    client.post(f"/problems/{two_sum}/not-now")
    shown = lambda: "Two Sum" in page(client).split("<h2>Patterns</h2>")[0]
    assert not shown()
    for days, expected in ((6, False), (7, True)):
        later = (date.today() + timedelta(days=days)).isoformat()
        monkeypatch.setattr(views, "today", lambda later=later: later)
        assert shown() is expected, days


# --- Review queue (R-42) ---

def test_review_queue_lists_due_and_upcoming_reviews(client, app):
    log(client, PARENS, 30)  # Due 16 days ago.
    log(client, "Course Schedule (Codeforces)", 5)  # Due in 9 days.
    log(client, TWO_SUM, 200)  # Old, so it waits while a newer review is due (R-12).
    html = page(client, "/reviews")
    due = html.split('id="due-heading"')[1].split('id="upcoming-heading"')[0]
    upcoming = html.split('id="upcoming-heading"')[1]
    assert "Valid Parentheses" in due and f'datetime="{ago(16)}"' in due and "<td>14 days</td>" in due
    assert "Course Schedule" in upcoming and "Course Schedule" not in due
    assert "Two Sum" not in html
    # No sibling is chosen just by opening the queue.
    assert query(app, "SELECT * FROM sibling_suggestions") == []
    assert 'href="/reviews"' in page(client)


def test_review_queue_swaps_a_sibling_and_stays(client, app):
    log(client, PARENS, 30)
    page(client)  # The dashboard suggests Daily Temperatures.
    html = page(client, "/reviews")
    assert "Daily Temperatures" in html.split('id="due-heading"')[1]
    temps, parens = pid(app, "Daily Temperatures"), pid(app, "Valid Parentheses")
    response = client.post(f"/problems/{temps}/not-now", data={"review_of": parens, "next": "reviews"})
    assert response.headers["Location"] == f"/reviews#review-{parens}"
    # No other sibling shares Stack in the test catalog, so the problem itself is the review.
    assert "No other sibling left; review it itself" in page(client, "/reviews")


def test_review_queue_with_reviews_off(client):
    log(client, PARENS, 30)
    save_reviews(client, on=False)
    html = page(client, "/reviews")
    assert "Reviews are turned off" in html and "Valid Parentheses" not in html


# --- Progress page (R-48) ---

def test_progress_page_charts_every_scored_pattern_and_the_movers(client, app):
    assert "Scores appear here once a pattern has 3 attempts." in page(client, "/progress")
    for days in (40, 33, 26, 5):
        log(client, PARENS, days)  # Stack is scored from the third attempt.
    html = page(client, "/progress")
    assert 'data-pattern="Stack"' in html and "js/progress_chart.js" in html
    assert 'data-pattern="Arrays and Hashing"' not in html  # No attempts, so no line.
    with app.app_context():
        from codecompass.state import Snapshot
        snap = Snapshot(get_db(), date.today().isoformat())
        days, series = snap.all_score_histories()
        assert days[0] == ago(40) and days[-1] == date.today().isoformat()
        assert all(later > earlier for earlier, later in zip(days, days[1:]))
        assert series["Stack"][:2] == [None, None]  # Before the third attempt.
        rising, falling = snap.movers()
        change = snap.score_change("Stack", 30)
    # Stack is the only scored pattern, so it is the one mover, in the direction its score went.
    assert rising == ([("Stack", change)] if change and change > 0 else [])
    assert falling == ([("Stack", change)] if change and change < 0 else [])
    assert ("None rose." in html) == (not rising) and ("None fell." in html) == (not falling)
    assert 'href="/progress"' in page(client)
