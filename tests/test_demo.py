"""Demo dataset (R-25)."""
from datetime import date

import pytest

from codecompass import create_app, demo
from conftest import app_db


@pytest.fixture
def demo_app(tmp_path):
    return create_app({
        "TESTING": True,
        "DEMO": True,
        "DATABASE": str(tmp_path / "demo.sqlite"),
        "RESERVE_PATH": None,
    })


def build(app):
    conn = app_db(app)
    try:
        demo.build(conn, date.today().isoformat())
        return [dict(r) for r in conn.execute("SELECT * FROM attempts ORDER BY id")]
    finally:
        conn.close()


def test_demo_covers_eight_weeks(demo_app):
    attempts = build(demo_app)
    first = date.fromisoformat(attempts[0]["date"])
    assert (date.today() - first).days >= 56
    assert any(a["review_of_problem_id"] for a in attempts)


def test_demo_is_repeatable(demo_app):
    first = build(demo_app)
    assert build(demo_app) == first


def test_demo_fills_the_dashboard(demo_app):
    build(demo_app)
    html = demo_app.test_client().get("/").get_data(as_text=True)
    assert "due" in html and "Review of" in html
    assert "No recommendations yet" not in html


def test_demo_command_refuses_real_data(app):
    result = app.test_cli_runner().invoke(args=["demo"])
    assert result.exit_code != 0
    assert "CODECOMPASS_DEMO=1" in result.output
