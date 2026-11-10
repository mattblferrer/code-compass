# R-01 spot check

R-01's verification compares 20 randomly chosen catalog entries with the public lists they came from, after running a validation script over the catalog file. This page records that comparison.

- **Date:** 2026-11-10
- **Catalog:** `codecompass/data/catalog.csv`, 2174 entries
- **Sample:** 20 entries drawn with Python's `random.Random(20261110).sample` over the row numbers, so the sample can be redrawn.
- **Validation script:** `tests/test_catalog.py::test_shipped_catalog_is_valid` runs the catalog validator over the real file (all five fields, every pattern on the documented list, at least 500 entries).
- **Sources compared:** the copies saved on 2026-11-10 while the catalog was built: the NeetCode, LeetCode Patterns, and Grind 169 list data, the CSES problem set page, the Codeforces API problem set, and AtCoder Problems' problem lists and difficulty estimates.

For each entry, the check confirms that the problem is on the source it names, that its title and link match that problem (the link in its canonical form), that its difficulty follows the rule in `docs/rules.md` for that source, and that the stored rating matches the source (blank where the source has none). Patterns are not part of this check; the public lists do not use the catalog's pattern names.

| # | Row | Title | Source | On source | Title | Link | Difficulty | Rating | Compared with |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 576 | Counting Numbers | CSES problem set | yes | yes | yes | medium (yes, expected medium) | yes | CSES page, 14304 solvers |
| 2 | 630 | Distinct Values Queries | CSES problem set | yes | yes | yes | medium (yes, expected medium) | yes | CSES page, 8607 solvers |
| 3 | 665 | Binomial Coefficients | CSES problem set | yes | yes | yes | medium (yes, expected medium) | yes | CSES page, 12873 solvers |
| 4 | 714 | Line Segment Intersection | CSES problem set | yes | yes | yes | medium (yes, expected medium) | yes | CSES page, 5350 solvers |
| 5 | 716 | Point in Polygon | CSES problem set | yes | yes | yes | medium (yes, expected medium) | yes | CSES page, 3451 solvers |
| 6 | 738 | Necessary Roads | CSES problem set | yes | yes | yes | hard (yes, expected hard) | yes | CSES page, 2510 solvers |
| 7 | 843 | Bubble Sort Rounds II | CSES problem set | yes | yes | yes | hard (yes, expected hard) | yes | CSES page, 432 solvers |
| 8 | 913 | Again Twenty Five! | Codeforces API | yes | yes | yes | easy (yes, expected easy) | yes | Codeforces API, rating 800 |
| 9 | 937 | Move Brackets | Codeforces API | yes | yes | yes | easy (yes, expected easy) | yes | Codeforces API, rating 1000 |
| 10 | 1226 | Decreasing String | Codeforces API | yes | yes | yes | hard (yes, expected hard) | yes | Codeforces API, rating 1600 |
| 11 | 1308 | Cover it! | Codeforces API | yes | yes | yes | hard (yes, expected hard) | yes | Codeforces API, rating 1700 |
| 12 | 1341 | Quiz Master | Codeforces API | yes | yes | yes | hard (yes, expected hard) | yes | Codeforces API, rating 1700 |
| 13 | 1344 | Torn Lucky Ticket | Codeforces API | yes | yes | yes | medium (yes, expected medium) | yes | Codeforces API, rating 1400 |
| 14 | 1442 | Character Blocking | Codeforces API | yes | yes | yes | hard (yes, expected hard) | yes | Codeforces API, rating 1600 |
| 15 | 1529 | Maximum Distance To Port | Codeforces API | yes | yes | yes | medium (yes, expected medium) | yes | Codeforces API, rating 1400 |
| 16 | 1642 | ''a'' String Problem | Codeforces API | yes | yes | yes | hard (yes, expected hard) | yes | Codeforces API, rating 2000 |
| 17 | 1649 | More Wrong | Codeforces API | yes | yes | yes | very hard (yes, expected very hard) | yes | Codeforces API, rating 2100 |
| 18 | 1835 | Darth Vader and Tree | Codeforces API | yes | yes | yes | very hard (yes, expected very hard) | yes | Codeforces API, rating 2200 |
| 19 | 1931 | Statue of Chokudai | AtCoder Typical 90 | yes | yes | yes | medium (yes, expected medium) | yes | Typical 90 stars |
| 20 | 2036 | Bento Packing | AtCoder Beginner Contest | yes | yes | yes | easy (yes, expected easy) | yes | AtCoder Problems estimate 251 |

**Result:** 20 of 20 entries match their source on every check.

## Beyond the sample

The same checks were also run over all 2,174 entries. The first run found one entry whose title did not match its source: "Fruits into Basket" (NeetCode's spelling) is listed by its source, LeetCode Patterns, as "Fruit Into Baskets". Titles are now taken from the list named as the source, which corrected that entry and six other LeetCode titles that differed only in capitalization or a trailing space. After the fix, all 2,174 entries pass.

## Reserve

R-01 covers the catalog only, but the same checks were run on the unreviewed reserve (R-37), `codecompass/data/reserve.csv`, on 2026-11-10.

- **Validation:** `tests/test_catalog.py::test_shipped_reserve_is_valid` runs the validator in reserve mode over the real file. All 12,444 entries pass (10,661 from the Codeforces API, 1,783 from AtCoder). Reserve mode differs from the catalog in one way set by `docs/rules.md`: a very hard reserve problem may have only core patterns.
- **Source comparison:** every reserve entry, not just a sample, was compared with the saved Codeforces API problem set or AtCoder Problems data: the problem exists, its title and link match, its stored rating equals the source's rating or difficulty estimate, and its difficulty follows the Codeforces or AtCoder table. No entry failed. A 20-entry sample drawn with the same seed passed 20 of 20 (by chance all from Codeforces).

These checks confirm that reserve entries match their sources. They do not review the reserve's patterns, which are unreviewed by design.
