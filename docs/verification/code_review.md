# Code review and AI mistakes log

This page records the review of the changes the AI wrote on 2026-11-10 and 2026-11-11, for the plan item "review each change for date and time zone bugs, outgoing requests (R-03), CDN links (R-24), and one shared validator for the form and CSV; log any mistakes the AI made."

- **Date:** 2026-11-11
- **Changes reviewed:** every commit after `b364cc5`, from `9b088e4` (catalog sources) to `e2ba680` (code review fixes)
- **Method:** an automated code review of that range, which reported 10 findings, followed by the four checks below, made by searching the code and reading each match
- **Tests:** 334 passing after the fixes

## Checks

| Check | How | Result |
| --- | --- | --- |
| Dates and time zones | Searched for every clock read (`date.today`, `datetime.now`, `time.time`, `fromtimestamp`, SQL `'now'`) and every date in the JavaScript | Pass. `core/` never reads the clock; it imports only `date` and `timedelta` and takes "today" as an argument. The current date and time are read only in `views.py` (`today`, `now_seconds`, `local_date`) and in the `demo` command. Synced submission times become local dates in `views.local_date`; the last sync time is stored in UTC and shown in local time. The .ics export uses all-day dates, so it has no time zone. The rating chart reads and writes its dates in UTC on both sides, so it cannot shift a day. |
| Outgoing requests (R-03) | Searched for `urllib`, `urlopen`, `http.client`, `requests`, and `socket`, and for `fetch(` in the JavaScript | Pass after one fix. Only `codecompass/remote.py` makes requests, called only by the lookup (`/problems/new?lookup=1`) and by a sync (`POST /sync`). The JavaScript fetches only this app's own routes. Every URL in `remote.py` is in the source table in `docs/rules.md`. **Fixed:** urllib followed redirects to any host, so a redirect could reach a source not on the list; redirects are now followed only within the same host (`remote.SameHostRedirects`, with a test). |
| CDN links (R-24) | Searched templates and CSS for external `src`, `href` on `script`, `link`, `img`, and `iframe`, `url(`, and `@import`, and listed `codecompass/static` | Pass. Every script and stylesheet is served from `codecompass/static` (one stylesheet, five scripts), fonts are system fonts, and the only external URLs are links to problems and site profiles, which the user opens. |
| One shared validator (R-05, R-20) | Listed every write to `attempts` and `problems` and every caller of the validators | Pass after one fix. The logging form, attempt edits, CSV import, and sync confirmation all use `validate_attempt`, and custom problems from the form, CSV import, and sync all use `validate_problem`. The only other writes are the catalog load, the demo data, and Undo, which restores a row that was validated when it was saved. **Fixed in `e2ba680`:** CSV import did not apply the hint rule (R-27) that the form applies. |

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
| 19 | 2026-11-11 | Outgoing requests (R-03) | Redirects to another host were followed. | This review | Same-host redirects only (this review's commit). |

Most mistakes were caught by a test, a browser check, or the code review before the feature was used. Items 10 and 11 were design choices the author corrected, and item 15 shows a fix made in one place and not carried to similar code.
