"""Tunable values for the rules in docs/rules.md.

Change a value here, rerun tests/data/generate_reference.py with the same
change, and update the affected tests.
"""

# Outcomes and difficulty levels, as stored in the database.
SOLVED_ALONE = "solved_alone"
SOLVED_WITH_HINTS = "solved_with_hints"
SOLVED_AFTER_SOLUTION = "solved_after_solution"
NOT_SOLVED = "not_solved"
OUTCOMES = (SOLVED_ALONE, SOLVED_WITH_HINTS, SOLVED_AFTER_SOLUTION, NOT_SOLVED)

LEVELS = ("easy", "medium", "hard", "very hard")
VERY_HARD = "very hard"

# Mastery score (R-09, R-10)
OUTCOME_VALUE = {
    SOLVED_ALONE: 1.0,
    SOLVED_WITH_HINTS: 0.5,
    SOLVED_AFTER_SOLUTION: 0.2,
    NOT_SOLVED: 0.0,
}
RATE_UP = {"narrow": 0.4, "normal": 0.3, "broad": 0.2}
STRETCH_BONUS = 0.1
MAX_RATE_UP = 0.5
RATE_DOWN = 0.2
RATE_DOWN_STRETCH = 0.1
FADE_HALF_LIFE_DAYS = 60
MIN_ATTEMPTS = 3
# Expected difficulty by score: (lowest score, level index), highest first.
EXPECTED_LEVEL_FLOORS = ((90, 3), (70, 2), (40, 1), (0, 0))

# Review intervals (R-12)
FIRST_INTERVAL_DAYS = {
    SOLVED_ALONE: 14,
    SOLVED_WITH_HINTS: 10,
    SOLVED_AFTER_SOLUTION: 7,
    NOT_SOLVED: 7,
}

# Recommendations (R-13, R-15, R-29, R-32)
LIST_SIZE = 5
MAX_REVIEW_SLOTS = 3
MAX_TARGET_SLOTS = 2
MAX_UNSCORED_SLOTS = 1
FOCUS_WINDOW_DAYS = 14
FOCUS_WEAKEST_PATTERNS = 2
NOT_NOW_DAYS = 7
LEVEL_WINDOW = 10
LEVEL_STEP_WINDOW = 5
LEVEL_STEP_COUNT = 3

# Difficulty levels from site ratings (R-01): (lowest rating, level), highest first.
CODEFORCES_LEVEL_FLOORS = ((2100, "very hard"), (1600, "hard"), (1200, "medium"))
ATCODER_LEVEL_FLOORS = ((2000, "very hard"), (1200, "hard"), (400, "medium"))

# How long a deleted attempt or interview can be restored with Undo, in days.
UNDO_DAYS = 1

# Sync (R-33). The first sync for a username reaches back FIRST_SYNC_DAYS (provisional).
# Later syncs reach back to the previous sync less SYNC_OVERLAP_HOURS, so submissions a
# source recorded late are still found; items already listed are never listed twice.
FIRST_SYNC_DAYS = 30
SYNC_OVERLAP_HOURS = 24
