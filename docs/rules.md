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
| 70 or more | Hard |

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
