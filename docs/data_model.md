# CodeCompass Data Model

The database tables and CSV columns. Dates are `YYYY-MM-DD` text.

## What is stored and what is calculated

Mastery scores, due dates, the current difficulty level, and the review streak are not stored. The app calculates them from the attempts each time, using the rules in `docs/rules.md`, so edits, deletions, and rule changes (R-07) cannot leave them out of date.

## Tables

### `patterns` (R-01, R-27)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | Integer | Primary key |
| `name` | Text | Unique |
| `category` | Text | `core` or `advanced` |
| `tier` | Text | `narrow`, `normal`, or `broad` |
| `family` | Text | The group the pattern belongs to on the dashboard's pattern map |
| `description` | Text | The beginner hint text |
| `list_position` | Integer | The order of `docs/patterns.md` |

### `problems` (R-01, R-02, R-35)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | Integer | Primary key |
| `title` | Text | Required |
| `link` | Text | Unique when present; optional for custom problems. Links to known sites are stored in one form (see below) |
| `difficulty` | Text | `easy`, `medium`, `hard`, or `very hard` |
| `rating` | Integer | The rating from the site the problem came from; blank if it has none |
| `source` | Text | The public list, API, or site it came from. A catalog problem on several lists names the first one in the order in `docs/rules.md` |
| `is_custom` | Integer | 1 for a custom problem |
| `catalog_position` | Integer | Catalog order; blank for custom and reserve problems |
| `reserve_position` | Integer | Reserve order, most solved first (R-37); blank for catalog and custom problems |

A problem with neither position and `is_custom` 0 was removed from the data files but kept for its attempts.

Links to these sites are stored in one form, so a problem can be found by its ID however the link was typed (R-38):

| Site | Stored link |
| --- | --- |
| LeetCode | `https://leetcode.com/problems/<slug>/` |
| Codeforces | `https://codeforces.com/problemset/problem/<contest>/<index>` |
| CSES | `https://cses.fi/problemset/task/<number>` |
| AtCoder | `https://atcoder.jp/contests/<contest>/tasks/<task>` |

Ratings use each site's own scale, so they are only comparable within one source. AtCoder values come from an unofficial estimate and can be negative. A rating is used only to set `difficulty`, by the rule in `docs/rules.md`. No other rule reads it.

### `problem_patterns` (R-01)

| Column | Type | Notes |
| --- | --- | --- |
| `problem_id` | Integer | References `problems` |
| `pattern_id` | Integer | References `patterns` |

The two columns together are the primary key.

### `attempts` (R-04, R-06, R-26, R-28)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | Integer | Primary key; also sets the logged order for attempts on the same date |
| `problem_id` | Integer | References `problems` |
| `date` | Text | Required, not in the future |
| `outcome` | Text | `solved_alone`, `solved_with_hints`, `solved_after_solution`, or `not_solved` |
| `time_seconds` | Integer | Optional, at least 1. The timer saves seconds, and a typed time is entered in minutes and converted |
| `notes` | Text | Optional |
| `entry_method` | Text | `manual`, `csv`, or `sync` |
| `review_of_problem_id` | Integer | The due problem, if this was a sibling attempt; otherwise blank |

### `settings` (R-13, R-15, R-32, R-41, R-43)

| Column | Type | Notes |
| --- | --- | --- |
| `key` | Text | Primary key: `starting_difficulty`, `advanced_on`, `very_hard_on`, `reviews_on`, `weekly_goal` |
| `value` | Text | |

### `hidden_sites` (R-36)

| Column | Type | Notes |
| --- | --- | --- |
| `site` | Text | `leetcode`, `codeforces`, `cses`, or `atcoder` |
| `category` | Text | `core` or `advanced` |

The two columns together are the primary key. A row means that site is hidden for that kind of problem, so an empty table shows every site. A problem's site is found from its link, so it is not stored.

### `interviews` (R-15, R-44)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | Integer | Primary key |
| `company` | Text | Required |
| `date` | Text | Required |
| `target_difficulty` | Text | Optional: `easy`, `medium`, `hard`, or `very hard` |
| `daily_target` | Integer | Problems a day in the interview's prep plan (R-44); empty means the default of 3 |

### `interview_patterns` (R-15)

| Column | Type | Notes |
| --- | --- | --- |
| `interview_id` | Integer | References `interviews` |
| `pattern_id` | Integer | References `patterns` |

The two columns together are the primary key. An interview with no rows here has no patterns of its own.

### `pattern_preferences` (R-32)

| Column | Type | Notes |
| --- | --- | --- |
| `pattern_id` | Integer | Primary key, so a pattern cannot be both |
| `preference` | Text | `target` or `mastered` |

### `sibling_suggestions` (R-28)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | Integer | Primary key |
| `due_problem_id` | Integer | References `problems` |
| `sibling_problem_id` | Integer | References `problems` |
| `status` | Text | `active` or `dismissed` |
| `date` | Text | The date it was suggested or dismissed |

### `not_now` (R-29)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | Integer | Primary key |
| `problem_id` | Integer | References `problems` |
| `date` | Text | Every use is kept |

### `deleted_items` (R-07, R-15)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | Integer | Primary key |
| `kind` | Text | `attempt` or `interview` |
| `payload` | Text | The deleted row as JSON; an interview's includes its pattern names |
| `date` | Text | The date it was deleted |

A deleted attempt or interview is kept here so Undo can put it back, under its old id when that id is still free. A row is removed when it is restored, and rows older than one day are removed at the next deletion.

### `hint_reveals` (R-27)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | Integer | Primary key |
| `problem_id` | Integer | References `problems` |
| `date` | Text | |
| `used` | Integer | 1 once an attempt has been logged after the reveal |

### `linked_accounts` (R-33)

| Column | Type | Notes |
| --- | --- | --- |
| `site` | Text | `codeforces`, `atcoder`, or `leetcode` |
| `username` | Text | |
| `last_synced` | Text | Blank before the first sync |

The two columns `site` and `username` together are the primary key.

### `sync_items` (R-33)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | Integer | Primary key |
| `site` | Text | |
| `username` | Text | |
| `problem_link` | Text | |
| `title` | Text | |
| `date` | Text | |
| `accepted` | Integer | 1 if any submission that day was accepted |
| `rating` | Integer | The site's problem rating, if any |
| `tags` | Text | The site's tags, if any |
| `status` | Text | `pending`, `confirmed`, or `dismissed` |

`site`, `problem_link`, and `date` together are unique. Rows stay after being dismissed, so dismissed items do not return.

### `sync_batches` (R-33)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | Integer | Primary key |
| `payload` | Text | JSON with the ids of the sync items the batch changed, the attempts and custom problems it added, and the hint reveals those attempts used |
| `date` | Text | The date of the batch |

Saving or dismissing several sync items at once keeps a row here so Undo can reverse it: the attempts are deleted, custom problems the batch added are deleted if nothing else uses them, the hint reveals are marked unused, and the items return to `pending`. A row is removed when it is undone, and rows older than one day are removed at the next batch.

### `rating_history` (R-34)

| Column | Type | Notes |
| --- | --- | --- |
| `site` | Text | |
| `username` | Text | |
| `contest` | Text | |
| `date` | Text | |
| `rating` | Integer | The user's rating after the contest |

`site`, `username`, and `contest` together are the primary key. This table holds the user's ratings, which never affect scores, due dates, or recommendations.

### `problem_notes` (R-45)

| Column | Type | Notes |
| --- | --- | --- |
| `problem_id` | Integer | Primary key; the problem, removed with it |
| `note` | Text | The user's note; an empty note is removed instead of stored |
| `updated` | Text | The date it was last saved |

### `problem_links` (R-45)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | Integer | Primary key |
| `problem_id` | Integer | The problem, removed with it |
| `url` | Text | An http or https link; CodeCompass never fetches it |
| `label` | Text | Optional name shown instead of the link |

## Deleting all data (R-39)

Deleting all data empties every table above that holds the user's data: `attempts`, `interviews`, `interview_patterns`, `settings`, `hidden_sites`, `pattern_preferences`, `sibling_suggestions`, `not_now`, `hint_reveals`, `linked_accounts`, `sync_items`, `sync_batches`, `rating_history`, `deleted_items`, `problem_notes`, and `problem_links`. It also removes custom problems and any problem kept only because an attempt used it. Patterns and the catalog and reserve problems stay, and settings fall back to their defaults.

Before deleting, the whole database is copied to a file beside it, named after the database with `-erased` added (for example `instance/codecompass.sqlite-erased`), and the `app_meta` table records the day of the deletion under the key `erased_on`. Undo copies the file back over the database, which also removes that key, and then deletes the file. Saving anything new, or a deletion older than one day, removes the file and the key, after which the deletion is final.

## Backup and restore (R-46)

A backup is the whole database as one SQLite file, so it holds every table above, including the catalog and reserve. Restoring first copies the current database aside, as deleting all data does (the `-erased` file and the `erased_on` key), then copies the backup over the database and runs the same setup as an app start, which adds any table, column, or setting a newer version has. Undo copies the earlier database back.

## Hosted mode (R-50 to R-56)

Local mode keeps all the tables above in one SQLite file for one user. Hosted mode keeps them in PostgreSQL (`codecompass/schema_pg_shared.sql` and `codecompass/schema_pg_user.sql`), with the same columns and meanings, split in two:

- **Shared, in the `public` schema:** `app_meta` (the catalog's fingerprint), `patterns`, `problems`, and `problem_patterns`, plus the tables below. `problems` gains an `owner` column: empty for the catalog and reserve, and the account's id for its custom problems. Shared problems and their patterns change only while the catalog loads; a database trigger refuses any other change. Links are unique among shared problems and within each account's custom problems, so two accounts can each add a custom problem with the same link.
- **Per account, in its own schema `u<account id>`:** every user table above, from `attempts` to `problem_links`, its own `app_meta` (the `erased_on` key), and a view named `problems` that shows the shared catalog and reserve with that account's own custom problems only. A connection for an account searches its schema first, so every query reaches only that account's tables (R-52). `rating_history` gains a `rowid` column that keeps the order ratings were stored in, as SQLite's built-in rowid does.

### `users` (R-51)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | Integer | Primary key; names the account's schema |
| `github_id` | Integer | The GitHub account's id; unique |
| `login` | Text | The GitHub username, updated at each sign-in |
| `name` | Text | The GitHub display name, if any |
| `created` | Text | The date the account was made |

No password is stored. New accounts stop at `MAX_ACCOUNTS` (`core/constants.py`).

### `sessions` (R-51)

| Column | Type | Notes |
| --- | --- | --- |
| `token_hash` | Text | Primary key; the SHA-256 hash of the token the browser holds in its signed session cookie |
| `user_id` | Integer | The account, removed with it |
| `created` | Real | When the session started (Unix seconds) |
| `last_used` | Real | When it was last used, written at most hourly; a session unused for 30 days ends |

Signing out deletes the row, so a copied cookie stops working.

### `site_clock` (R-54)

| Column | Type | Notes |
| --- | --- | --- |
| `host` | Text | Primary key; a site the sync asks, such as `codeforces.com` |
| `next_at` | Real | The earliest time (Unix seconds) any account may next send it a request |

### `rate_limits` (R-53)

| Column | Type | Notes |
| --- | --- | --- |
| `key` | Text | Primary key; what is counted, such as `signin:<address>` or `upload:<account>` |
| `window_start` | Real | When the current window began (Unix seconds) |
| `count` | Integer | Uses in this window |

### `sync_job` (R-54), per account

| Column | Type | Notes |
| --- | --- | --- |
| `id` | Integer | Always 1: an account has at most one sync |
| `data` | Text | JSON: the sites in order, each site's progress, the current site's saved request state (`remote.sync_state`), and the results |
| `lease` | Real | When the step running it ends, so two open pages never run it at once |

### `kept_copy` (R-39, R-46), per account

| Column | Type | Notes |
| --- | --- | --- |
| `id` | Integer | Always 1 |
| `data` | Bytes | The account's data as a backup file, kept for Undo after deleting all data or restoring a backup |

### Backups between modes (R-55)

A hosted account's backup is a SQLite file in local mode's format (`codecompass/transfer.py`): the patterns, the problems the account's records use, its custom problems, and every user table. Local mode restores it as any backup. Reading a backup into an account matches problems by link to the shared catalog and reserve, and adds the rest as the account's custom problems; patterns match by name. The undo records in `deleted_items` and `sync_batches` are kept only when every problem keeps its id, as in a backup from the same account.

## Catalog and pattern files

The catalog and pattern list are kept as reviewed CSV files, `codecompass/data/catalog.csv` and `codecompass/data/patterns.csv`. The unreviewed reserve (R-37) is `codecompass/data/reserve.csv`, in the same columns, built with `flask --app codecompass build-reserve` from a saved `problemset.problems` response. The app loads the files at each start, adding or updating problems by link and patterns by name, and skips the load when the files are unchanged since the last one. A reserve row whose link is in the catalog is ignored. Loading leaves attempts and custom problems alone, and a problem removed from the files stays in the database if it has attempts.

`patterns.csv` is copied from `docs/patterns.md`.

## CSV import and export (R-19, R-20)

Exports and imports use the same columns, in this order:

| Column | Required | Notes |
| --- | --- | --- |
| `date` | Yes | `YYYY-MM-DD` |
| `title` | Yes | Matched after `link`, ignoring case |
| `link` | No | Matched first |
| `difficulty` | For a new custom problem | `Easy`, `Medium`, `Hard`, or `Very hard` |
| `rating` | No | The site's problem rating |
| `patterns` | For a new custom problem | Separated by semicolons, for example `Tree Traversal; Greedy` |
| `outcome` | Yes | `Solved alone`, `Solved with hints`, `Solved after viewing the solution`, or `Not solved` |
| `time_minutes` | No | Minutes, and decimals are allowed, so testers can type `25`. Exports round to 4 decimals, which converts back to the same number of seconds |
| `notes` | No | |
| `review_of` | No | The link or title of the due problem, if this attempt was a sibling |

- `difficulty`, `rating`, and `patterns` are used only when a row creates a custom problem. A matched problem keeps its existing values.
- Rows are exported in logged order and imported in file order, so attempts on the same date keep their order.
- A `review_of` value that matches no problem makes the row invalid, so it is skipped and reported (R-20).
- A blank `review_of` means a normal attempt. Testers logging in a spreadsheet leave it blank, so a sibling they solved between sessions starts its own review schedule. This is a known limitation of spreadsheet logging, and sessions in the app are not affected.
