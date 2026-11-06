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

## Test

```
pytest
```

## Layout

- `codecompass/core/`: scoring, scheduling, and recommendation logic as plain functions, with no Flask imports
- `codecompass/views.py`: routes
- `codecompass/db.py` and `codecompass/schema.sql`: SQLite connection and tables
- `codecompass/templates/`: Jinja templates
- `codecompass/static/css/pico.min.css`: local copy of Pico.css v2.1.1, so the app works offline
