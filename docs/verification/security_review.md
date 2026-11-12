# Security review of hosted mode (R-53)

R-53 asks for a security review before anyone other than the author signs in to the hosted site. This is that review.

- **Date:** 2026-11-12
- **Scope:** hosted mode as committed in `45f01af` (R-50 to R-56): sign-in and sessions (`auth.py`), the per-account split in PostgreSQL (`pg.py`, `schema_pg_shared.sql`, `schema_pg_user.sql`), backups between modes (`transfer.py`, `backup.py`), the stepped sync (`sync.py`, `remote.py`), limits (`limits.py`), the templates and scripts, and the Vercel and Neon setup (`api/index.py`, `vercel.json`, `docs/deploying.md`). Local mode was checked wherever it shares code with these.
- **Method:** the AI read the code for each area below, looking at what an outsider, a signed-in account, or a crafted file could reach. Each suspected problem was confirmed before it was counted: on the real libraries (`hmac.compare_digest`, a PostgreSQL 17 identity column, Werkzeug's redirect), or by following the code from input to page. The author chose which findings to fix. The content policy was then checked in Chrome on the dashboard, Progress, History, Settings, Log, and a pattern page, with no violations in the console.
- **Not covered:** the live deployment (Vercel's and Neon's own settings, GitHub's sign-in pages), which needs checking once deployed; load and denial of service beyond the limits below; and third-party library code.
- **Tests:** 475 passing in local mode (33 hosted-only skipped) and 498 in hosted mode (10 local-only skipped). `tests/test_security.py` covers each finding.

## Findings

| # | Severity | Finding | Fix |
| --- | --- | --- | --- |
| 1 | High | A restored backup kept problem links, solution links, and sync item links as written, including `javascript:` links. Restoring a file someone handed over, then clicking "Open problem", would run their script in the signed-in session, able to read or delete the account's data. Local mode had the same gap. Forms and CSV import already refused such links. | Only web links (http or https) become links on any page, whatever their source (the `web_link` filter); restoring into an account also drops other links. |
| 2 | Medium | Restoring a backup reused a custom problem's id when it was free. PostgreSQL's identity counter does not move past ids inserted by hand, so a crafted backup could take the ids it would hand out next, and every other account's new custom or synced problem would fail until the counter passed them. | An id is kept only if PostgreSQL has already handed it out (as for Undo), so it can never be handed out again. |
| 3 | Medium | The page to return to after signing in accepted `/\evil.example`, which browsers read as another site, so a link to `/signin?next=/\evil.example` sent people there right after signing in. The hint button's redirect had the same gap, behind a form token. | One check, `local_path`, refuses a backslash, a control character, or `//`, for both. |
| 4 | Low | A form token with non-ASCII characters made `hmac.compare_digest` raise an error, so the request failed with a server error instead of being refused. Nothing changed. | Tokens are compared as bytes. |

## Hardening added

| Area | Before | Now |
| --- | --- | --- |
| Content-Security-Policy | None | Only this site's scripts run; forms post only here or to GitHub; no framing, plugins, or base URL. The one script that sat in the page (applying the saved theme) is now a file. Styles in attributes are still allowed, since charts and score tiles use them. |
| Caching | Pages carried no cache rule | `Cache-Control: no-store` on every page except static files, so no browser or shared cache keeps an account's data. |
| Reading uploaded backups | Opened as a trusted database | SQLite's defensive mode and untrusted-schema setting, as SQLite advises for files from elsewhere; a file with triggers or views is refused, since CodeCompass's database has none and they could run their own SQL after a restore. |
| Database connection | `sslmode=require` encrypts without checking Neon's certificate | `docs/deploying.md` uses `sslmode=verify-full`; the app then checks the certificate against certifi's authorities. |
| Accounts | No way to see or remove accounts, so throwaway GitHub accounts could fill the 50-account cap | `flask --app codecompass accounts` lists them, and `accounts delete <username>` removes one, from the author's laptop. The site has no admin page. |

## Checks that passed

| Area | What was checked | Result |
| --- | --- | --- |
| SQL injection | Every query in the changed code | Pass. Values are always parameters, quoted by psycopg; table and schema names come from constants or the integer account id. |
| Sessions | `auth.py` | Pass. The browser holds a random token; the database keeps only its SHA-256 hash. Signing out deletes it, so a copied cookie stops working; sessions end after 30 days unused; signing in clears the old session, so one cannot be planted. Cookies are Secure, HttpOnly, and SameSite=Lax. |
| GitHub sign-in | Authlib's flow | Pass. Authlib checks the state value, so another site cannot finish a sign-in for someone; only the public profile is asked for; no password is stored anywhere (a test checks the columns). |
| Secrets | Configuration | Pass. Every secret comes from environment variables; hosted mode will not start without a fixed secret key; none is in the repository. |
| Keeping accounts apart (R-52) | `pg.py`, the schemas, every route taking an id | Pass. Each request's connection reaches only its account's schema; the `problems` view shows only shared and own custom problems; a trigger refuses changes to shared problems outside the catalog load; routes look problems up through the view and return 404 for another account's. Tests try every kind of id from a second account. |
| Forged form posts | Every POST route and script | Pass after finding 4. Every form carries the session's token and every script sends it; posts without it are refused. |
| Outgoing requests (R-03) | `remote.py`, `auth.py` | Pass. Requests go only to the documented hosts; redirects to another host are refused; GitHub is contacted only while signing in. |
| HTTPS and headers | `auth.py` | Pass. Plain HTTP redirects to HTTPS; HSTS, nosniff, DENY framing, and same-origin referrers are set. The original scheme and address come from Vercel's forwarded headers, which Vercel sets itself. |
| Limits | `limits.py` and the routes | Pass. Sign-ins per address, and uploads and sync starts per account, are limited; one sync per account at a time; requests to each site are spaced across all accounts. |
| Errors | Error responses | Pass. Hosted mode never runs in debug mode, so errors show a plain page without details. |
| Page output | Templates | Pass after finding 1. Jinja escapes everything; the two places that build HTML in Python escape their values; JSON in attributes is escaped by `tojson`. |

## Accepted risks

- **A very long first sync** (a username with tens of thousands of submissions) holds a site's turns for minutes, and other accounts' syncs wait. Acceptable at 50 accounts; the per-account sync start limit bounds it.
- **Usage limits.** Anyone signed in can make requests until Vercel's or Neon's free-plan limits are reached; there is no per-account request limit beyond those above. Vercel's own firewall can be turned on if that happens.
- **CSV export** writes titles as stored; a spreadsheet may treat a title starting with `=` as a formula. Titles come from the user or from the problem sites, not from other accounts.
- **Signing out** ends only that browser's session; there is no "sign out everywhere". Deleting the account ends them all.

These are the author's to revisit if the site grows past testing.
