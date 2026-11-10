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
| `link` | Text | Unique when present; optional for custom problems |
| `difficulty` | Text | `easy`, `medium`, `hard`, or `very hard` |
| `rating` | Integer | The rating from the site the problem came from; blank if it has none |
| `source` | Text | The public list, API, or site it came from. A catalog problem on several lists names the first one in the order in `docs/rules.md` |
| `is_custom` | Integer | 1 for a custom problem |
| `catalog_position` | Integer | Catalog order; blank for custom problems |

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

### `settings` (R-13, R-15, R-32)

| Column | Type | Notes |
| --- | --- | --- |
| `key` | Text | Primary key: `starting_difficulty`, `advanced_on`, `very_hard_on` |
| `value` | Text | |

### `hidden_sites` (R-36)

| Column | Type | Notes |
| --- | --- | --- |
| `site` | Text | `leetcode`, `codeforces`, or `cses` |
| `category` | Text | `core` or `advanced` |

The two columns together are the primary key. A row means that site is hidden for that kind of problem, so an empty table shows every site. A problem's site is found from its link, so it is not stored.

### `interviews` (R-15)

| Column | Type | Notes |
| --- | --- | --- |
| `id` | Integer | Primary key |
| `company` | Text | Required |
| `date` | Text | Required |
| `target_difficulty` | Text | Optional: `easy`, `medium`, `hard`, or `very hard` |

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

### `rating_history` (R-34)

| Column | Type | Notes |
| --- | --- | --- |
| `site` | Text | |
| `username` | Text | |
| `contest` | Text | |
| `date` | Text | |
| `rating` | Integer | The user's rating after the contest |

`site`, `username`, and `contest` together are the primary key. This table holds the user's ratings, which never affect scores, due dates, or recommendations.

## Catalog and pattern files

The catalog and pattern list are kept as reviewed CSV files, `codecompass/data/catalog.csv` and `codecompass/data/patterns.csv`. The app loads them at each start, adding or updating catalog problems by link and patterns by name. Loading leaves attempts and custom problems alone, and a problem removed from the file stays in the database if it has attempts.

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
