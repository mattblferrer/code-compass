# CodeCompass

A web app for tracking coding-interview practice by pattern, for one user per local copy or, in hosted mode (R-50), one user per account. `docs/requirements.md` is the source of truth for behavior; cite requirement IDs (R-01 to R-56) when working on a feature.

## Commands

Activate the virtual environment first with `.venv\Scripts\activate`.

- Run: `flask --app codecompass run`
- Test: `pytest`

## Stack

Python, Flask, server-rendered Jinja templates, SQLite through the standard `sqlite3` module, a hand-written stylesheet (`codecompass/static/css/app.css`) using system fonts, and small amounts of vanilla JavaScript, tested with pytest. Do not add a front-end or CSS framework, build step, or ORM. Ask before adding a dependency. Hosted mode's dependencies (Authlib, and later PostgreSQL's driver and a production server) are installed only for hosted mode; local mode needs only Flask.

## Code rules

- **Logic lives in `codecompass/core/`.** Scoring, scheduling, recommendations, streaks, and validation are plain functions on plain data, with no Flask imports and no database access. Routes in `views.py` stay thin.
- **One validator per record type.** The logging form and CSV import share the same attempt validation (R-05, R-20).
- **Dates are `YYYY-MM-DD` strings** in storage and in `core/`. Functions take "today" as an argument rather than reading the clock, so tests can use fixed dates. The current date is resolved only in the route layer, using the user's local time zone (in hosted mode, the signed-in user's).
- **Offline first (R-24).** Local mode works with no internet. In both modes, serve every asset from `codecompass/static/`, with no CDN links. Vendor any new library.
- **No outgoing requests** except the optional sync (R-03, R-33, R-34), which runs only when the user starts it, by public username, for Codeforces, AtCoder, and LeetCode, and the problem lookup by ID or link (R-35), which runs only when the user starts it, for Codeforces and AtCoder. Keep all of that code in one module. In hosted mode, the server also contacts GitHub, only to sign the user in (R-51), from its own module. Never sign in to practice sites or store their passwords or cookies, and never add bot evasion. Hosted mode stores no passwords of its own.
- **Time taken and the user's contest ratings never affect** scores, review dates, or recommendations (R-26, R-34). A problem's rating from its source site is used only to set its difficulty level (`docs/rules.md`), which the rules then use.
- **Every user's data is their own (R-52).** Local mode keeps one user per SQLite file. Hosted mode gives each account its own PostgreSQL schema holding the user tables, with the catalog, reserve, and patterns shared; custom problems are shared rows marked with their owner, so every query on `problems` must filter by owner. Tests check routes with two accounts.
- `schema.sql` runs on every app start, so its statements must be safe to rerun.

## Testing rules

- **The author provides test data** for scoring, scheduling, recommendation, and streak tests. If data for a test is missing, ask for it.
- **Algorithms and weights will change during development.** Keep tunable values (weights, intervals, thresholds) as named constants in one place in `core/`, so they are easy to adjust. When the author changes a rule, update the affected tests to match and list what changed.
- If a test fails without an intended rule change, report the failure instead of editing the test to pass.
- Tests never call real sites. Sync tests use recorded responses.

## Working agreements

- Do not edit anything in `docs/` without being asked. If the code and the PRD disagree, or a rule is undefined, ask rather than deciding silently. The rules for scoring, intervals, and recommendations are the author's decisions.
- Commit only when asked, directly on `main`. Do not push unless asked.
