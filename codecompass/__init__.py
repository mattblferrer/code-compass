import os
from pathlib import Path

from flask import Flask

from . import catalog, db, demo, views


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    # The demo (R-25) uses its own database, so it never touches real data.
    app.config["DEMO"] = os.environ.get("CODECOMPASS_DEMO") == "1"
    default_db = "demo.sqlite" if app.config["DEMO"] else "codecompass.sqlite"
    app.config["DATABASE"] = os.environ.get(
        "CODECOMPASS_DATABASE",
        str(Path(app.instance_path) / default_db),
    )
    # Only used to sign the flash-message cookie on this local app.
    app.config["SECRET_KEY"] = os.environ.get("CODECOMPASS_SECRET_KEY") or os.urandom(16).hex()
    app.config["PATTERNS_PATH"] = str(catalog.DATA_DIR / "patterns.csv")
    app.config["CATALOG_PATH"] = str(catalog.DATA_DIR / "catalog.csv")
    # The unreviewed Codeforces reserve (R-37).
    reserve = catalog.DATA_DIR / "reserve.csv"
    app.config["RESERVE_PATH"] = str(reserve) if reserve.exists() else None
    # Codeforces problems the reserve cannot hold, read only to fill in the custom-problem form.
    unmapped = catalog.DATA_DIR / "codeforces_unmapped.csv"
    app.config["UNMAPPED_PATH"] = str(unmapped) if unmapped.exists() else None
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    catalog.init_app(app)
    demo.init_app(app)
    app.register_blueprint(views.bp)
    return app
