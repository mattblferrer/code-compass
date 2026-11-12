# Proposal: a hosted mode alongside local use

**Status: adopted on 2026-11-12.** Decisions D1 and D4 took the recommended option. D2 changed to a PostgreSQL schema per account (its own set of user tables, with the catalog shared), which keeps nearly every query unchanged, with GitHub as the only sign-in provider for now. D3 changed to open sign-up with a cap, and D5 to Vercel's and Neon's free plans, for a live version testers can use. Authlib and psycopg are approved. R-50 to R-56 and the changes below are now in `docs/requirements.md` and `CLAUDE.md`, which are the source of truth; this file records the reasoning.

## Summary

The same code runs in one of two modes, chosen by a setting when the app starts:

- **Local mode** (the default) is CodeCompass as it is today: one user, no sign-in, one SQLite file, and it works offline (R-24). Its behavior does not change.
- **Hosted mode** runs on a server at a web address. People sign in, and each person sees only their own data. The catalog, reserve, and patterns are shared. Hosted mode needs a connection to work.

Data moves between the two by backup and import (R-55), so one person can use a local copy offline and an account online. The two copies are separate, and nothing syncs them automatically.

## Decisions for the author

Each of these changes the requirements below. The author chose the first option (in bold) for each on 2026-11-12.

| # | Decision | Options | Why the recommendation |
| --- | --- | --- | --- |
| D1 | How people sign in | **(a) GitHub or Google sign-in (OAuth)**; (b) email and password; (c) a link sent by email | With (a), CodeCompass stores no passwords, so no password resets, no password database to protect, and no email service. Most candidates already have a GitHub account. |
| D2 | How each user's data is stored | **(a) one PostgreSQL database with a user column on every user table**; (b) one SQLite file per user | (a) handles many people writing at once and is standard on hosts. (b) changes less code but makes backups, migrations, and shared rate limits harder as users grow. |
| D3 | Who can sign up | **(a) invite list (accounts the author approves)**; (b) open sign-up | (a) keeps the first version small and lets the author watch sync load and costs before opening up. |
| D4 | LeetCode sync in hosted mode | **(a) off in hosted mode, kept in local mode**; (b) on, with the same notice | LeetCode's terms forbid scraping. One person's requests from their own laptop are a different risk from a public server making them for everyone, and the server's address could be blocked for all users. |
| D5 | Where it runs | **(a) a Python host with managed Postgres and a worker process (for example Fly.io or Render paid)**; (b) a rented virtual server run by hand | (a) handles HTTPS, restarts, and database backups. Roughly $10 to $30 a month at small scale. |

Hosted mode needs new dependencies, each to be approved under CLAUDE.md's "Ask before adding a dependency": a production server (gunicorn), a PostgreSQL driver (psycopg) for D2(a), an OAuth library (Authlib) for D1(a), and possibly a task queue for R-54. Local mode would still need only Flask.

## Changes to sections 1 to 4

| Section | Now | Proposed |
| --- | --- | --- |
| 1. Overview | "CodeCompass covers one user at a time" | "CodeCompass covers one user per local copy, or one user per account in hosted mode" |
| 2. Software | "Prototype with no security hardening or scaling." | Local mode unchanged. Hosted mode adds sign-in, protection against forged form posts, HTTPS, and a security review (R-53). |
| 2. Coverage | "One local profile per database with no login" | Local mode: unchanged. Hosted mode: one account per person, with no shared or team features. |
| 2. Storage and hosting | "No hosted version is planned." | A hosted mode runs on a paid host (D5) with a managed database and daily backups. Local mode is unchanged and remains the default. |
| 2. Data access | Sync runs from the user's laptop. | In hosted mode, sync requests come from the server for every user, so each site's limit is shared across all users (R-54). LeetCode per D4. |
| 2. Time | "R-01 to R-49 are in scope" | Hosted mode is a separate phase of several weeks after R-01 to R-49 are verified. |
| 4. Excluded | "user accounts with security hardening" | Removed from the list. Still excluded: logging in to any practice site or storing its passwords or cookies, social or group features, push or email notifications. |
| 4. Working conditions | "no internet needed apart from opening problem links and the optional sync" | True of local mode. Hosted mode needs a connection. |

## Changes to existing requirements

| ID | Change |
| --- | --- |
| R-03 | Add: in hosted mode, the server also contacts the chosen sign-in provider (D1), and only during sign-in. The rule against asking for other sites' passwords or cookies is unchanged. |
| R-21 | Measured on the chosen host as well as the laptop, with 500 attempts in one account and at least 10 other accounts present. |
| R-22 | In hosted mode, data also survives a redeploy, and the host keeps daily database backups for at least 7 days. |
| R-23 | The same-Wi-Fi condition applies to local mode only. In hosted mode the phone reaches the site over the internet. |
| R-24 | Applies to local mode only. |
| R-33 | In hosted mode, syncs wait in a shared queue (R-54), the progress shows the place in the queue, and LeetCode follows D4. |
| R-39 | In hosted mode, deletes only the signed-in user's data. The shared catalog stays. |
| R-46 | In hosted mode, a backup holds only the signed-in user's data, and a restore replaces only that user's data. See R-55 for moving data between modes. |

## New requirements

| ID | Requirement | Why it is needed | What counts as passing | How you will check |
| --- | --- | --- | --- | --- |
| R-50 | [Modes] The system must run in local mode or hosted mode, chosen by a setting when the app starts, with local mode the default. Local mode behaves exactly as R-01 to R-49 describe. Scoring, scheduling, and recommendation rules are the same in both modes. | Users who practice offline keep everything they have now, and the rules stay one set of code. | The full test suite passes in local mode with no change to its tests, and the rule tests (R-09 to R-16, R-28 to R-32) give identical results in hosted mode for one account. | The test suite run in both modes. |
| R-51 | [Accounts] In hosted mode, a person must sign in (D1) before seeing any page except the sign-in page and a privacy notice. The system stores no passwords. The user can sign out, and a session ends after 30 days without use (provisional). | Data is personal practice history and must not be open to anyone with the address. | Every page except sign-in and the privacy notice redirects to sign-in when signed out. After signing out, the previous session cannot open any page. | Integration tests on every route. |
| R-52 | [Accounts] In hosted mode, each user must see and change only their own data: attempts, interviews, custom problems, notes and links, settings and goals, linked usernames, sync items and batches, and rating history. The catalog, reserve, and patterns are shared and read-only. | One user reading or changing another's history would break trust and privacy. | With two accounts holding reference histories, every page and every form post made as one user shows and changes only that user's data, including by guessing another user's attempt, interview, problem, or batch IDs. | Integration tests over every route with two accounts. |
| R-53 | [Security] In hosted mode, the site must be served only over HTTPS, every form must reject posts from other sites, session cookies must be secure and unreadable by scripts, and sign-in, uploads, and sync starts must be rate limited (values provisional). A security review must be done before anyone other than the author signs in. | A public site is reachable by anyone, so the trusted-network assumption in section 2 no longer holds. | A form posted without a valid token is refused. Plain HTTP redirects to HTTPS. Repeated sign-in attempts or uploads beyond the limit are refused with a message. The review's findings are fixed or accepted by the author. | Integration tests, and a written security review in `docs/verification/`. |
| R-54 | [Sync] In hosted mode, syncs must run in a background worker, one request at a time per site across all users, within each source's published limits. A user's sync waits in a queue, and the sync page shows its place. A user can have at most one sync waiting or running. | Sites limit requests by address, and all users share the server's address, so per-user limits would break the sites' rules. | With recorded responses and three users starting syncs at once, requests to each site never come closer together than its limit, each user's results match a sync run alone, and a second start by the same user is refused while one is waiting. | Integration tests with recorded responses and a fake clock. |
| R-55 | [Data exchange] The user must be able to move all their data from local mode to a hosted account and back: a backup from local mode (R-46) can be imported into an account, and a backup from an account can be restored in local mode. An import replaces the account's data after confirmation and can be undone as R-46 describes. | A user who practices both offline and online needs one way to carry their history between the two copies. | A local reference history imported into an empty account gives identical attempts, scores, and due dates, and exporting it back and restoring it locally gives the original data. | Round-trip integration test. |
| R-56 | [Accounts] In hosted mode, the user must be able to delete their account, which removes all their data and their sign-in link after confirmation. Deleted accounts are removed from the host's backups within 30 days (provisional). A privacy notice must say what is stored, why, and how to delete it. | Holding other people's data brings the duty to let them remove it. | After deleting an account, no row belongs to it, and signing in again starts a new empty account. | Integration test, and a check of the privacy notice. |

## Changes to CLAUDE.md

These would be the author's edits if the proposal is adopted:

- "A single-user web app" becomes "A web app for one user per local copy or per account".
- "Never add logins, stored passwords or cookies" becomes "Never sign in to practice sites or store their passwords or cookies. Hosted-mode sign-in uses only the provider chosen in R-51."
- "The current date is resolved only in the route layer, using the user's local time zone" stays, with the time zone taken from each user's settings in hosted mode.
- "Offline first (R-24)" applies to local mode. Hosted mode still serves every asset from `codecompass/static/`.
- New: "Every query on a user table filters by the signed-in user. Tests check every route with two accounts (R-52)."

## What changes in the code

- **Unchanged:** `core/` (rules, scoring, filters, plans), templates apart from the header's sign-out link, and the scripts in `static/js/`.
- **Changed:** `db.py` and `schema.sql` (a `users` table, and a user column on `attempts`, `settings`, `interviews`, `interview_patterns`, `hidden_sites`, `pattern_preferences`, `sibling_suggestions`, `not_now`, `hint_reveals`, `linked_accounts`, `sync_items`, `sync_batches`, `rating_history`, `deleted_items`, `problem_notes`, `problem_links`, and custom rows of `problems`), `queries.py` and `state.py` (every query takes the user), `views.py` (sign-in check on every route), `sync.py` (a queue in place of threads keyed by database), `erase.py` and `backup.py` (per user, not whole-file copies).
- **New:** a sign-in module, a worker for R-54, and deployment settings.

## Suggested order

1. The author settles D1 to D5 and adopts or changes R-50 to R-56.
2. Add the user column and sign-in behind R-50's setting, with local mode passing every current test.
3. R-52's two-account tests over every route.
4. PostgreSQL and a hosted test deployment, invite only.
5. The sync queue (R-54).
6. Import and export between modes (R-55), account deletion and the privacy notice (R-56).
7. Security review (R-53), then invite testers.
