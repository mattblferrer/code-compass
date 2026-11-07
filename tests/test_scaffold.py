import re
from pathlib import Path

from codecompass import create_app
from codecompass.db import get_db

PACKAGE = Path(__file__).resolve().parent.parent / "codecompass"


def test_dashboard_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Dashboard" in response.data


def test_stylesheet_is_served_locally(client):
    assert b'href="/static/css/app.css"' in client.get("/").data
    response = client.get("/static/css/app.css")
    assert response.status_code == 200
    assert b"No framework" in response.data
    response.close()


def test_no_external_assets_in_templates():
    for template in (PACKAGE / "templates").rglob("*.html"):
        assert not re.search(r"(src|href)=[\"'](https?:)?//", template.read_text(encoding="utf-8")), template


def test_saved_data_survives_restart(app, db_path):
    with app.app_context():
        conn = get_db()
        conn.execute("INSERT INTO app_meta (key, value) VALUES ('probe', 'kept')")
        conn.commit()

    restarted = create_app({"TESTING": True, "DATABASE": db_path})
    with restarted.app_context():
        row = get_db().execute("SELECT value FROM app_meta WHERE key = 'probe'").fetchone()
    assert row["value"] == "kept"


def test_core_does_not_import_flask():
    for module in (PACKAGE / "core").rglob("*.py"):
        assert not re.search(r"^\s*(from|import)\s+flask\b", module.read_text(encoding="utf-8"), re.M), module


def test_buttons_update_without_reloading(client):
    html = client.get("/").get_data(as_text=True)
    assert 'src="/static/js/enhance.js"' in html
    assert 'data-swap="#today, #next-panel, #messages"' in html
    response = client.get("/static/js/enhance.js")
    assert response.status_code == 200
    response.close()
