"""Activity strip and score changes on the dashboard (R-17, R-30)."""
from datetime import date, timedelta

from codecompass.core.reviews import activity

TODAY = "2026-11-10"


def test_activity_statuses():
    records = [
        {"date": "2026-11-06", "due": True, "completed": True},
        {"date": "2026-11-07", "due": True, "completed": False},
        {"date": "2026-11-10", "due": True, "completed": False},
    ]
    days = activity(records, ["2026-11-07", "2026-11-08"], TODAY, 5)
    assert days == [
        {"date": "2026-11-06", "status": "review"},
        {"date": "2026-11-07", "status": "missed"},  # Practice that day does not hide a missed review.
        {"date": "2026-11-08", "status": "practice"},
        {"date": "2026-11-09", "status": "quiet"},
        {"date": "2026-11-10", "status": "quiet"},  # Today is never missed.
    ]


def test_dashboard_shows_strip_and_changes(client):
    def ago(n):
        return (date.today() - timedelta(days=n)).isoformat()

    for days_ago, outcome in ((40, "not_solved"), (30, "not_solved"), (20, "not_solved"),
                              (5, "solved_alone"), (2, "solved_alone")):
        client.post("/log", data={"problem": "Valid Parentheses (Test list)", "date": ago(days_ago),
                                  "outcome": outcome, "time_minutes": "", "time_seconds": "", "notes": ""})
    html = client.get("/").get_data(as_text=True)
    assert html.count('<li class="') >= 56
    assert 'class="change up"' in html
