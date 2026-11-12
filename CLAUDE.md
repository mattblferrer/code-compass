# CodeCompass

A single-user web app for tracking coding-interview practice by pattern. `docs/requirements.md` is the source of truth for behavior; cite requirement IDs (R-01 to R-49) when working on a feature.

## Commands

Activate the virtual environment first with `.venv\Scripts\activate`.

- Run: `flask --app codecompass run`
- Test: `pytest`

## Stack

Python, Flask, server-rendered Jinja templates, SQLite through the standard `sqlite3` module, a hand-written stylesheet (`codecompass/static/css/app.css`) using system fonts, and small amounts of vanilla JavaScript, tested with pytest. Do not add a front-end or CSS framework, build step, or ORM. Ask before adding a dependency.

## Code rules

- **Logic lives in `codecompass/core/`.** Scoring, scheduling, recommendations, streaks, and validation are plain functions on plain data, with no Flask imports and no database access. Routes in `views.py` stay thin.
- **One validator per record type.** The logging form and CSV import share the same attempt validation (R-05, R-20).
- **Dates are `YYYY-MM-DD` strings** in storage and in `core/`. Functions take "today" as an argument rather than reading the clock, so tests can use fixed dates. The current date is resolved only in the route layer, using the user's local time zone.
- **Offline first (R-24).** Serve every asset from `codecompass/static/`, with no CDN links. Vendor any new library.
- **No outgoing requests** except the optional sync (R-03, R-33, R-34), which runs only when the user starts it, by public username, for Codeforces, AtCoder, and LeetCode, and the problem lookup by ID or link (R-35), which runs only when the user starts it, for Codeforces and AtCoder. Keep all of that code in one module. Never add logins, stored passwords or cookies, or bot evasion.
- **Time taken and the user's contest ratings never affect** scores, review dates, or recommendations (R-26, R-34). A problem's rating from its source site is used only to set its difficulty level (`docs/rules.md`), which the rules then use.
- `schema.sql` runs on every app start, so its statements must be safe to rerun.

## Testing rules

- **The author provides test data** for scoring, scheduling, recommendation, and streak tests. If data for a test is missing, ask for it.
- **Algorithms and weights will change during development.** Keep tunable values (weights, intervals, thresholds) as named constants in one place in `core/`, so they are easy to adjust. When the author changes a rule, update the affected tests to match and list what changed.
- If a test fails without an intended rule change, report the failure instead of editing the test to pass.
- Tests never call real sites. Sync tests use recorded responses.

## Working agreements

- Do not edit anything in `docs/` without being asked. If the code and the PRD disagree, or a rule is undefined, ask rather than deciding silently. The rules for scoring, intervals, and recommendations are the author's decisions.
- Commit only when asked, directly on `main`. Do not push unless asked.
