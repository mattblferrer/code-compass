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
- Its difficulty is the same as the due problem's, or one level away.

Rank the problems that qualify by these, in order:

1. **Difficulty:** same difficulty, then one level easier, then one level harder.
2. **Most patterns shared** with the due problem.
3. **Fewest extra patterns** that the due problem does not have.
4. **Catalog order.**

The first-ranked problem is suggested. If none qualifies, the original problem is suggested.

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
- Its difficulty is the user's current level, or one level away. For a target slot, any difficulty qualifies, because choosing a target is an explicit request.

Rank the problems that qualify by these, in order:

1. **Difficulty:** the current level, then one level easier, then one level harder. For a target slot, this continues to the levels further away, trying the easier one first at each distance.
2. **Fewest extra patterns** besides the pattern it was chosen for.
3. **Catalog order.**

A pattern with no qualifying problem is skipped, and its slot passes to the next pattern.

### Due reviews on the same date

Compare each problem's weakest pattern and take the weaker one first. A pattern showing "not enough data" counts as weaker than any score. Then use catalog order, with custom problems after catalog problems in the order they were added.

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

### What counts

- **Core patterns:** catalog problems in core patterns stop below the very hard level (2099 on Codeforces, 1999 on AtCoder), so very hard problems enter the catalog only through advanced patterns. A catalog problem with both core and advanced patterns follows the advanced limit.
- **Other sites:** problems from LeetCode and other sites keep their own labels, so a LeetCode Hard stays hard by default. The catalog reviewer can mark an individual problem as very hard during review, and a user can choose very hard when adding a custom problem.
- **Sync and lookup:** a Codeforces or AtCoder problem of any rating is mapped by the tables above (R-33, R-35). The user supplies the level when a problem has no rating.
- **Unrated problems:** Codeforces problems with no rating, and AtCoder problems with no difficulty value or flagged `is_experimental`, are left out of the catalog. In sync and lookup, the user supplies their level.
- **Stored ratings:** a problem's rating from its source site is stored (`docs/data_model.md`), but no rule other than these tables reads it.

### Very hard setting (R-32)

Very hard problems are not recommended unless the user turns on the very hard setting, which is off by default. While it is off:

- New problems exclude very hard problems, except that a target slot can use one when no easier problem qualifies.
- A sibling can be very hard only if the due problem is very hard.
- The current difficulty level stops at hard.

The setting never affects logging, sync, due dates, or scores. Turning on advanced patterns does not turn it on.

### Why these values

No official conversion between Codeforces ratings and LeetCode levels was found. The lower cutoffs follow Codeforces rank boundaries: below Pupil is easy, Pupil and Specialist are medium, and Expert and Candidate Master are hard. Informal forum estimates place LeetCode's hardest problems at about 2000 or below, so the very hard level starts just above that. No reliable conversion between Codeforces and AtCoder was found, so the AtCoder cutoffs are set so that each contest position falls clearly in one level. These values are provisional.

Sources:

- [Codeforces ranks on Wikipedia](https://en.wikipedia.org/wiki/Codeforces)
- [Forum estimate of LeetCode levels in Codeforces ratings](https://mirror.codeforces.com/blog/entry/87135)
- [Forum thread on LeetCode hards](https://mirror.codeforces.com/topic/87680/en2)
- [AtCoder Problems difficulty estimates](https://kenkoooo.com/atcoder/resources/problem-models.json)
- [Forum post comparing Codeforces and AtCoder ratings](https://codeforces.com/blog/entry/93069)

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
