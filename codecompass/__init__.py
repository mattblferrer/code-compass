import os
from pathlib import Path

from flask import Flask

from . import catalog, db, views


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    app.config["DATABASE"] = os.environ.get(
        "CODECOMPASS_DATABASE",
        str(Path(app.instance_path) / "codecompass.sqlite"),
    )
    app.config["PATTERNS_PATH"] = str(catalog.DATA_DIR / "patterns.csv")
    app.config["CATALOG_PATH"] = str(catalog.DATA_DIR / "catalog.csv")
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    catalog.init_app(app)
    app.register_blueprint(views.bp)
    return app
