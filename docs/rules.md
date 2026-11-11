# CodeCompass Rules

The documented rules that `docs/requirements.md` refers to. All values are provisional and may be tuned during development and after testing with users.

## Mastery score (R-09, R-10)

Each pattern has its own score from 0 to 100. Start at 0 and go through the pattern's attempts from oldest to newest, then fade the result to today.

For each attempt:

1. **Fade.** If there was an earlier attempt, multiply the score by the fade for the days since that attempt.
2. **Find the stretch.** Stretch is the number of levels the problem's difficulty is above the expected difficulty for the faded score, and never less than 0.
3. **Find the target.** Target = 100 × the outcome value.
4. **Move toward the target.** Score = score + rate × (target − score), with the rate chosen as follows:
   - If the target is at or above the score, the rate is the pattern's tier rate, plus 10 points for each level of stretch, up to a maximum of 50%.
   - If the target is below the score and the stretch is 0, the rate is 20%.
   - If the target is below the score and the stretch is above 0, the rate is 10%.

After the last attempt, multiply the score by the fade for the days from that attempt to today, and round to two decimals.

Fade = 0.5 ^ (days / 60)

### Values

| Name | Value | Note |
| --- | --- | --- |
| Solved alone | 1.0 | Outcome value |
| Solved with hints | 0.5 | Outcome value |
| Solved after viewing the solution | 0.2 | Outcome value |
| Not solved | 0 | Outcome value |
| Rate up, narrow tier | 40% | Tiers are listed in `docs/patterns.md` |
| Rate up, normal tier | 30% | |
| Rate up, broad tier | 20% | |
| Stretch bonus | 10 points per level | Added to the rate up |
| Maximum rate up | 50% | Applies after the stretch bonus |
| Rate down | 20% | Same for every tier |
| Rate down on a stretch problem | 10% | Same for every tier |
| Fade half-life | 60 days | Placeholder with no source yet |
| Minimum attempts | 3 | Below this, the pattern shows "not enough data" (R-10) |

### Expected difficulty

| Score | Expected difficulty |
| --- | --- |
| Under 40 | Easy |
| 40 to 69.99 | Medium |
| 70 to 89.99 | Hard |
| 90 or more | Very hard |

### What counts

- An attempt on a problem with several patterns counts in full toward each of them, using each pattern's own tier.
- Attempts on the same date are taken in the order they were logged.
- Sibling attempts count toward their patterns' scores (R-28).
- The stretch applies to any problem above the expected difficulty, because the app cannot tell whether the user chose it or it was recommended.
- Time taken, ratings, and target or mastered settings never change a score (R-26, R-32, R-34).

### Worked example

Today is 2026-11-10, and the pattern is in the normal tier.

| Date | Difficulty | Outcome | Score after fade | Expected | Stretch | Target | Rate | New score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-01 | Easy | Solved alone | 0.00 | Easy | 0 | 100 | 30% | 30.00 |
| 2026-10-11 | Easy | Not solved | 26.73 | Easy | 0 | 0 | 20% | 21.38 |
| 2026-10-21 | Medium | Solved alone | 19.05 | Easy | 1 | 100 | 40% | 51.43 |
| 2026-10-31 | Hard | Solved alone | 45.82 | Medium | 1 | 100 | 40% | 67.49 |

Fading 67.49 over the 10 days to today gives a score of **60.13**. The same attempts give 69.43 in the narrow tier and 54.16 in the broad tier.

## Review intervals (R-12, R-28)

Each attempted problem has a current interval and a due date, except that a sibling attempt starts no schedule of its own. The next due date is the attempt date plus the new interval.

| Attempt | New interval |
| --- | --- |
| First attempt on the problem | The first interval for its outcome |
| Review, solved alone | Double the current interval |
| Review, any other outcome | The first interval for its outcome |
| Early attempt, any outcome | The first interval for its outcome, and no review is completed |

### Values

| Outcome | First interval |
| --- | --- |
| Solved alone | 14 days |
| Solved with hints | 10 days |
| Solved after viewing the solution | 7 days |
| Not solved | 7 days |

### What counts

- A review is an attempt on the due problem or its suggested sibling, on or after the due date. A sibling's outcome sets the original problem's next interval (R-28).
- An early attempt is an attempt on the problem itself before its due date.
- A late review gets no extra credit: doubling uses the current interval, not the days that actually passed, and the next due date counts from the attempt date.
- Intervals have no maximum.
- **Reviews turned off (R-41):** no review is served: none takes a recommendation slot, none counts as due, the calendar file is empty, no sibling is chosen, and the review streak and missed days are not shown. Schedules are still worked out from the attempts as usual, so turning reviews on again shows each problem due on the date it would have been, with the rule below applied.
- **Old problems wait:** a problem is old when the latest attempt in its schedule (its own, or a sibling attempt for one of its reviews) is more than 180 days before today. While any review of a problem that is not old is due, reviews of old problems are not served: they are left out of the review slots, the number due, and the calendar file, and no sibling is chosen for them. When no such review is due, the old ones are served as usual. A review held back keeps its schedule, so an attempt on that problem still completes it, and the streak is unchanged, since a day with any review due always has one served. The calendar file also leaves out reviews that will be old by their due date.
- Dates follow the user's local time zone.

### Why these values

These are provisional and will be checked against tester feedback. The rule follows the growing intervals of SM-2 and Anki, with these differences:

- **Longer first intervals.** SM-2 starts at 1 day and then 6 days, which suits flashcards that take seconds. A coding problem can take 30 minutes or more, and re-solving it the next day mostly tests memory of that problem.
- **Doubling instead of a per-problem ease factor.** SM-2 and Anki start at 2.5 and adjust ease for each item. A fixed multiplier is simpler to explain and test.
- **A first interval of 14 days for solved alone.** Cepeda et al. (2008) found the best gap was about 20% of the time until the test for delays of a few weeks, which suggests up to about 11 days for an interview 8 weeks away. That study covered memorizing facts, so it is only a rough guide. Fourteen days gives 2 reviews in 8 weeks if every review is solved alone (days 14 and 42).

No published schedule designed for coding problems was found.

Sources:

- [Anki deck options](https://docs.ankiweb.net/deck-options.html)
- [Anki's scheduling algorithm FAQ](https://docs.ankiweb.net/faqs/what-spaced-repetition-algorithm)
- [SM-2 original article](https://www-v1.supermemo.com/archives1990-2015/english/ol/sm2)
- [Cepeda et al. (2008)](https://escholarship.org/uc/item/0kp5q19x)

### Worked example

| Date | Outcome | Attempt type | New interval | Next due |
| --- | --- | --- | --- | --- |
| 2026-09-01 | Solved alone | First attempt | 14 days | 2026-09-15 |
| 2026-09-15 | Solved alone | Review | 28 days | 2026-10-13 |
| 2026-10-13 | Solved with hints | Review | 10 days | 2026-10-23 |
| 2026-10-18 | Not solved | Early attempt | 7 days | 2026-10-25 |
| 2026-10-25 | Solved alone | Review | 14 days | 2026-11-08 |
| 2026-11-08 | Not solved | Review | 7 days | 2026-11-15 |
| 2026-11-20 | Solved alone | Review | 14 days | 2026-12-04 |

## Sibling selection (R-28)

A sibling is chosen when a due review is first shown, oldest due date first, and stays the same until the review is completed or the user dismisses it.

A problem can be a sibling only if it meets all of these:

- It is a catalog problem, not a custom problem.
- The user has not attempted it.
- It shares at least one pattern with the due problem.
- Any inactive advanced pattern it has is also on the due problem (R-32).
- It is not reserved by another open review.
- It has not been dismissed for this review, and is not within a 7-day "not now" period (R-29).
- It meets the very hard setting (see Difficulty levels).
- Its site is shown by the site filter (R-36).
- Its difficulty is the same as the due problem's, or one level away.

Rank the problems that qualify by these, in order:

1. **Difficulty:** same difficulty, then one level easier, then one level harder.
2. **Most patterns shared** with the due problem.
3. **Fewest extra patterns** that the due problem does not have.
4. **Catalog order.**

The first-ranked problem is suggested. If no catalog problem qualifies, the same conditions and ranking are applied to the reserve (R-37), with reserve order in place of catalog order. If none qualifies there either, the original problem is suggested.

### Reservation

A problem suggested as a sibling is reserved until the review closes or the user dismisses it. While reserved, it cannot be suggested for another open review or offered as a new problem (R-13). Only reviews already shown reserve a sibling, so a backlog of unseen reviews does not use up the catalog.

### Why these choices

- **Closest match** keeps the review on the skill being checked, because an extra pattern tests something else. It also always gives the same result, so it is easy to test.
- **Easier before harder** keeps the review about recognizing the pattern rather than adding a new challenge. A harder sibling is still covered fairly by the mastery rule's stretch bonus and softer decline.
- **Reservation** stops one attempt from having to count as a review for two problems, or as both a review and a new problem.

### Worked example

The due problem is Medium, with the patterns Tree Traversal and 1-D Dynamic Programming. FFT and NTT is inactive.

| Catalog position | Difficulty | Patterns | Result |
| --- | --- | --- | --- |
| 120 | Medium | 1-D Dynamic Programming, Tree Traversal | Rank 1 |
| 80 | Medium | 1-D Dynamic Programming, Greedy, Tree Traversal | Rank 2 |
| 40 | Medium | Tree Traversal | Rank 3 |
| 15 | Medium | Greedy, Tree Traversal | Rank 4 |
| 5 | Easy | 1-D Dynamic Programming, Tree Traversal | Rank 5 |
| 6 | Hard | 1-D Dynamic Programming, Tree Traversal | Rank 6 |
| 10 | Medium | 1-D Dynamic Programming, Tree Traversal | Already attempted |
| 12 | Medium | 1-D Dynamic Programming, Tree Traversal | Reserved by another open review |
| 20 | Medium | 1-D Dynamic Programming, FFT and NTT | Has an inactive advanced pattern the due problem lacks |
| 25 | Medium | Greedy | Shares no pattern |

Problem 120 is suggested. If the user dismisses it, problem 80 is suggested next.

## Recommendation tie-breaks (R-13, R-15, R-32)

R-13 sets the order of the slots. These rules decide what fills each one.

### Sharing slots across patterns

New-problem slots go to one problem per pattern, in ranked order. A pattern that has already supplied a new problem to the list is skipped until every other ranked pattern has supplied one, then the order starts again. This applies across the target, unscored, and weakest-pattern groups. Due reviews do not count. A group with a single pattern loops back to it, so one target pattern can fill both target slots.

### Ranking patterns

| Group | Order |
| --- | --- |
| Scored patterns | Lowest score first, then longest since the last attempt, then pattern-list order. Mastered patterns come after all others (R-32), including when choosing the 2 weakest patterns near an interview (R-15). |
| Unscored patterns | Most attempts first, then pattern-list order. |
| Target patterns | Unscored targets first, in the unscored order above, then scored targets in the scored order above. |

Pattern-list order is the order of `docs/patterns.md`.

### Current difficulty level

When two levels tie for the most common difficulty in the last 10 attempts (R-13), the harder level is used.

### Choosing a problem within a pattern

A problem can be offered as new only if it meets all of these:

- The user has never attempted it. A problem attempted with help returns through its own review schedule.
- It is not within a 7-day "not now" period (R-29).
- It is not reserved as a sibling (R-28).
- It has no inactive advanced pattern (R-32).
- It is not already on the list.
- It meets the very hard setting (see Difficulty levels).
- Its site is shown by the site filter (R-36). A target slot has no exception to either.
- Its difficulty is the user's current level, or one level away. For a target slot, any difficulty qualifies, because choosing a target is an explicit request.

Rank the problems that qualify by these, in order:

1. **Difficulty:** the current level, then one level easier, then one level harder. For a target slot, this continues to the levels further away, trying the easier one first at each distance.
2. **Fewest extra patterns** besides the pattern it was chosen for.
3. **Catalog order.**

If no catalog problem qualifies for the pattern, the same conditions and ranking are applied to the reserve (R-37), with reserve order in place of catalog order. For a target slot, every catalog level that qualifies is used up first, before the reserve is tried; very hard problems qualify only with the very hard setting on. A pattern with no qualifying problem in either is skipped, and its slot passes to the next pattern.

### Due reviews on the same date

Compare each problem's weakest pattern and take the weaker one first. A pattern showing "not enough data" counts as weaker than any score. Then use catalog order, with reserve problems after catalog problems in reserve order, and custom problems last in the order they were added.

### Worked example

The current level is Medium, with no target patterns and no interviews.

| Pattern | Score | Last attempt | Note |
| --- | --- | --- | --- |
| Intervals | 30.00 | 2026-11-03 | Marked as mastered |
| Greedy | 40.00 | 2026-10-20 | |
| Stack | 40.00 | 2026-11-05 | Has a review due 2026-11-01 |
| Heap | 55.00 | 2026-11-01 | Has a review due 2026-11-01 |
| Sorting | 70.00 | 2026-11-02 | |
| Linked List | Not enough data | | 2 attempts |
| Prefix Sums | Not enough data | | 1 attempt |
| Arrays and Hashing | Not enough data | | 0 attempts |

The list is:

| Slot | Group | Pattern | Why |
| --- | --- | --- | --- |
| 1 | Due review | Stack | Same due date as Heap, and a lower score |
| 2 | Due review | Heap | |
| 3 | Unscored | Linked List | Most attempts among unscored patterns |
| 4 | New | Greedy | Tied with Stack on score, and longest since its last attempt |
| 5 | New | Stack | Next weakest, because Intervals is marked as mastered |

Within Greedy, suppose the qualifying problems are:

| Catalog position | Difficulty | Extra patterns | Rank |
| --- | --- | --- | --- |
| 31 | Medium | 0 | 1 |
| 12 | Medium | 1 | 2 |
| 4 | Easy | 0 | 3 |
| 50 | Hard | 0 | 4 |

Problem 31 fills slot 4.

## Catalog sources (R-01)

The catalog is built once, before release, from these sources. A problem is identified by its link, so a problem on several lists is one entry. Its `source` is the first source in this table that includes it.

| Order | Source | What is taken | Problems on 2026-11-10 |
| --- | --- | --- | --- |
| 1 | Blind 75 | Every problem | 75 |
| 2 | NeetCode 150 | Every problem | 150 |
| 3 | Grind 169 | Every problem | 169 |
| 4 | LeetCode Patterns (Sean Prashad) | Every problem | 179 |
| 5 | NeetCode All | Every problem | 450 |
| 6 | CSES problem set | Every problem | 400 |
| 7 | Codeforces API | Picked per pattern (see below) | 980 after merging duplicates |
| 8 | AtCoder Educational DP Contest | Every problem | 26 |
| 9 | AtCoder Library Practice Contest | Every problem | 12 |
| 10 | AtCoder Typical 90 | Every problem | 90 |
| 11 | AtCoder Beginner Contest | Picked per level (see below) | 171 |

The five LeetCode lists give 515 unique problems. The 20 that any list marks as needing LeetCode Premium are left out, because the user could not open them, leaving 495. The 495 include NeetCode All's 30 JavaScript exercises, which are tagged with the advanced JavaScript pattern, so they appear only for users who turn it on. The lists are read from where they are published (NeetCode's and Sean Prashad's data files on GitHub, the Grind 169 site, and cses.fi), never from LeetCode itself (R-03). LeetCode's own Top Interview 150 and LeetCode 75 are not used for the same reason.

### Picking Codeforces problems

Codeforces problems add a different style from LeetCode and CSES, often relying more on an observation than on a known technique, so each pattern with a matching tag takes a fixed share of them.

1. **Pool.** For each pattern, the pool is the rated Codeforces problems with the pattern's tag from `docs/patterns.md`, leaving out `*special` problems. Tree DP needs both of its tags (`trees` and `dp`). For a core pattern, the pool stops below very hard (see What counts).
2. **Cutoffs.** Leave out problems solved by fewer than 1,000 users (`solvedCount` from `problemset.problems`) and problems from contests that started before 2015 (`startTimeSeconds` from `contest.list`), so obscure and old problems stay out.
3. **Count.** N = the smaller of 50 and 75% of the pool after the cutoffs, rounded down.
4. **Spread.** Take problems in rounds over the levels the pattern allows, easy first: one easy, one medium, one hard, and for an advanced pattern one very hard, then repeat until N are taken. Within a level, the problem solved by the most users comes first. A level that runs out is skipped.
5. **Merge.** Patterns are picked independently. A problem picked for two patterns is one entry and counts toward both.

Some patterns get no automatic picks:

- **No tag or only broad tags:** patterns whose Codeforces tags are all on the "too broad" list in `docs/patterns.md`, or that have none, such as Stack, Heap, Linked List, Tree Traversal, and 1-D Dynamic Programming. The reviewer can still add these patterns to a picked problem.
- **Shared tags:** a tag listed for more than one pattern is picked alone only for the first: `greedy` for Greedy and `sortings` for Sorting. Intervals, whose tags are `greedy` and `sortings`, gets no automatic picks.
- **Unreliable tag pairs:** Minimum Spanning Tree and Bitmask DP have no tags, because the pairs `graphs` with `dsu` and `bitmasks` with `dp` matched the technique in only 21% and 43% of editorials (`docs/patterns.md`). A problem that the old pair would have picked (steps 1 to 4 with the pair as the pattern's tags) is still picked when its editorial confirms the technique.

This gives 30 patterns with picks, 1,213 picks in all and 980 problems after merging, from the API on 2026-11-10. Most patterns take 50. Those with small pools or only confirmed picks take fewer: Minimum Spanning Tree 6, Bitmask DP 9, Expression Parsing 9, Chinese Remainder Theorem 13, 2-SAT 18, Meet in the Middle 20, FFT and NTT 26, Bipartite Matching 37, Suffix Structures 38, Ternary Search 40, Matrices and Matrix Exponentiation 48, and Max Flow and Min Cut 49.

### AtCoder problems

AtCoder has no tags, so every AtCoder entry's patterns come from a source that names the technique. The lists come from AtCoder Problems' `merged-problems.json` and `problem-models.json` on 2026-11-10.

- **Curated sets.** The Educational DP Contest, the AtCoder Library Practice Contest, and Typical 90 are each built around one technique per problem, so their patterns come from the problem itself or, for Typical 90, the set's sample solution. They have no difficulty estimate, so their levels come from elsewhere: Typical 90 by the author's star rating (★2 easy, ★3 to ★4 medium, ★5 to ★6 hard, ★7 very hard), and the other two by the number of AtCoder users who solved the problem (20,000 or more easy, 5,000 to 19,999 medium, 1,500 to 4,999 hard, fewer otherwise very hard). As with CSES, a problem that would be very hard but has only core patterns is labeled hard.
- **Beginner Contest picks.** From contests ABC 212 and later (the current format), take problems with a usable difficulty estimate, sort each level by the number of users who solved them, and take the 50 most solved per level. Patterns are read from each problem's official editorial. A very hard problem is taken only if its patterns include an advanced one, so core-only very hard problems are skipped in favor of the next. On 2026-11-10 this gave 34 easy and 37 medium problems (all of the usable ones, since most A and B problems have no estimate or an experimental one), 50 hard, and 50 very hard.

### Reserve (R-37)

Besides the reviewed catalog, the app keeps an unreviewed reserve of Codeforces and AtCoder problems. The Codeforces part is built automatically from the same `problemset.problems` response with `flask --app codecompass build-reserve`. It lets the user log any of these problems without typing their details, and it supplies new problems and siblings when the catalog runs out for a pattern.

- **What is in it:** every rated programming problem that is not tagged `*special` and has at least one tag that maps to a pattern, including through the broad-tag defaults below. The cutoffs above (1,000 solvers, 2015) do not apply. On 2026-11-10 this was 10,661 problems.
- **Patterns:** from the tags alone, with no review: each tag in the "Codeforces tags" column of `docs/patterns.md` that is not too broad, a shared tag only for the first pattern listed above, and the Tree DP tag pair. Only when none of these apply, each broad tag adds a default pattern: `math` Math, `dp` 1-D Dynamic Programming, `strings` Strings, `graphs` and `dfs and similar` Graph Traversal, `trees` Tree Traversal, `data structures` Data Structure Design, and `two pointers` Two Pointers. These patterns are rougher than the catalog's.
- **Corrections from editorials and code:** `codecompass/data/reserve_corrections.csv` lists, by link, patterns to add or remove, and `build-reserve` applies it. It was derived automatically on 2026-11-10, without review, from the open-r1/codeforces editorials (English only) and, for problems without one, from accepted solutions in open-r1/codeforces-submissions. A pattern is added when its technique is named at least twice in the editorial, or when at least two accepted solutions, and at least half of them, use a specific structure such as a segment tree or Dijkstra. Tree DP and Divide and Conquer are removed when an editorial of 300 or more characters never uses them, and 1-D becomes 2-D Dynamic Programming when the editorial's state has two indices. This corrected 1,254 problems (1,203 by editorial, 51 by code). A hand check of 20 random additions found about 17 clearly right and the rest plausible.
- **AtCoder problems:** every AtCoder Beginner, Regular, and Grand Contest problem with a usable difficulty estimate (2,561 on 2026-11-10), from `codecompass/data/atcoder_reserve_source.csv`, which `build-reserve` merges in. AtCoder has no tags, so patterns come only from editorials, with the same matching as the Codeforces corrections plus Japanese terms: a pattern is added when its technique is named at least twice, or, when nothing is named twice, once. Sources, in order: the official editorial pages; the contest's official PDF (only its English section, since the Japanese text of older PDFs cannot be decoded); user editorials on AtCoder; then external write-ups linked from the editorial page. Submission pages are not used, because AtCoder's `robots.txt` disallows them. The 211 Beginner Contest problems read by hand for the catalog keep those tags. On 2026-11-10, 1,783 problems got patterns (1,612 of them not already in the catalog); 682 editorials named no technique, mostly short easy problems and observation-heavy Regular and Grand Contest problems, and 96 problems had no editorial found. A hand check of 20 random automatic tags found about 16 clearly right, 3 partly right, and 1 wrong.
- **Problems it cannot hold:** a regular Codeforces problem with no rating, or with no tag that maps even by default, is not in the reserve (290 on 2026-11-10), and neither is an AtCoder problem whose editorial gave no pattern (778). Its title, link, and level (blank without a rating) are kept in a separate list, so when the user looks it up by ID, link, or exact title, the custom-problem form (R-02) opens with them filled in and the user chooses the patterns.
- **Difficulty:** from the rating by the Codeforces table below, or for AtCoder from the difficulty estimate by the AtCoder table. Unlike the catalog, a reserve problem with only core patterns can be very hard, as in sync and lookup.
- **Order:** most solved first, by solver count on each problem's own site. This order replaces catalog order in every tie-break that uses it.
- **Overlap:** a problem in both the catalog and the reserve is a catalog problem.

### Drafting entries

Entries are drafted by AI from the source's title, link, difficulty or rating, and tags, then reviewed by the author (R-01). No problem statement is copied. A Codeforces problem's patterns start from its tags as mapped in `docs/patterns.md`, and the reviewer decides any that come from broad tags.

Before the author's review, the drafts were checked against public solutions, and a pattern was added or removed only where a solution showed it: LeetCode against the tags and named solutions in the doocs/leetcode repository, CSES against the write-ups and accepted code in public solution repositories, and Codeforces against the editorials in the open-r1/codeforces dataset. Each changed entry's note in `review/catalog_review.csv` names its source.

The author reviewed the checked drafts on 2026-11-10 with a quick pass over the catalog, relying on the check against editorials and code for the individual tags. The `reviewed` column of `review/catalog_review.csv` records the date for each entry; flags such as "tags unverified" stay in place so those entries can be revisited.

When there is reasonable doubt that a Codeforces tag fits the problem, such as a pattern that comes from a tag pair or from a tag Codeforces applies loosely (`divide and conquer` matched its editorial in about half of the problems checked), the tag is checked against the problem's editorial if one is available, and otherwise against readily available accepted solutions (for example, the open-r1/codeforces-submissions dataset). The pattern is kept, changed, or removed to match. If neither is available, the tags stay and the entry is marked as unverified in the review file.

## Difficulty levels (R-01)

Every problem has one of four levels: easy, medium, hard, or very hard.

### Codeforces ratings

| Rating | Level | Share of rated Codeforces problems |
| --- | --- | --- |
| Under 1200 | Easy | 21% |
| 1200 to 1599 | Medium | 17% |
| 1600 to 2099 | Hard | 23% |
| 2100 or more | Very hard | 39% |

The shares come from the Codeforces API on 2026-11-07 (11,194 rated problems out of 11,503).

### AtCoder difficulty estimates

AtCoder has no official problem rating, so these use the `difficulty` value from AtCoder Problems' `problem-models.json`, an unofficial estimate. The value is stored as given, and it can be negative.

| Difficulty value | Level | Share of usable AtCoder problems | Typical AtCoder Beginner Contest position |
| --- | --- | --- | --- |
| Under 400 | Easy | 28% | A to C |
| 400 to 1199 | Medium | 19% | D |
| 1200 to 1999 | Hard | 20% | E and F |
| 2000 or more | Very hard | 33% | G and H |

The shares come from the file on 2026-11-07 (4,401 usable problems out of 5,201). The positions are from the median difficulty at each position in contests numbered 212 and above.

### CSES solver counts

CSES has no problem rating, so these use the number of users who solved the problem, shown on the CSES problem set page. More solvers means an easier level.

| Users who solved it | Level | Share of CSES problems |
| --- | --- | --- |
| 20,000 or more | Easy | 24% |
| 3,000 to 19,999 | Medium | 28% |
| 700 to 2,999 | Hard | 27% |
| Under 700 | Very hard | 21% |

The shares come from the page on 2026-11-10 (400 problems). A solver count is not a rating, so `rating` is left blank for CSES problems. The level is set once, when the catalog is built, and is not updated as counts grow.

### What counts

- **Core patterns:** catalog problems in core patterns stop below the very hard level (2099 on Codeforces, 1999 on AtCoder), so very hard problems enter the catalog only through advanced patterns. A CSES problem with only core patterns and under 700 solvers is kept and labeled hard. A catalog problem with both core and advanced patterns follows the advanced limit.
- **Other sites:** problems from LeetCode and other sites keep their own labels, so a LeetCode Hard stays hard by default. The catalog reviewer can mark an individual problem as very hard during review, and a user can choose very hard when adding a custom problem.
- **Sync and lookup:** a Codeforces or AtCoder problem of any rating is mapped by the tables above (R-33, R-35). The user supplies the level when a problem has no rating.
- **Unrated problems:** Codeforces problems with no rating, and AtCoder problems with no difficulty value or flagged `is_experimental`, are left out of the catalog, except the curated AtCoder sets, whose levels come from star ratings or solver counts (see AtCoder problems). In sync and lookup, the user supplies their level.
- **Stored ratings:** a problem's rating from its source site is stored (`docs/data_model.md`), but no rule other than these tables reads it.

### Very hard setting (R-32)

Very hard problems are not recommended unless the user turns on the very hard setting, which is off by default. While it is off:

- New problems exclude very hard problems, including in target slots.
- A sibling can be very hard only if the due problem is very hard.
- The current difficulty level stops at hard.

The setting never affects logging, sync, due dates, or scores. Turning on advanced patterns does not turn it on.

### Why these values

No official conversion between Codeforces ratings and LeetCode levels was found. The lower cutoffs follow Codeforces rank boundaries: below Pupil is easy, Pupil and Specialist are medium, and Expert and Candidate Master are hard. Informal forum estimates place LeetCode's hardest problems at about 2000 or below, so the very hard level starts just above that. No reliable conversion between Codeforces and AtCoder was found, so the AtCoder cutoffs are set so that each contest position falls clearly in one level. The CSES cutoffs split the problem set into roughly equal quarters. Solver counts measure difficulty only roughly: users probably work through CSES in page order, so early sections have more solvers, and the sections added in 2025 (such as Counting, Construction, and Additional Problems) have had less time to collect solvers. These values are provisional.

Sources:

- [Codeforces ranks on Wikipedia](https://en.wikipedia.org/wiki/Codeforces)
- [Forum estimate of LeetCode levels in Codeforces ratings](https://mirror.codeforces.com/blog/entry/87135)
- [Forum thread on LeetCode hards](https://mirror.codeforces.com/topic/87680/en2)
- [AtCoder Problems difficulty estimates](https://kenkoooo.com/atcoder/resources/problem-models.json)
- [Forum post comparing Codeforces and AtCoder ratings](https://codeforces.com/blog/entry/93069)
- [CSES problem set](https://cses.fi/problemset/)

## Site filter (R-36)

In settings, each site with catalog problems (LeetCode, Codeforces, CSES, and AtCoder) has two switches: one for core problems and one for advanced problems. The Codeforces and AtCoder switches also cover their reserve problems (R-37). All are on by default. A problem's site comes from its link. A problem with at least one advanced pattern is an advanced problem, and any other problem is a core problem.

While a switch is off, that site's problems of that kind:

- are not offered as new problems, including in target slots and while an interview is in focus. A pattern with no other qualifying problem is skipped, and its slot passes to the next pattern.
- are not suggested as siblings. If no other sibling qualifies, the original problem is suggested, as in R-28.
- are replaced if already suggested as a sibling, the next time the review is shown. The replacement does not count as a dismissal.

The filter never affects due reviews, scores, due dates, logging, sync, lookup, or custom problems. A due review of a problem from a hidden site still appears.

## Interview focus (R-15)

### Which interview

The interview in focus is the nearest one dated from today to 14 days ahead. Interviews on that same date are combined: their patterns are joined, and the hardest target difficulty given is used. Past interviews and interviews further away are kept but ignored, and the app does not prompt about them.

### While an interview is in focus

- **Due reviews:** weakest pattern first, then due date, then catalog order.
- **Target slots:** unchanged (R-32).
- **Unscored slot:** dropped.
- **New problems with interview patterns:** they come only from the 2 weakest of the interview's patterns. Unscored patterns rank first, in the unscored order, then scored patterns, weakest first, with mastered patterns last. This applies even when no pattern has a score yet.
- **New problems without interview patterns:** they come only from the 2 weakest scored active patterns. If no active pattern has a score, the interview has no effect.
- **Advanced patterns:** an interview's patterns are active while it is in focus, even if advanced patterns are off.
- **Target difficulty:** it replaces the current difficulty level for new problems, still allowing one level either way. If it is very hard, very hard problems are allowed while that interview is in focus.

Interviews never change a score. Because only 2 patterns supply new problems, the list can have fewer than 5 problems when those patterns run out.

## Sync and lookup sources (R-03, R-33, R-34, R-35)

CodeCompass contacts only these sources, and only when the user starts a sync or a lookup. All requests are in `codecompass/remote.py`. They are plain requests with an honest User-Agent, with no logins, passwords, or cookies, and a username is the public one shown on the site.

| Site | Source | What is read | Used by |
| --- | --- | --- | --- |
| Codeforces | `https://codeforces.com/api/user.status` (official API) | The user's submissions, newest first, 200 per request until the sync's start time is reached | Sync |
| Codeforces | `https://codeforces.com/api/user.rating` (official API) | Rating after each rated contest | Sync |
| Codeforces | `https://codeforces.com/api/problemset.problems` (official API) | Problem title, rating, and tags | Lookup |
| AtCoder | `https://kenkoooo.com/atcoder/atcoder-api/v3/user/submissions` (AtCoder Problems, unofficial) | The user's submissions from the sync's start time, 500 per request | Sync |
| AtCoder | `https://kenkoooo.com/atcoder/resources/problems.json` (AtCoder Problems) | Problem titles, only when a synced problem is not in CodeCompass | Sync |
| AtCoder | `https://kenkoooo.com/atcoder/resources/problem-models.json` (AtCoder Problems) | Difficulty estimates, only for a problem not in CodeCompass | Sync, lookup |
| AtCoder | `https://atcoder.jp/users/{username}/history/json` | Rating after each contest; unrated contests are skipped | Sync |
| AtCoder | `https://atcoder.jp/contests/{contest}/tasks/{task}` | The task page's title | Lookup |
| LeetCode | `https://leetcode.com/graphql` (undocumented), one request per sync | `recentAcSubmissionList` (the last 20 accepted submissions) and `userContestRankingHistory` (attended contests) | Sync |

**Limits.** Requests to one host are spaced by its published limit: 2 seconds for the Codeforces API (one call per 2 seconds) and 1.1 seconds for AtCoder Problems (which asks for more than 1 second). AtCoder and LeetCode publish no limit, so requests to them are spaced by 1 and 2 seconds. A refused request (HTTP 401, 403, or 429, or Codeforces' "call limit exceeded") is never retried: that site's sync or the lookup stops and says so, and nothing from it is saved.

**Unknown usernames.** Codeforces reports a username that does not exist. AtCoder and LeetCode return empty results for one, the same as a user with no activity, so a mistyped username there shows no new submissions and no rated contests.

### Sync items (R-33)

- **First sync:** the whole submission history, read a page at a time until the source has no more. For LeetCode this is the roughly 20 recent submissions it shows. A changed username starts with a first sync again.
- **Later syncs:** submissions since the previous sync, less 24 hours, so submissions a source records late are still found. An item already listed, confirmed, or dismissed is never listed again.
- **One item per problem per day,** by the user's local date. It counts as accepted if any submission that day was accepted.
- **Failed tries before a solve:** a day with no accepted submission is dropped when the problem was accepted on a later day, so the failed tries and the solve are one item, dated the day of the solve. This also removes such an item still waiting for an outcome when a later sync finds the solve; one already confirmed or dismissed stays as it is.
- **Separate solves:** accepted submissions on different days are separate items. A day with no accepted submission after the last solve is still listed, and offers "not solved."
- **Several at once:** items selected together are saved oldest first, as if confirmed one by one. An item the chosen outcome does not fit stays listed, and the message gives the reason: a problem new to CodeCompass that still needs its level or patterns, a revealed hint (it cannot be "solved alone"), or an accepted submission (it cannot be "not solved"). **Auto-classify**, chosen by the user for selected items, saves each accepted item as "solved alone" and each other item as "not solved", with the same reasons for leaving an item listed. Undo, offered for up to one day, removes the attempts the batch saved and the custom problems it added that nothing else uses, marks any hint those attempts used as unused again, and lists the items again.
- **Progress:** while a sync runs, each site shows the submissions read so far and how far back they reach. The bar fills by the share of the time to cover that has been read: for Codeforces, from now back to the previous sync, and for AtCoder, from the previous sync (or the first submission, on a first sync) up to now. A first Codeforces sync has no known end, and LeetCode is one request, so their bars show activity instead of a share.
- **Skipped:** Codeforces gym contests, which are not in the problem set.
