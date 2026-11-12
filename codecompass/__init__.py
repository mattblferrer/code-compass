import os
from pathlib import Path

from flask import Flask

from . import auth, catalog, db, demo, views


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    if os.environ.get("CODECOMPASS_MODE", "local") != "hosted":
        # Local mode keeps its database here. A hosted server's files may be read-only.
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    # The demo (R-25) uses its own database, so it never touches real data.
    app.config["DEMO"] = os.environ.get("CODECOMPASS_DEMO") == "1"
    default_db = "demo.sqlite" if app.config["DEMO"] else "codecompass.sqlite"
    app.config["DATABASE"] = os.environ.get(
        "CODECOMPASS_DATABASE",
        str(Path(app.instance_path) / default_db),
    )
    # Local mode (the default) keeps one user's data in the SQLite file above. Hosted mode
    # (R-50) keeps each account's data in PostgreSQL at CODECOMPASS_DATABASE_URL.
    app.config["MODE"] = os.environ.get("CODECOMPASS_MODE", "local")
    app.config["DATABASE_URL"] = os.environ.get("CODECOMPASS_DATABASE_URL")
    # Signs the session cookie. Hosted mode needs a fixed secret, so sign-ins survive restarts.
    app.config["SECRET_KEY"] = os.environ.get("CODECOMPASS_SECRET_KEY") or os.urandom(16).hex()
    # Hosted mode's GitHub sign-in (R-51): the OAuth app registered for this site.
    app.config["GITHUB_CLIENT_ID"] = os.environ.get("CODECOMPASS_GITHUB_CLIENT_ID")
    app.config["GITHUB_CLIENT_SECRET"] = os.environ.get("CODECOMPASS_GITHUB_CLIENT_SECRET")
    app.config["PATTERNS_PATH"] = str(catalog.DATA_DIR / "patterns.csv")
    # Largest accepted upload, for CSV import (R-19).
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
    app.config["CATALOG_PATH"] = str(catalog.DATA_DIR / "catalog.csv")
    # The unreviewed Codeforces reserve (R-37).
    reserve = catalog.DATA_DIR / "reserve.csv"
    app.config["RESERVE_PATH"] = str(reserve) if reserve.exists() else None
    # Codeforces and AtCoder problems the reserve cannot hold, read only to fill in the custom-problem form.
    unmapped = catalog.DATA_DIR / "reserve_unmapped.csv"
    app.config["UNMAPPED_PATH"] = str(unmapped) if unmapped.exists() else None
    if test_config:
        app.config.update(test_config)

    if app.config["MODE"] == "hosted" and not app.testing and not os.environ.get("CODECOMPASS_SECRET_KEY"):
        raise RuntimeError("Hosted mode needs CODECOMPASS_SECRET_KEY, so sign-ins survive restarts.")
    db.init_app(app)
    catalog.init_app(app)
    demo.init_app(app)
    auth.init_app(app)
    app.register_blueprint(views.bp)
    return app
