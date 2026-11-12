"""The History calendar: problems solved per day over a year, with the year's stats (R-40)."""
from datetime import date, timedelta

from codecompass.core import constants as c
from codecompass.core import progress

PARENS = "Valid Parentheses (Test list)"
TWO_SUM = "Two Sum (Test list)"


def attempt(day, outcome=c.SOLVED_ALONE):
    return {"date": day, "outcome": outcome}


def log(client, problem, day, outcome=c.SOLVED_ALONE):
    response = client.post("/log", data={"problem": problem, "date": day, "outcome": outcome,
                                         "time_minutes": "", "time_seconds": "", "notes": ""})
    assert response.status_code == 302


# --- Plain rules ---

def test_every_solved_outcome_counts_and_not_solved_does_not():
    totals = progress.day_totals([
        attempt("2026-03-02"), attempt("2026-03-02", c.SOLVED_WITH_HINTS),
        attempt("2026-03-02", c.SOLVED_AFTER_SOLUTION), attempt("2026-03-02", c.NOT_SOLVED),
        attempt("2026-03-04", c.NOT_SOLVED),
    ])
    assert totals["2026-03-02"]["solved"] == 3 and totals["2026-03-02"]["attempts"] == 4
    assert totals["2026-03-02"][c.NOT_SOLVED] == 1
    assert totals["2026-03-04"]["solved"] == 0  # A day with only failed tries is practised, not solved.


def test_shades_follow_the_thresholds():
    assert c.CALENDAR_SHADES == (1, 2, 4, 6)
    assert [progress.shade(n) for n in (0, 1, 2, 3, 4, 5, 6, 20)] == [0, 1, 2, 2, 3, 3, 4, 4]


def test_periods():
    assert progress.period(None, "2026-11-11") == ("2025-11-12", "2026-11-11", "Past 12 months")
    assert progress.period(2025, "2026-11-11") == ("2025-01-01", "2025-12-31", "2025")


def test_weeks_run_monday_to_sunday_and_mark_months():
    totals = progress.day_totals([attempt("2026-03-02"), attempt("2026-03-02")])
    columns = progress.weeks("2026-02-26", "2026-03-10", totals, "2026-03-08")
    # 2026-02-26 is a Thursday, so the first week starts with three days outside the period.
    assert [d and d["date"] for d in columns[0]["days"]] == [None, None, None, "2026-02-26", "2026-02-27",
                                                              "2026-02-28", "2026-03-01"]
    assert [w["month"] for w in columns] == ["Mar", None, None]  # March starts in the first week.
    monday = columns[1]["days"][0]
    assert (monday["date"], monday["solved"], monday["shade"], monday["future"]) == ("2026-03-02", 2, 2, False)
    assert columns[2]["days"][1]["future"]  # 2026-03-10, after today.
    assert columns[2]["days"][2] is None  # 2026-03-11, after the period.


def test_stats_for_a_period():
    totals = progress.day_totals([
        attempt("2026-03-03"), attempt("2026-03-03", c.NOT_SOLVED),  # Tuesday
        attempt("2026-03-10", c.SOLVED_WITH_HINTS),  # Tuesday
        attempt("2026-03-05"), attempt("2026-03-05"),  # Thursday
        attempt("2025-12-30"),  # Outside the period.
    ])
    assert progress.stats(totals, "2026-01-01", "2026-12-31") == {
        "solved": 4, "attempts": 5, "days": 3, "average": 1.3, "busiest": "Tuesday", "busiest_attempts": 3}
    # A tie goes to the earlier weekday; with no attempts there is no busiest day.
    tie = progress.day_totals([attempt("2026-03-05"), attempt("2026-03-03")])
    assert progress.stats(tie, "2026-01-01", "2026-12-31")["busiest"] == "Tuesday"
    assert progress.stats({}, "2026-01-01", "2026-12-31") == {
        "solved": 0, "attempts": 0, "days": 0, "average": 0, "busiest": None, "busiest_attempts": 0}


def test_years_include_this_year():
    totals = progress.day_totals([attempt("2024-05-01"), attempt("2026-01-01")])
    assert progress.years(totals, "2026-11-11") == [2026, 2024]
    assert progress.years({}, "2026-11-11") == [2026]


def test_is_date():
    assert progress.is_date("2026-02-28") and not progress.is_date("2026-02-30")
    assert not progress.is_date("2026-2-3") and not progress.is_date("") and not progress.is_date("soon")


# --- The page ---

def test_history_shows_the_calendar_and_the_years_stats(client):
    today = date.today()
    log(client, PARENS, today.isoformat())
    log(client, TWO_SUM, today.isoformat(), c.NOT_SOLVED)
    log(client, PARENS, (today - timedelta(days=1)).isoformat(), c.SOLVED_WITH_HINTS)
    page = client.get("/history").get_data(as_text=True)
    assert "Problems solved, past 12 months" in page
    assert '<dt>Problems solved</dt><dd>2</dd>' in page and '<dt>Attempts</dt><dd>3</dd>' in page
    assert '<dt>Days practised</dt><dd>2</dd>' in page and '<dt>Solved per day practised</dt><dd>1.0</dd>' in page
    # Today's square links to today in the list and says what happened.
    assert f'href="#day-{today.isoformat()}"' in page and f'id="day-{today.isoformat()}"' in page
    assert ": 1 solved (1 alone), 1 not solved" in page
    assert page.count('class="cell s1"') >= 2  # Today and yesterday, one solve each.
    assert f'href="/history?year={today.year}"' in page and "js/history.js" in page


def test_a_calendar_year_and_an_earlier_day(client):
    log(client, PARENS, "2025-03-04")
    log(client, TWO_SUM, date.today().isoformat())
    page = client.get("/history?year=2025").get_data(as_text=True)
    assert "Problems solved, 2025" in page and '<dt>Problems solved</dt><dd>1</dd>' in page
    assert 'href="/history?year=2025" aria-current="page"' in page
    # A day can open the list at that day.
    earlier = client.get("/history?year=2025&until=2025-03-04").get_data(as_text=True)
    assert "Showing attempts up to Tue 4 Mar 2025." in earlier
    log_part = earlier.split('<div class="table-wrap log">', 1)[1]
    assert "Valid Parentheses" in log_part and "Two Sum" not in log_part
    # A year without attempts, or a malformed day, falls back to the default view.
    assert "Problems solved, past 12 months" in client.get("/history?year=1999").get_data(as_text=True)
    assert "Showing attempts up to" not in client.get("/history?until=soon").get_data(as_text=True)


def test_calendar_days_carry_the_charts_details_card(client):
    """Each day gives the shared details card its date, outcome breakdown, and solves."""
    today = date.today()
    log(client, PARENS, today.isoformat())
    log(client, TWO_SUM, today.isoformat(), c.NOT_SOLVED)
    page = client.get("/history").get_data(as_text=True)
    from codecompass.core.dates import full_date

    assert (f'data-tip-title="{full_date(today.isoformat())}" data-tip-note="1 alone, 1 not solved"\n'
            in page) and 'data-tip-value="1 solved"' in page
    assert 'data-tip-note="Nothing logged"' in page
    assert page.index("js/chart_tip.js") < page.index("js/history.js")


def test_site_label():
    from codecompass.core.sites import site_label

    assert site_label("https://leetcode.com/problems/two-sum/") == "LeetCode"
    assert site_label("https://codeforces.com/problemset/problem/4/A") == "Codeforces"
    assert site_label("https://atcoder.jp/contests/abc300/tasks/abc300_a") == "AtCoder"
    assert site_label("https://cses.fi/problemset/task/1068") == "CSES"
    assert site_label("https://www.hackerrank.com/challenges/x") == "hackerrank.com"
    assert site_label(None) == "Custom" and site_label("") == "Custom"


def test_history_shows_each_problems_source_and_difficulty(client):
    log(client, "Course Schedule (Codeforces)", date.today().isoformat())
    page = client.get("/history").get_data(as_text=True)
    assert "<th>Source</th><th>Difficulty</th>" in page
    row = page.split('<td class="problem-cell">', 1)[1].split("</tr>", 1)[0]
    # The test catalog links to example.com; its level shows in the dashboard's pill.
    assert '<td class="source-cell">example.com</td>' in row
    assert '<span class="mark level-medium">Medium</span>' in row


# --- Weekly goal (R-43) ---

def test_week_progress_and_weeks_that_met_the_goal():
    # 2026-03-04 is a Wednesday; its week runs from Monday 2026-03-02.
    totals = progress.day_totals([attempt("2026-03-02"), attempt("2026-03-03", c.SOLVED_WITH_HINTS),
                                  attempt("2026-03-04", c.NOT_SOLVED), attempt("2026-02-27")])
    assert progress.week_start("2026-03-04") == "2026-03-02" and progress.week_start("2026-03-02") == "2026-03-02"
    assert progress.week_progress(totals, "2026-03-04", 0) is None
    assert progress.week_progress(totals, "2026-03-04", 3) == {
        "solved": 2, "goal": 3, "met": False, "start": "2026-03-02", "share": 2 / 3}
    assert progress.week_progress(totals, "2026-03-04", 2)["met"]
    columns = progress.weeks("2026-02-23", "2026-03-08", totals, "2026-03-08", goal=2)
    assert [(w["solved"], w["met"]) for w in columns] == [(1, False), (2, True)]
    assert not any(w["met"] for w in progress.weeks("2026-02-23", "2026-03-08", totals, "2026-03-08"))


def test_weekly_goal_on_the_dashboard_and_calendar(client, app):
    from codecompass.core.sites import FILTER_SITES, KINDS

    today = date.today()
    log(client, PARENS, today.isoformat())
    assert "This week" not in client.get("/").get_data(as_text=True)  # No goal yet.
    client.post("/settings", data={"starting_difficulty": "easy", "reviews_on": "1", "weekly_goal": "1",
                                   **{f"show:{s}:{k}": "1" for s in FILTER_SITES for k in KINDS}})
    dashboard = client.get("/").get_data(as_text=True)
    assert "<dt>This week</dt>" in dashboard and "1 of 1 solved" in dashboard and 'aria-label="goal met"' in dashboard
    history = client.get("/history").get_data(as_text=True)
    assert 'class="goal-row"' in history and "Goal met, 1 solved" in history
