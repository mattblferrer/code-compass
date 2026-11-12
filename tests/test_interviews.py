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


# --- Prep plan (R-44) ---

def test_plan_rule():
    from codecompass.core.plan import plan_patterns, prep_plan, weakest_first

    order = ["Arrays and Hashing", "Stack", "Heap", "Trie", "Greedy"]
    scores = {"Stack": 60, "Heap": 30, "Greedy": 30}
    # Unscored first (list order), then by score, ties in list order.
    assert weakest_first(["Greedy", "Stack", "Trie", "Heap", "Arrays and Hashing"], scores, order) == [
        "Arrays and Hashing", "Trie", "Heap", "Greedy", "Stack"]
    assert plan_patterns(["Stack", "Heap"], scores, order, order) == ["Heap", "Stack"]
    assert plan_patterns([], scores, order, order, weakest=3) == ["Arrays and Hashing", "Trie", "Heap"]
    plan = prep_plan("2026-11-12", "2026-11-16", ["A", "B", "C"], per_day=2)
    assert [(d["date"], d["patterns"], d["mixed"]) for d in plan] == [
        ("2026-11-12", ["A", "B"], False), ("2026-11-13", ["C", "A"], False), ("2026-11-14", ["B", "C"], False),
        ("2026-11-15", ["A", "B", "C"], True)]
    assert [d["mixed"] for d in prep_plan("2026-11-12", "2026-11-13", ["A"])] == [False]  # One day: no mixed day.
    assert prep_plan("2026-11-12", "2026-11-12", ["A"]) == [] and prep_plan("2026-11-12", "2026-11-20", []) == []


def test_plan_page_and_daily_target(client, app):
    response = add(client, company="Acme", date=day(4), patterns=["Stack", "Heap"], daily_target="2")
    assert response.status_code == 302
    page = client.get("/interviews").get_data(as_text=True)
    plan_link = page.split('">Prep plan</a>')[0].rsplit('href="', 1)[1]
    plan = client.get(plan_link).get_data(as_text=True)
    assert "Prep plan: Acme" in plan and "The interview&#39;s patterns" in plan
    assert plan.count('<li class="') == 4  # Today and the next three days; the last is mixed.
    assert "Mixed review" in plan and "of 2 solved" in plan
    bad = add(client, company="Beta", date=day(4), daily_target="0")
    assert bad.status_code == 400 and "Enter a whole number of problems a day from 1 to 20." in bad.get_data(as_text=True)
