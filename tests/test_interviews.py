"""The interviews page: add, edit, and delete upcoming interviews (R-15)."""
from datetime import date, timedelta

from codecompass import queries
from codecompass.db import get_db


def day(offset):
    return (date.today() + timedelta(days=offset)).isoformat()


def stored(app):
    with app.app_context():
        return [{k: i[k] for k in ("company", "date", "target_difficulty", "patterns")}
                for i in queries.interviews(get_db())]


def add(client, **form):
    data = {"company": "Acme", "date": day(5), "target_difficulty": "", **form}
    return client.post("/interviews", data=data)


def test_empty_page_offers_the_form(client):
    page = client.get("/interviews").get_data(as_text=True)
    assert "No interviews yet." in page
    assert "Add an interview" in page
    assert 'href="/interviews" aria-current="page"' in page


def test_adding_an_interview(client, app):
    response = add(client, company=" Acme ", target_difficulty="medium", patterns=["Stack", "Two Pointers"])
    assert response.status_code == 302
    assert stored(app) == [{"company": "Acme", "date": day(5), "target_difficulty": "medium",
                            "patterns": ["Two Pointers", "Stack"]}]
    page = client.get("/interviews").get_data(as_text=True)
    assert "Interview with Acme added." in page
    assert "<li>Two Pointers</li><li>Stack</li>" in page  # The patterns, as chips on the interview's card.
    # 5 days away, so the countdown shows it and recommendations focus on it.
    assert '<strong class="days-left">5</strong> days' in page and "Recommendations are focused on it" in page


def test_difficulty_and_patterns_are_optional(client, app):
    assert add(client).status_code == 302
    assert stored(app)[0]["target_difficulty"] is None and stored(app)[0]["patterns"] == []
    page = " ".join(client.get("/interviews").get_data(as_text=True).split())
    assert "Any difficulty; any patterns" in page


def test_invalid_interviews_are_not_saved(client, app):
    response = add(client, company="  ", date="next week", target_difficulty="impossible")
    page = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "Enter the company name." in page
    assert "Enter the date as YYYY-MM-DD." in page
    assert "Choose a difficulty, or leave it as any." in page
    assert stored(app) == []


def test_editing_replaces_details_and_patterns(client, app):
    add(client, patterns=["Stack", "Heap"])
    interview_id = queries_id(app)
    form = client.get(f"/interviews/{interview_id}/edit").get_data(as_text=True)
    assert "Edit the interview with Acme" in form
    assert 'value="Stack" checked' in form
    response = client.post(f"/interviews/{interview_id}/edit",
                           data={"company": "Acme Labs", "date": day(9), "target_difficulty": "hard",
                                 "patterns": ["Greedy"]})
    assert response.status_code == 302
    assert stored(app) == [{"company": "Acme Labs", "date": day(9), "target_difficulty": "hard",
                            "patterns": ["Greedy"]}]


def test_deleting_an_interview(client, app):
    add(client, patterns=["Stack"])
    interview_id = queries_id(app)
    response = client.post(f"/interviews/{interview_id}/delete")
    assert response.status_code == 302
    assert stored(app) == []
    with app.app_context():
        assert get_db().execute("SELECT count(*) FROM interview_patterns").fetchone()[0] == 0
    assert client.post(f"/interviews/{interview_id}/delete").status_code == 404


def test_focus_and_past_interviews_are_marked(client):
    add(client, company="Past Co", date=day(-3))
    add(client, company="Near A", date=day(4))
    add(client, company="Near B", date=day(4))
    add(client, company="Later Co", date=day(30))
    page = client.get("/interviews").get_data(as_text=True)
    assert page.count('<span class="tag">In focus</span>') == 2  # Same-date interviews combine.
    assert page.count('<span class="tag">Past</span>') == 1
    dashboard = client.get("/").get_data(as_text=True)
    assert "Focused on your" in dashboard and "with Near A and Near B on " in dashboard
    assert f'<time datetime="{day(4)}">' in dashboard.split("Focused on your")[1]


def test_no_focus_outside_the_window(client):
    add(client, company="Later Co", date=day(15))
    assert "In focus" not in client.get("/interviews").get_data(as_text=True)
    assert "Focused on your" not in client.get("/").get_data(as_text=True)


def queries_id(app):
    with app.app_context():
        return queries.interviews(get_db())[0]["id"]
