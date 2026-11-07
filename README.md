# CodeCompass

A web app for tracking coding-interview practice by pattern. See [docs/requirements.md](docs/requirements.md).

## Setup

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```
flask --app codecompass run
```

Then open http://127.0.0.1:5000. To reach the app from a phone on the same trusted Wi-Fi network, add `--host 0.0.0.0` and open the laptop's IP address on port 5000. Data is saved to `instance/codecompass.sqlite`. Set the `CODECOMPASS_DATABASE` environment variable to use a different file, for example one per tester.

## Demo

The demo (R-25) uses its own database and a catalog of made-up problems, so it never touches your data. In PowerShell:

```
$env:CODECOMPASS_DEMO = "1"
flask --app codecompass demo
flask --app codecompass run
```

`flask --app codecompass demo` rebuilds 8 weeks of practice history ending today. Run it again to refresh the dates.

## Test

```
pytest
```

## Layout

- `codecompass/core/`: scoring, scheduling, and recommendation logic as plain functions, with no Flask imports
- `codecompass/state.py`: reads the database and runs the rules for the dashboard
- `codecompass/views.py`: routes
- `codecompass/db.py` and `codecompass/schema.sql`: SQLite connection and tables
- `codecompass/catalog.py` and `codecompass/data/`: the pattern list and catalog, loaded at each start
- `codecompass/demo.py`: the demo dataset
- `codecompass/templates/`: Jinja templates
- `codecompass/static/css/app.css`: the stylesheet, using system fonts so the app works offline
