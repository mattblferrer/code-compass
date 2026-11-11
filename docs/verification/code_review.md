# Code review and AI mistakes log

This page records the reviews of the changes the AI wrote, for the plan item "review each change for date and time zone bugs, outgoing requests (R-03), CDN links (R-24), and one shared validator for the form and CSV; log any mistakes the AI made." Each review covers the commits since the one before, and the AI mistakes log at the end runs across all of them.

## First review

- **Date:** 2026-11-11
- **Changes reviewed:** every commit after `b364cc5`, from `9b088e4` (catalog sources) to `e2ba680` (code review fixes)
- **Method:** an automated code review of that range, which reported 10 findings, followed by the four checks below, made by searching the code and reading each match
- **Tests:** 334 passing after the fixes

### Checks

| Check | How | Result |
| --- | --- | --- |
| Dates and time zones | Searched for every clock read (`date.today`, `datetime.now`, `time.time`, `fromtimestamp`, SQL `'now'`) and every date in the JavaScript | Pass. `core/` never reads the clock; it imports only `date` and `timedelta` and takes "today" as an argument. The current date and time are read only in `views.py` (`today`, `now_seconds`, `local_date`) and in the `demo` command. Synced submission times become local dates in `views.local_date`; the last sync time is stored in UTC and shown in local time. The .ics export uses all-day dates, so it has no time zone. The rating chart reads and writes its dates in UTC on both sides, so it cannot shift a day. |
| Outgoing requests (R-03) | Searched for `urllib`, `urlopen`, `http.client`, `requests`, and `socket`, and for `fetch(` in the JavaScript | Pass after one fix. Only `codecompass/remote.py` makes requests, called only by the lookup (`/problems/new?lookup=1`) and by a sync (`POST /sync`). The JavaScript fetches only this app's own routes. Every URL in `remote.py` is in the source table in `docs/rules.md`. **Fixed:** urllib followed redirects to any host, so a redirect could reach a source not on the list; redirects are now followed only within the same host (`remote.SameHostRedirects`, with a test). |
| CDN links (R-24) | Searched templates and CSS for external `src`, `href` on `script`, `link`, `img`, and `iframe`, `url(`, and `@import`, and listed `codecompass/static` | Pass. Every script and stylesheet is served from `codecompass/static` (one stylesheet, five scripts), fonts are system fonts, and the only external URLs are links to problems and site profiles, which the user opens. |
| One shared validator (R-05, R-20) | Listed every write to `attempts` and `problems` and every caller of the validators | Pass after one fix. The logging form, attempt edits, CSV import, and sync confirmation all use `validate_attempt`, and custom problems from the form, CSV import, and sync all use `validate_problem`. The only other writes are the catalog load, the demo data, and Undo, which restores a row that was validated when it was saved. **Fixed in `e2ba680`:** CSV import did not apply the hint rule (R-27) that the form applies. |

## Second review

- **Date:** 2026-11-11
- **Changes reviewed:** the 23 commits after `37d2166`, from `badcb49` (measured checks) to `8ee674e` (filters folded on phones): 66 files and about 6,200 changed lines. They added the redesign and branding, sync of the whole history with progress, batch actions and auto-classify, the 180-day review rule, delete all data (R-39), the History calendar (R-40), the reviews setting (R-41), filters, sorting, and settings autosave.
- **Method:** an automated code review of that range, which reported 10 findings; the AI checked each against the code before reporting it, and the author chose how to handle each. The four checks below were then repeated by searching the code and reading each match.
- **Tests:** 411 passing after the fixes, in `14fd0d6` (bugs and R-41) and `b8df954` (speed and structure)

### Findings

| # | Finding | Decision | Fix |
| --- | --- | --- | --- |
| 1 | The log form's in-browser checks did not match `validate_attempt`: they blocked an empty date, which the server takes as today, and minutes such as "5." that the server reads, against the one-validator rule (R-05). | Fix | The checks follow the server's rules exactly (`14fd0d6`). |
| 2 | Adding `reviews_on` to an older settings table took three separate steps, so an interruption could lose saved settings or stop the app starting. | Fix | One transaction, and a half-done rebuild is finished on the next start (`14fd0d6`). |
| 3 | A background sync that hit an unexpected error dropped the results of sites that had finished, and a new sync dropped a finished sync's unseen results. | Fix | Both are kept and shown (`14fd0d6`). |
| 4 | With the page cap removed, Codeforces paging had no guard, so an API that ignored the page offset would loop forever. | Fix | A page with nothing new stops the sync with an error (`14fd0d6`). |
| 5 | The sync page ran several queries per waiting item, about 10,000 after a long first sync, and the dashboard loaded every item to count them. | Fix | One query for the list, two for hints and patterns, one count: 147 ms to 49 ms and 138 ms to 70 ms on 1,600 items (`b8df954`). |
| 6 | With a sibling suggestion active, a batch rebuilt the whole review picture for every item. | Fix | Read once, and again only when a save changes what is due: 300 items, 1,371 ms to 865 ms (`b8df954`). |
| 7 | History read every attempt three times per visit. | Fix | One read (`b8df954`). |
| 8 | Batch rules and the interview countdown lived in `views.py`, against "logic lives in `core/`". | Fix | Plain functions with tests in `core/sync.py` and `core/dates.py` (`b8df954`). |
| 9 | With reviews off, History still marked reviews and offered "Reviews only", against R-41. | Author chose to hide them | Hidden while reviews are off (`14fd0d6`). |
| 10 | The Undo cutoff was written out in five places, and month names in two. | Fix | `undo_cutoff()` and one list (`b8df954`). |

### Checks

| Check | How | Result |
| --- | --- | --- |
| Dates and time zones | Searched again for every clock read in Python and JavaScript, and for every date the new scripts handle | Pass. `core/` still takes "today" as an argument, including the new `progress`, `ordering`, `filters`, and date wording. The clock is read only in `views.py`, the `demo` command, and the timer. The background sync takes "now" and the local-date function from the request that starts it. The calendar card, the chart cards, and the rating chart build dates in UTC on both sides; the sync progress shows months in local time, which is display only. |
| Outgoing requests (R-03) | Searched again for `urllib`, `urlopen`, `http.client`, `requests`, and `socket`, and for `fetch(` in the JavaScript | Pass. `remote.py` is still the only module that contacts another site; other matches only parse links. Every `fetch` in the new scripts (settings autosave, sync progress, problem search, log context) calls this app's own routes. |
| CDN links (R-24) | Searched templates and CSS again for external `src`, `href`, `url(`, and `@import`, and listed `codecompass/static` | Pass. The new scripts and `favicon.svg` are served from `codecompass/static`, the header's contour lines are an inline SVG in the stylesheet, and fonts are still system fonts (Bahnschrift, or DIN Alternate on Apple). |
| One shared validator (R-05, R-20) | Listed every write to `attempts` and `problems` again, and every caller of the validators | Pass after finding 1. Single confirms, batch saves, and auto-classify all go through `confirm_sync_item`, which uses `validate_attempt` and `validate_problem`; settings autosave uses `validate_settings`, as the Save button does. The other writes are still the catalog load, the demo data, and Undo, which only removes a batch's rows or puts back what was there. |

## AI mistakes

Mistakes in work the AI produced, in the order they were found. "Found by" says whether a test, the AI's own check, the author, or the code review caught it.

| # | Date | Area | Mistake | Found by | Fix |
| --- | --- | --- | --- | --- | --- |
| 1 | 2026-11-10 | Catalog (R-01) | Titles were taken from the wrong field, giving "Fruits into Basket" for "Fruit Into Baskets" and 6 casing errors. | R-01 full check | Titles come from the source list (`a51334a`). |
| 2 | 2026-11-10 | Reserve (R-37) | Tags drawn automatically from AtCoder editorials picked up noisy keywords, such as game words and "construct". | AI's sample check | Keyword list corrected in the drafting script, which is not in the repo, before the reserve was committed (`71baf31`). |
| 3 | 2026-11-10 | Reserve (R-37) | A half-applied edit left code evidence as a string, so it was read one character at a time. | AI's sample check | Fixed in the drafting script before the corrections were committed (`357eb8a`). |
| 4 | 2026-11-10 | Undo (R-07) | The Undo button in the message did nothing: messages had `pointer-events: none`, which also broke the existing "not now" Undo. The AI first added a second toast instead of finding the cause. | Browser check | `.flash { pointer-events: auto }`, duplicate toast removed (`7279ae4`). |
| 5 | 2026-11-10 | CSV (R-19) | An export and re-import lost 4 rows whose `review_of` named a problem created further down the file. | Round-trip test | Import collects new problems first (`9b9fe3d`). |
| 6 | 2026-11-10 | CSV (R-20) | Import ignored the `rating` column for new custom problems. | AI's check | Fixed (`9b9fe3d`). |
| 7 | 2026-11-10 | Editing | Python edit scripts wrote a literal newline into `lineterminator="\n"` and a byte-order mark into `views.py`. | Tests | Rewritten with the Edit tool before commit (`9b9fe3d`). |
| 8 | 2026-11-10 | Lookup (R-35) | An explicit `selected` on the default site option broke two picker tests. | Tests | Removed; the tests were not edited (`367145f`). |
| 9 | 2026-11-11 | Sync (R-33) | The AI wrote a recorded "no such user" response for LeetCode before checking what LeetCode returns. A real check showed LeetCode and AtCoder return empty data for an unknown user. | AI's check | Invented response removed; the docs say unknown users cannot be detected there (`b6a3002`). |
| 10 | 2026-11-11 | Sync (R-33) | Failed days before a later solve were listed as separate items to confirm. | Author | Folded into the solve; R-33 updated (`b6a3002`). |
| 11 | 2026-11-11 | Ratings (R-34) | The rating chart spaced contests evenly, which misstates time. | Author | Time scale with zoom (`b6a3002`). |
| 12 | 2026-11-11 | Picker (R-38) | A leftover "Other" site made logging a problem picked by title fail. | Code review | `e2ba680` |
| 13 | 2026-11-11 | CSV (R-20) | A row whose link matched nothing fell back to a title match, so it could land on another site's problem with the same title. | Code review | `e2ba680` |
| 14 | 2026-11-11 | CSV (R-20, R-27) | Import skipped the hint rule, against the rule that the form and CSV share validation. | Code review | `e2ba680` |
| 15 | 2026-11-11 | Sync (R-33) | AtCoder tasks shared by two contests got a second link and would become duplicate custom problems. The same bug had already been fixed for the reserve but was repeated in sync. | Code review | One link rule for all AtCoder links (`e2ba680`). |
| 16 | 2026-11-10 | Undo (R-07) | Restore did not check the 1-day window, and failed with an error page if the problem had been removed. | Code review | `e2ba680` |
| 17 | 2026-11-10 | Recommendations (R-32) | Target slots could show a very hard problem with the setting off. This followed the documented rule at the time; the author changed the rule. | Code review | Rule and docs changed (`e2ba680`). |
| 18 | 2026-11-10 to 11 | Performance | After the reserve was added, saving an attempt and CSV import and export loaded all 13,000+ problems. | Code review | Load only what is needed (`e2ba680`). |
| 19 | 2026-11-11 | Outgoing requests (R-03) | Redirects to another host were followed. | First review | Same-host redirects only (`37d2166`). |
| 20 | 2026-11-11 | Design (R-33, R-34) | The sync popover overflowed its card, and the chart's drag code overwrote its own animation handle and failed when pointer capture was refused. | Browser check | Fixed before commit (`209cc25`). |
| 21 | 2026-11-11 | Branding | New class names `.mark` and `.days` were already in use, which shrank the logo and broke the countdown layout. | Browser check | Renamed before commit (`6b61179`). |
| 22 | 2026-11-11 | Layout | Several pages overflowed a phone's width: the calendar's hidden screen-reader text, the rating chart's caption, and a settings fieldset. | Browser check | Fixed before commit (`be4fd4a`, `f209a7d`). |
| 23 | 2026-11-11 | Sync progress (R-33) | The new progress list picked up the linked-accounts list's layout, putting site rows side by side. | Browser check | Fixed before commit (`9cb9752`). |
| 24 | 2026-11-11 | Logging (R-05) | The log form's in-browser checks blocked saves the server accepts. | Second review | `14fd0d6` |
| 25 | 2026-11-11 | Settings (R-41) | The settings table rebuild was not one transaction. | Second review | `14fd0d6` |
| 26 | 2026-11-11 | Sync (R-33) | A crashed background sync dropped finished sites' results, and removing the page cap left Codeforces paging without a guard. | Second review | `14fd0d6` |
| 27 | 2026-11-11 | Performance | The sync page, dashboard, batches, and History did far more database work than needed after a long first sync. | Second review | `b8df954` |
| 28 | 2026-11-11 | Code rules | Batch rules and the countdown were put in `views.py`, and the Undo cutoff was copied five times. | Second review | `b8df954` |
| 29 | 2026-11-11 | Reviews (R-41) | History still showed reviews while they were turned off. | Second review | `14fd0d6` |
| 30 | 2026-11-11 | Sync (R-33) | The first two versions of the paging guard compared times, then submission IDs, and stopped good syncs, since both can arrive slightly out of order. | Tests | The guard stops only when a page has nothing new (`14fd0d6`). |
| 31 | 2026-11-11 | Editing | An edit script named a set `seen`, hiding the progress counter of the same name (38 tests failed), and another wrote a literal newline inside a string in `db.py`. | Tests, AI's check | Fixed before commit (`14fd0d6`). |

Most mistakes were caught by a test, a browser check, or a code review before the feature was used. Items 10 and 11 were design choices the author corrected, and item 15 shows a fix made in one place and not carried to similar code. In the second review, items 26 and 28 repeat that pattern: limits and rules that existed in one place (AtCoder's paging guard, `core/` for rules) were not carried to new code, and items 20 to 23 show that most layout mistakes were caught only by looking at the page.
